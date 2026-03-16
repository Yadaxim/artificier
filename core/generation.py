"""Interpret and generate flows; all Claude calls and WorldStateManager usage."""

import json
import os
import re
from pathlib import Path
from uuid import UUID

# Last raw API response text (for debugging when interpret shows wrong name)
_last_interpret_raw: str = ""


def get_last_interpret_raw() -> str:
    return _last_interpret_raw

from anthropic import Anthropic
from models.models import (
    Dungeon,
    Edge,
    EdgeType,
    Item,
    ItemRarity,
    ItemType,
    Location,
    Monster,
    NPC,
    Room,
    Town,
)

from core.context_assembler import (
    get_floor_context,
    get_location_context_for_generation,
    get_room_context_for_generation,
)
from core.state_manager import WorldStateManager
from core.topology import create_edges_from_topology


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_prompt(relative_path: str) -> str:
    path = _project_root() / "prompts" / relative_path
    return path.read_text(encoding="utf-8")


def _clean_json(text: str, *, extract_bounds: bool = True, remove_trailing_commas: bool = True) -> str:
    """
    Clean LLM response before JSON parsing. Matches CodeLife behavior:
    - Strip whitespace and markdown code fences (```json, ```).
    - If extract_bounds: keep only the outermost {...} or [...].
    - If remove_trailing_commas: strip trailing commas before } or ].
    """
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()
    if extract_bounds:
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace >= first_brace:
            text = text[first_brace : last_brace + 1]
        else:
            first_bracket = text.find("[")
            last_bracket = text.rfind("]")
            if first_bracket != -1 and last_bracket != -1 and last_bracket >= first_bracket:
                text = text[first_bracket : last_bracket + 1]
    if remove_trailing_commas:
        text = re.sub(r",\s*}", "}", text)
        text = re.sub(r",\s*]", "]", text)
    return text


def _looks_like_placeholder_name(val: str) -> bool:
    """True if value looks like a placeholder (e.g. '\\n \"name\"', '"name"', 'name')."""
    if not val or not isinstance(val, str):
        return True
    # Normalize: strip, lower, collapse whitespace and escape sequences to space
    normalized = re.sub(r"[\s\\]+", " ", val.strip().lower())
    normalized = normalized.strip('"').strip()
    if not normalized or len(normalized) <= 2:
        return True
    if normalized == "name":
        return True
    if re.match(r'^["\']?name["\']?$', normalized):
        return True
    return False


def _fix_placeholder_name(data: dict, raw_json: str, name_key: str = "name") -> None:
    """If data[name_key] looks like a placeholder (e.g. '\\n \"name\"'), try to fix it."""
    val = data.get(name_key)
    if not isinstance(val, str):
        return
    if not _looks_like_placeholder_name(val):
        return
    # Try to find "name": "ActualValue" in raw JSON (value must not be another placeholder)
    match = re.search(r'"name"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_json)
    if match:
        candidate = match.group(1).replace("\\n", " ").replace("\\\"", '"').strip()
        if not _looks_like_placeholder_name(candidate) and len(candidate) > 2:
            data[name_key] = candidate
            return
    # Fallback: use first few words of concept as a default name
    concept = data.get("concept") or data.get("concept_summary") or ""
    if isinstance(concept, str) and len(concept) > 5:
        first_words = concept.strip().split()[:4]
        data[name_key] = " ".join(first_words) if first_words else "Unnamed"
    else:
        data[name_key] = ""


def _get_client() -> Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return Anthropic(api_key=api_key)


def _get_response_text(response) -> tuple[str, list[dict]]:
    """Extract full text from API response. Returns (full_text, block_info_for_debug)."""
    block_info = []
    for i, block in enumerate(response.content):
        btype = getattr(block, "type", None)
        has_text = hasattr(block, "text")
        text = getattr(block, "text", None) if has_text else None
        block_info.append({
            "index": i,
            "type": str(btype) if btype is not None else "?",
            "has_text": has_text,
            "text_len": len(text) if text else 0,
            "text_preview": (text or "")[:100] if text else "",
        })
    result = "".join(
        block.text for block in response.content if hasattr(block, "text") and block.text
    )
    return result, block_info


def interpret_dungeon(text: str, party_level: int) -> tuple[dict, str, dict]:
    """
    Interpret free-text dungeon description into structured seed.
    Returns (data, raw_response, debug_info).
    """
    prompt_tpl = _load_prompt("dungeon/interpret.txt")
    prompt = prompt_tpl.format(party_level=party_level, description=text or "(no description)")
    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw, block_info = _get_response_text(response)
    raw = raw or "{}"
    global _last_interpret_raw
    _last_interpret_raw = raw
    cleaned = _clean_json(raw)
    data = json.loads(cleaned)
    name_before = repr(data.get("name")) if isinstance(data, dict) else "N/A"
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, dict):
        raise ValueError("Interpret response was not a JSON object")
    _fix_placeholder_name(data, cleaned)
    name_after = repr(data.get("name"))
    debug = {
        "content_block_count": len(response.content),
        "block_info": block_info,
        "raw_len": len(raw),
        "raw_first_400": raw[:400],
        "cleaned_len": len(cleaned),
        "cleaned_first_400": cleaned[:400],
        "parsed_keys": list(data.keys()) if isinstance(data, dict) else [],
        "name_before_fix": name_before,
        "name_after_fix": name_after,
    }
    return data, raw, debug


