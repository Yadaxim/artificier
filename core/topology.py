"""Dungeon connection graph: create CONNECTS_TO edges from Claude output."""

from uuid import UUID

from models.models import Edge, EdgeType

from core.state_manager import WorldStateManager


def create_edges_from_topology(
    manager: WorldStateManager,
    connections: list[dict],
) -> list[Edge]:
    """
    Create CONNECTS_TO edges from a list of connection dicts.
    Each dict: from_room_id (str), to_room_id (str), passage_type, length.
    """
    created = []
    for c in connections:
        try:
            from_id = UUID(c["from_room_id"]) if isinstance(c["from_room_id"], str) else c["from_room_id"]
            to_id = UUID(c["to_room_id"]) if isinstance(c["to_room_id"], str) else c["to_room_id"]
        except (KeyError, TypeError, ValueError):
            continue
        passage_type = c.get("passage_type", "DOOR")
        length = c.get("length", "medium")
        edge = Edge(
            source_id=from_id,
            target_id=to_id,
            edge_type=EdgeType.CONNECTS_TO,
            properties={"passage_type": passage_type, "length": length},
        )
        manager.add_edge(edge)
        created.append(edge)
    return created
