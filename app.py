"""Streamlit entry point for Artificier."""

import streamlit as st

from ui.components.campaign_list import render_campaigns_list
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
    get_campaign,
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

campaign = get_campaign()
title_suffix = f" · {campaign.name}" if campaign else ""
st.title("Artificier" + title_suffix)
if get_view_kind() == "room_single":
    st.divider()

# Sidebar: mode, navigation
with st.sidebar:
    manager = get_manager()
    if get_campaign_id():
        manager.load_campaign(get_campaign_id())

    st.divider()
    mode = st.radio("Mode", ["Create", "Play"], key="sidebar_mode", horizontal=True)
    set_mode(mode)

    st.divider()
    st.subheader("Navigate")
    if st.button("Campaigns"):
        set_view_kind("campaigns")
        st.rerun()
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
if view == "campaigns":
    render_campaigns_list()
elif view == "campaign_home":
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
    render_campaigns_list()
