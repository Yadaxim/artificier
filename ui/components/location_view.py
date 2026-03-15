"""Single location view."""

from uuid import UUID

import streamlit as st

from ui.state import get_manager, get_selected_location_id, set_view_kind


def render_location_single() -> None:
    location_id = get_selected_location_id()
    if not location_id:
        set_view_kind("town_single")
        st.rerun()
        return
    manager = get_manager()
    location = manager.get_location(location_id)
    if not location:
        st.error("Location not found.")
        return
    st.subheader(location.name)
    st.caption(f"{location.location_type}")
    st.write("**Description**")
    st.write(location.description or "(none)")
    st.write("**DM notes**")
    st.write(location.dm_notes or "(none)")
    if location.atmosphere:
        st.write("**Atmosphere**")
        st.write(location.atmosphere)
    if location.notable_features:
        st.write("**Notable features**")
        for f in location.notable_features:
            st.write(f"- {f}")
    if location.encounter_seeds:
        st.write("**Encounter seeds**")
        for s in location.encounter_seeds:
            st.write(f"- {s}")
    if st.button("Back to town"):
        set_view_kind("town_single")
        st.rerun()
