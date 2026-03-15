"""Single room view: full content; Play mode with read_aloud prominent and Record Event."""

from datetime import datetime
from uuid import UUID

import streamlit as st

from core.state_manager import WorldStateManager
from models.models import EdgeType

from ui.state import get_manager, get_mode, get_selected_dungeon_id, get_selected_room_id, set_view_kind


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
    play_mode = get_mode() == "Play"
    if play_mode:
        _render_room_play(manager, room)
    else:
        _render_room_create(manager, room)


def _render_room_play(manager: WorldStateManager, room) -> None:
    st.subheader(room.name)
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
    event_text = st.text_input("Event note", key="room_event_note")
    if st.button("Record Event") and event_text:
        events = room.metadata.get("events") or []
        events.append({"at": datetime.utcnow().isoformat(), "text": event_text})
        room.metadata["events"] = events
        manager.update_room(room)
        st.success("Event recorded.")
        st.rerun()


def _render_room_create(manager: WorldStateManager, room) -> None:
    st.subheader(room.name)
    st.caption(f"Floor {room.floor_level} · {room.purpose}")
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
    if st.button("Back to dungeon"):
        set_view_kind("dungeon_single")
        st.rerun()


def _render_passages(manager: WorldStateManager, room_id: UUID) -> None:
    edges = manager.get_connections(room_id, EdgeType.CONNECTS_TO)
    if not edges:
        st.write("(No passages)")
        return
    for e in edges:
        target = manager.get_room(e.target_id)
        name = target.name if target else str(e.target_id)
        ptype = e.properties.get("passage_type", "?")
        length = e.properties.get("length", "?")
        st.write(f"- **{name}**: {ptype} ({length})")
