"""Dungeon creation flow: interpret → create dungeon → jump to dungeon view."""

import traceback
from uuid import UUID

import streamlit as st

from core.generation import interpret_dungeon
from core.state_manager import WorldStateManager
from models.models import Campaign, Dungeon, Edge, EdgeType

from ui.state import get_campaign_id, get_manager, set_selected_dungeon_id, set_view_kind


def render_dungeon_form() -> None:
    manager = get_manager()
    campaign_id = get_campaign_id()
    if not campaign_id:
        st.warning("Select or create a campaign first.")
        return

    _step_interpret(manager, campaign_id)


def _step_interpret(manager: WorldStateManager, campaign_id) -> None:
    st.subheader("Describe your dungeon")
    st.caption("After you click Interpret, the dungeon will be created and you will be taken directly to its view.")
    description = st.text_area("Free-text description", height=120, key="dungeon_description")
    party_level = st.number_input("Party level", min_value=1, max_value=20, value=5, key="dungeon_party_level")
    if st.button("Interpret with Claude"):
        with st.spinner("Interpreting... (this may take 10–30 seconds)"):
            try:
                result, raw_response, debug = interpret_dungeon(description, party_level)
                name = result.get("name", "").strip() or "Unnamed Dungeon"
                concept = result.get("concept", "")
                tone = result.get("tone", "")
                level_range = result.get("level_range", "")
                world_context = result.get("world_context", "")
                history = result.get("history") or {}
                floors = result.get("floors") or []

                campaign = manager.get_campaign(campaign_id)
                if not campaign:
                    st.error("Campaign not found.")
                    return
                dungeon = Dungeon(
                    name=name,
                    concept=concept,
                    tone=tone,
                    history=history,
                    world_context=world_context,
                    level_range=level_range,
                )
                dungeon.metadata["floors"] = floors
                manager.create_dungeon(dungeon)
                manager.add_edge(Edge(source_id=campaign_id, target_id=dungeon.id, edge_type=EdgeType.CONTAINS))
                set_selected_dungeon_id(dungeon.id)
                set_view_kind("dungeon_single")
                st.success("Dungeon created.")
                st.rerun()
            except Exception as e:
                st.error("Interpret failed — see details below.")
                st.exception(e)
                st.code(traceback.format_exc(), language="text")
