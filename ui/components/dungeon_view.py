"""List dungeons and show single dungeon with rooms grouped by floor."""

import graphviz
import streamlit as st

from core.generation import generate_room, seed_dungeon_rooms
from models.models import EdgeType
from ui.state import (
    clear_pending_delete,
    get_campaign_id,
    get_manager,
    get_pending_delete,
    get_selected_dungeon_id,
    get_selected_room_id,
    set_pending_delete,
    set_selected_dungeon_id,
    set_selected_room_id,
    set_view_kind,
)


def render_dungeons_list() -> None:
    manager = get_manager()
    campaign_id = manager._loaded_campaign_id
    if not campaign_id:
        st.info("Select a campaign to see dungeons.")
        return
    dungeons = manager.get_dungeons_in_campaign(campaign_id)
    dungeons = sorted(dungeons, key=lambda d: d.created_at, reverse=True)
    pending = get_pending_delete()
    if not dungeons:
        st.info("No dungeons yet. Create one from the sidebar.")
        return
    for d in dungeons:
        row_col, action1_col, action2_col = st.columns([6, 1, 1])
        with row_col:
            st.markdown(f"### {d.name}")
            st.caption(f"{d.concept[:200]}..." if len(d.concept) > 200 else d.concept)
        if pending and pending.get("kind") == "dungeon" and pending.get("id") == str(d.id):
            st.warning("Delete this dungeon and all its rooms?")
            with action1_col:
                if st.button("Cancel", key=f"cancel_del_dungeon_{d.id}"):
                    clear_pending_delete()
                    st.rerun()
            with action2_col:
                if st.button("Yes, delete", key=f"confirm_del_dungeon_{d.id}", type="primary"):
                    manager.delete_dungeon(d.id)
                    if get_selected_dungeon_id() == d.id:
                        set_selected_dungeon_id(None)
                    clear_pending_delete()
                    st.rerun()
        else:
            with action1_col:
                if st.button("View", key=f"view_dungeon_{d.id}"):
                    set_selected_dungeon_id(d.id)
                    set_view_kind("dungeon_single")
                    st.rerun()
            with action2_col:
                if st.button("Delete", key=f"del_dungeon_{d.id}"):
                    set_pending_delete("dungeon", d.id, d.name, "all its rooms")
                    st.rerun()
        st.divider()


