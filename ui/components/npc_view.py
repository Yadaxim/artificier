"""NPC list and single view; create flow (interpret → review → generate)."""

import traceback
from uuid import UUID

import streamlit as st

from core.generation import generate_npc_from_seed, interpret_npc
from ui.state import (
    clear_pending_delete,
    get_campaign_id,
    get_manager,
    get_pending_delete,
    get_selected_npc_id,
    set_pending_delete,
    set_selected_npc_id,
    set_view_kind,
)


def render_npcs_list() -> None:
    manager = get_manager()
    campaign_id = get_campaign_id()
    if not campaign_id:
        st.info("Select a campaign.")
        return
    npcs = manager.get_npcs_in_campaign(campaign_id)
    npcs = sorted(npcs, key=lambda n: n.created_at, reverse=True)
    pending = get_pending_delete()
    if not npcs:
        st.info("No NPCs yet. Create one below.")
    else:
        for n in npcs:
            st.write(f"**{n.name}** — {n.race}" + (f" {n.character_class}" if n.character_class else ""))
            if pending and pending.get("kind") == "npc" and pending.get("id") == str(n.id):
                st.warning("Delete this NPC?")
                if st.button("Cancel", key=f"cancel_del_npc_{n.id}"):
                    clear_pending_delete()
                    st.rerun()
                if st.button("Yes, delete", key=f"confirm_del_npc_{n.id}", type="primary"):
                    manager.delete_npc(n.id)
                    if get_selected_npc_id() == n.id:
                        set_selected_npc_id(None)
                    clear_pending_delete()
                    st.rerun()
            else:
                if st.button("View", key=f"view_npc_{n.id}"):
                    set_selected_npc_id(n.id)
                    set_view_kind("npc_single")
                    st.rerun()
                if st.button("Delete", key=f"del_npc_{n.id}"):
                    set_pending_delete("npc", n.id, n.name, "")
                    st.rerun()
    if st.button("Create NPC"):
        set_view_kind("npc_new")
        st.session_state.pop("npc_interpret_result", None)
        st.rerun()


def render_npc_single() -> None:
    npc_id = get_selected_npc_id()
    if not npc_id:
        set_view_kind("npcs")
        st.rerun()
        return
    manager = get_manager()
    npc = manager.get_npc(npc_id)
    if not npc:
        st.error("NPC not found.")
        return
    st.subheader(npc.name)
    st.caption(f"{npc.race}" + (f" · {npc.character_class} {npc.level}" if npc.character_class else ""))
    st.write(npc.description)
    st.write("**Personality**")
    for p in npc.personality or []:
        st.write(f"- {p}")
    st.write("**Roleplaying notes**")
    st.write(npc.roleplaying_notes or "(none)")
    st.write("**Backstory**")
    st.write(npc.backstory or "(none)")
    with st.expander("Stat block"):
        st.write(f"AC {npc.armor_class}, HP {npc.hit_points}, Speed {npc.speed}")
        st.write("Ability scores:", npc.ability_scores)
        st.write("Skills:", npc.skills)
        for f in npc.features_and_traits or []:
            st.write(f"- {f}")
    if st.button("Back to NPCs"):
        set_selected_npc_id(None)
        set_view_kind("npcs")
        st.rerun()


def render_npc_form() -> None:
    campaign_id = get_campaign_id()
    if not campaign_id:
        st.warning("Select a campaign first.")
        return
    manager = get_manager()
    st.subheader("Create NPC")
    st.caption("After you click Interpret, the page will refresh and show the result below. If nothing appears, check for a red error or ensure ANTHROPIC_API_KEY is set.")
    description = st.text_area("Describe the NPC", height=100, key="npc_desc")
    party_level = st.number_input("Party level", min_value=1, max_value=20, value=5, key="npc_pl")
    if st.button("Interpret"):
        with st.spinner("Interpreting... (this may take 10–30 seconds)"):
            try:
                result, raw_response, debug = interpret_npc(description, party_level)
                st.session_state["npc_interpret_result"] = result
                st.session_state["npc_interpret_raw"] = raw_response
                st.session_state["npc_interpret_debug"] = debug
                st.rerun()
            except Exception as e:
                st.error("Interpret failed — see details below.")
                st.exception(e)
                st.code(traceback.format_exc(), language="text")
    result = st.session_state.get("npc_interpret_result")
    if result:
        st.success("Interpret complete. Review the result below.")
        name_val = result.get("name", "") or ""
        raw = st.session_state.get("npc_interpret_raw", "")
        debug = st.session_state.get("npc_interpret_debug") or {}
        st.info(f"**DEBUG (NPC)** — raw_len={debug.get('raw_len', len(raw))} | name_before_fix={debug.get('name_before_fix', 'N/A')} | name_after_fix={debug.get('name_after_fix', 'N/A')} | blocks={debug.get('content_block_count', '?')}")
        with st.expander("Debug details (NPC)", expanded=True):
            st.json({k: v for k, v in (debug or {}).items() if k != "block_info"})
            if debug.get("block_info"):
                for b in debug["block_info"]:
                    st.text(f"Block {b.get('index')}: type={b.get('type')} text_len={b.get('text_len')}")
            st.caption("Raw (first 400):")
            st.text(debug.get("raw_first_400", raw[:400] if raw else "(none)"))
        st.markdown("---")
        st.write("**Review seed** (edit if needed, then Generate)")
        name_looks_wrong = (
            not name_val.strip()
            or name_val.strip().lower() in ("name", '"name"', "'name'")
            or ("name" in name_val.lower() and len(name_val.strip()) < 20 and '"' in name_val)
            or name_val.strip() == ' "name"'
        )
        if name_looks_wrong:
            st.warning("The name field looks like a placeholder. See DEBUG above.")
        with st.expander("Full raw API response", expanded=name_looks_wrong):
            st.text((raw or "")[:8000] + ("..." if len(raw or "") > 8000 else ""))
        name = st.text_input("Name", value=name_val, key="npc_seed_name")
        race = st.text_input("Race", value=result.get("race", ""), key="npc_seed_race")
        result["name"] = name
        result["race"] = race
        if st.button("Generate full NPC"):
            with st.spinner("Generating..."):
                try:
                    generate_npc_from_seed(manager, campaign_id, result)
                    st.success("NPC created.")
                    st.session_state.pop("npc_interpret_result", None)
                    set_view_kind("npcs")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    else:
        st.caption("No result yet. Click **Interpret** above. If you already clicked and still see this, an error may have occurred — check above for a red message.")
    if st.button("Cancel"):
        set_view_kind("npcs")
        st.rerun()
