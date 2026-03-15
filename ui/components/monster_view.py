"""Monster list and single view; create flow."""

import traceback
from uuid import UUID

import streamlit as st

from core.generation import generate_monster_from_seed, interpret_monster
from ui.state import get_campaign_id, get_manager, get_selected_monster_id, set_selected_monster_id, set_view_kind


def render_monsters_list() -> None:
    manager = get_manager()
    campaign_id = get_campaign_id()
    if not campaign_id:
        st.info("Select a campaign.")
        return
    monsters = manager.get_monsters_in_campaign(campaign_id)
    if not monsters:
        st.info("No monsters yet. Create one below.")
    else:
        for m in monsters:
            st.write(f"**{m.name}** — {m.creature_type} {m.size}")
            if st.button("View", key=f"view_monster_{m.id}"):
                set_selected_monster_id(m.id)
                set_view_kind("monster_single")
                st.rerun()
    if st.button("Create Monster"):
        set_view_kind("monster_new")
        st.session_state.pop("monster_interpret_result", None)
        st.rerun()


def render_monster_single() -> None:
    monster_id = get_selected_monster_id()
    if not monster_id:
        set_view_kind("monsters")
        st.rerun()
        return
    manager = get_manager()
    monster = manager.get_monster(monster_id)
    if not monster:
        st.error("Monster not found.")
        return
    st.subheader(monster.name)
    st.caption(f"{monster.size} {monster.creature_type}, {monster.alignment}")
    st.write(monster.description)
    st.write("**Tactics**")
    st.write(monster.tactics or "(none)")
    with st.expander("Stat block"):
        st.write(f"AC {monster.armor_class}, HP {monster.hit_points} (avg {monster.hit_points_avg})")
        st.write(f"Speed {monster.speed} · CR {monster.challenge_rating}")
        st.write("Ability scores:", monster.ability_scores)
        for a in monster.actions or []:
            st.write(f"- **{a.get('name', '')}**: {a.get('description', '')}")
    if st.button("Back to Monsters"):
        set_selected_monster_id(None)
        set_view_kind("monsters")
        st.rerun()


def render_monster_form() -> None:
    campaign_id = get_campaign_id()
    if not campaign_id:
        st.warning("Select a campaign first.")
        return
    manager = get_manager()
    st.subheader("Create Monster")
    st.caption("After you click Interpret, the page will refresh and show the result below. If nothing appears, check for a red error or ensure ANTHROPIC_API_KEY is set.")
    description = st.text_area("Describe the monster", height=100, key="monster_desc")
    party_level = st.number_input("Party level", min_value=1, max_value=20, value=5, key="monster_pl")
    if st.button("Interpret"):
        with st.spinner("Interpreting... (this may take 10–30 seconds)"):
            try:
                result, raw_response, debug = interpret_monster(description, party_level)
                st.session_state["monster_interpret_result"] = result
                st.session_state["monster_interpret_raw"] = raw_response
                st.session_state["monster_interpret_debug"] = debug
                st.rerun()
            except Exception as e:
                st.error("Interpret failed — see details below.")
                st.exception(e)
                st.code(traceback.format_exc(), language="text")
    result = st.session_state.get("monster_interpret_result")
    if result:
        st.success("Interpret complete. Review the result below.")
        name_val = result.get("name", "") or ""
        raw = st.session_state.get("monster_interpret_raw", "")
        debug = st.session_state.get("monster_interpret_debug") or {}
        st.info(f"**DEBUG (monster)** — raw_len={debug.get('raw_len', len(raw))} | name_before_fix={debug.get('name_before_fix', 'N/A')} | name_after_fix={debug.get('name_after_fix', 'N/A')} | blocks={debug.get('content_block_count', '?')}")
        with st.expander("Debug details (monster)", expanded=True):
            st.json({k: v for k, v in (debug or {}).items() if k != "block_info"})
            if debug.get("block_info"):
                for b in debug["block_info"]:
                    st.text(f"Block {b.get('index')}: type={b.get('type')} text_len={b.get('text_len')}")
            st.caption("Raw (first 400):")
            st.text(debug.get("raw_first_400", raw[:400] if raw else "(none)"))
        st.markdown("---")
        st.write("**Review seed**")
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
        name = st.text_input("Name", value=name_val, key="monster_seed_name")
        result["name"] = name
        if st.button("Generate full stat block"):
            with st.spinner("Generating..."):
                try:
                    generate_monster_from_seed(manager, campaign_id, result)
                    st.success("Monster created.")
                    st.session_state.pop("monster_interpret_result", None)
                    set_view_kind("monsters")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    else:
        st.caption("No result yet. Click **Interpret** above. If you already clicked and still see this, an error may have occurred — check above for a red message.")
    if st.button("Cancel"):
        set_view_kind("monsters")
        st.rerun()
