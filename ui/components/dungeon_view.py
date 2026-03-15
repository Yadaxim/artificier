"""List dungeons and show single dungeon with rooms grouped by floor."""

from uuid import UUID

import streamlit as st

from core.generation import generate_room, seed_rooms
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
        with st.container():
            st.markdown(f"### {d.name}")
            st.caption(f"{d.concept[:200]}..." if len(d.concept) > 200 else d.concept)
            col1, col2 = st.columns([1, 3])
            with col1:
                if pending and pending.get("kind") == "dungeon" and pending.get("id") == str(d.id):
                    st.warning("Delete this dungeon and all its rooms?")
                    if st.button("Cancel", key=f"cancel_del_dungeon_{d.id}"):
                        clear_pending_delete()
                        st.rerun()
                    if st.button("Yes, delete", key=f"confirm_del_dungeon_{d.id}", type="primary"):
                        manager.delete_dungeon(d.id)
                        if get_selected_dungeon_id() == d.id:
                            set_selected_dungeon_id(None)
                        clear_pending_delete()
                        st.rerun()
                else:
                    if st.button("View", key=f"view_dungeon_{d.id}"):
                        set_selected_dungeon_id(d.id)
                        set_view_kind("dungeon_single")
                        st.rerun()
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
        campaign_id = get_campaign_id()
        for idx, f in enumerate(planned_floors):
            lvl = f.get("level_number", 0)
            name = f.get("name", "Floor")
            theme = f.get("theme", "")
            count = f.get("room_count", 0)
            room_count = len(by_floor.get(lvl, []))
            col_label, col_btn = st.columns([4, 1])
            with col_label:
                if room_count > 0:
                    st.caption(f"- Level {lvl}: {name} — {theme} ({room_count}/{count} rooms seeded)")
                else:
                    st.caption(f"- Level {lvl}: {name} — {theme} ({count} rooms, not yet seeded)")
            with col_btn:
                if room_count == 0 and campaign_id:
                    if st.button("Seed", key=f"seed_floor_{dungeon_id}_{idx}"):
                        with st.spinner(f"Seeding {name}..."):
                            try:
                                seed_rooms(manager, campaign_id, dungeon_id, f)
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))
        st.divider()
    if not rooms:
        st.info("No rooms yet. Generate room seeds to create a floor plan.")
        if st.button("Generate room seeds", key="dungeon_single_seed_rooms"):
            st.session_state["dungeon_form_step"] = 2
            st.session_state["dungeon_id_created"] = str(dungeon_id)
            set_view_kind("dungeon_new")
            st.rerun()
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
                st.write(f"- **{r.name}**: {r.purpose} — *{status}*")
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
