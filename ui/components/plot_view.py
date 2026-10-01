"""Single plot view with create/play behavior."""

import streamlit as st

from models.models import EdgeType, PlotBeatStatus
from ui.state import (
    get_manager,
    get_mode,
    get_selected_plot_id,
    set_selected_dungeon_id,
    set_selected_item_id,
    set_selected_location_id,
    set_selected_monster_id,
    set_selected_npc_id,
    set_selected_plot_id,
    set_selected_town_id,
    set_view_kind,
)


def render_plot_single() -> None:
    plot_id = get_selected_plot_id()
    if not plot_id:
        set_view_kind("plots")
        st.rerun()
        return
    manager = get_manager()
    plot = manager.get_plot(plot_id)
    if not plot:
        st.error("Plot not found.")
        return

    created_notes = st.session_state.pop("plot_last_created_entity_notes", None)
    if created_notes:
        with st.expander("Required entities — creation log", expanded=False):
            for line in created_notes:
                st.caption(line)

    mode = get_mode()
    st.subheader(plot.title)
    st.caption(f"{plot.plot_type.value} · {plot.status.value} · {plot.party_level_range}")
    st.write(plot.premise)

    with st.expander("🔒 The Truth", expanded=False):
        st.write(plot.secret or "(none)")

    clues = manager.get_clues_in_plot(plot.id)
    clues_by_beat = {}
    for clue in clues:
        clues_by_beat.setdefault(clue.beat_title or "Unassigned", []).append(clue)

    if mode == "Play":
        _render_play_mode(manager, plot, clues_by_beat)
    else:
        _render_create_mode(manager, plot, clues_by_beat)

    with st.expander("Resolution variants", expanded=False):
        for variant in plot.resolution_variants or []:
            st.write(f"- {variant}")
        if not plot.resolution_variants:
            st.write("(none)")

    with st.expander("World consequences", expanded=False):
        for c in plot.world_consequences or []:
            st.write(f"- {c}")
        if not plot.world_consequences:
            st.write("(none)")

    if st.button("Back to plots"):
        set_selected_plot_id(None)
        set_view_kind("plots")
        st.rerun()


def _render_create_mode(manager, plot, clues_by_beat: dict) -> None:
    st.write("**Beat tracker**")
    for i, beat in enumerate(plot.beats):
        st.markdown(f"### {beat.title}")
        st.caption(f"{beat.beat_type.value} · {beat.status.value}")
        st.write(beat.description or "(no description)")
        if beat.dm_notes:
            st.caption(beat.dm_notes)
        for clue in clues_by_beat.get(beat.title, []):
            _render_clue_row(manager, clue, key_prefix=f"create_{i}")

    st.write("**Involved entities**")
    inv_edges = manager.get_edges_from(plot.id, EdgeType.INVOLVES)
    if not inv_edges:
        st.caption("(none)")
    for edge in inv_edges:
        role = edge.properties.get("role", "")
        label, handler = _entity_link_handler(manager, edge.target_id)
        cols = st.columns([5, 1])
        with cols[0]:
            st.write(f"- {label}" + (f" — {role}" if role else ""))
        with cols[1]:
            if handler and st.button("Open", key=f"open_inv_entity_{plot.id}_{edge.id}"):
                handler()
                st.rerun()


def _render_play_mode(manager, plot, clues_by_beat: dict) -> None:
    active_idx = next((i for i, b in enumerate(plot.beats) if b.status != PlotBeatStatus.COMPLETE), 0)
    for i, beat in enumerate(plot.beats):
        expanded = i == active_idx
        with st.expander(f"{beat.title} ({beat.status.value})", expanded=expanded):
            st.write(beat.description or "(no description)")
            if beat.dm_notes and st.checkbox("Reveal DM notes", key=f"reveal_dm_notes_{plot.id}_{i}"):
                st.caption(beat.dm_notes)
            if beat.status != PlotBeatStatus.COMPLETE:
                if st.button("Mark beat complete", key=f"complete_beat_{plot.id}_{i}"):
                    beat.status = PlotBeatStatus.COMPLETE
                    manager.update_plot(plot)
                    st.rerun()
            for clue in clues_by_beat.get(beat.title, []):
                _render_clue_row(manager, clue, key_prefix=f"play_{i}", hide_undiscovered=True)


def _render_clue_row(manager, clue, key_prefix: str, hide_undiscovered: bool = False) -> None:
    col1, col2 = st.columns([5, 1])
    with col1:
        if hide_undiscovered and not clue.is_discovered:
            st.write("- ?")
        else:
            st.write(f"- {clue.content}")
            st.caption(clue.how_found)
    with col2:
        discovered = st.checkbox("Found", value=bool(clue.is_discovered), key=f"{key_prefix}_clue_{clue.id}")
        if discovered != clue.is_discovered:
            clue.is_discovered = discovered
            manager.update_clue(clue)
            st.rerun()


def _entity_link_handler(manager, entity_id):
    npc = manager.get_npc(entity_id)
    if npc:
        return npc.name, lambda: (set_selected_npc_id(npc.id), set_view_kind("npc_single"))
    item = manager.get_item(entity_id)
    if item:
        return item.name, lambda: (set_selected_item_id(item.id), set_view_kind("item_single"))
    location = manager.get_location(entity_id)
    if location:
        return location.name, lambda: (set_selected_location_id(location.id), set_view_kind("location_single"))
    town = manager.get_town(entity_id)
    if town:
        return town.name, lambda: (set_selected_town_id(town.id), set_view_kind("town_single"))
    dungeon = manager.get_dungeon(entity_id)
    if dungeon:
        return dungeon.name, lambda: (set_selected_dungeon_id(dungeon.id), set_view_kind("dungeon_single"))
    monster = manager.get_monster(entity_id)
    if monster:
        return monster.name, lambda: (set_selected_monster_id(monster.id), set_view_kind("monster_single"))
    return str(entity_id), None