def seed_dungeon_rooms(
    manager: WorldStateManager,
    campaign_id: UUID,
    dungeon_id: UUID,
) -> list[Room]:
    """
    Generate room seeds for the entire dungeon (all floors) and create Room nodes
    plus CONTAINS/PART_OF, CONNECTS_TO, and RELATED_TO edges.
    """
    dungeon = manager.get_dungeon(dungeon_id)
    if not dungeon:
        return []
    floors = dungeon.metadata.get("floors") or []
    floors_json = json.dumps(floors, indent=2)
    ctx = get_floor_context(manager, dungeon_id, 0)
    prompt_tpl = _load_prompt("dungeon/rooms_seed.txt")
    prompt = prompt_tpl.format(
        dungeon_name=ctx.get("dungeon_name", dungeon.name),
        dungeon_concept=ctx.get("dungeon_concept", dungeon.concept),
        level_range=ctx.get("level_range", dungeon.level_range),
        floors_json=floors_json,
    )
    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = (_get_response_text(response)[0] or "{}")
    data = json.loads(_clean_json(raw))
    rooms_data = data.get("rooms") or []
    connections_data = data.get("connections") or []
    relationships_data = data.get("relationships") or []
    created: list[Room] = []
    by_name: dict[str, Room] = {}
    # Create rooms first
    for r in rooms_data:
        room = Room(
            name=r.get("name", "Unnamed"),
            purpose=r.get("purpose", ""),
            atmosphere=r.get("atmosphere", ""),
            construction_era=r.get("construction_era", ""),
            floor_level=r.get("floor_level", 0),
            is_entrance=r.get("is_entrance", False),
            is_boss_room=r.get("is_boss_room", False),
        )
        room.metadata["vertical_connection"] = r.get("vertical_connection")
        manager.create_room(room)
        manager.add_edge(
            Edge(source_id=dungeon_id, target_id=room.id, edge_type=EdgeType.CONTAINS)
        )
        manager.add_edge(
            Edge(source_id=room.id, target_id=dungeon_id, edge_type=EdgeType.PART_OF)
        )
        created.append(room)
        if room.name:
            by_name[room.name] = room

    # Then create topology edges using room names from the seed response
    for c in connections_data:
        from_name = c.get("from_room_name")
        to_name = c.get("to_room_name")
        if not from_name or not to_name:
            continue
        from_room = by_name.get(from_name)
        to_room = by_name.get(to_name)
        if not from_room or not to_room:
            continue
        passage_type = c.get("passage_type", "DOOR")
        length = c.get("length", "medium")
        edge = Edge(
            source_id=from_room.id,
            target_id=to_room.id,
            edge_type=EdgeType.CONNECTS_TO,
            properties={"passage_type": passage_type, "length": length},
        )
        manager.add_edge(edge)

    # And create inter-room relationship edges
    for rel in relationships_data:
        from_name = rel.get("from_room_name")
        to_name = rel.get("to_room_name")
        if not from_name or not to_name:
            continue
        from_room = by_name.get(from_name)
        to_room = by_name.get(to_name)
        if not from_room or not to_room:
            continue
        rel_type = rel.get("type", "related")
        desc = rel.get("description", "")
        edge = Edge(
            source_id=from_room.id,
            target_id=to_room.id,
            edge_type=EdgeType.RELATED_TO,
            properties={"type": rel_type, "description": desc},
        )
        manager.add_edge(edge)
        # Add reverse edge so the relationship is naturally visible from both rooms
        reverse_edge = Edge(
            source_id=to_room.id,
            target_id=from_room.id,
            edge_type=EdgeType.RELATED_TO,
            properties={"type": rel_type, "description": desc},
        )
        manager.add_edge(reverse_edge)

    return created


