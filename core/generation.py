"""Interpret and generate flows; all Claude calls and WorldStateManager usage."""

import json
import os
import re
from pathlib import Path
from uuid import UUID

from anthropic import Anthropic
from models.models import (
    Clue,
    Dungeon,
    Edge,
    EdgeType,
    Item,
    ItemRarity,
    ItemType,
    Location,
    Monster,
    NPC,
    Plot,
    PlotBeat,
    PlotBeatStatus,
    PlotBeatType,
    PlotType,
    PlotStatus,
    Room,
    Town,
)

from core.context_assembler import (
    get_campaign_summary,
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


def _call_json_prompt(prompt: str, *, max_tokens: int = 8192) -> dict | list:
    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    raw, _ = _get_response_text(response)
    raw = raw or "{}"
    cleaned = _clean_json(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Claude sometimes returns valid JSON followed by extra text/JSON.
        # Decode only the first valid JSON value and ignore trailing content.
        decoder = json.JSONDecoder()
        start = min([i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1], default=-1)
        if start == -1:
            raise
        data, _ = decoder.raw_decode(cleaned, idx=start)
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, (dict, list)):
        raise ValueError("Claude response was not valid JSON")
    return data


def _coerce_clue_distribution_list(data: object) -> list[dict]:
    """
    Claude often returns {"clues": [...]} despite instructions for a raw array.
    Accept a list of clue objects or common object wrappers.
    """
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if not isinstance(data, dict):
        return []
    for key in (
        "clues",
        "clue_list",
        "clues_list",
        "items",
        "data",
        "results",
        "distribution",
    ):
        val = data.get(key)
        if isinstance(val, list) and val and all(isinstance(x, dict) for x in val):
            return list(val)
    # Single clue returned as one object (not wrapped in a list)
    if any(k in data for k in ("content", "how_found", "beat_title", "location_name_or_npc_name")):
        return [data]
    # First list-of-dicts value that looks like clue rows
    for val in data.values():
        if not isinstance(val, list) or not val:
            continue
        if not all(isinstance(x, dict) for x in val):
            continue
        sample = val[0]
        if any(k in sample for k in ("content", "how_found", "beat_title", "location_name_or_npc_name")):
            return list(val)
    return []


def _manager_for_plot(plot_id: UUID) -> tuple[WorldStateManager, UUID]:
    manager = WorldStateManager()
    for campaign_id in manager.list_campaign_ids():
        manager.load_campaign(campaign_id)
        if manager.get_plot(plot_id):
            return manager, campaign_id
    raise KeyError(f"Plot {plot_id} not found in any campaign")


def interpret_dungeon(text: str, party_level: int) -> dict:
    """Interpret free-text dungeon description into structured seed."""
    prompt_tpl = _load_prompt("dungeon/interpret.txt")
    prompt = prompt_tpl.format(party_level=party_level, description=text or "(no description)")
    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw, _ = _get_response_text(response)
    raw = raw or "{}"
    cleaned = _clean_json(raw)
    data = json.loads(cleaned)
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, dict):
        raise ValueError("Interpret response was not a JSON object")
    _fix_placeholder_name(data, cleaned)
    return data


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


def interpret_town(text: str, party_level: int) -> dict:
    """Interpret free-text town description."""
    prompt_tpl = _load_prompt("town/interpret.txt")
    prompt = prompt_tpl.format(party_level=party_level, description=text or "(no description)")
    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw, _ = _get_response_text(response)
    raw = raw or "{}"
    cleaned = _clean_json(raw)
    data = json.loads(cleaned)
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, dict):
        raise ValueError("Interpret response was not a JSON object")
    _fix_placeholder_name(data, cleaned)
    return data


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


# --- Plot generation ---


