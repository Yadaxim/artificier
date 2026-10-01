"""Plot list view."""

import streamlit as st

from models.models import PlotStatus
from ui.state import (
    clear_pending_delete,
    get_campaign_id,
    get_manager,
    get_pending_delete,
    get_selected_plot_id,
    set_pending_delete,
    set_selected_plot_id,
    set_view_kind,
)


def render_plots_list() -> None:
    campaign_id = get_campaign_id()
    if not campaign_id:
        st.info("Select a campaign.")
        return
    manager = get_manager()
    title_col, action_col = st.columns([6, 1])
    with title_col:
        st.subheader("Plots")
    with action_col:
        if st.button("✨ New Plot", key="plots_list_new", use_container_width=True):
            st.session_state.pop("pending_plot", None)
            set_view_kind("plot_new")
            st.rerun()

    plots = manager.get_plots_in_campaign(campaign_id)
    plots = sorted(plots, key=lambda p: p.created_at, reverse=True)
    statuses = [s.value for s in PlotStatus]
    selected_statuses = st.multiselect("Filter status", options=statuses, default=statuses, key="plot_status_filter")
    filtered = [p for p in plots if p.status.value in selected_statuses]
    pending = get_pending_delete()

    if not filtered:
        st.info("No plots found for the selected filter.")
        return

    for plot in filtered:
        col1, col2, col3 = st.columns([6, 1, 1])
        with col1:
            st.markdown(f"### {plot.title}")
            st.caption(f"{plot.plot_type.value} · {plot.status.value}")
            st.write(plot.premise[:260] + ("..." if len(plot.premise) > 260 else ""))
        if pending and pending.get("kind") == "plot" and pending.get("id") == str(plot.id):
            st.warning("Delete this plot and all its clues?")
            with col2:
                if st.button("Cancel", key=f"cancel_del_plot_{plot.id}", use_container_width=True):
                    clear_pending_delete()
                    st.rerun()
            with col3:
                if st.button("Yes, delete", key=f"confirm_del_plot_{plot.id}", type="primary", use_container_width=True):
                    manager.delete_plot(plot.id)
                    if get_selected_plot_id() == plot.id:
                        set_selected_plot_id(None)
                    clear_pending_delete()
                    st.rerun()
        else:
            with col2:
                if st.button("Open", key=f"open_plot_{plot.id}", use_container_width=True):
                    set_selected_plot_id(plot.id)
                    set_view_kind("plot_single")
                    st.rerun()
            with col3:
                if st.button("Delete", key=f"del_plot_{plot.id}", use_container_width=True):
                    set_pending_delete("plot", plot.id, plot.title, "all its clues")
                    st.rerun()
        st.divider()