def generate_topology(manager: WorldStateManager, dungeon_id: UUID) -> list:
    """Call Claude for connection graph; create CONNECTS_TO edges. Returns list of created edges."""
    rooms = manager.get_rooms_in_dungeon(dungeon_id)
    if not rooms:
        return []
    rooms_json = json.dumps(
        [
            {
                "id": str(r.id),
                "name": r.name,
                "floor_level": r.floor_level,
                "vertical_connection": r.metadata.get("vertical_connection"),
            }
            for r in rooms
        ],
        indent=2,
    )
    prompt_tpl = _load_prompt("dungeon/topology.txt")
    prompt = prompt_tpl.format(rooms_json=rooms_json)
    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = (_get_response_text(response)[0] or "{}")
    data = json.loads(_clean_json(raw))
    connections = data.get("connections") or []
    return create_edges_from_topology(manager, connections)


def generate_room(
    manager: WorldStateManager,
    dungeon_id: UUID,
    room_id: UUID,
    already_generated_room_ids: list[UUID],
) -> Room | None:
    """Generate full room description; update Room node."""
    room = manager.get_room(room_id)
    if not room:
        return None
    ctx = get_room_context_for_generation(manager, dungeon_id, room_id, already_generated_room_ids)
    prompt_tpl = _load_prompt("dungeon/room.txt")
    prompt = prompt_tpl.format(
        dungeon_name=ctx.get("dungeon_name", ""),
        dungeon_concept=ctx.get("dungeon_concept", ""),
        dungeon_tone=ctx.get("dungeon_tone", ""),
        level_range=ctx.get("level_range", ""),
        floor_name=ctx.get("floor_name", ""),
        floor_theme=ctx.get("floor_theme", ""),
        room_name=ctx.get("room_name", ""),
        room_purpose=ctx.get("room_purpose", ""),
        room_atmosphere=ctx.get("room_atmosphere", ""),
        room_construction_era=ctx.get("room_construction_era", ""),
        adjacent_rooms=ctx.get("adjacent_rooms", ""),
        already_generated_summaries=ctx.get("already_generated_summaries", ""),
    )
    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = (_get_response_text(response)[0] or "{}")
    data = json.loads(_clean_json(raw))
    room.description = data.get("description", "")
    room.read_aloud = data.get("read_aloud", "")
    room.dm_notes = data.get("dm_notes", "")
    room.features = data.get("features") or []
    room.encounter_seeds = data.get("encounter_seeds") or []
    room.references_rooms = data.get("references_rooms") or []
    manager.update_room(room)
    return room


# --- Town generation ---


def interpret_town(text: str, party_level: int) -> tuple[dict, str, dict]:
    """Interpret free-text town description. Returns (data, raw, debug)."""
    prompt_tpl = _load_prompt("town/interpret.txt")
    prompt = prompt_tpl.format(party_level=party_level, description=text or "(no description)")
    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw, block_info = _get_response_text(response)
    raw = raw or "{}"
    global _last_interpret_raw
    _last_interpret_raw = raw
    cleaned = _clean_json(raw)
    data = json.loads(cleaned)
    name_before = repr(data.get("name")) if isinstance(data, dict) else "N/A"
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, dict):
        raise ValueError("Interpret response was not a JSON object")
    _fix_placeholder_name(data, cleaned)
    name_after = repr(data.get("name"))
    debug = {
        "content_block_count": len(response.content),
        "block_info": block_info,
        "raw_len": len(raw),
        "raw_first_400": raw[:400],
        "cleaned_len": len(cleaned),
        "cleaned_first_400": cleaned[:400],
        "parsed_keys": list(data.keys()),
        "name_before_fix": name_before,
        "name_after_fix": name_after,
    }
    return data, raw, debug


def seed_locations(
    manager: WorldStateManager,
    campaign_id: UUID,
    town_id: UUID,
    suggested_locations: list[dict] | None = None,
) -> list[Location]:
    """Generate location seeds and create Location nodes + CONTAINS/PART_OF edges."""
    town = manager.get_town(town_id)
    if not town:
        return []
    suggested = suggested_locations or (town.metadata.get("locations") or [])
    suggested_str = "\n".join(
        f"- {l.get('name', '')} ({l.get('location_type', '')}): {l.get('theme', '')}"
        for l in suggested
    )
    prompt_tpl = _load_prompt("town/locations_seed.txt")
    prompt = prompt_tpl.format(
        town_name=town.name,
        town_concept=town.concept,
        town_tone=town.tone,
        population_size=town.population_size.value if hasattr(town.population_size, "value") else str(town.population_size),
        suggested_locations=suggested_str or "(none)",
    )
    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = (_get_response_text(response)[0] or "{}")
    data = json.loads(_clean_json(raw))
    locs_data = data.get("locations") or []
    created = []
    for L in locs_data:
        loc = Location(
            name=L.get("name", "Unnamed"),
            location_type=L.get("location_type", ""),
            atmosphere=L.get("atmosphere", ""),
            notable_features=L.get("notable_features") or [],
        )
        manager.create_location(loc)
        manager.add_edge(Edge(source_id=town_id, target_id=loc.id, edge_type=EdgeType.CONTAINS))
        manager.add_edge(Edge(source_id=loc.id, target_id=town_id, edge_type=EdgeType.PART_OF))
        created.append(loc)
    return created


