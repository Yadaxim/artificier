# Artificier

A campaign aide for D&D 5e dungeon masters. You describe a dungeon, a town or a character in a sentence or two; Artificier turns that into a full, playable write-up and keeps everything it creates linked together as one world.

I have been a DM for a long time. I built this tool for myself and my own campaigns.

**Status:** a working prototype, built in March 2026 and currently parked. Dungeons, towns, NPCs, monsters and items all generate end to end. Plot threads are unfinished and live on the `wip-plots` branch.

## What it does

- **Dungeons.** Describe the idea. Artificier proposes a concept, history and floor plan, you correct it, and it then generates the rooms floor by floor: purpose, atmosphere, read-aloud text, DM notes, features and encounter seeds. Rooms are connected into a map, with an entrance and a boss room.
- **Towns.** The same flow for settlements and their locations.
- **NPCs, monsters and items.** Describe one, review the outline, generate the full stat block.
- **One world, not loose pages.** Everything is a node in a graph (campaign, dungeon, room, town, location, NPC, monster, item) joined by typed edges. When a room is generated, the dungeon it belongs to, its floor and its neighbours are part of the prompt, so the results stay consistent with what already exists.
- **Play mode.** Open a room at the table for its read-aloud text and DM notes, and record what happened there.

## How generation works

Every creation goes through the same three steps, so the model never writes the final content unsupervised:

1. **Interpret.** Your free-text description becomes a structured seed.
2. **Review.** You read the seed and change anything before it is used.
3. **Generate.** The full content is written from the approved seed plus the surrounding world.

## Run it

Requires Python 3 and an Anthropic API key.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here
streamlit run app.py
```

The key can also be supplied through [Streamlit secrets](https://docs.streamlit.io/develop/concepts/configuration/secrets-management).

Tests:

```bash
pytest tests/ -v
```

## Layout

- `models/` — Pydantic models for every node type, plus `Edge` and `WorldState`.
- `core/` — `WorldStateManager` (JSON load and save, CRUD, graph queries), the context assembler that builds each prompt's view of the world, generation (interpret and generate), and dungeon topology.
- `prompts/` — plain-text prompt templates for the dungeon, town and entity flows.
- `ui/` — Streamlit state, styles and one component per view.
- `data/campaigns/` — one JSON file per campaign, created on first save.

Built with Python, Streamlit, Pydantic and the Claude API.
