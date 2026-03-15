"""List towns and show single town with locations."""

from uuid import UUID

import streamlit as st

from ui.state import get_manager, get_selected_town_id, set_selected_location_id, set_selected_town_id, set_view_kind


def render_towns_list() -> None:
    manager = get_manager()
    campaign_id = manager._loaded_campaign_id
    if not campaign_id:
        st.info("Select a campaign to see towns.")
        return
    towns = manager.get_towns_in_campaign(campaign_id)
    if not towns:
        st.info("No towns yet. Create one from the sidebar.")
        return
    for t in towns:
        st.markdown(f"### {t.name}")
        st.caption(f"{t.concept[:200]}..." if len(t.concept) > 200 else t.concept)
        if st.button("View", key=f"view_town_{t.id}"):
            set_selected_town_id(t.id)
            set_view_kind("town_single")
            st.rerun()
        st.divider()


def render_town_single() -> None:
    town_id = get_selected_town_id()
    if not town_id:
        set_view_kind("towns")
        st.rerun()
        return
    manager = get_manager()
    town = manager.get_town(town_id)
    if not town:
        st.error("Town not found.")
        return
    st.subheader(town.name)
    st.write(town.concept)
    st.caption(f"Population: {town.population_size.value} · {town.tone}")
    locations = manager.get_locations_in_town(town_id)
    for loc in locations:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"- **{loc.name}** ({loc.location_type})")
        with col2:
            if st.button("Open", key=f"open_loc_{loc.id}"):
                set_selected_location_id(loc.id)
                set_view_kind("location_single")
                st.rerun()
    if st.button("Back to towns"):
        set_selected_town_id(None)
        set_view_kind("towns")
        st.rerun()
