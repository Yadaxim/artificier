"""Campaign home: summary and entry to Create/Play."""

import streamlit as st

from ui.state import get_campaign, get_manager


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
    st.write(f"**Dungeons:** {len(dungeons)} · **Towns:** {len(towns)}")
