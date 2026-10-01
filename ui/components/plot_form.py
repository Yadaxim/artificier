"""Plot creation flow: interpret -> review -> generate."""

import traceback

import streamlit as st

from core.generation import (
    fulfill_plot_required_entities,
    generate_clues,
    generate_plot,
    interpret_plot,
    wire_plot_entities,
)
from models.models import Edge, EdgeType, Plot, PlotBeat, PlotBeatStatus, PlotBeatType, PlotType
from ui.state import get_campaign, get_campaign_id, get_manager, set_selected_plot_id, set_view_kind


def render_plot_form() -> None:
    campaign_id = get_campaign_id()
    if not campaign_id:
        st.warning("Select a campaign first.")
        return
    manager = get_manager()

    st.subheader("Create Plot")
    text = st.text_area("Plot description", height=140, key="plot_desc")
    campaign = get_campaign()
    default_level = int(campaign.party_level) if campaign and campaign.party_level else 1
    party_level = st.number_input("Party level", min_value=1, max_value=20, value=default_level, key="plot_party_level")

    if st.button("✨ Interpret", key="plot_interpret"):
        with st.spinner("Interpreting plot..."):
            try:
                plot_seed = interpret_plot(text, int(party_level), campaign_id, manager=manager)
                st.session_state["pending_plot"] = plot_seed.model_dump(mode="json")
                st.rerun()
            except Exception as e:
                st.error("Plot interpretation failed.")
                st.exception(e)
                st.code(traceback.format_exc(), language="text")

    pending = st.session_state.get("pending_plot")
    if not pending:
        return

    st.success("Interpretation complete. Review and edit before generation.")
    _render_plot_seed_editor(pending)

    if st.button("Accept & Generate", key="plot_accept_generate", type="primary"):
        created_msgs: list[str] = []
        with st.spinner("Generating plot and clues..."):
            try:
                plot = _build_plot_from_editor()
                manager.create_plot(plot)
                manager.add_edge(Edge(source_id=campaign_id, target_id=plot.id, edge_type=EdgeType.CONTAINS))
                if st.session_state.get("plot_create_required_entities", True):
                    created_msgs = fulfill_plot_required_entities(manager, campaign_id, plot.id)
                plot = generate_plot(plot.id)
                generate_clues(plot.id)
                wire_plot_entities(plot.id)
                st.session_state.pop("pending_plot", None)
                set_selected_plot_id(plot.id)
                set_view_kind("plot_single")
                st.session_state["plot_last_created_entity_notes"] = created_msgs
                st.success("Plot generated.")
                st.rerun()
            except Exception as e:
                st.error("Failed to generate plot.")
                st.exception(e)
                st.code(traceback.format_exc(), language="text")


def _plot_seed_metadata(seed: dict) -> dict:
    md = seed.get("metadata")
    return md if isinstance(md, dict) else {}


def _plot_seed_suggested_links(seed: dict) -> list:
    md = _plot_seed_metadata(seed)
    links = md.get("suggested_links")
    if isinstance(links, list) and links:
        return links
    top = seed.get("suggested_links")
    return list(top) if isinstance(top, list) else []


def _plot_seed_required_entities(seed: dict) -> list:
    md = _plot_seed_metadata(seed)
    req = md.get("required_entities")
    if isinstance(req, list) and req:
        return req
    top = seed.get("required_entities")
    return list(top) if isinstance(top, list) else []


