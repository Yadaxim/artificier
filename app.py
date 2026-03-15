"""Streamlit entry point for Artificier."""

import streamlit as st
from uuid import UUID

from ui.components.campaign_home import render_campaign_home
from ui.components.dungeon_form import render_dungeon_form
from ui.components.dungeon_view import render_dungeons_list, render_dungeon_single
from ui.components.location_view import render_location_single
from ui.components.monster_view import render_monster_form, render_monsters_list, render_monster_single
from ui.components.npc_view import render_npc_form, render_npcs_list, render_npc_single
from ui.components.item_view import render_item_form, render_items_list, render_item_single
from ui.components.room_view import render_room_single
from ui.components.town_form import render_town_form
from ui.components.town_view import render_towns_list, render_town_single
from ui.state import (
    get_campaign_id,
    get_manager,
    get_mode,
    get_view_kind,
    set_campaign_id,
    set_mode,
    set_view_kind,
)
from ui.styles import inject_styles

inject_styles()

st.title("Artificier")

# Sidebar: campaign selector, mode, tree
with st.sidebar:
    st.subheader("Campaign")
    manager = get_manager()
    existing_ids = manager.list_campaign_ids()
    # Load each campaign to get its name for the dropdown
    names = []
    for cid in existing_ids:
        manager.load_campaign(cid)
        c = manager.get_campaign(cid)
        names.append(c.name if c else "(Unnamed)")
    options = ["(New campaign)"] + names
    current = get_campaign_id()
    idx = 0
    if current and current in existing_ids:
        idx = existing_ids.index(current) + 1
    choice = st.selectbox(
        "Select campaign",
        options=options,
        index=idx,
        key="sidebar_campaign",
    )
    if choice == "(New campaign)":
        new_name = st.text_input("Campaign name", key="new_campaign_name", placeholder="Enter name")
        new_pl = st.number_input("Party level", min_value=1, max_value=20, value=5, key="new_campaign_pl")
        if st.button("Create campaign") and new_name and new_name.strip():
            from models.models import Campaign
            c = Campaign(name=new_name.strip(), party_level=int(new_pl))
            manager.ensure_loaded(c.id)
            manager.create_campaign(c)
            set_campaign_id(c.id)
            st.rerun()
    else:
        choice_idx = options.index(choice)
        if choice_idx > 0:
            cid = existing_ids[choice_idx - 1]
            if get_campaign_id() != cid:
                set_campaign_id(cid)
    if get_campaign_id():
        manager.load_campaign(get_campaign_id())

    st.divider()
    mode = st.radio("Mode", ["Create", "Play"], key="sidebar_mode", horizontal=True)
    set_mode(mode)

    st.divider()
    st.subheader("Navigate")
    if get_campaign_id():
        if st.button("Campaign home"):
            set_view_kind("campaign_home")
            st.rerun()
        if st.button("Dungeons"):
            set_view_kind("dungeons")
            st.rerun()
        if st.button("New dungeon"):
            set_view_kind("dungeon_new")
            st.session_state.pop("dungeon_form_step", None)
            st.session_state.pop("dungeon_interpret_result", None)
            st.session_state.pop("dungeon_id_created", None)
            st.rerun()
        if st.button("Towns"):
            set_view_kind("towns")
            st.rerun()
        if st.button("New town"):
            set_view_kind("town_new")
            st.session_state.pop("town_form_step", None)
            st.session_state.pop("town_interpret_result", None)
            st.session_state.pop("town_id_created", None)
            st.rerun()
        if st.button("NPCs"):
            set_view_kind("npcs")
            st.rerun()
        if st.button("New NPC"):
            set_view_kind("npc_new")
            st.session_state.pop("npc_interpret_result", None)
            st.rerun()
        if st.button("Monsters"):
            set_view_kind("monsters")
            st.rerun()
        if st.button("New Monster"):
            set_view_kind("monster_new")
            st.session_state.pop("monster_interpret_result", None)
            st.rerun()
        if st.button("Items"):
            set_view_kind("items")
            st.rerun()
        if st.button("New Item"):
            set_view_kind("item_new")
            st.session_state.pop("item_interpret_result", None)
            st.rerun()

# Main panel
view = get_view_kind()
if view == "campaign_home":
    render_campaign_home()
elif view == "dungeons":
    render_dungeons_list()
elif view == "dungeon_new":
    render_dungeon_form()
elif view == "dungeon_single":
    render_dungeon_single()
elif view == "room_single":
    render_room_single()
elif view == "towns":
    render_towns_list()
elif view == "town_new":
    render_town_form()
elif view == "town_single":
    render_town_single()
elif view == "location_single":
    render_location_single()
elif view == "npcs":
    render_npcs_list()
elif view == "npc_new":
    render_npc_form()
elif view == "npc_single":
    render_npc_single()
elif view == "monsters":
    render_monsters_list()
elif view == "monster_new":
    render_monster_form()
elif view == "monster_single":
    render_monster_single()
elif view == "items":
    render_items_list()
elif view == "item_new":
    render_item_form()
elif view == "item_single":
    render_item_single()
else:
    render_campaign_home()
