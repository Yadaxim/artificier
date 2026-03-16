"""Single room view: full content; Play mode with read_aloud prominent and Record Event."""

from datetime import datetime
from uuid import UUID

import streamlit as st

from core.generation import generate_room
from core.state_manager import WorldStateManager
from models.models import EdgeType

from ui.state import (
    get_manager,
    get_mode,
    get_selected_dungeon_id,
    get_selected_room_id,
    set_selected_room_id,
    set_view_kind,
)


def render_room_single() -> None:
    room_id = get_selected_room_id()
    if not room_id:
        set_view_kind("dungeon_single")
        st.rerun()
        return
    manager = get_manager()
    room = manager.get_room(room_id)
    if not room:
        st.error("Room not found.")
        return
    room_not_generated = not (room.description or room.read_aloud)
    play_mode = get_mode() == "Play"
    if play_mode:
        _render_room_play(manager, room)
    else:
        _render_room_create(manager, room)


def _render_room_play(manager: WorldStateManager, room) -> None:
    st.subheader(room.name)
    if room.is_entrance:
        st.caption("Entrance to the dungeon")
    if room.read_aloud:
        st.markdown(
            '<div class="artificier-read-aloud">' + room.read_aloud + "</div>",
            unsafe_allow_html=True,
        )
    if room.dm_notes:
        st.markdown(
            '<div class="artificier-dm-notes">' + room.dm_notes + "</div>",
            unsafe_allow_html=True,
        )
    with st.expander("Full description"):
        st.write(room.description)
    with st.expander("Features"):
        for f in room.features or []:
            st.write(f"- {f}")
    with st.expander("Encounters"):
        for seed in room.encounter_seeds or []:
            st.write(f"- {seed}")
        # TODO: list CONTAINS NPCs/Monsters in this room
    with st.expander("Items"):
        # TODO: list CONTAINS Items in this room
        st.write("(No items linked yet)")
    with st.expander("Passages"):
        _render_passages(manager, room.id)
    with st.expander("Room relationships"):
        _render_relationships(manager, room.id)
    event_text = st.text_input("Event note", key="room_event_note")
    if st.button("Record Event") and event_text:
        events = room.metadata.get("events") or []
        events.append({"at": datetime.utcnow().isoformat(), "text": event_text})
        room.metadata["events"] = events
        manager.update_room(room)
        st.success("Event recorded.")
        st.rerun()


def _render_generate_room_cta(manager: WorldStateManager, room) -> None:
    """Show generate button when room has no description/read_aloud yet."""
    dungeon_id = get_selected_dungeon_id()
    if not dungeon_id:
        edges = manager.get_edges_to(room.id, EdgeType.CONTAINS)
        if edges:
            dungeon_id = edges[0].source_id
    if dungeon_id:
        st.info("This room has not been fully generated yet. Generate description, read-aloud text, and DM notes.")
        if st.button("Generate room", key="room_single_generate"):
            with st.spinner("Generating room..."):
                try:
                    all_rooms = manager.get_rooms_in_dungeon(dungeon_id)
                    already_generated = [r.id for r in all_rooms if r.id != room.id and (r.description or r.read_aloud)]
                    generate_room(manager, dungeon_id, room.id, already_generated)
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    else:
        st.warning("Could not determine this room's dungeon. Open the room from the dungeon view and try again.")


def _render_room_create(manager: WorldStateManager, room) -> None:
    st.subheader(room.name)
    parts = [f"Floor {room.floor_level}", room.purpose]
    if room.is_entrance:
        parts.append("Entrance to the dungeon")
    st.caption(" · ".join(parts))
    # Generate panel when room has not been generated yet (blue panel, inline position)
    if not (room.description or room.read_aloud):
        _render_generate_room_cta(manager, room)
    st.write("**Description**")
    st.write(room.description or "(not generated yet)")
    st.write("**Read aloud**")
    st.write(room.read_aloud or "(not generated yet)")
    st.write("**DM notes**")
    st.write(room.dm_notes or "(none)")
    if room.features:
        st.write("**Features**")
        for f in room.features:
            st.write(f"- {f}")
    if room.encounter_seeds:
        st.write("**Encounter seeds**")
        for s in room.encounter_seeds:
            st.write(f"- {s}")
    st.write("**Passages**")
    _render_passages(manager, room.id)
    st.write("**Relationships**")
    _render_relationships(manager, room.id)
    if st.button("Back to dungeon"):
        set_view_kind("dungeon_single")
        st.rerun()


def _render_passages(manager: WorldStateManager, room_id: UUID) -> None:
    # Treat passages as undirected: show both outgoing and incoming connections
    out_edges = manager.get_connections(room_id, EdgeType.CONNECTS_TO)
    in_edges = manager.get_edges_to(room_id, EdgeType.CONNECTS_TO)
    # Deduplicate by unordered pair of room IDs
    edges = []
    seen_pairs: set[tuple[str, str]] = set()
    for e in list(out_edges) + list(in_edges):
        a = str(e.source_id)
        b = str(e.target_id)
        pair = tuple(sorted((a, b)))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        edges.append(e)
    if not edges:
        st.write("(No passages)")
        return
    for e in edges:
        # Determine the "other" room on this edge
        if e.source_id == room_id:
            other_id = e.target_id
        else:
            other_id = e.source_id
        target = manager.get_room(other_id)
        if not target:
            continue
        name = target.name
        ptype = e.properties.get("passage_type", "?")
        length = e.properties.get("length", "?")
        # Show vertical direction if this is a cross-floor connection
        this_room = manager.get_room(room_id)
        dir_part = ""
        if this_room and target and this_room.floor_level != target.floor_level:
            if target.floor_level > this_room.floor_level:
                dir_part = f"↑ to Floor {target.floor_level}"
            else:
                dir_part = f"↓ to Floor {target.floor_level}"
        suffix = f"{ptype} ({length})"
        if dir_part:
            suffix = f"{suffix}, {dir_part}"
        cols = st.columns([4, 1])
        with cols[0]:
            st.write(f"- **{name}**: {suffix}")
        with cols[1]:
            if st.button("Open", key=f"open_conn_{room_id}_{target.id}"):
                set_selected_room_id(target.id)
                set_view_kind("room_single")
                st.rerun()


def _render_relationships(manager: WorldStateManager, room_id: UUID) -> None:
    # Relationships are also shown from both sides so you can see them in each room
    out_edges = manager.get_connections(room_id, EdgeType.RELATED_TO)
    in_edges = manager.get_edges_to(room_id, EdgeType.RELATED_TO)
    # Deduplicate by unordered pair of room IDs
    edges = []
    seen_pairs: set[tuple[str, str]] = set()
    for e in list(out_edges) + list(in_edges):
        a = str(e.source_id)
        b = str(e.target_id)
        pair = tuple(sorted((a, b)))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        edges.append(e)
    if not edges:
        st.write("(No relationships)")
        return
    for e in edges:
        if e.source_id == room_id:
            other_id = e.target_id
        else:
            other_id = e.source_id
        target = manager.get_room(other_id)
        if not target:
            continue
        name = target.name
        rtype = e.properties.get("type", "related")
        desc = e.properties.get("description", "")
        cols = st.columns([4, 1])
        with cols[0]:
            if desc:
                st.write(f"- **{rtype} → {name}** — {desc}")
            else:
                st.write(f"- **{rtype} → {name}**")
        with cols[1]:
            if st.button("Open", key=f"open_rel_{room_id}_{target.id}"):
                set_selected_room_id(target.id)
                set_view_kind("room_single")
                st.rerun()
