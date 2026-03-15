# Artificier

A D&D 5e campaign aide: create dungeons, towns, NPCs, monsters, and items with Claude. Interpret free text → review seed → generate full content. JSON-backed world state; graph-ready nodes and edges.

## Setup

The project uses a Python virtual environment in `.venv` (already created with dependencies installed). Activate it before running or testing:

```bash
cd Artificier
source .venv/bin/activate   # Linux/macOS
# or:  .venv\Scripts\activate   # Windows
```

If you need to recreate the venv or install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set your Claude API key:

```bash
export ANTHROPIC_API_KEY=your_key_here
```

Or use Streamlit secrets (see [Streamlit docs](https://docs.streamlit.io/develop/concepts/configuration/secrets-management)).

## Run

With the venv activated:

```bash
streamlit run app.py
```

## Tests

With the venv activated:

```bash
pytest tests/ -v
```

## Structure

- **models/** — Pydantic nodes (Campaign, Dungeon, Room, Town, Location, NPC, Monster, Item) and Edge, WorldState
- **core/** — WorldStateManager (JSON load/save, CRUD, graph queries), context_assembler, generation (interpret/generate), topology
- **prompts/** — Plain-text prompts with `{placeholders}` for dungeon, town, and entity flows
- **ui/** — Streamlit state, styles, and components (campaign home, dungeon/town forms and views, room/location/NPC/monster/item views)
- **data/campaigns/** — One JSON file per campaign (created on first save)

## Create flow

1. Create or select a campaign.
2. **Dungeon**: Describe → interpret → review seed and floors → confirm → seed rooms per floor → generate topology → generate each room.
3. **Town**: Describe → interpret → review → confirm → seed locations → generate each location.
4. **NPC / Monster / Item**: Describe → interpret → review seed → generate full stat block.

Play mode: open a room and use read-aloud, DM notes, and Record Event (events stored in room metadata).
