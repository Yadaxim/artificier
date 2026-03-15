"""Campaign list view: first view; select or create a campaign."""

from datetime import datetime
from uuid import UUID

import streamlit as st

from ui.state import (
    clear_pending_delete,
    get_campaign_id,
    get_manager,
    get_pending_delete,
    set_campaign_id,
    set_pending_delete,
    set_view_kind,
)


def render_campaigns_list() -> None:
    manager = get_manager()
    existing_ids = manager.list_campaign_ids()
    pending = get_pending_delete()

    st.subheader("Campaigns")
    if not existing_ids:
        st.info("No campaigns yet. Create one below.")
    else:
        campaigns_with_id = []
        for cid in existing_ids:
            manager.load_campaign(cid)
            c = manager.get_campaign(cid)
            campaigns_with_id.append((cid, c))
        campaigns_with_id.sort(key=lambda t: t[1].created_at if t[1] else datetime.min, reverse=True)
        for cid, c in campaigns_with_id:
            name = c.name if c else "(Unnamed)"
            pl = c.party_level if c else 1
            summary = (c.setting_summary or "")[:120] if c else ""
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{name}**")
                    st.caption(f"Party level {pl}" + (f" · {summary}" if summary else ""))
                with col2:
                    if pending and pending.get("kind") == "campaign" and pending.get("id") == str(cid):
                        st.warning("Delete this campaign and all its dungeons, towns, NPCs, monsters, and items?")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("Cancel", key=f"cancel_del_campaign_{cid}"):
                                clear_pending_delete()
                                st.rerun()
                        with c2:
                            if st.button("Yes, delete", key=f"confirm_del_campaign_{cid}", type="primary"):
                                manager.delete_campaign(cid)
                                if get_campaign_id() == cid:
                                    set_campaign_id(None)
                                clear_pending_delete()
                                set_view_kind("campaigns")
                                st.rerun()
                    else:
                        if st.button("Select", key=f"select_campaign_{cid}"):
                            set_campaign_id(cid)
                            set_view_kind("campaign_home")
                            st.rerun()
                        if st.button("Delete", key=f"del_campaign_{cid}"):
                            set_pending_delete("campaign", cid, name, "all dungeons, towns, NPCs, monsters, and items")
                            st.rerun()
                st.divider()

    st.subheader("New campaign")
    new_name = st.text_input("Campaign name", key="campaign_list_new_name", placeholder="Enter name")
    new_pl = st.number_input("Party level", min_value=1, max_value=20, value=5, key="campaign_list_new_pl")
    if st.button("Create campaign", key="campaign_list_create") and new_name and new_name.strip():
        from models.models import Campaign

        c = Campaign(name=new_name.strip(), party_level=int(new_pl))
        manager.ensure_loaded(c.id)
        manager.create_campaign(c)
        set_campaign_id(c.id)
        set_view_kind("campaign_home")
        st.rerun()
