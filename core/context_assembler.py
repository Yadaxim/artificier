"""Builds context dicts for generation prompts. No Claude calls."""

from uuid import UUID

from core.state_manager import WorldStateManager
from models.models import EdgeType, PlotStatus


def get_dungeon_context(manager: WorldStateManager, dungeon_id: UUID) -> dict:
    """Context for dungeon-level prompts."""
    dungeon = manager.get_dungeon(dungeon_id)
    if not dungeon:
        return {}
    return {
        "dungeon_name": dungeon.name,
        "dungeon_concept": dungeon.concept,
        "dungeon_tone": dungeon.tone,
        "level_range": dungeon.level_range,
        "dungeon": dungeon,
    }


def get_floor_context(manager: WorldStateManager, dungeon_id: UUID, floor_level: int) -> dict:
    """Context for a specific floor (from dungeon.metadata['floors'])."""
    base = get_dungeon_context(manager, dungeon_id)
    dungeon = manager.get_dungeon(dungeon_id)
    if not dungeon:
        return base
    floors = dungeon.metadata.get("floors") or []
    floor_meta = next((f for f in floors if f.get("level_number") == floor_level), None)
    if floor_meta:
        base["floor_name"] = floor_meta.get("name", "")
        base["floor_theme"] = floor_meta.get("theme", "")
        base["floor_level"] = floor_level
        base["room_count"] = floor_meta.get("room_count", 0)
        base["hazard_summary"] = floor_meta.get("hazard_summary", "")
    return base


def get_room_seed_summaries(manager: WorldStateManager, room_ids: list[UUID]) -> str:
    """One-line per room: name, purpose, one sentence. For already-generated rooms."""
    lines = []
    for rid in room_ids:
        room = manager.get_room(rid)
        if not room:
            continue
        # Use first sentence of description if present, else purpose
        desc = room.description.strip()
        if desc:
            first_sentence = desc.split(".")[0].strip() + "." if "." in desc else desc
        else:
            first_sentence = room.purpose or "(no description yet)"
        lines.append(f"- {room.name}: {room.purpose}. {first_sentence}")
    return "\n".join(lines) if lines else "(none yet)"


def get_adjacent_room_seeds(manager: WorldStateManager, room_id: UUID) -> str:
    """List room seeds that CONNECT_TO this room (for context in generate_room)."""
    edges = manager.get_edges_to(room_id, EdgeType.CONNECTS_TO)
    edges += manager.get_edges_from(room_id, EdgeType.CONNECTS_TO)
    seen = set()
    lines = []
    for e in edges:
        other_id = e.target_id if e.source_id == room_id else e.source_id
        if other_id in seen:
            continue
        seen.add(other_id)
        other = manager.get_room(other_id)
        if other:
            vc = other.metadata.get("vertical_connection", "")
            lines.append(f"- {other.name} (floor {other.floor_level}, purpose: {other.purpose}, vertical: {vc})")
    return "\n".join(lines) if lines else "(no adjacent rooms yet)"


def get_room_context_for_generation(
    manager: WorldStateManager,
    dungeon_id: UUID,
    room_id: UUID,
    already_generated_room_ids: list[UUID],
) -> dict:
    """Full context for generate_room prompt."""
    dungeon = manager.get_dungeon(dungeon_id)
    room = manager.get_room(room_id)
    if not dungeon or not room:
        return {}
    ctx = get_dungeon_context(manager, dungeon_id)
    floors = dungeon.metadata.get("floors") or []
    floor_meta = next((f for f in floors if f.get("level_number") == room.floor_level), None)
    if floor_meta:
        ctx["floor_name"] = floor_meta.get("name", "")
        ctx["floor_theme"] = floor_meta.get("theme", "")
    ctx["room_name"] = room.name
    ctx["room_purpose"] = room.purpose
    ctx["room_atmosphere"] = room.atmosphere
    ctx["room_construction_era"] = room.construction_era
    ctx["adjacent_rooms"] = get_adjacent_room_seeds(manager, room_id)
    ctx["already_generated_summaries"] = get_room_seed_summaries(manager, already_generated_room_ids)
    return ctx


def get_town_context(manager: WorldStateManager, town_id: UUID) -> dict:
    """Context for town-level prompts."""
    town = manager.get_town(town_id)
    if not town:
        return {}
    return {
        "town_name": town.name,
        "town_concept": town.concept,
        "town_tone": town.tone,
        "population_size": town.population_size.value if hasattr(town.population_size, "value") else str(town.population_size),
        "town": town,
    }


