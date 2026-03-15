"""Session state management for Streamlit app."""

from uuid import UUID

import streamlit as st

from core.state_manager import WorldStateManager
from models.models import Campaign


def get_manager() -> WorldStateManager:
    if "world_state_manager" not in st.session_state:
        st.session_state["world_state_manager"] = WorldStateManager()
    return st.session_state["world_state_manager"]


def get_campaign_id() -> UUID | None:
    return st.session_state.get("campaign_id")


def set_campaign_id(campaign_id: UUID | None) -> None:
    st.session_state["campaign_id"] = campaign_id
    manager = get_manager()
    if campaign_id:
        manager.load_campaign(campaign_id)


def get_campaign() -> Campaign | None:
    cid = get_campaign_id()
    if not cid:
        return None
    return get_manager().get_campaign(cid)


def get_mode() -> str:
    return st.session_state.get("mode", "Create")


def set_mode(mode: str) -> None:
    st.session_state["mode"] = mode


def get_selected_dungeon_id() -> UUID | None:
    return st.session_state.get("selected_dungeon_id")


def set_selected_dungeon_id(dungeon_id: UUID | None) -> None:
    st.session_state["selected_dungeon_id"] = dungeon_id


def get_selected_room_id() -> UUID | None:
    return st.session_state.get("selected_room_id")


def set_selected_room_id(room_id: UUID | None) -> None:
    st.session_state["selected_room_id"] = room_id


def get_selected_town_id() -> UUID | None:
    return st.session_state.get("selected_town_id")


def set_selected_town_id(town_id: UUID | None) -> None:
    st.session_state["selected_town_id"] = town_id


def get_selected_location_id() -> UUID | None:
    return st.session_state.get("selected_location_id")


def set_selected_location_id(location_id: UUID | None) -> None:
    st.session_state["selected_location_id"] = location_id


def get_selected_npc_id() -> UUID | None:
    return st.session_state.get("selected_npc_id")


def set_selected_npc_id(npc_id: UUID | None) -> None:
    st.session_state["selected_npc_id"] = npc_id


def get_selected_monster_id() -> UUID | None:
    return st.session_state.get("selected_monster_id")


def set_selected_monster_id(monster_id: UUID | None) -> None:
    st.session_state["selected_monster_id"] = monster_id


def get_selected_item_id() -> UUID | None:
    return st.session_state.get("selected_item_id")


def set_selected_item_id(item_id: UUID | None) -> None:
    st.session_state["selected_item_id"] = item_id


def get_view_kind() -> str:
    """One of: campaign_home, dungeons, dungeon_new, dungeon_single, room_single, towns, town_new, town_single, location_single, npcs, npc_single, monsters, monster_single, items, item_single."""
    return st.session_state.get("view_kind", "campaign_home")


def set_view_kind(kind: str) -> None:
    st.session_state["view_kind"] = kind
