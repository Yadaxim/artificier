"""List dungeons and show single dungeon with rooms grouped by floor."""

from uuid import UUID

import streamlit as st

from ui.state import (
    get_manager,
    get_selected_dungeon_id,
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
    if not dungeons:
        st.info("No dungeons yet. Create one from the sidebar.")
        return
    for d in dungeons:
        with st.container():
            st.markdown(f"### {d.name}")
            st.caption(f"{d.concept[:200]}..." if len(d.concept) > 200 else d.concept)
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("View", key=f"view_dungeon_{d.id}"):
                    set_selected_dungeon_id(d.id)
                    set_view_kind("dungeon_single")
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
    by_floor: dict[int, list] = {}
    for r in rooms:
        by_floor.setdefault(r.floor_level, []).append(r)
    for level in sorted(by_floor.keys()):
        st.markdown(f"**Floor {level}**")
        for r in by_floor[level]:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"- {r.name}: {r.purpose}")
            with col2:
                if st.button("Open", key=f"open_room_{r.id}"):
                    set_selected_room_id(r.id)
                    set_view_kind("room_single")
                    st.rerun()
        st.divider()
    if st.button("Back to dungeons"):
        set_selected_dungeon_id(None)
        set_view_kind("dungeons")
        st.rerun()