def render_dungeon_single() -> None:
    dungeon_id = get_selected_dungeon_id()
    if not dungeon_id:
        set_view_kind("dungeons")
        st.rerun()
        return
    manager = get_manager()
    dungeon = manager.get_dungeon(dungeon_id)
    if not dungeon:
        st.error("Dungeon not found.")
        return
    st.subheader(dungeon.name)
    st.write(dungeon.concept)
    st.caption(f"Level range: {dungeon.level_range} · Tone: {dungeon.tone}")
    rooms = manager.get_rooms_in_dungeon(dungeon_id)
    planned_floors = dungeon.metadata.get("floors") or []
    if planned_floors:
        st.markdown("**Planned floors**")
        by_floor: dict[int, list] = {}
        for r in rooms:
            by_floor.setdefault(r.floor_level, []).append(r)
        for idx, f in enumerate(planned_floors):
            lvl = f.get("level_number", 0)
            name = f.get("name", "Floor")
            theme = f.get("theme", "")
            count = f.get("room_count", 0)
            room_count = len(by_floor.get(lvl, []))
            if room_count > 0:
                st.caption(f"- Level {lvl}: {name} — {theme} ({room_count}/{count} rooms seeded)")
            else:
                st.caption(f"- Level {lvl}: {name} — {theme} ({count} rooms, not yet seeded)")
        st.divider()

    # Visual dungeon graph (rooms as nodes, passages as edges)
    if rooms:
        with st.expander("Dungeon graph (rooms and connections)", expanded=False):
            _render_dungeon_graph(manager, dungeon_id, rooms)
    if not rooms and planned_floors:
        st.info("No rooms yet. Seed all dungeon rooms in one step.")
        campaign_id = get_campaign_id()
        if campaign_id and st.button("Seed all rooms", key="dungeon_single_seed_all"):
            with st.spinner("Seeding all dungeon rooms..."):
                try:
                    seed_dungeon_rooms(manager, campaign_id, dungeon_id)
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    by_floor_rooms: dict[int, list] = {}
    for r in rooms:
        by_floor_rooms.setdefault(r.floor_level, []).append(r)
    pending = get_pending_delete()
    campaign_id = get_campaign_id()
    for level in sorted(by_floor_rooms.keys()):
        st.markdown(f"**Floor {level}**")
        for r in by_floor_rooms[level]:
            generated = bool(r.description or r.read_aloud)
            col1, col2 = st.columns([3, 1])
            with col1:
                status = "✓ generated" if generated else "○ not generated"
                prefix = "[Entrance] " if r.is_entrance else ""
                # Make room heading visually distinct
                st.markdown(f"### {prefix}{r.name}")
                st.caption(f"{r.purpose} — {status}")
                # Topology: show connections involving this room (both directions)
                out_conns = manager.get_connections(r.id, EdgeType.CONNECTS_TO)
                in_conns = manager.get_edges_to(r.id, EdgeType.CONNECTS_TO)
                connections = out_conns + [e for e in in_conns if e not in out_conns]
                if connections:
                    st.caption("Connections:")
                    for e in connections:
                        other_id = e.target_id if e.source_id == r.id else e.source_id
                        target = manager.get_room(other_id)
                        if not target:
                            continue
                        ptype = e.properties.get("passage_type", "?")
                        length = e.properties.get("length", "?")
                        # Include vertical direction if this is a cross-floor connection
                        dir_part = ""
                        if target.floor_level != r.floor_level:
                            if target.floor_level > r.floor_level:
                                dir_part = f"↑ to Floor {target.floor_level}"
                            else:
                                dir_part = f"↓ to Floor {target.floor_level}"
                        extra = f"{ptype}, {length}"
                        if dir_part:
                            extra = f"{extra}, {dir_part}"
                        st.write(f"  - {target.name} [{extra}]")
                # Relationships: show inter-room logic links (both directions)
                out_rels = manager.get_connections(r.id, EdgeType.RELATED_TO)
                in_rels = manager.get_edges_to(r.id, EdgeType.RELATED_TO)
                # Deduplicate by unordered pair of room IDs
                relationships: list = []
                seen_pairs: set[tuple[str, str]] = set()
                for e in list(out_rels) + list(in_rels):
                    a = str(e.source_id)
                    b = str(e.target_id)
                    pair = tuple(sorted((a, b)))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    relationships.append(e)
                if relationships:
                    st.caption("Relationships:")
                    for e in relationships:
                        other_id = e.target_id if e.source_id == r.id else e.source_id
                        target = manager.get_room(other_id)
                        if not target:
                            continue
                        rtype = e.properties.get("type", "related")
                        desc = e.properties.get("description")
                        if desc:
                            st.write(f"  - {rtype} → {target.name} ({desc})")
                        else:
                            st.write(f"  - {rtype} → {target.name}")
            with col2:
                if pending and pending.get("kind") == "room" and pending.get("id") == str(r.id):
                    st.caption("Delete?")
                    if st.button("Cancel", key=f"cancel_del_room_{r.id}"):
                        clear_pending_delete()
                        st.rerun()
                    if st.button("Yes", key=f"confirm_del_room_{r.id}", type="primary"):
                        manager.delete_room(r.id)
                        if get_selected_room_id() == r.id:
                            set_selected_room_id(None)
                        clear_pending_delete()
                        st.rerun()
                else:
                    if not generated and campaign_id:
                        if st.button("Generate", key=f"generate_room_{r.id}"):
                            with st.spinner(f"Generating {r.name}..."):
                                try:
                                    already = [x.id for x in rooms if x.id != r.id and (x.description or x.read_aloud)]
                                    generate_room(manager, dungeon_id, r.id, already)
                                    set_selected_room_id(r.id)
                                    set_view_kind("room_single")
                                    st.rerun()
                                except Exception as e:
                                    st.error(str(e))
                    if st.button("Open", key=f"open_room_{r.id}"):
                        set_selected_room_id(r.id)
                        set_view_kind("room_single")
                        st.rerun()
                    if st.button("Delete", key=f"del_room_{r.id}"):
                        set_pending_delete("room", r.id, r.name, "")
                        st.rerun()
        st.divider()
    if st.button("Back to dungeons"):
        set_selected_dungeon_id(None)
        set_view_kind("dungeons")
        st.rerun()


def _render_dungeon_graph(manager, dungeon_id, rooms: list) -> None:
    """Render per-floor graphs of rooms and their connections using Graphviz."""
    if not rooms:
        st.caption("No rooms to display yet.")
        return

    # Group rooms by floor level
    by_floor: dict[int, list] = {}
    for r in rooms:
        by_floor.setdefault(r.floor_level, []).append(r)

    for level in sorted(by_floor.keys()):
        floor_rooms = by_floor[level]
        st.markdown(f"**Floor {level}**")

        dot = graphviz.Digraph()

        # Nodes: label with name, entrance marker, plus vertical connection indicators
        for r in floor_rooms:
            vc = (r.metadata or {}).get("vertical_connection")
            vc_label = ""
            if vc == "up":
                vc_label = "\\n↑ up"
            elif vc == "down":
                vc_label = "\\n↓ down"
            elif vc == "both":
                vc_label = "\\n↑↓ up & down"
            entrance_label = "\\n[ENTRANCE]" if r.is_entrance else ""
            label = f"{r.name}{entrance_label}{vc_label}"
            dot.node(str(r.id), label=label, shape="box")

        # Edges: only show connections where both rooms are on this floor
        floor_ids = {r.id for r in floor_rooms}
        seen: set[tuple[str, str]] = set()
        for r in floor_rooms:
            edges = manager.get_connections(r.id, EdgeType.CONNECTS_TO)
            for e in edges:
                if e.source_id not in floor_ids or e.target_id not in floor_ids:
                    continue
                key = (str(e.source_id), str(e.target_id))
                if key in seen:
                    continue
                seen.add(key)
                ptype = e.properties.get("passage_type", "")
                length = e.properties.get("length", "")
                src = manager.get_room(e.source_id)
                tgt = manager.get_room(e.target_id)
                dir_part = ""
                if src and tgt and src.floor_level != tgt.floor_level:
                    if tgt.floor_level > src.floor_level:
                        dir_part = f"up to Floor {tgt.floor_level}"
                    else:
                        dir_part = f"down to Floor {tgt.floor_level}"
                label_parts = [p for p in [ptype, length, dir_part] if p]
                label = " / ".join(label_parts)
                dot.edge(str(e.source_id), str(e.target_id), label=label)

        st.graphviz_chart(dot)