def _unwrap_plot_interpret_dict(data: dict) -> dict:
    """
    Merge nested wrappers (plot/result/...) into one dict.
    Important: suggested_links often live only under \"plot\" while beats are top-level — old logic dropped them.
    """
    if not isinstance(data, dict):
        return {}
    merged = dict(data)
    for wk in ("plot", "result", "interpretation", "output", "response", "data"):
        inner = merged.get(wk)
        if not isinstance(inner, dict):
            continue
        for ik, iv in inner.items():
            if iv is None:
                continue
            cur = merged.get(ik)
            if ik == "beats":
                if isinstance(iv, list) and iv and (not isinstance(cur, list) or len(iv) > len(cur)):
                    merged[ik] = iv
            elif ik in ("suggested_links", "required_entities"):
                if isinstance(iv, list) and iv and (not isinstance(cur, list) or len(iv) > len(cur or [])):
                    merged[ik] = iv
            elif cur in (None, "", [], {}):
                merged[ik] = iv
    return merged


def _coerce_dict_list(val: object) -> list[dict]:
    if isinstance(val, list):
        return [x for x in val if isinstance(x, dict)]
    if isinstance(val, str) and val.strip():
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return [x for x in parsed if isinstance(x, dict)]
        except json.JSONDecodeError:
            pass
    return []


def _normalize_suggested_link_item(item: dict) -> dict | None:
    """Map alternate LLM keys to {entity_type, entity_name, role}."""
    if not isinstance(item, dict):
        return None
    name = (
        item.get("entity_name")
        or item.get("name")
        or item.get("npc_name")
        or item.get("monster_name")
        or item.get("item_name")
        or item.get("dungeon_name")
        or item.get("town_name")
        or item.get("location_name")
    )
    if not name or not str(name).strip():
        return None
    et_raw = (
        item.get("entity_type")
        or item.get("type")
        or item.get("kind")
        or item.get("entity")
        or "NPC"
    )
    et = str(et_raw).strip().upper().replace(" ", "_")
    aliases = {
        "CHARACTER": "NPC",
        "PC": "NPC",
        "PERSON": "NPC",
        "PLACE": "LOCATION",
        "SHOP": "LOCATION",
        "BUILDING": "LOCATION",
    }
    et = aliases.get(et, et)
    role = item.get("role") or item.get("relationship") or item.get("involvement") or "Relevant to this plot"
    return {"entity_type": et, "entity_name": str(name).strip(), "role": str(role).strip()}


def _dedupe_suggested_links(links: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for L in links:
        if not isinstance(L, dict):
            continue
        et = str(L.get("entity_type", "NPC")).strip().upper() or "NPC"
        nm = str(L.get("entity_name", "")).strip()
        if not nm:
            continue
        key = (et, nm.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "entity_type": et,
            "entity_name": nm,
            "role": str(L.get("role", "Plot connection")).strip() or "Plot connection",
        })
    return out


def _extract_involved_entities_as_links(data: dict) -> list[dict]:
    """LLMs often put existing-campaign ties under involved_entities instead of suggested_links."""
    out: list[dict] = []
    for key in (
        "involved_entities",
        "involved_parties",
        "existing_involvements",
        "anchor_entities",
        "campaign_entity_links",
    ):
        for item in _coerce_dict_list(data.get(key)):
            n = _normalize_suggested_link_item(item)
            if n:
                out.append(n)
    return out


def _gather_suggested_links_from_interpret(data: dict) -> list[dict]:
    """Collect from every known key and merge (do not stop at first empty key)."""
    gathered: list[dict] = []
    for key in (
        "suggested_links",
        "suggested_connections",
        "suggested_involvements",
        "entity_links",
        "links",
        "involvements",
        "campaign_links",
    ):
        for item in _coerce_dict_list(data.get(key)):
            n = _normalize_suggested_link_item(item)
            if n:
                gathered.append(n)
    gathered.extend(_extract_involved_entities_as_links(data))

    skip_heuristic = {
        "beats",
        "resolution_variants",
        "world_consequences",
        "required_entities",
        "new_entities",
        "entities_to_create",
        "missing_entities",
        "plot",
        "result",
        "interpretation",
        "output",
        "response",
        "data",
    }
    for key, val in data.items():
        if key in skip_heuristic or isinstance(val, (str, int, float, bool)) or val is None:
            continue
        if not isinstance(val, list) or len(val) < 1:
            continue
        dicts = [x for x in val if isinstance(x, dict)]
        if len(dicts) != len(val):
            continue
        sample = dicts[0]
        if not any(
            k in sample
            for k in ("entity_name", "npc_name", "name", "location_name", "entity_type", "entity")
        ):
            continue
        if "beat_type" in sample and "entity_name" not in sample and "entity_type" not in sample:
            continue
        for item in dicts:
            n = _normalize_suggested_link_item(item)
            if n:
                gathered.append(n)

    return _dedupe_suggested_links(gathered)


