"""JSON persistence and graph queries for Artificier world state."""

import json
from pathlib import Path
from uuid import UUID

from pydantic import TypeAdapter

from models.models import (
    Campaign,
    Clue,
    Dungeon,
    Edge,
    EdgeType,
    Item,
    Location,
    Monster,
    NPC,
    Plot,
    Room,
    Town,
    WorldState,
)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _campaigns_dir() -> Path:
    d = _project_root() / "data" / "campaigns"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _campaign_path(campaign_id: UUID) -> Path:
    return _campaigns_dir() / f"{campaign_id}.json"


def _str_id(u: UUID) -> str:
    return str(u)


# Pydantic v2: serialize/deserialize with mode='json' for UUID/datetime
def _world_state_to_json_serializable(ws: WorldState) -> dict:
    return ws.model_dump(mode="json")


def _world_state_from_dict(data: dict) -> WorldState:
    # Dict keys from JSON are already strings; nested models need parsing
    adapter = TypeAdapter(WorldState)
    return adapter.validate_python(data)


class WorldStateManager:
    """Single class responsible for loading/saving WorldState and graph queries."""

    def __init__(self):
        self._state: WorldState | None = None
        self._loaded_campaign_id: UUID | None = None

    def load_campaign(self, campaign_id: UUID) -> WorldState:
        path = _campaign_path(campaign_id)
        if not path.exists():
            self._state = WorldState()
            self._loaded_campaign_id = campaign_id
            return self._state
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        self._state = _world_state_from_dict(data)
        self._loaded_campaign_id = campaign_id
        return self._state

    def save(self) -> None:
        if self._state is None or self._loaded_campaign_id is None:
            return
        path = _campaign_path(self._loaded_campaign_id)
        data = _world_state_to_json_serializable(self._state)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_state(self) -> WorldState | None:
        return self._state

    def ensure_loaded(self, campaign_id: UUID) -> WorldState:
        if self._loaded_campaign_id != campaign_id or self._state is None:
            return self.load_campaign(campaign_id)
        return self._state

    # --- Campaign CRUD ---

    def create_campaign(self, campaign: Campaign) -> Campaign:
        self._ensure_state()
        sid = _str_id(campaign.id)
        self._state.campaigns[sid] = campaign
        self.save()
        return campaign

    def get_campaign(self, campaign_id: UUID) -> Campaign | None:
        self._ensure_state()
        return self._state.campaigns.get(_str_id(campaign_id))

    def update_campaign(self, campaign: Campaign) -> Campaign:
        self._ensure_state()
        sid = _str_id(campaign.id)
        if sid not in self._state.campaigns:
            raise KeyError(f"Campaign {campaign.id} not found")
        self._state.campaigns[sid] = campaign
        self.save()
        return campaign

    # --- Dungeon CRUD ---

    def create_dungeon(self, dungeon: Dungeon) -> Dungeon:
        self._ensure_state()
        self._state.dungeons[_str_id(dungeon.id)] = dungeon
        self.save()
        return dungeon

    def get_dungeon(self, dungeon_id: UUID) -> Dungeon | None:
        self._ensure_state()
        return self._state.dungeons.get(_str_id(dungeon_id))

    def update_dungeon(self, dungeon: Dungeon) -> Dungeon:
        self._ensure_state()
        sid = _str_id(dungeon.id)
        if sid not in self._state.dungeons:
            raise KeyError(f"Dungeon {dungeon.id} not found")
        self._state.dungeons[sid] = dungeon
        self.save()
        return dungeon

    # --- Room CRUD ---

    def create_room(self, room: Room) -> Room:
        self._ensure_state()
        self._state.rooms[_str_id(room.id)] = room
        self.save()
        return room

    def get_room(self, room_id: UUID) -> Room | None:
        self._ensure_state()
        return self._state.rooms.get(_str_id(room_id))

    def update_room(self, room: Room) -> Room:
        self._ensure_state()
        sid = _str_id(room.id)
        if sid not in self._state.rooms:
            raise KeyError(f"Room {room.id} not found")
        self._state.rooms[sid] = room
        self.save()
        return room

    # --- Town CRUD ---

    def create_town(self, town: Town) -> Town:
        self._ensure_state()
        self._state.towns[_str_id(town.id)] = town
        self.save()
        return town

    def get_town(self, town_id: UUID) -> Town | None:
        self._ensure_state()
        return self._state.towns.get(_str_id(town_id))

    def update_town(self, town: Town) -> Town:
        self._ensure_state()
        sid = _str_id(town.id)
        if sid not in self._state.towns:
            raise KeyError(f"Town {town.id} not found")
        self._state.towns[sid] = town
        self.save()
        return town

    # --- Location CRUD ---

    def create_location(self, location: Location) -> Location:
        self._ensure_state()
        self._state.locations[_str_id(location.id)] = location
        self.save()
        return location

    def get_location(self, location_id: UUID) -> Location | None:
        self._ensure_state()
        return self._state.locations.get(_str_id(location_id))

    def update_location(self, location: Location) -> Location:
        self._ensure_state()
        sid = _str_id(location.id)
        if sid not in self._state.locations:
            raise KeyError(f"Location {location.id} not found")
        self._state.locations[sid] = location
        self.save()
        return location

    # --- NPC, Monster, Item CRUD ---

    def create_npc(self, npc: NPC) -> NPC:
        self._ensure_state()
        self._state.npcs[_str_id(npc.id)] = npc
        self.save()
        return npc

    def get_npc(self, npc_id: UUID) -> NPC | None:
        self._ensure_state()
        return self._state.npcs.get(_str_id(npc_id))

    def update_npc(self, npc: NPC) -> NPC:
        self._ensure_state()
        sid = _str_id(npc.id)
        if sid not in self._state.npcs:
            raise KeyError(f"NPC {npc.id} not found")
        self._state.npcs[sid] = npc
        self.save()
        return npc

    def create_monster(self, monster: Monster) -> Monster:
        self._ensure_state()
        self._state.monsters[_str_id(monster.id)] = monster
        self.save()
        return monster

    def get_monster(self, monster_id: UUID) -> Monster | None:
        self._ensure_state()
        return self._state.monsters.get(_str_id(monster_id))

    def update_monster(self, monster: Monster) -> Monster:
        self._ensure_state()
        sid = _str_id(monster.id)
        if sid not in self._state.monsters:
            raise KeyError(f"Monster {monster.id} not found")
        self._state.monsters[sid] = monster
        self.save()
        return monster

    def create_item(self, item: Item) -> Item:
        self._ensure_state()
        self._state.items[_str_id(item.id)] = item
        self.save()
        return item

    def get_item(self, item_id: UUID) -> Item | None:
        self._ensure_state()
        return self._state.items.get(_str_id(item_id))

    def update_item(self, item: Item) -> Item:
        self._ensure_state()
        sid = _str_id(item.id)
        if sid not in self._state.items:
            raise KeyError(f"Item {item.id} not found")
        self._state.items[sid] = item
        self.save()
        return item

    # --- Plot, Clue CRUD ---

    def create_plot(self, plot: Plot) -> Plot:
        self._ensure_state()
        self._state.plots[_str_id(plot.id)] = plot
        self.save()
        return plot

    def get_plot(self, plot_id: UUID) -> Plot | None:
        self._ensure_state()
        return self._state.plots.get(_str_id(plot_id))

    def update_plot(self, plot: Plot) -> Plot:
        self._ensure_state()
        sid = _str_id(plot.id)
        if sid not in self._state.plots:
            raise KeyError(f"Plot {plot.id} not found")
        self._state.plots[sid] = plot
        self.save()
        return plot

    def create_clue(self, clue: Clue) -> Clue:
        self._ensure_state()
        self._state.clues[_str_id(clue.id)] = clue
        self.save()
        return clue

    def get_clue(self, clue_id: UUID) -> Clue | None:
        self._ensure_state()
        return self._state.clues.get(_str_id(clue_id))

    def update_clue(self, clue: Clue) -> Clue:
        self._ensure_state()
        sid = _str_id(clue.id)
        if sid not in self._state.clues:
            raise KeyError(f"Clue {clue.id} not found")
        self._state.clues[sid] = clue
        self.save()
        return clue

    # --- Edges ---

    def add_edge(self, edge: Edge) -> Edge:
        self._ensure_state()
        self._state.edges[_str_id(edge.id)] = edge
        self.save()
        return edge

    def remove_edge(self, edge_id: UUID) -> None:
        self._ensure_state()
        self._state.edges.pop(_str_id(edge_id), None)
        self.save()

    def _remove_edges_involving(self, node_id: UUID) -> None:
        """Remove all edges where source_id or target_id is node_id."""
        self._ensure_state()
        to_remove = [
            e.id for e in self._state.edges.values()
            if e.source_id == node_id or e.target_id == node_id
        ]
        for eid in to_remove:
            self._state.edges.pop(_str_id(eid), None)
        if to_remove:
            self.save()

    def get_edges_from(self, source_id: UUID, edge_type: EdgeType | None = None) -> list[Edge]:
        self._ensure_state()
        out = [
            e for e in self._state.edges.values()
            if e.source_id == source_id and (edge_type is None or e.edge_type == edge_type)
        ]
        return out

    def get_edges_to(self, target_id: UUID, edge_type: EdgeType | None = None) -> list[Edge]:
        self._ensure_state()
        out = [
            e for e in self._state.edges.values()
            if e.target_id == target_id and (edge_type is None or e.edge_type == edge_type)
        ]
        return out

    # --- Graph queries ---

    def get_children(self, parent_id: UUID, edge_type: EdgeType = EdgeType.CONTAINS) -> list[tuple[str, UUID]]:
        """Return list of (collection_name, child_id) for CONTAINS edges from parent_id."""
        self._ensure_state()
        edges = self.get_edges_from(parent_id, edge_type)
        # Resolve target to collection by checking which dict contains it
        result = []
        for e in edges:
            tid = _str_id(e.target_id)
            if tid in self._state.rooms:
                result.append(("rooms", e.target_id))
            elif tid in self._state.dungeons:
                result.append(("dungeons", e.target_id))
            elif tid in self._state.towns:
                result.append(("towns", e.target_id))
            elif tid in self._state.locations:
                result.append(("locations", e.target_id))
            elif tid in self._state.npcs:
                result.append(("npcs", e.target_id))
            elif tid in self._state.monsters:
                result.append(("monsters", e.target_id))
            elif tid in self._state.items:
                result.append(("items", e.target_id))
            elif tid in self._state.plots:
                result.append(("plots", e.target_id))
            elif tid in self._state.clues:
                result.append(("clues", e.target_id))
        return result

    def get_connections(self, node_id: UUID, edge_type: EdgeType = EdgeType.CONNECTS_TO) -> list[Edge]:
        """Return CONNECTS_TO edges from this node (e.g. passages from a room)."""
        return self.get_edges_from(node_id, edge_type)

    def get_rooms_in_dungeon(self, dungeon_id: UUID) -> list[Room]:
        """Rooms that are CONTAINS targets from this dungeon (or PART_OF dungeon)."""
        self._ensure_state()
        child_ids = [
            cid for coll, cid in self.get_children(dungeon_id)
            if coll == "rooms"
        ]
        rooms = [self._state.rooms[_str_id(cid)] for cid in child_ids if _str_id(cid) in self._state.rooms]
        return rooms

    def get_locations_in_town(self, town_id: UUID) -> list[Location]:
        self._ensure_state()
        child_ids = [
            cid for coll, cid in self.get_children(town_id)
            if coll == "locations"
        ]
        return [self._state.locations[_str_id(cid)] for cid in child_ids if _str_id(cid) in self._state.locations]

    def get_dungeons_in_campaign(self, campaign_id: UUID) -> list[Dungeon]:
        self._ensure_state()
        child_ids = [
            cid for coll, cid in self.get_children(campaign_id)
            if coll == "dungeons"
        ]
        return [self._state.dungeons[_str_id(cid)] for cid in child_ids if _str_id(cid) in self._state.dungeons]

    def get_towns_in_campaign(self, campaign_id: UUID) -> list[Town]:
        self._ensure_state()
        child_ids = [
            cid for coll, cid in self.get_children(campaign_id)
            if coll == "towns"
        ]
        return [self._state.towns[_str_id(cid)] for cid in child_ids if _str_id(cid) in self._state.towns]

    def list_campaign_ids(self) -> list[UUID]:
        """List campaign IDs that have a saved file."""
        return [UUID(p.stem) for p in _campaigns_dir().glob("*.json")]

    def get_npcs_in_campaign(self, campaign_id: UUID) -> list:
        self._ensure_state()
        child_ids = [cid for coll, cid in self.get_children(campaign_id) if coll == "npcs"]
        return [self._state.npcs[_str_id(cid)] for cid in child_ids if _str_id(cid) in self._state.npcs]

    def get_monsters_in_campaign(self, campaign_id: UUID) -> list:
        self._ensure_state()
        child_ids = [cid for coll, cid in self.get_children(campaign_id) if coll == "monsters"]
        return [self._state.monsters[_str_id(cid)] for cid in child_ids if _str_id(cid) in self._state.monsters]

    def get_items_in_campaign(self, campaign_id: UUID) -> list:
        self._ensure_state()
        child_ids = [cid for coll, cid in self.get_children(campaign_id) if coll == "items"]
        return [self._state.items[_str_id(cid)] for cid in child_ids if _str_id(cid) in self._state.items]

    def get_plots_in_campaign(self, campaign_id: UUID) -> list[Plot]:
        self._ensure_state()
        child_ids = [cid for coll, cid in self.get_children(campaign_id) if coll == "plots"]
        return [self._state.plots[_str_id(cid)] for cid in child_ids if _str_id(cid) in self._state.plots]

    def get_clues_in_plot(self, plot_id: UUID) -> list[Clue]:
        self._ensure_state()
        child_ids = [cid for coll, cid in self.get_children(plot_id) if coll == "clues"]
        return [self._state.clues[_str_id(cid)] for cid in child_ids if _str_id(cid) in self._state.clues]

    # --- Cascade deletes ---

    def delete_room(self, room_id: UUID) -> None:
        self._ensure_state()
        self._remove_edges_involving(room_id)
        self._state.rooms.pop(_str_id(room_id), None)
        self.save()

    def delete_dungeon(self, dungeon_id: UUID) -> None:
        self._ensure_state()
        for room in self.get_rooms_in_dungeon(dungeon_id):
            self.delete_room(room.id)
        self._remove_edges_involving(dungeon_id)
        self._state.dungeons.pop(_str_id(dungeon_id), None)
        self.save()

    def delete_location(self, location_id: UUID) -> None:
        self._ensure_state()
        self._remove_edges_involving(location_id)
        self._state.locations.pop(_str_id(location_id), None)
        self.save()

    def delete_town(self, town_id: UUID) -> None:
        self._ensure_state()
        for loc in self.get_locations_in_town(town_id):
            self.delete_location(loc.id)
        self._remove_edges_involving(town_id)
        self._state.towns.pop(_str_id(town_id), None)
        self.save()

    def delete_npc(self, npc_id: UUID) -> None:
        self._ensure_state()
        self._remove_edges_involving(npc_id)
        self._state.npcs.pop(_str_id(npc_id), None)
        self.save()

    def delete_monster(self, monster_id: UUID) -> None:
        self._ensure_state()
        self._remove_edges_involving(monster_id)
        self._state.monsters.pop(_str_id(monster_id), None)
        self.save()

    def delete_item(self, item_id: UUID) -> None:
        self._ensure_state()
        self._remove_edges_involving(item_id)
        self._state.items.pop(_str_id(item_id), None)
        self.save()

    def delete_clue(self, clue_id: UUID) -> None:
        self._ensure_state()
        self._remove_edges_involving(clue_id)
        self._state.clues.pop(_str_id(clue_id), None)
        self.save()

    def delete_plot(self, plot_id: UUID) -> None:
        self._ensure_state()
        for clue in self.get_clues_in_plot(plot_id):
            self.delete_clue(clue.id)
        self._remove_edges_involving(plot_id)
        self._state.plots.pop(_str_id(plot_id), None)
        self.save()

    def delete_campaign(self, campaign_id: UUID) -> None:
        """Delete campaign and all nested content (dungeons/rooms, towns/locations, npcs, monsters, items). Removes the campaign file."""
        self.load_campaign(campaign_id)
        self._ensure_state()
        children = self.get_children(campaign_id)
        for coll, cid in children:
            if coll == "dungeons":
                self.delete_dungeon(cid)
            elif coll == "towns":
                self.delete_town(cid)
            elif coll == "npcs":
                self.delete_npc(cid)
            elif coll == "monsters":
                self.delete_monster(cid)
            elif coll == "items":
                self.delete_item(cid)
            elif coll == "plots":
                self.delete_plot(cid)
        self._remove_edges_involving(campaign_id)
        self._state.campaigns.pop(_str_id(campaign_id), None)
        path = _campaign_path(campaign_id)
        path.unlink(missing_ok=True)
        if self._loaded_campaign_id == campaign_id:
            self._state = None
            self._loaded_campaign_id = None

    def _ensure_state(self) -> None:
        if self._state is None:
            self._state = WorldState()