def generate_location(
    manager: WorldStateManager,
    town_id: UUID,
    location_id: UUID,
    already_generated_location_ids: list[UUID],
) -> Location | None:
    """Generate full location description; update Location node."""
    location = manager.get_location(location_id)
    if not location:
        return None
    ctx = get_location_context_for_generation(manager, town_id, location_id, already_generated_location_ids)
    prompt_tpl = _load_prompt("town/location.txt")
    prompt = prompt_tpl.format(
        town_name=ctx.get("town_name", ""),
        town_concept=ctx.get("town_concept", ""),
        town_tone=ctx.get("town_tone", ""),
        location_name=ctx.get("location_name", ""),
        location_type=ctx.get("location_type", ""),
        already_generated_summaries=ctx.get("already_generated_summaries", ""),
    )
    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = (_get_response_text(response)[0] or "{}")
    data = json.loads(_clean_json(raw))
    location.description = data.get("description", "")
    location.dm_notes = data.get("dm_notes", "")
    location.atmosphere = data.get("atmosphere", "")
    location.notable_features = data.get("notable_features") or []
    location.encounter_seeds = data.get("encounter_seeds") or []
    manager.update_location(location)
    return location


# --- Entity generation (NPC, Monster, Item) ---


def _call_entity_prompt(prompt: str) -> tuple[dict, str, dict]:
    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw, block_info = _get_response_text(response)
    raw = raw or "{}"
    global _last_interpret_raw
    _last_interpret_raw = raw
    cleaned = _clean_json(raw)
    data = json.loads(cleaned)
    name_before = repr(data.get("name")) if isinstance(data, dict) else "N/A"
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, dict):
        raise ValueError("Interpret response was not a JSON object")
    _fix_placeholder_name(data, cleaned)
    name_after = repr(data.get("name"))
    debug = {
        "content_block_count": len(response.content),
        "block_info": block_info,
        "raw_len": len(raw),
        "raw_first_400": raw[:400],
        "cleaned_len": len(cleaned),
        "cleaned_first_400": cleaned[:400],
        "parsed_keys": list(data.keys()),
        "name_before_fix": name_before,
        "name_after_fix": name_after,
    }
    return data, raw, debug


def interpret_npc(text: str, party_level: int, context: str = "") -> tuple[dict, str, dict]:
    prompt_tpl = _load_prompt("entities/npc_interpret.txt")
    prompt = prompt_tpl.format(party_level=party_level, context=context or "(none)", description=text or "(no description)")
    return _call_entity_prompt(prompt)


def generate_npc_from_seed(manager: WorldStateManager, campaign_id: UUID, seed: dict) -> NPC:
    """Create NPC node from seed, then call Claude for full sheet; update and return NPC."""
    npc = NPC(
        name=seed.get("name", ""),
        race=seed.get("race", ""),
        character_class=seed.get("character_class"),
        level=seed.get("level"),
        description=seed.get("description", ""),
        personality=seed.get("personality") or [],
        roleplaying_notes=seed.get("roleplaying_notes", ""),
        backstory=seed.get("backstory", ""),
        motivations=seed.get("motivations") or [],
        secrets=seed.get("secrets") or [],
        faction=seed.get("faction"),
    )
    manager.create_npc(npc)
    manager.add_edge(Edge(source_id=campaign_id, target_id=npc.id, edge_type=EdgeType.CONTAINS))
    prompt_tpl = _load_prompt("entities/npc_generate.txt")
    prompt = prompt_tpl.format(seed_json=json.dumps(seed))
    data, _, _ = _call_entity_prompt(prompt)
    npc.name = data.get("name", npc.name)
    npc.race = data.get("race", npc.race)
    npc.character_class = data.get("character_class")
    npc.level = data.get("level")
    npc.description = data.get("description", "")
    npc.personality = data.get("personality") or []
    npc.roleplaying_notes = data.get("roleplaying_notes", "")
    npc.backstory = data.get("backstory", "")
    npc.motivations = data.get("motivations") or []
    npc.secrets = data.get("secrets") or []
    npc.faction = data.get("faction")
    npc.ability_scores = data.get("ability_scores") or {}
    npc.saving_throws = data.get("saving_throws") or []
    npc.skills = data.get("skills") or {}
    npc.armor_class = data.get("armor_class", 10)
    npc.hit_points = data.get("hit_points", 1)
    npc.speed = data.get("speed", "")
    npc.features_and_traits = data.get("features_and_traits") or []
    npc.equipment = data.get("equipment") or []
    npc.spells = data.get("spells")
    manager.update_npc(npc)
    return npc


