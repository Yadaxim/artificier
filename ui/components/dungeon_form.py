"""Dungeon creation flow: interpret → review → seed rooms → topology → generate rooms."""

import traceback
from uuid import UUID

import streamlit as st

from core.generation import generate_room, generate_topology, interpret_dungeon, seed_rooms
from core.state_manager import WorldStateManager
from models.models import Campaign, Dungeon, Edge, EdgeType

from ui.state import get_campaign_id, get_manager, set_selected_dungeon_id, set_view_kind


def render_dungeon_form() -> None:
    manager = get_manager()
    campaign_id = get_campaign_id()
    if not campaign_id:
        st.warning("Select or create a campaign first.")
        return

    step = st.session_state.get("dungeon_form_step", 0)

    if step == 0:
        _step_interpret(manager, campaign_id)
    elif step == 1:
        _step_review_and_confirm(manager, campaign_id)
    elif step == 2:
        _step_seed_rooms(manager, campaign_id)
    elif step == 3:
        _step_topology(manager, campaign_id)
    elif step == 4:
        _step_generate_rooms(manager, campaign_id)
    else:
        st.session_state["dungeon_form_step"] = 0
        st.session_state.pop("dungeon_interpret_result", None)
        st.session_state.pop("dungeon_id_created", None)
        set_view_kind("dungeons")
        st.rerun()


def _step_interpret(manager: WorldStateManager, campaign_id) -> None:
    st.subheader("Describe your dungeon")
    st.caption("After you click Interpret, the page will refresh and show the review step. If nothing changes, check for a red error below or in the terminal.")
    description = st.text_area("Free-text description", height=120, key="dungeon_description")
    party_level = st.number_input("Party level", min_value=1, max_value=20, value=5, key="dungeon_party_level")
    if st.button("Interpret with Claude"):
        with st.spinner("Interpreting... (this may take 10–30 seconds)"):
            try:
                result, raw_response, debug = interpret_dungeon(description, party_level)
                st.session_state["dungeon_interpret_result"] = result
                st.session_state["dungeon_interpret_raw"] = raw_response
                st.session_state["dungeon_interpret_debug"] = debug
                st.session_state["dungeon_form_step"] = 1
                st.rerun()
            except Exception as e:
                st.error("Interpret failed — see details below.")
                st.exception(e)
                st.code(traceback.format_exc(), language="text")


def _step_review_and_confirm(manager: WorldStateManager, campaign_id) -> None:
    result = st.session_state.get("dungeon_interpret_result")
    if not result:
        st.session_state["dungeon_form_step"] = 0
        st.rerun()
        return

    st.success("Interpret complete. Review the result below.")
    name_val = result.get("name", "") or ""
    raw = st.session_state.get("dungeon_interpret_raw", "")
    debug = st.session_state.get("dungeon_interpret_debug") or {}

    # Debug first so it's impossible to miss
    st.info(f"**DEBUG (dungeon)** — raw_len={debug.get('raw_len', len(raw))} | name_before_fix={debug.get('name_before_fix', 'N/A')} | name_after_fix={debug.get('name_after_fix', 'N/A')} | blocks={debug.get('content_block_count', '?')}")
    with st.expander("Debug details (dungeon)", expanded=True):
        st.json({k: v for k, v in (debug or {}).items() if k != "block_info"})
        if debug.get("block_info"):
            for b in debug["block_info"]:
                st.text(f"Block {b.get('index')}: type={b.get('type')} has_text={b.get('has_text')} text_len={b.get('text_len')}")
        st.caption("Raw (first 400):")
        st.text(debug.get("raw_first_400", raw[:400] if raw else "(none)"))
        st.caption("Cleaned (first 400):")
        st.text((debug.get("cleaned_first_400") or "")[:400])
    st.markdown("---")

    st.subheader("Review dungeon seed")
    name_looks_wrong = (
        not name_val.strip()
        or name_val.strip().lower() in ("name", '"name"', "'name'")
        or ("name" in name_val.lower() and len(name_val.strip()) < 20 and '"' in name_val)
        or name_val.strip() == ' "name"'
    )
    if name_looks_wrong:
        st.warning("The name field looks like a placeholder. Edit it below; debug info is above.")
    with st.expander("Full raw API response", expanded=name_looks_wrong):
        if raw:
            st.text(raw[:8000] + ("..." if len(raw) > 8000 else ""))
        else:
            st.caption("No raw stored. Click Interpret again.")
    name = st.text_input("Name", value=name_val, key="dungeon_seed_name")
    concept = st.text_area("Concept", value=result.get("concept", ""), key="dungeon_seed_concept")
    tone = st.text_input("Tone", value=result.get("tone", ""), key="dungeon_seed_tone")
    level_range = st.text_input("Level range", value=result.get("level_range", ""), key="dungeon_seed_level_range")
    world_context = st.text_area("World context", value=result.get("world_context", ""), key="dungeon_seed_world_context")
    history = result.get("history") or {}
    st.write("**History** (from interpretation):")
    st.json(history)

    floors = result.get("floors") or []
    st.write("**Floors** (from interpretation):")
    for f in floors:
        st.write(f"- Level {f.get('level_number')}: {f.get('name')} — {f.get('theme')} ({f.get('room_count')} rooms)")

    if st.button("Confirm and create dungeon"):
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
        st.session_state["dungeon_id_created"] = str(dungeon.id)
        st.session_state["dungeon_form_step"] = 2
        st.success("Dungeon created. Now seed rooms per floor.")
        st.rerun()