def _render_plot_seed_editor(seed: dict) -> None:
    st.text_input("Title", value=seed.get("title", ""), key="plot_seed_title")
    st.text_area("Premise", value=seed.get("premise", ""), key="plot_seed_premise", height=80)
    st.text_input("Tone", value=seed.get("tone", ""), key="plot_seed_tone")
    all_types = [p.value for p in PlotType]
    current = str(seed.get("plot_type", PlotType.OTHER.value))
    idx = all_types.index(current) if current in all_types else all_types.index(PlotType.OTHER.value)
    st.selectbox("Plot type", options=all_types, index=idx, key="plot_seed_plot_type")
    st.text_input("Party level range", value=seed.get("party_level_range", ""), key="plot_seed_pl_range")
    st.text_area("Summary", value=seed.get("summary", ""), key="plot_seed_summary", height=100)
    st.text_area("Secret", value=seed.get("secret", ""), key="plot_seed_secret", height=100)

    beats = seed.get("beats") or []
    st.write("**Beats**")
    for i, beat in enumerate(beats):
        with st.expander(f"Beat {i + 1}: {beat.get('title', 'Untitled')}"):
            st.text_input("Title", value=beat.get("title", ""), key=f"plot_beat_title_{i}")
            st.text_area("Description", value=beat.get("description", ""), key=f"plot_beat_desc_{i}", height=100)
            st.text_input("Trigger", value=beat.get("trigger", ""), key=f"plot_beat_trigger_{i}")
            st.text_area("DM notes", value=beat.get("dm_notes", ""), key=f"plot_beat_notes_{i}", height=80)
            beat_types = [b.value for b in PlotBeatType]
            bt_val = str(beat.get("beat_type", PlotBeatType.HOOK.value))
            bt_idx = beat_types.index(bt_val) if bt_val in beat_types else 0
            st.selectbox("Beat type", options=beat_types, index=bt_idx, key=f"plot_beat_type_{i}")

    required = _plot_seed_required_entities(seed)
    st.write("**Required entities** (new things the plot needs — not in the campaign yet)")
    st.caption(
        "NPC, Monster, Item, and **Location** can be auto-created on generate. "
        "For a new location, set **town_name** (or parent_town) on the requirement if the campaign has more than one town. "
        "Dungeon and Town still must be added from the campaign tools."
    )
    if required:
        for req in required:
            st.info(f"{req.get('entity_type', 'Entity')}: {req.get('description', '')}")
    else:
        st.caption("(none)")

    st.checkbox(
        "Create required NPCs, Monsters, Items, and Locations when I accept (uses Claude per entity / location)",
        value=True,
        key="plot_create_required_entities",
    )

    links = _plot_seed_suggested_links(seed)
    st.write("**Suggested connections** (link this plot to existing campaign entities)")
    if links:
        for i, link in enumerate(links):
            label = f"{link.get('entity_type', '')} · {link.get('entity_name', '')} → {link.get('role', '')}"
            st.checkbox(label, value=True, key=f"plot_link_accept_{i}")
    else:
        st.caption("(none — no ties to existing entities were proposed)")


def _build_plot_from_editor() -> Plot:
    seed = st.session_state.get("pending_plot") or {}
    beats_data = seed.get("beats") or []
    beats: list[PlotBeat] = []
    for i, _ in enumerate(beats_data):
        bt = st.session_state.get(f"plot_beat_type_{i}", PlotBeatType.HOOK.value)
        try:
            beat_type = PlotBeatType(bt)
        except ValueError:
            beat_type = PlotBeatType.HOOK
        beats.append(
            PlotBeat(
                title=st.session_state.get(f"plot_beat_title_{i}", ""),
                description=st.session_state.get(f"plot_beat_desc_{i}", ""),
                trigger=st.session_state.get(f"plot_beat_trigger_{i}", ""),
                dm_notes=st.session_state.get(f"plot_beat_notes_{i}", ""),
                beat_type=beat_type,
                status=PlotBeatStatus.PENDING,
            )
        )

    selected_links = []
    all_links = _plot_seed_suggested_links(seed)
    for i, link in enumerate(all_links):
        if st.session_state.get(f"plot_link_accept_{i}", True):
            selected_links.append(link)

    plot_type_val = st.session_state.get("plot_seed_plot_type", PlotType.OTHER.value)
    try:
        plot_type = PlotType(plot_type_val)
    except ValueError:
        plot_type = PlotType.OTHER

    plot = Plot(
        title=st.session_state.get("plot_seed_title", ""),
        premise=st.session_state.get("plot_seed_premise", ""),
        tone=st.session_state.get("plot_seed_tone", ""),
        plot_type=plot_type,
        party_level_range=st.session_state.get("plot_seed_pl_range", ""),
        summary=st.session_state.get("plot_seed_summary", ""),
        secret=st.session_state.get("plot_seed_secret", ""),
        beats=beats,
        resolution_variants=seed.get("resolution_variants") or [],
        world_consequences=seed.get("world_consequences") or [],
    )
    plot.metadata["required_entities"] = _plot_seed_required_entities(seed)
    plot.metadata["suggested_links"] = selected_links
    return plot
