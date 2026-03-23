"""List towns and show single town with locations."""

from uuid import UUID

import streamlit as st

from ui.state import (
    clear_pending_delete,
    get_manager,
    get_pending_delete,
    get_selected_location_id,
    get_selected_town_id,
    set_pending_delete,
    set_selected_location_id,
    set_selected_town_id,
    set_view_kind,
)


def render_towns_list() -> None:
    manager = get_manager()
    campaign_id = manager._loaded_campaign_id
    if not campaign_id:
        st.info("Select a campaign to see towns.")
        return
    towns = manager.get_towns_in_campaign(campaign_id)
    towns = sorted(towns, key=lambda t: t.created_at, reverse=True)
    pending = get_pending_delete()
    if not towns:
        st.info("No towns yet. Create one from the sidebar.")
        return
    for t in towns:
        row_col, action1_col, action2_col = st.columns([6, 1, 1])
        with row_col:
            st.markdown(f"### {t.name}")
            st.caption(f"{t.concept[:200]}..." if len(t.concept) > 200 else t.concept)
        if pending and pending.get("kind") == "town" and pending.get("id") == str(t.id):
            st.warning("Delete this town and all its locations?")
            with action1_col:
                if st.button("Cancel", key=f"cancel_del_town_{t.id}"):
                    clear_pending_delete()
                    st.rerun()
            with action2_col:
                if st.button("Yes, delete", key=f"confirm_del_town_{t.id}", type="primary"):
                    manager.delete_town(t.id)
                    if get_selected_town_id() == t.id:
                        set_selected_town_id(None)
                    clear_pending_delete()
                    st.rerun()
        else:
            with action1_col:
                if st.button("View", key=f"view_town_{t.id}"):
                    set_selected_town_id(t.id)
                    set_view_kind("town_single")
                    st.rerun()
            with action2_col:
                if st.button("Delete", key=f"del_town_{t.id}"):
                    set_pending_delete("town", t.id, t.name, "all its locations")
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
    pending = get_pending_delete()
    for loc in locations:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"- **{loc.name}** ({loc.location_type})")
        with col2:
            if pending and pending.get("kind") == "location" and pending.get("id") == str(loc.id):
                st.caption("Delete?")
                if st.button("Cancel", key=f"cancel_del_loc_{loc.id}"):
                    clear_pending_delete()
                    st.rerun()
                if st.button("Yes", key=f"confirm_del_loc_{loc.id}", type="primary"):
                    manager.delete_location(loc.id)
                    if get_selected_location_id() == loc.id:
                        set_selected_location_id(None)
                    clear_pending_delete()
                    st.rerun()
            else:
                if st.button("Open", key=f"open_loc_{loc.id}"):
                    set_selected_location_id(loc.id)
                    set_view_kind("location_single")
                    st.rerun()
                if st.button("Delete", key=f"del_loc_{loc.id}"):
                    set_pending_delete("location", loc.id, loc.name, "")
                    st.rerun()
    if st.button("Back to towns"):
        set_selected_town_id(None)
        set_view_kind("towns")
        st.rerun()