def _step_seed_rooms(manager: WorldStateManager, campaign_id) -> None:
    dungeon_id_str = st.session_state.get("dungeon_id_created")
    if not dungeon_id_str:
        st.session_state["dungeon_form_step"] = 0
        st.rerun()
        return
    dungeon_id = UUID(dungeon_id_str)
    dungeon = manager.get_dungeon(dungeon_id)
    if not dungeon:
        st.error("Dungeon not found.")
        return

    floors = dungeon.metadata.get("floors") or []
    if not floors:
        st.warning("No floors in dungeon metadata. Go back and confirm with at least one floor.")
        if st.button("Back to review"):
            st.session_state["dungeon_form_step"] = 1
            st.rerun()
        return

    floor_index = st.session_state.get("dungeon_seed_floor_index", 0)

    st.markdown("**Planned floors**")
    for i, f in enumerate(floors):
        label = f"Level {f.get('level_number', 0)}: {f.get('name', 'Floor')} — {f.get('theme', '')} ({f.get('room_count', 0)} rooms)"
        if i < floor_index:
            st.caption(f"✓ {label} (seeded)")
        elif i == floor_index:
            st.caption(f"→ **{label}** (current)")
        else:
            st.caption(f"○ {label}")
    st.divider()

    if floor_index >= len(floors):
        st.success("All floors seeded. Generate topology next.")
        if st.button("Generate topology"):
            st.session_state["dungeon_form_step"] = 3
            st.rerun()
        return

    floor = floors[floor_index]
    st.subheader(f"Seed rooms: {floor.get('name', 'Floor')} (level {floor.get('level_number', 0)})")
    if st.button("Seed rooms for this floor"):
        with st.spinner("Seeding rooms..."):
            try:
                seed_rooms(manager, campaign_id, dungeon_id, floor)
                st.session_state["dungeon_seed_floor_index"] = floor_index + 1
                set_selected_dungeon_id(dungeon_id)
                set_view_kind("dungeon_single")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    if st.button("Skip to topology (use already-seeded rooms only)"):
        st.session_state["dungeon_form_step"] = 3
        st.rerun()


def _step_topology(manager: WorldStateManager, campaign_id) -> None:
    dungeon_id_str = st.session_state.get("dungeon_id_created")
    if not dungeon_id_str:
        st.session_state["dungeon_form_step"] = 0
        st.rerun()
        return
    dungeon_id = UUID(dungeon_id_str)
    st.subheader("Generate room connections")
    if st.button("Generate topology with Claude"):
        with st.spinner("Generating connections..."):
            try:
                edges = generate_topology(manager, dungeon_id)
                st.success(f"Created {len(edges)} passage connections.")
                st.session_state["dungeon_form_step"] = 4
                st.rerun()
            except Exception as e:
                st.error(str(e))


def _step_generate_rooms(manager: WorldStateManager, campaign_id) -> None:
    dungeon_id_str = st.session_state.get("dungeon_id_created")
    if not dungeon_id_str:
        st.session_state["dungeon_form_step"] = 0
        st.rerun()
        return
    dungeon_id = UUID(dungeon_id_str)
    rooms = manager.get_rooms_in_dungeon(dungeon_id)
    generated_ids = st.session_state.get("dungeon_generated_room_ids", [])

    remaining = [r for r in rooms if r.id not in generated_ids]
    if not remaining:
        st.success("All rooms generated. You can view the dungeon now.")
        if st.button("Finish and view dungeon"):
            st.session_state["dungeon_form_step"] = 99
            st.session_state["selected_dungeon_id"] = dungeon_id
            set_view_kind("dungeon_single")
            st.rerun()
        return

    room = remaining[0]
    st.subheader(f"Generate room: {room.name}")
    st.caption(f"Purpose: {room.purpose}. Atmosphere: {room.atmosphere}")
    if st.button("Generate full description"):
        with st.spinner("Generating room..."):
            try:
                generate_room(manager, dungeon_id, room.id, generated_ids)
                generated_ids.append(room.id)
                st.session_state["dungeon_generated_room_ids"] = generated_ids
                st.success("Room generated.")
                st.rerun()
            except Exception as e:
                st.error(str(e))
