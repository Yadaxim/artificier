"""Monster list and single view; create flow."""

import json
import traceback
from uuid import UUID

import streamlit as st
from pydantic import ValidationError

from core.generation import generate_monster_from_seed, interpret_monster
from ui.state import (
    clear_pending_delete,
    get_campaign_id,
    get_manager,
    get_pending_delete,
    get_selected_monster_id,
    set_pending_delete,
    set_selected_monster_id,
    set_view_kind,
)


def render_monsters_list() -> None:
    manager = get_manager()
    campaign_id = get_campaign_id()
    if not campaign_id:
        st.info("Select a campaign.")
        return
    monsters = manager.get_monsters_in_campaign(campaign_id)
    monsters = sorted(monsters, key=lambda m: m.created_at, reverse=True)
    pending = get_pending_delete()
    if not monsters:
        st.info("No monsters yet. Create one below.")
    else:
        for m in monsters:
            st.write(f"**{m.name}** — {m.creature_type} {m.size}")
            if pending and pending.get("kind") == "monster" and pending.get("id") == str(m.id):
                st.warning("Delete this monster?")
                if st.button("Cancel", key=f"cancel_del_monster_{m.id}"):
                    clear_pending_delete()
                    st.rerun()
                if st.button("Yes, delete", key=f"confirm_del_monster_{m.id}", type="primary"):
                    manager.delete_monster(m.id)
                    if get_selected_monster_id() == m.id:
                        set_selected_monster_id(None)
                    clear_pending_delete()
                    st.rerun()
            else:
                if st.button("View", key=f"view_monster_{m.id}"):
                    set_selected_monster_id(m.id)
                    set_view_kind("monster_single")
                    st.rerun()
                if st.button("Delete", key=f"del_monster_{m.id}"):
                    set_pending_delete("monster", m.id, m.name, "")
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
        st.write(f"Speed {monster.speed} · CR {monster.challenge_rating} · Prof bonus {monster.proficiency_bonus}")
        spellcasting = getattr(monster, "spellcasting", None)
        if spellcasting:
            st.write("**Spellcasting**")
            st.write(spellcasting)
        if monster.saving_throws:
            st.write("Saving throws:", ", ".join(monster.saving_throws))
        if monster.skills:
            st.write("Skills:", ", ".join(f"{k} {v}" for k, v in monster.skills.items()))
        if monster.damage_resistances:
            st.write("Damage resistances:", ", ".join(monster.damage_resistances))
        if monster.damage_immunities:
            st.write("Damage immunities:", ", ".join(monster.damage_immunities))
        if monster.condition_immunities:
            st.write("Condition immunities:", ", ".join(monster.condition_immunities))
        if monster.senses:
            st.write("Senses:", monster.senses)
        if monster.languages:
            st.write("Languages:", monster.languages)
        st.write("Ability scores:", monster.ability_scores)
        special_abilities = getattr(monster, "special_abilities", None) or []
        if special_abilities:
            st.write("**Traits**")
            for trait in special_abilities:
                name = trait.get("name", "")
                desc = trait.get("description", "")
                st.write(f"- **{name}**: {desc}")
        for a in monster.actions or []:
            st.write(f"- **{a.get('name', '')}**: {a.get('description', '')}")
        bonus_actions = getattr(monster, "bonus_actions", None) or []
        if bonus_actions:
            st.write("**Bonus Actions**")
            for a in bonus_actions:
                st.write(f"- **{a.get('name', '')}**: {a.get('description', '')}")
        reactions = getattr(monster, "reactions", None) or []
        if reactions:
            st.write("**Reactions**")
            for a in reactions:
                st.write(f"- **{a.get('name', '')}**: {a.get('description', '')}")
        legendary_actions = getattr(monster, "legendary_actions", None) or []
        if legendary_actions:
            st.write("**Legendary Actions**")
            for a in legendary_actions:
                st.write(f"- **{a.get('name', '')}**: {a.get('description', '')}")
        lair_actions = getattr(monster, "lair_actions", None) or []
        if lair_actions:
            st.write("**Lair Actions**")
            for text in lair_actions:
                st.write(f"- {text}")
        regional_effects = getattr(monster, "regional_effects", None) or []
        if regional_effects:
            st.write("**Regional Effects**")
            for text in regional_effects:
                st.write(f"- {text}")
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
    st.caption(
        "After you click Interpret, the page will refresh and show the result below. "
        "If nothing appears, check for a red error or ensure ANTHROPIC_API_KEY is set."
    )
    description = st.text_area("Describe the monster", height=100, key="monster_desc")
    challenge_rating = st.text_input(
        "Target Challenge Rating (CR)",
        value="5",
        help="Examples: 1/8, 1/2, 2, 5, 10",
        key="monster_cr",
    )
    if st.button("Interpret"):
        with st.spinner("Interpreting... (this may take 10–30 seconds)"):
            try:
                result, raw_response, debug = interpret_monster(description, challenge_rating)
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
        # Ensure the original target CR is kept on the seed so it can drive stat generation
        result.setdefault("challenge_rating", challenge_rating)
        if st.button("Generate full stat block"):
            with st.spinner("Generating..."):
                try:
                    monster = generate_monster_from_seed(manager, campaign_id, result)
                    st.success(f"Monster '{monster.name or '(unnamed)'}' created.")
                    st.session_state.pop("monster_interpret_result", None)
                    set_selected_monster_id(monster.id)
                    set_view_kind("monster_single")
                    st.rerun()
                except ValidationError as e:
                    st.error(
                        "Monster generation failed: the AI returned data that does not match "
                        "the expected monster schema (likely in abilities or actions)."
                    )
                    with st.expander("Technical details (validation error)"):
                        st.text(str(e))
                        st.caption(
                            "This usually means one of: special_abilities/actions are not a list of "
                            "{name, description, ...} objects, or contain unexpected types."
                        )
                        st.json({"seed_keys": list(result.keys())})
                except json.JSONDecodeError as e:
                    st.error(
                        "Monster generation failed: could not parse JSON from the AI response. "
                        "Try again or simplify your monster description."
                    )
                    with st.expander("Technical details (JSON parse)"):
                        st.text(str(e))
                except Exception as e:
                    st.error("Unexpected error while generating monster. See details below.")
                    with st.expander("Technical details (unexpected error)"):
                        st.text(repr(e))
    else:
        st.caption("No result yet. Click **Interpret** above. If you already clicked and still see this, an error may have occurred — check above for a red message.")
    if st.button("Cancel"):
        set_view_kind("monsters")
        st.rerun()
