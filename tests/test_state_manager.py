"""Unit tests for WorldStateManager CRUD and edge queries."""

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from core.state_manager import WorldStateManager
from models.models import Campaign, Dungeon, Edge, EdgeType, Room


@pytest.fixture
def manager(tmp_path):
    """Use a temp directory for campaign data."""
    import core.state_manager as sm
    original_root = sm._project_root

    def mock_root():
        return tmp_path

    sm._project_root = mock_root
    (tmp_path / "data" / "campaigns").mkdir(parents=True)
    m = WorldStateManager()
    yield m
    sm._project_root = original_root


def test_create_and_get_campaign(manager):
    c = Campaign(name="Test", party_level=5)
    manager.load_campaign(c.id)
    manager.create_campaign(c)
    got = manager.get_campaign(c.id)
    assert got is not None
    assert got.name == "Test"
    assert got.party_level == 5


def test_create_dungeon_and_rooms(manager):
    campaign = Campaign(name="C", party_level=5)
    manager.load_campaign(campaign.id)
    manager.create_campaign(campaign)
    dungeon = Dungeon(name="D", concept="A test dungeon")
    manager.create_dungeon(dungeon)
    manager.add_edge(Edge(source_id=campaign.id, target_id=dungeon.id, edge_type=EdgeType.CONTAINS))
    room = Room(name="R1", floor_level=0, purpose="Entrance")
    manager.create_room(room)
    manager.add_edge(Edge(source_id=dungeon.id, target_id=room.id, edge_type=EdgeType.CONTAINS))
    rooms = manager.get_rooms_in_dungeon(dungeon.id)
    assert len(rooms) == 1
    assert rooms[0].name == "R1"


def test_get_connections(manager):
    campaign = Campaign(name="C", party_level=5)
    manager.load_campaign(campaign.id)
    manager.create_campaign(campaign)
    d = Dungeon(name="D", concept="Dungeon")
    manager.create_dungeon(d)
    r1 = Room(name="R1", floor_level=0)
    r2 = Room(name="R2", floor_level=0)
    manager.create_room(r1)
    manager.create_room(r2)
    e = Edge(source_id=r1.id, target_id=r2.id, edge_type=EdgeType.CONNECTS_TO, properties={"passage_type": "DOOR"})
    manager.add_edge(e)
    conns = manager.get_connections(r1.id, EdgeType.CONNECTS_TO)
    assert len(conns) == 1
    assert conns[0].target_id == r2.id
    assert conns[0].properties.get("passage_type") == "DOOR"
