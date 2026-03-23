"""Item list and single view; create flow."""

import traceback
from uuid import UUID

import streamlit as st

from core.generation import generate_item_from_seed, interpret_item
from ui.state import (
    clear_pending_delete,
    get_campaign_id,
    get_manager,
    get_pending_delete,
    get_selected_item_id,
    set_pending_delete,
    set_selected_item_id,
    set_view_kind,
)


def render_items_list() -> None:
    manager = get_manager()
    campaign_id = get_campaign_id()
    if not campaign_id:
        st.info("Select a campaign.")
        return
    title_col, action_col = st.columns([6, 1])
    with title_col:
        st.subheader("Items")
    with action_col:
        if st.button("+", key="items_list_new", help="New item", use_container_width=True):
            set_view_kind("item_new")
            st.session_state.pop("item_interpret_result", None)
            st.rerun()
    items = manager.get_items_in_campaign(campaign_id)
    items = sorted(items, key=lambda i: i.created_at, reverse=True)
    pending = get_pending_delete()
    if not items:
        st.info("No items yet. Create one below.")
    else:
        for it in items:
            row_col, action1_col, action2_col = st.columns([6, 1, 1])
            with row_col:
                st.write(f"**{it.name}** — {it.item_type.value} {it.rarity.value}")
            if pending and pending.get("kind") == "item" and pending.get("id") == str(it.id):
                st.warning("Delete this item?")
                with action1_col:
                    if st.button("Cancel", key=f"cancel_del_item_{it.id}"):
                        clear_pending_delete()
                        st.rerun()
                with action2_col:
                    if st.button("Yes, delete", key=f"confirm_del_item_{it.id}", type="primary"):
                        manager.delete_item(it.id)
                        if get_selected_item_id() == it.id:
                            set_selected_item_id(None)
                        clear_pending_delete()
                        st.rerun()
            else:
                with action1_col:
                    if st.button("View", key=f"view_item_{it.id}"):
                        set_selected_item_id(it.id)
                        set_view_kind("item_single")
                        st.rerun()
                with action2_col:
                    if st.button("Delete", key=f"del_item_{it.id}"):
                        set_pending_delete("item", it.id, it.name, "")
                        st.rerun()
            st.divider()
def render_item_single() -> None:
    item_id = get_selected_item_id()
    if not item_id:
        set_view_kind("items")
        st.rerun()
        return
    manager = get_manager()
    item = manager.get_item(item_id)
    if not item:
        st.error("Item not found.")
        return
    st.subheader(item.name)
    st.caption(f"{item.item_type.value} · {item.rarity.value}")
    st.write(item.description)
    st.write("**Lore**")
    st.write(item.lore or "(none)")
    st.write("**Mechanics**")
    st.write(item.mechanics or "(none)")
    if item.requires_attunement:
        st.write("Requires attunement")
    if item.value:
        st.write(f"Value: {item.value}")
    if st.button("Back to Items"):
        set_selected_item_id(None)
        set_view_kind("items")
        st.rerun()


def render_item_form() -> None:
    campaign_id = get_campaign_id()
    if not campaign_id:
        st.warning("Select a campaign first.")
        return
    manager = get_manager()
    st.subheader("Create Item")
    st.caption("After you click Interpret, the page will refresh and show the result below. If nothing appears, check for a red error or ensure ANTHROPIC_API_KEY is set.")
    description = st.text_area("Describe the item", height=100, key="item_desc")
    if st.button("Interpret"):
        with st.spinner("Interpreting... (this may take 10–30 seconds)"):
            try:
                result = interpret_item(description)
                st.session_state["item_interpret_result"] = result
                st.rerun()
            except Exception as e:
                st.error("Interpret failed — see details below.")
                st.exception(e)
                st.code(traceback.format_exc(), language="text")
    result = st.session_state.get("item_interpret_result")
    if result:
        st.success("Interpret complete. Review the result below.")
        name_val = result.get("name", "") or ""
        st.write("**Review seed**")
        name = st.text_input("Name", value=name_val, key="item_seed_name")
        result["name"] = name
        if st.button("Generate full item"):
            with st.spinner("Generating..."):
                try:
                    generate_item_from_seed(manager, campaign_id, result)
                    st.success("Item created.")
                    st.session_state.pop("item_interpret_result", None)
                    set_view_kind("items")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    else:
        st.caption("No result yet. Click **Interpret** above. If you already clicked and still see this, an error may have occurred — check above for a red message.")
    if st.button("Cancel"):
        set_view_kind("items")
        st.rerun()