def _extract_required_entities_from_interpret(data: dict) -> list[dict]:
    for key in (
        "required_entities",
        "new_entities",
        "entities_to_create",
        "missing_entities",
    ):
        out = _coerce_dict_list(data.get(key))
        if out:
            return out
    return []


def _campaign_has_linkable_entities(manager: WorldStateManager, campaign_id: UUID) -> bool:
    return bool(
        manager.get_npcs_in_campaign(campaign_id)
        or manager.get_towns_in_campaign(campaign_id)
        or manager.get_dungeons_in_campaign(campaign_id)
        or manager.get_monsters_in_campaign(campaign_id)
        or manager.get_items_in_campaign(campaign_id)
    )


def _fallback_suggested_links(
    manager: WorldStateManager,
    campaign_id: UUID,
    plot: Plot,
    user_text: str,
    *,
    max_links: int = 8,
) -> list[dict]:
    """
    If the model returns no suggested_links, still offer DM checkboxes by tying known campaign entities.
    Prefer entities whose names appear in the plot text; pad with a few campaign anchors if needed.
    """
    parts = [
        user_text or "",
        plot.title or "",
        plot.premise or "",
        plot.summary or "",
    ]
    for b in plot.beats:
        parts.extend([b.title or "", b.description or "", b.trigger or "", b.dm_notes or ""])
    corpus = " ".join(parts).lower()

    candidates: list[tuple[str, str]] = []
    for n in manager.get_npcs_in_campaign(campaign_id):
        if n.name.strip():
            candidates.append(("NPC", n.name.strip()))
    for t in manager.get_towns_in_campaign(campaign_id):
        if t.name.strip():
            candidates.append(("TOWN", t.name.strip()))
    for d in manager.get_dungeons_in_campaign(campaign_id):
        if d.name.strip():
            candidates.append(("DUNGEON", d.name.strip()))
    for town in manager.get_towns_in_campaign(campaign_id):
        for loc in manager.get_locations_in_town(town.id):
            if loc.name.strip():
                candidates.append(("LOCATION", loc.name.strip()))
    for m in manager.get_monsters_in_campaign(campaign_id):
        if m.name.strip():
            candidates.append(("MONSTER", m.name.strip()))
    for it in manager.get_items_in_campaign(campaign_id):
        if it.name.strip():
            candidates.append(("ITEM", it.name.strip()))

    matches: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for etype, name in candidates:
        key = (etype, name.lower())
        if key in seen:
            continue
        nl = name.lower()
        if len(nl) >= 2 and nl in corpus:
            matches.append({
                "entity_type": etype,
                "entity_name": name,
                "role": "Referenced by name in the plot idea or seed — strong default involvement",
            })
            seen.add(key)
        if len(matches) >= max_links:
            return matches

    for etype, name in candidates:
        if len(matches) >= max_links:
            break
        key = (etype, name.lower())
        if key in seen:
            continue
        matches.append({
            "entity_type": etype,
            "entity_name": name,
            "role": "Existing campaign entity — consider weaving into this plot",
        })
        seen.add(key)

    return matches[:max_links]


