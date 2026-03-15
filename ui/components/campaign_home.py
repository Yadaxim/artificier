"""Campaign home: summary and entry to Create/Play."""

import streamlit as st

from ui.state import get_campaign, get_manager, set_view_kind


def render_campaign_home() -> None:
    campaign = get_campaign()
    if not campaign:
        st.info("Select or create a campaign in the sidebar.")
        return
    st.subheader(campaign.name)
    st.write(campaign.description or "(No description)")
    st.caption(f"Party level: {campaign.party_level} · {campaign.setting_summary or ''}")
    manager = get_manager()
    dungeons = manager.get_dungeons_in_campaign(campaign.id)
    towns = manager.get_towns_in_campaign(campaign.id)
    npcs = manager.get_npcs_in_campaign(campaign.id)
    monsters = manager.get_monsters_in_campaign(campaign.id)
    items = manager.get_items_in_campaign(campaign.id)

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button(f"🏰 Dungeons\n{len(dungeons)}", key="campaign_home_dungeons", use_container_width=True):
            set_view_kind("dungeons")
            st.rerun()
    with col2:
        if st.button(f"🏘 Towns\n{len(towns)}", key="campaign_home_towns", use_container_width=True):
            set_view_kind("towns")
            st.rerun()
    with col3:
        if st.button(f"👤 NPCs\n{len(npcs)}", key="campaign_home_npcs", use_container_width=True):
            set_view_kind("npcs")
            st.rerun()
    with col4:
        if st.button(f"👹 Monsters\n{len(monsters)}", key="campaign_home_monsters", use_container_width=True):
            set_view_kind("monsters")
            st.rerun()
    with col5:
        if st.button(f"⚔ Items\n{len(items)}", key="campaign_home_items", use_container_width=True):
            set_view_kind("items")
            st.rerun()
