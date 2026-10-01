"""Campaign home: summary and entry to Create/Play."""

import streamlit as st

from ui.state import get_campaign, get_manager, set_view_kind


def render_campaign_home() -> None:
    campaign = get_campaign()
    if not campaign:
        st.info("Select or create a campaign in the sidebar.")
        return
    manager = get_manager()
    st.subheader(campaign.name)
    new_desc = st.text_area(
        "Campaign description",
        value=campaign.description or "",
        key=f"campaign_home_description_{campaign.id}",
        height=120,
        placeholder="Add campaign description",
    )
    if st.button("Save description", key="campaign_home_save_description"):
        if (new_desc or "") != (campaign.description or ""):
            campaign.description = (new_desc or "").strip()
            manager.update_campaign(campaign)
            st.success("Campaign description updated.")
            st.rerun()

    col_pl, col_save = st.columns([1, 1])
    with col_pl:
        new_pl = st.number_input(
            "Party level",
            min_value=1,
            max_value=20,
            value=int(campaign.party_level or 1),
            key="campaign_home_party_level",
        )
    with col_save:
        st.markdown("&nbsp;")
        if st.button("Save party level", key="campaign_home_save_pl"):
            if new_pl != campaign.party_level:
                campaign.party_level = int(new_pl)
                manager.update_campaign(campaign)
                st.success("Party level updated.")
                st.rerun()

    if campaign.setting_summary:
        st.caption(campaign.setting_summary)

    dungeons = manager.get_dungeons_in_campaign(campaign.id)
    towns = manager.get_towns_in_campaign(campaign.id)
    npcs = manager.get_npcs_in_campaign(campaign.id)
    monsters = manager.get_monsters_in_campaign(campaign.id)
    items = manager.get_items_in_campaign(campaign.id)
    plots = manager.get_plots_in_campaign(campaign.id)

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        if st.button(f"🏰 Dungeons\n{len(dungeons)}", key="campaign_home_dungeons", use_container_width=True):
            set_view_kind("dungeons")
            st.rerun()
    with col2:
        if st.button(f"🏘 Towns\n{len(towns)}", key="campaign_home_towns", use_container_width=True):
            set_view_kind("towns")
            st.rerun()
    with col3:
        if st.button(f"🧭 Plots\n{len(plots)}", key="campaign_home_plots", use_container_width=True):
            set_view_kind("plots")
            st.rerun()
    with col4:
        if st.button(f"👤 NPCs\n{len(npcs)}", key="campaign_home_npcs", use_container_width=True):
            set_view_kind("npcs")
            st.rerun()
    with col5:
        if st.button(f"👹 Monsters\n{len(monsters)}", key="campaign_home_monsters", use_container_width=True):
            set_view_kind("monsters")
            st.rerun()
    with col6:
        if st.button(f"⚔ Items\n{len(items)}", key="campaign_home_items", use_container_width=True):
            set_view_kind("items")
            st.rerun()