def interpret_plot(
    text: str,
    party_level: int,
    campaign_id: UUID,
    manager: WorldStateManager | None = None,
) -> Plot:
    m = manager if manager is not None else WorldStateManager()
    m.ensure_loaded(campaign_id)
    campaign_summary = get_campaign_summary(m, campaign_id)
    prompt_tpl = _load_prompt("plot/interpret.txt")
    prompt = prompt_tpl.format(
        text=text or "(no description)",
        party_level=party_level,
        campaign_summary=campaign_summary,
    )
    data = _call_json_prompt(prompt, max_tokens=8192)
    if not isinstance(data, dict):
        raise ValueError("Interpret plot response was not a JSON object")
    data = _unwrap_plot_interpret_dict(data)

    plot_type_raw = str(data.get("plot_type", PlotType.OTHER.value)).upper()
    try:
        plot_type = PlotType(plot_type_raw)
    except ValueError:
        plot_type = PlotType.OTHER

    beats: list[PlotBeat] = []
    for b in (data.get("beats") or []):
        beat_type_raw = str(b.get("beat_type", PlotBeatType.HOOK.value)).upper()
        try:
            beat_type = PlotBeatType(beat_type_raw)
        except ValueError:
            beat_type = PlotBeatType.HOOK
        beats.append(
            PlotBeat(
                title=b.get("title", ""),
                description=b.get("description", ""),
                trigger=b.get("trigger", ""),
                dm_notes=b.get("dm_notes", ""),
                beat_type=beat_type,
                status=PlotBeatStatus.PENDING,
            )
        )

    plot = Plot(
        title=data.get("title", ""),
        premise=data.get("premise", ""),
        tone=data.get("tone", ""),
        plot_type=plot_type,
        status=PlotStatus.INACTIVE,
        party_level_range=data.get("party_level_range", f"levels {party_level}-{party_level + 2}"),
        summary=data.get("summary", ""),
        secret=data.get("secret", ""),
        beats=beats,
        resolution_variants=data.get("resolution_variants") or [],
        world_consequences=data.get("world_consequences") or [],
    )
    plot.metadata["required_entities"] = _extract_required_entities_from_interpret(data)
    links = _gather_suggested_links_from_interpret(data)
    if not links and _campaign_has_linkable_entities(m, campaign_id):
        links = _fallback_suggested_links(m, campaign_id, plot, text)
    plot.metadata["suggested_links"] = links
    return plot


def generate_plot(plot_id: UUID) -> Plot:
    manager, campaign_id = _manager_for_plot(plot_id)
    plot = manager.get_plot(plot_id)
    if not plot:
        raise KeyError(f"Plot {plot_id} not found")
    campaign_summary = get_campaign_summary(manager, campaign_id)
    prompt_tpl = _load_prompt("plot/generate.txt")
    prompt = prompt_tpl.format(
        plot_seed=json.dumps(plot.model_dump(mode="json"), indent=2),
        campaign_summary=campaign_summary,
    )
    data = _call_json_prompt(prompt, max_tokens=8192)
    if not isinstance(data, dict):
        raise ValueError("Generate plot response was not a JSON object")

    plot.title = data.get("title", plot.title)
    plot.premise = data.get("premise", plot.premise)
    plot.tone = data.get("tone", plot.tone)
    plot.summary = data.get("summary", plot.summary)
    plot.secret = data.get("secret", plot.secret)
    if "party_level_range" in data:
        plot.party_level_range = data.get("party_level_range", plot.party_level_range)

    plot_type_raw = str(data.get("plot_type", plot.plot_type.value)).upper()
    try:
        plot.plot_type = PlotType(plot_type_raw)
    except ValueError:
        pass

    status_raw = str(data.get("status", plot.status.value)).upper()
    try:
        plot.status = PlotStatus(status_raw)
    except ValueError:
        pass

    beats: list[PlotBeat] = []
    for b in (data.get("beats") or []):
        beat_type_raw = str(b.get("beat_type", PlotBeatType.HOOK.value)).upper()
        status_raw = str(b.get("status", PlotBeatStatus.PENDING.value)).upper()
        try:
            beat_type = PlotBeatType(beat_type_raw)
        except ValueError:
            beat_type = PlotBeatType.HOOK
        try:
            beat_status = PlotBeatStatus(status_raw)
        except ValueError:
            beat_status = PlotBeatStatus.PENDING
        beats.append(
            PlotBeat(
                title=b.get("title", ""),
                description=b.get("description", ""),
                trigger=b.get("trigger", ""),
                dm_notes=b.get("dm_notes", ""),
                beat_type=beat_type,
                status=beat_status,
            )
        )
    if beats:
        plot.beats = beats
    plot.resolution_variants = data.get("resolution_variants") or plot.resolution_variants
    plot.world_consequences = data.get("world_consequences") or plot.world_consequences
    manager.update_plot(plot)
    return plot