def interpret_monster(text: str, challenge_rating: str, context: str = "") -> tuple[dict, str]:
    prompt_tpl = _load_prompt("entities/monster_interpret.txt")
    prompt = prompt_tpl.format(
        challenge_rating=challenge_rating,
        context=context or "(none)",
        description=text or "(no description)",
    )
    return _call_entity_prompt(prompt)


def generate_monster_from_seed(manager: WorldStateManager, campaign_id: UUID, seed: dict) -> Monster:
    monster = Monster(
        name=seed.get("name", ""),
        creature_type=seed.get("creature_type", ""),
        size=seed.get("size", ""),
        alignment=seed.get("alignment", ""),
        description=seed.get("description", ""),
        tactics=seed.get("tactics", ""),
    )
    manager.create_monster(monster)
    manager.add_edge(Edge(source_id=campaign_id, target_id=monster.id, edge_type=EdgeType.CONTAINS))
    prompt_tpl = _load_prompt("entities/monster_generate.txt")
    cr = str(seed.get("challenge_rating", "") or "").strip()
    prompt = prompt_tpl.format(
        seed_json=json.dumps(seed),
        challenge_rating=cr or "(unspecified)",
    )
    data, _, _ = _call_entity_prompt(prompt)
    for key in (
        "name",
        "creature_type",
        "size",
        "alignment",
        "description",
        "tactics",
        "ability_scores",
        "armor_class",
        "hit_points",
        "hit_points_avg",
        "speed",
        "skills",
        "saving_throws",
        "damage_resistances",
        "damage_immunities",
        "condition_immunities",
        "senses",
        "languages",
        "challenge_rating",
        "proficiency_bonus",
        "special_abilities",
        "actions",
        "bonus_actions",
        "reactions",
        "legendary_actions",
        "spellcasting",
        "lair_actions",
        "regional_effects",
    ):
        if key in data and data[key] is not None:
            setattr(monster, key, data[key])
    manager.update_monster(monster)
    return monster


def interpret_item(text: str, context: str = "") -> tuple[dict, str]:
    prompt_tpl = _load_prompt("entities/item_interpret.txt")
    prompt = prompt_tpl.format(context=context or "(none)", description=text or "(no description)")
    return _call_entity_prompt(prompt)


def generate_item_from_seed(manager: WorldStateManager, campaign_id: UUID, seed: dict) -> Item:
    itype = seed.get("item_type", "WONDROUS")
    rarity = seed.get("rarity", "COMMON")
    try:
        itype = ItemType(itype) if isinstance(itype, str) else itype
    except ValueError:
        itype = ItemType.WONDROUS
    try:
        rarity = ItemRarity(rarity) if isinstance(rarity, str) else rarity
    except ValueError:
        rarity = ItemRarity.COMMON
    item = Item(
        name=seed.get("name", ""),
        item_type=itype,
        rarity=rarity,
        description=seed.get("description", ""),
        lore=seed.get("lore", ""),
        requires_attunement=seed.get("requires_attunement", False),
        value=seed.get("value"),
    )
    manager.create_item(item)
    manager.add_edge(Edge(source_id=campaign_id, target_id=item.id, edge_type=EdgeType.CONTAINS))
    prompt_tpl = _load_prompt("entities/item_generate.txt")
    prompt = prompt_tpl.format(seed_json=json.dumps(seed))
    data, _, _ = _call_entity_prompt(prompt)
    item.name = data.get("name", item.name)
    try:
        item.item_type = ItemType(str(data.get("item_type", item.item_type.value)))
    except ValueError:
        pass
    try:
        item.rarity = ItemRarity(str(data.get("rarity", item.rarity.value)))
    except ValueError:
        pass
    item.description = data.get("description", "")
    item.lore = data.get("lore", "")
    item.requires_attunement = data.get("requires_attunement", False)
    item.properties = data.get("properties") or []
    item.mechanics = data.get("mechanics", "")
    item.value = data.get("value")
    manager.update_item(item)
    return item