def get_location_seed_summaries(manager: WorldStateManager, location_ids: list[UUID]) -> str:
    """One-line per location for already-generated locations."""
    lines = []
    for lid in location_ids:
        loc = manager.get_location(lid)
        if not loc:
            continue
        desc = loc.description.strip()
        first = (desc.split(".")[0].strip() + ".") if "." in desc else desc or loc.location_type
        lines.append(f"- {loc.name} ({loc.location_type}): {first}")
    return "\n".join(lines) if lines else "(none yet)"


def get_location_context_for_generation(
    manager: WorldStateManager,
    town_id: UUID,
    location_id: UUID,
    already_generated_location_ids: list[UUID],
) -> dict:
    """Full context for generate_location prompt."""
    town = manager.get_town(town_id)
    location = manager.get_location(location_id)
    if not town or not location:
        return {}
    ctx = get_town_context(manager, town_id)
    ctx["location_name"] = location.name
    ctx["location_type"] = location.location_type
    ctx["already_generated_summaries"] = get_location_seed_summaries(manager, already_generated_location_ids)
    return ctx


def get_campaign_summary(manager: WorldStateManager, campaign_id: UUID) -> str:
    """Compact campaign summary for plot prompts, capped to a short token budget."""
    campaign = manager.get_campaign(campaign_id)
    if not campaign:
        return "Campaign not found."

    lines: list[str] = []
    lines.append(f"Campaign: {campaign.name}")
    lines.append(f"Party level: {campaign.party_level}")
    if campaign.setting_summary:
        lines.append(f"Setting: {campaign.setting_summary}")

    npcs = manager.get_npcs_in_campaign(campaign_id)
    lines.append("NPCs:")
    if npcs:
        for npc in npcs:
            location_name = ""
            for edge in manager.get_edges_to(npc.id, EdgeType.CONTAINS):
                loc = manager.get_location(edge.source_id)
                if loc:
                    location_name = loc.name
                    break
            brief = npc.description.strip().split(".")[0].strip() if npc.description else "No description"
            where = f" @ {location_name}" if location_name else ""
            lines.append(f"- {npc.name}: {brief}{where}")
    else:
        lines.append("- (none)")

    lines.append("Locations:")
    dungeons = manager.get_dungeons_in_campaign(campaign_id)
    towns = manager.get_towns_in_campaign(campaign_id)
    if dungeons:
        for dungeon in dungeons:
            status = dungeon.status.value if hasattr(dungeon.status, "value") else str(dungeon.status)
            lines.append(f"- {dungeon.name} [dungeon] status={status}")
    if towns:
        for town in towns:
            lines.append(f"- {town.name} [town] status=ESTABLISHED")
            for loc in manager.get_locations_in_town(town.id):
                lines.append(f"- {loc.name} [location] status=UNKNOWN")
    if not dungeons and not towns:
        lines.append("- (none)")

    plots = manager.get_plots_in_campaign(campaign_id)
    lines.append("Plots (active/completed):")
    kept = [
        p for p in plots
        if p.status in (PlotStatus.ACTIVE, PlotStatus.COMPLETED)
    ]
    if kept:
        for plot in kept:
            premise = plot.premise.strip().split(".")[0].strip() if plot.premise else ""
            lines.append(f"- {plot.title}: {premise}")
    else:
        lines.append("- (none)")

    monsters = manager.get_monsters_in_campaign(campaign_id)
    lines.append("Monsters:")
    if monsters:
        for m in monsters:
            brief = m.description.strip().split(".")[0].strip() if m.description else m.creature_type or "creature"
            lines.append(f"- {m.name} [monster]: {brief}")
    else:
        lines.append("- (none)")

    items = manager.get_items_in_campaign(campaign_id)
    lines.append("Items:")
    if items:
        for it in items:
            brief = it.description.strip().split(".")[0].strip() if it.description else it.item_type.value
            lines.append(f"- {it.name} [item]: {brief}")
    else:
        lines.append("- (none)")

    lines.append(
        "For plot linking: use suggested_links with entity_type NPC|MONSTER|ITEM|DUNGEON|TOWN|LOCATION "
        "and entity_name EXACTLY matching a name from the lists above (case-sensitive match to the name shown)."
    )

    summary = "\n".join(lines)
    max_chars = 3600  # Roughly <600 tokens for compact plain text.
    if len(summary) > max_chars:
        summary = summary[: max_chars - 3].rstrip() + "..."
    return summary