def generate_clues(plot_id: UUID) -> list[Clue]:
    manager, campaign_id = _manager_for_plot(plot_id)
    plot = manager.get_plot(plot_id)
    if not plot:
        raise KeyError(f"Plot {plot_id} not found")

    existing = manager.get_clues_in_plot(plot.id)
    for clue in existing:
        manager.delete_clue(clue.id)

    npcs = manager.get_npcs_in_campaign(campaign_id)
    locations = []
    for town in manager.get_towns_in_campaign(campaign_id):
        locations.extend(manager.get_locations_in_town(town.id))
    locations.extend(manager.get_dungeons_in_campaign(campaign_id))
    locations.extend(manager.get_towns_in_campaign(campaign_id))

    prompt_tpl = _load_prompt("plot/clue_distribute.txt")
    prompt = prompt_tpl.format(
        plot_title=plot.title,
        plot_beats=json.dumps([b.model_dump(mode="json") for b in plot.beats], indent=2),
        locations=json.dumps(
            [{"name": getattr(l, "name", ""), "type": l.__class__.__name__} for l in locations],
            indent=2,
        ),
        npcs=json.dumps([{"name": n.name, "description": n.description} for n in npcs], indent=2),
    )
    data = _call_json_prompt(prompt, max_tokens=8192)
    clue_rows = _coerce_clue_distribution_list(data)
    if not clue_rows:
        raise ValueError(
            "Clue distribution response was not a JSON array of clues "
            "(expected a list or an object with a 'clues' array)."
        )

    by_name: dict[str, object] = {}
    for npc in npcs:
        by_name[npc.name.lower()] = npc
    for loc in locations:
        by_name[getattr(loc, "name", "").lower()] = loc

    created: list[Clue] = []
    for c in clue_rows:
        clue = Clue(
            content=c.get("content", ""),
            how_found=c.get("how_found", ""),
            plot_id=str(plot.id),
            beat_title=c.get("beat_title", ""),
        )
        manager.create_clue(clue)
        manager.add_edge(Edge(source_id=plot.id, target_id=clue.id, edge_type=EdgeType.CONTAINS))
        target_name = str(c.get("location_name_or_npc_name", "")).strip().lower()
        target = by_name.get(target_name)
        if target is not None and hasattr(target, "id"):
            manager.add_edge(Edge(source_id=target.id, target_id=clue.id, edge_type=EdgeType.CONTAINS))
        created.append(clue)
    return created


def _plot_has_involves_edge(manager: WorldStateManager, plot_id: UUID, target_id: UUID) -> bool:
    for e in manager.get_edges_from(plot_id, EdgeType.INVOLVES):
        if e.target_id == target_id:
            return True
    return False


