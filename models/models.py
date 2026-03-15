"""Pydantic node and edge models for Artificier world state."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_serializer


# --- Enums ---


class DungeonStatus(str, Enum):
    UNVISITED = "UNVISITED"
    PARTIALLY_EXPLORED = "PARTIALLY_EXPLORED"
    CLEARED = "CLEARED"


class RoomStatus(str, Enum):
    UNVISITED = "UNVISITED"
    VISITED = "VISITED"
    CLEARED = "CLEARED"


class PopulationSize(str, Enum):
    HAMLET = "HAMLET"
    VILLAGE = "VILLAGE"
    TOWN = "TOWN"
    CITY = "CITY"


class NPCStatus(str, Enum):
    ALIVE = "ALIVE"
    DEAD = "DEAD"
    FLED = "FLED"
    UNKNOWN = "UNKNOWN"


class MonsterStatus(str, Enum):
    ALIVE = "ALIVE"
    DEAD = "DEAD"
    FLED = "FLED"


class ItemType(str, Enum):
    WEAPON = "WEAPON"
    ARMOR = "ARMOR"
    WONDROUS = "WONDROUS"
    CONSUMABLE = "CONSUMABLE"
    TOOL = "TOOL"
    TREASURE = "TREASURE"


class ItemRarity(str, Enum):
    COMMON = "COMMON"
    UNCOMMON = "UNCOMMON"
    RARE = "RARE"
    VERY_RARE = "VERY_RARE"
    LEGENDARY = "LEGENDARY"
    ARTIFACT = "ARTIFACT"


class ItemStatus(str, Enum):
    PRESENT = "PRESENT"
    TAKEN = "TAKEN"
    DESTROYED = "DESTROYED"


class EdgeType(str, Enum):
    CONTAINS = "CONTAINS"
    CONNECTS_TO = "CONNECTS_TO"
    PART_OF = "PART_OF"
    RELATED_TO = "RELATED_TO"
    GUARDS = "GUARDS"
    QUEST_INVOLVES = "QUEST_INVOLVES"


# --- Base ---


def _default_uuid() -> UUID:
    return uuid4()


def _default_now() -> datetime:
    return datetime.utcnow()


class BaseNode(BaseModel):
    id: UUID = Field(default_factory=_default_uuid)
    created_at: datetime = Field(default_factory=_default_now)
    updated_at: datetime = Field(default_factory=_default_now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


# --- Campaign ---


class Campaign(BaseNode):
    name: str = ""
    description: str = ""
    party_level: int = 1
    tone: str = ""
    setting_summary: str = ""


# --- Dungeon ---


class Dungeon(BaseNode):
    name: str = ""
    concept: str = ""
    tone: str = ""
    history: dict[str, str] = Field(default_factory=dict)  # origin, original_purpose, downfall, timeline
    world_context: str = ""
    level_range: str = ""
    status: DungeonStatus = DungeonStatus.UNVISITED

    @field_serializer("status")
    def _serialize_status(self, v: DungeonStatus) -> str:
        return v.value


# --- Room ---


class Room(BaseNode):
    name: str = ""
    floor_level: int = 0
    purpose: str = ""
    atmosphere: str = ""
    construction_era: str = ""
    description: str = ""
    read_aloud: str = ""
    dm_notes: str = ""
    features: list[str] = Field(default_factory=list)
    status: RoomStatus = RoomStatus.UNVISITED
    is_entrance: bool = False
    is_boss_room: bool = False
    encounter_seeds: list[str] = Field(default_factory=list)
    references_rooms: list[str] = Field(default_factory=list)

    @field_serializer("status")
    def _serialize_status(self, v: RoomStatus) -> str:
        return v.value


# --- Town ---


class Town(BaseNode):
    name: str = ""
    concept: str = ""
    tone: str = ""
    population_size: PopulationSize = PopulationSize.TOWN
    history: str = ""
    world_context: str = ""
    dominant_faction: str = ""

    @field_serializer("population_size")
    def _serialize_population_size(self, v: PopulationSize) -> str:
        return v.value


# --- Location ---


class Location(BaseNode):
    name: str = ""
    location_type: str = ""
    description: str = ""
    dm_notes: str = ""
    atmosphere: str = ""
    notable_features: list[str] = Field(default_factory=list)
    encounter_seeds: list[str] = Field(default_factory=list)


# --- NPC (5e character sheet fields) ---


class NPC(BaseNode):
    name: str = ""
    race: str = ""
    character_class: Optional[str] = None
    level: Optional[int] = None
    description: str = ""
    personality: list[str] = Field(default_factory=list)
    roleplaying_notes: str = ""
    backstory: str = ""
    motivations: list[str] = Field(default_factory=list)
    secrets: list[str] = Field(default_factory=list)
    faction: Optional[str] = None
    ability_scores: dict[str, int] = Field(default_factory=dict)  # STR, DEX, CON, INT, WIS, CHA
    saving_throws: list[str] = Field(default_factory=list)
    skills: dict[str, Any] = Field(default_factory=dict)
    armor_class: int = 10
    hit_points: int = 1
    speed: str = ""
    features_and_traits: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    spells: Optional[dict[str, Any]] = None
    status: NPCStatus = NPCStatus.ALIVE

    @field_serializer("status")
    def _serialize_status(self, v: NPCStatus) -> str:
        return v.value


# --- Monster (5e stat block) ---


class Monster(BaseNode):
    name: str = ""
    creature_type: str = ""
    size: str = ""
    alignment: str = ""
    ability_scores: dict[str, int] = Field(default_factory=dict)
    armor_class: int = 10
    hit_points: str = ""  # dice expression
    hit_points_avg: Optional[int] = None
    speed: str = ""
    skills: dict[str, Any] = Field(default_factory=dict)
    saving_throws: list[str] = Field(default_factory=list)
    damage_resistances: list[str] = Field(default_factory=list)
    damage_immunities: list[str] = Field(default_factory=list)
    condition_immunities: list[str] = Field(default_factory=list)
    senses: str = ""
    languages: str = ""
    challenge_rating: str = ""
    proficiency_bonus: Optional[int] = None
    special_abilities: list[dict[str, str]] = Field(default_factory=list)  # name, description
    actions: list[dict[str, Any]] = Field(default_factory=list)  # name, description, attack_bonus, damage
    bonus_actions: list[dict[str, Any]] = Field(default_factory=list)
    reactions: list[dict[str, Any]] = Field(default_factory=list)
    legendary_actions: list[dict[str, Any]] = Field(default_factory=list)
    description: str = ""
    tactics: str = ""
    status: MonsterStatus = MonsterStatus.ALIVE

    @field_serializer("status")
    def _serialize_status(self, v: MonsterStatus) -> str:
        return v.value


# --- Item ---


class Item(BaseNode):
    name: str = ""
    item_type: ItemType = ItemType.WONDROUS
    rarity: ItemRarity = ItemRarity.COMMON
    description: str = ""
    lore: str = ""
    requires_attunement: bool = False
    properties: list[str] = Field(default_factory=list)
    mechanics: str = ""
    value: Optional[str] = None
    status: ItemStatus = ItemStatus.PRESENT

    @field_serializer("item_type", "rarity", "status")
    def _serialize_enums(self, v):
        if hasattr(v, "value"):
            return v.value
        return v


# --- Edge ---


class Edge(BaseModel):
    id: UUID = Field(default_factory=_default_uuid)
    source_id: UUID
    target_id: UUID
    edge_type: EdgeType
    properties: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

    @field_serializer("edge_type")
    def _serialize_edge_type(self, v: EdgeType) -> str:
        return v.value


# --- WorldState ---


class WorldState(BaseModel):
    campaigns: dict[str, Campaign] = Field(default_factory=dict)
    dungeons: dict[str, Dungeon] = Field(default_factory=dict)
    rooms: dict[str, Room] = Field(default_factory=dict)
    towns: dict[str, Town] = Field(default_factory=dict)
    locations: dict[str, Location] = Field(default_factory=dict)
    npcs: dict[str, NPC] = Field(default_factory=dict)
    monsters: dict[str, Monster] = Field(default_factory=dict)
    items: dict[str, Item] = Field(default_factory=dict)
    edges: dict[str, Edge] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}
