"""Town creation flow: interpret → review → seed locations → generate locations."""

import traceback
from uuid import UUID

import streamlit as st

from core.generation import generate_location, interpret_town, seed_locations
from models.models import Edge, EdgeType, PopulationSize, Town

from ui.state import get_campaign_id, get_manager, set_view_kind


def render_town_form() -> None:
    manager = get_manager()
    campaign_id = get_campaign_id()
    if not campaign_id:
        st.warning("Select or create a campaign first.")
        return

    step = st.session_state.get("town_form_step", 0)

    if step == 0:
        _step_interpret(manager, campaign_id)
    elif step == 1:
        _step_review_and_confirm(manager, campaign_id)
    elif step == 2:
        _step_seed_locations(manager, campaign_id)
    elif step == 3:
        _step_generate_locations(manager, campaign_id)
    else:
        st.session_state["town_form_step"] = 0
        st.session_state.pop("town_interpret_result", None)
        st.session_state.pop("town_id_created", None)
        set_view_kind("towns")
        st.rerun()


def _step_interpret(manager, campaign_id) -> None:
    st.subheader("Describe your town")
    st.caption("After you click Interpret, the page will refresh and show the review step. If nothing changes, check for a red error below.")
    description = st.text_area("Free-text description", height=120, key="town_description")
    party_level = st.number_input("Party level", min_value=1, max_value=20, value=5, key="town_party_level")
    if st.button("Interpret with Claude"):
        with st.spinner("Interpreting... (this may take 10–30 seconds)"):
            try:
                result, raw_response, debug = interpret_town(description, party_level)
                st.session_state["town_interpret_result"] = result
                st.session_state["town_interpret_raw"] = raw_response
                st.session_state["town_interpret_debug"] = debug
                st.session_state["town_form_step"] = 1
                st.rerun()
            except Exception as e:
                st.error("Interpret failed — see details below.")
                st.exception(e)
                st.code(traceback.format_exc(), language="text")


def _step_review_and_confirm(manager, campaign_id) -> None:
    result = st.session_state.get("town_interpret_result")
    if not result:
        st.session_state["town_form_step"] = 0
        st.rerun()
        return

    st.success("Interpret complete. Review the result below.")
    name_val = result.get("name", "") or ""
    raw = st.session_state.get("town_interpret_raw", "")
    debug = st.session_state.get("town_interpret_debug") or {}
    st.info(f"**DEBUG (town)** — raw_len={debug.get('raw_len', len(raw))} | name_before_fix={debug.get('name_before_fix', 'N/A')} | name_after_fix={debug.get('name_after_fix', 'N/A')} | blocks={debug.get('content_block_count', '?')}")
    with st.expander("Debug details (town)", expanded=True):
        st.json({k: v for k, v in (debug or {}).items() if k != "block_info"})
        if debug.get("block_info"):
            for b in debug["block_info"]:
                st.text(f"Block {b.get('index')}: type={b.get('type')} text_len={b.get('text_len')}")
        st.caption("Raw (first 400):")
        st.text(debug.get("raw_first_400", raw[:400] if raw else "(none)"))
    st.markdown("---")
    st.subheader("Review town seed")
    name_looks_wrong = (
        not name_val.strip()
        or name_val.strip().lower() in ("name", '"name"', "'name'")
        or ("name" in name_val.lower() and len(name_val.strip()) < 20 and '"' in name_val)
        or name_val.strip() == ' "name"'
    )
    if name_looks_wrong:
        st.warning("The name field looks like a placeholder. Edit it below or check the debug section.")
    with st.expander("Debug: raw API response", expanded=name_looks_wrong):
        if raw:
            st.text(raw[:8000] + ("..." if len(raw) > 8000 else ""))
        else:
            st.caption("Click **Interpret with Claude** again to capture the API response.")
    name = st.text_input("Name", value=name_val, key="town_seed_name")
    concept = st.text_area("Concept", value=result.get("concept", ""), key="town_seed_concept")
    tone = st.text_input("Tone", value=result.get("tone", ""), key="town_seed_tone")
    pop_str = result.get("population_size", "TOWN")
    try:
        pop = PopulationSize(pop_str)
    except ValueError:
        pop = PopulationSize.TOWN
    population_size = st.selectbox(
        "Population size",
        options=[e.value for e in PopulationSize],
        index=[e.value for e in PopulationSize].index(pop.value),
        key="town_seed_pop",
    )
    history = st.text_area("History", value=result.get("history", ""), key="town_seed_history")
    world_context = st.text_area("World context", value=result.get("world_context", ""), key="town_seed_world_context")
    dominant_faction = st.text_input("Dominant faction", value=result.get("dominant_faction", ""), key="town_seed_faction")

    locations = result.get("locations") or []
    st.write("**Suggested locations** (from interpretation):")
    for loc in locations:
        st.write(f"- {loc.get('name')} ({loc.get('location_type')}): {loc.get('theme', '')}")

    if st.button("Confirm and create town"):
        campaign = manager.get_campaign(campaign_id)
        if not campaign:
            st.error("Campaign not found.")
            return
        town = Town(
            name=name,
            concept=concept,
            tone=tone,
            population_size=PopulationSize(population_size),
            history=history,
            world_context=world_context,
            dominant_faction=dominant_faction,
        )
        town.metadata["locations"] = locations
        manager.create_town(town)
        manager.add_edge(Edge(source_id=campaign_id, target_id=town.id, edge_type=EdgeType.CONTAINS))
        st.session_state["town_id_created"] = str(town.id)
        st.session_state["town_form_step"] = 2
        st.success("Town created. Seed locations next.")
        st.rerun()


def _step_seed_locations(manager, campaign_id) -> None:
    town_id_str = st.session_state.get("town_id_created")
    if not town_id_str:
        st.session_state["town_form_step"] = 0
        st.rerun()
        return
    town_id = UUID(town_id_str)
    town = manager.get_town(town_id)
    if not town:
        st.error("Town not found.")
        return

    st.subheader("Seed locations")
    if st.button("Seed locations with Claude"):
        with st.spinner("Seeding locations..."):
            try:
                suggested = town.metadata.get("locations")
                created = seed_locations(manager, campaign_id, town_id, suggested)
                st.success(f"Created {len(created)} locations.")
                st.session_state["town_form_step"] = 3
                st.rerun()
            except Exception as e:
                st.error(str(e))


def _step_generate_locations(manager, campaign_id) -> None:
    town_id_str = st.session_state.get("town_id_created")
    if not town_id_str:
        st.session_state["town_form_step"] = 0
        st.rerun()
        return
    town_id = UUID(town_id_str)
    locations = manager.get_locations_in_town(town_id)
    generated_ids = st.session_state.get("town_generated_location_ids", [])

    remaining = [loc for loc in locations if loc.id not in generated_ids]
    if not remaining:
        st.success("All locations generated.")
        if st.button("Finish and view town"):
            st.session_state["town_form_step"] = 99
            st.session_state["selected_town_id"] = town_id
            set_view_kind("town_single")
            st.rerun()
        return

    loc = remaining[0]
    st.subheader(f"Generate location: {loc.name}")
    st.caption(f"{loc.location_type} · {loc.atmosphere}")
    if st.button("Generate full description"):
        with st.spinner("Generating..."):
            try:
                generate_location(manager, town_id, loc.id, generated_ids)
                generated_ids.append(loc.id)
                st.session_state["town_generated_location_ids"] = generated_ids
                st.success("Location generated.")
                st.rerun()
            except Exception as e:
                st.error(str(e))