def _match_entity_for_plot_wire(entity_name: str, candidates: list) -> object | None:
    """Resolve LLM name to a campaign node; tolerate extra words / punctuation vs graph names."""
    raw = entity_name.strip()
    if not raw:
        return None
    n = raw.lower()
    exact = [e for e in candidates if getattr(e, "name", "").strip().lower() == n]
    if exact:
        return exact[0]
    for e in candidates:
        en = getattr(e, "name", "").strip()
        if not en:
            continue
        el = en.lower()
        if n in el or el in n:
            return e

    def alnum(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", s.lower())

    an = alnum(raw)
    if an:
        for e in candidates:
            if alnum(getattr(e, "name", "")) == an:
                return e
    return None


def wire_plot_entities(plot_id: UUID) -> None:
    manager, campaign_id = _manager_for_plot(plot_id)
    plot = manager.get_plot(plot_id)
    if not plot:
        raise KeyError(f"Plot {plot_id} not found")
    links = plot.metadata.get("suggested_links") or []
    if not isinstance(links, list):
        return

    npcs = manager.get_npcs_in_campaign(campaign_id)
    monsters = manager.get_monsters_in_campaign(campaign_id)
    items = manager.get_items_in_campaign(campaign_id)
    dungeons = manager.get_dungeons_in_campaign(campaign_id)
    towns = manager.get_towns_in_campaign(campaign_id)
    locations = []
    for town in towns:
        locations.extend(manager.get_locations_in_town(town.id))

    typed = {
        "NPC": npcs,
        "MONSTER": monsters,
        "ITEM": items,
        "DUNGEON": dungeons,
        "TOWN": towns,
        "LOCATION": locations,
    }

    for link in links:
        entity_type = str(link.get("entity_type", "")).upper().replace(" ", "_")
        entity_name = str(link.get("entity_name", "")).strip()
        role = str(link.get("role", "")).strip()
        if not entity_name:
            continue
        candidates = typed.get(entity_type, [])
        match = _match_entity_for_plot_wire(entity_name, candidates)
        if not match:
            continue
        if _plot_has_involves_edge(manager, plot.id, match.id):
            continue
        manager.add_edge(
            Edge(
                source_id=plot.id,
                target_id=match.id,
                edge_type=EdgeType.INVOLVES,
                properties={"role": role},
            )
        )
        if isinstance(match, NPC):
            if role and role not in (match.roleplaying_notes or ""):
                match.roleplaying_notes = (match.roleplaying_notes + "\n" if match.roleplaying_notes else "") + f"Plot role ({plot.title}): {role}"
                manager.update_npc(match)
        elif isinstance(match, Location):
            if role and role not in (match.dm_notes or ""):
                match.dm_notes = (match.dm_notes + "\n" if match.dm_notes else "") + f"Plot role ({plot.title}): {role}"
                manager.update_location(match)
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
    cleaned = _clean_json(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        start = min([i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1], default=-1)
        if start == -1:
            raise
        data, _ = decoder.raw_decode(cleaned, idx=start)
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


def interpret_npc(text: str, context: str = "") -> dict:
    prompt_tpl = _load_prompt("entities/npc_interpret.txt")
    prompt = prompt_tpl.format(context=context or "(none)", description=text or "(no description)")
    return _call_entity_prompt(prompt)[0]


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


def interpret_monster(text: str, challenge_rating: str, context: str = "") -> dict:
    prompt_tpl = _load_prompt("entities/monster_interpret.txt")
    prompt = prompt_tpl.format(
        challenge_rating=challenge_rating,
        context=context or "(none)",
        description=text or "(no description)",
    )
    return _call_entity_prompt(prompt)[0]


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


def interpret_item(text: str, context: str = "") -> dict:
    prompt_tpl = _load_prompt("entities/item_interpret.txt")
    prompt = prompt_tpl.format(context=context or "(none)", description=text or "(no description)")
    return _call_entity_prompt(prompt)[0]


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


def _guess_requirement_placeholder_name(description: str) -> str:
    text = (description or "").strip()
    if not text:
        return "Plot entity"
    line = text.split("\n")[0].strip()
    words = re.findall(r"[A-Za-z0-9']+", line)
    stop = {
        "a", "an", "the", "for", "who", "that", "with", "and", "or", "to", "of", "in", "on", "at",
    }
    picked: list[str] = []
    for w in words:
        wl = w.lower()
        if wl in stop and not picked:
            continue
        picked.append(w)
        if len(picked) >= 4:
            break
    label = " ".join(picked).strip()
    return (label or "Plot entity")[:80]


def _resolve_town_for_new_location(
    manager: WorldStateManager,
    campaign_id: UUID,
    req: dict,
) -> tuple[Town | None, str | None]:
    """
    Pick a parent town for a new Location. Returns (town, error_message).
    """
    towns = manager.get_towns_in_campaign(campaign_id)
    hint = (
        str(req.get("town_name") or req.get("parent_town") or req.get("in_town") or "").strip()
    )
    if hint:
        match = _match_entity_for_plot_wire(hint, towns)
        if match:
            return match, None
        return None, f"No town matching «{hint}» — check spelling or add the town first."
    if len(towns) == 1:
        return towns[0], None
    if len(towns) == 0:
        return None, "No towns in this campaign — create a town first, or set town_name on the location requirement."
    return None, "Several towns exist — add town_name (or parent_town) to the location requirement to pick one."


def fulfill_plot_required_entities(
    manager: WorldStateManager,
    campaign_id: UUID,
    plot_id: UUID,
) -> list[str]:
    """
    Create NPC / Monster / Item / Location nodes from plot.metadata['required_entities'] and link via INVOLVES.
    Location is created under a town (CONTAINS/PART_OF); parent town from town_name hint, or the only town in campaign.
    Skips Dungeon and Town (still add those from campaign tools).
    """
    plot = manager.get_plot(plot_id)
    if not plot:
        return ["Plot not found."]
    reqs = plot.metadata.get("required_entities") or []
    if not isinstance(reqs, list) or not reqs:
        return []

    notes: list[str] = []
    for req in reqs:
        if not isinstance(req, dict):
            continue
        et = str(req.get("entity_type", "")).strip().upper().replace(" ", "_")
        desc = str(req.get("description", "") or "").strip()
        name_hint = str(req.get("name") or req.get("suggested_name") or "").strip()
        name = name_hint or _guess_requirement_placeholder_name(desc)
        role = f"Required for plot «{plot.title}»"

        if et in ("DUNGEON", "TOWN"):
            notes.append(f"Skipped auto-create for {et} ({name}): add from Dungeons/Towns in the app.")
            continue
        if not desc and not name_hint:
            notes.append(f"Skipped a {et or 'unknown'} requirement (no description or name).")
            continue

        try:
            if et == "LOCATION":
                town, terr = _resolve_town_for_new_location(manager, campaign_id, req)
                if not town or terr:
                    notes.append(f"Location «{name}»: {terr or 'Could not pick a parent town.'}")
                    continue
                loc = Location(
                    name=name,
                    location_type=str(req.get("location_type") or "PLACE"),
                    description=desc or "",
                    dm_notes=role,
                )
                manager.create_location(loc)
                manager.add_edge(Edge(source_id=town.id, target_id=loc.id, edge_type=EdgeType.CONTAINS))
                manager.add_edge(Edge(source_id=loc.id, target_id=town.id, edge_type=EdgeType.PART_OF))
                try:
                    generate_location(manager, town.id, loc.id, [])
                except Exception as gen_ex:
                    notes.append(f"Location «{name}» created under «{town.name}» (full text generation failed: {gen_ex}).")
                else:
                    notes.append(f"Created LOCATION «{name}» under town «{town.name}» (with generated details).")
                ent = loc
            elif et == "NPC":
                seed = {
                    "name": name,
                    "description": desc or name,
                    "roleplaying_notes": role,
                }
                ent = generate_npc_from_seed(manager, campaign_id, seed)
            elif et == "MONSTER":
                seed = {
                    "name": name,
                    "description": desc or name,
                    "creature_type": str(req.get("creature_type") or "unknown"),
                    "challenge_rating": str(req.get("challenge_rating") or "3"),
                }
                ent = generate_monster_from_seed(manager, campaign_id, seed)
            elif et == "ITEM":
                seed = {
                    "name": name,
                    "description": desc or name,
                    "item_type": str(req.get("item_type") or "WONDROUS"),
                    "rarity": str(req.get("rarity") or "UNCOMMON"),
                }
                ent = generate_item_from_seed(manager, campaign_id, seed)
            else:
                notes.append(f"Unknown entity_type {et!r} — skipped.")
                continue

            if not _plot_has_involves_edge(manager, plot_id, ent.id):
                manager.add_edge(
                    Edge(
                        source_id=plot_id,
                        target_id=ent.id,
                        edge_type=EdgeType.INVOLVES,
                        properties={"role": role},
                    )
                )
            if et != "LOCATION":
                notes.append(f"Created {et} «{getattr(ent, 'name', name)}».")
        except Exception as ex:
            notes.append(f"Failed to create {et} «{name}»: {ex}")

    return notes
