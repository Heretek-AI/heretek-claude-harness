"""Task dependency graph with cycle detection and graph algorithms."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

class GraphNodeType(Enum):
    TASK = "task"
    MILESTONE = "milestone"
    BARRIER = "barrier"

class EdgeType(Enum):
    DEPENDENCY = "dependency"
    BLOCKS = "blocks"
    WAITS_FOR = "waits_for"
    PART_OF = "part_of"

@dataclass
class GraphNode:
    node_id: str
    node_type: GraphNodeType = GraphNodeType.TASK
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    in_degree: int = 0
    out_degree: int = 0
    depth: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "in_degree": self.in_degree,
            "out_degree": self.out_degree,
            "depth": self.depth,
        }

@dataclass
class GraphEdge:
    edge_id: str
    source_id: str
    target_id: str
    edge_type: EdgeType = EdgeType.DEPENDENCY
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type.value,
            "weight": self.weight,
        }

class TaskGraph:
    def __init__(self, max_nodes: int = 10000):
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}
        self._adjacency: dict[str, set[str]] = {}
        self._reverse_adjacency: dict[str, set[str]] = {}
        self._max_nodes = max_nodes
        self._cycle_cache: list[list[str]] | None = None
        self._topo_order_cache: list[str] | None = None
        self._cycle_resolution_strategy: str = "notify"
        self._last_cycle_detection: datetime | None = None

    def add_node(
        self,
        node_id: str,
        node_type: GraphNodeType = GraphNodeType.TASK,
        metadata: dict[str, Any] | None = None,
    ) -> GraphNode | None:
        if len(self._nodes) >= self._max_nodes:
            return None
        if node_id in self._nodes:
            return self._nodes[node_id]
        node = GraphNode(node_id=node_id, node_type=node_type, metadata=metadata or {})
        self._nodes[node_id] = node
        self._adjacency[node_id] = set()
        self._reverse_adjacency[node_id] = set()
        self._cycle_cache = None
        self._topo_order_cache = None
        return node

    def remove_node(self, node_id: str) -> bool:
        if node_id not in self._nodes:
            return False
        for edge_id in list(self._edges.keys()):
            edge = self._edges[edge_id]
            if edge.source_id == node_id or edge.target_id == node_id:
                self.remove_edge(edge_id)
        del self._nodes[node_id]
        if node_id in self._adjacency:
            del self._adjacency[node_id]
        if node_id in self._reverse_adjacency:
            del self._reverse_adjacency[node_id]
        self._cycle_cache = None
        self._topo_order_cache = None
        return True

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def node_exists(self, node_id: str) -> bool:
        return node_id in self._nodes

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType = EdgeType.DEPENDENCY,
        weight: float = 1.0,
    ) -> GraphEdge | None:
        if source_id not in self._nodes or target_id not in self._nodes:
            return None
        if source_id == target_id:
            return None
        edge_id = str(uuid.uuid4())
        edge = GraphEdge(
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
        )
        self._edges[edge_id] = edge
        self._adjacency[source_id].add(target_id)
        self._reverse_adjacency[target_id].add(source_id)
        self._nodes[source_id].out_degree += 1
        self._nodes[target_id].in_degree += 1
        self._cycle_cache = None
        self._topo_order_cache = None
        return edge

    def remove_edge(self, edge_id: str) -> bool:
        if edge_id not in self._edges:
            return False
        edge = self._edges[edge_id]
        if edge.source_id in self._adjacency:
            self._adjacency[edge.source_id].discard(edge.target_id)
        if edge.target_id in self._reverse_adjacency:
            self._reverse_adjacency[edge.target_id].discard(edge.source_id)
        if edge.source_id in self._nodes:
            self._nodes[edge.source_id].out_degree = max(
                0, self._nodes[edge.source_id].out_degree - 1
            )
        if edge.target_id in self._nodes:
            self._nodes[edge.target_id].in_degree = max(
                0, self._nodes[edge.target_id].in_degree - 1
            )
        del self._edges[edge_id]
        self._cycle_cache = None
        self._topo_order_cache = None
        return True

    def get_outgoing_edges(self, node_id: str) -> list[GraphEdge]:
        return [e for e in self._edges.values() if e.source_id == node_id]

    def get_incoming_edges(self, node_id: str) -> list[GraphEdge]:
        return [e for e in self._edges.values() if e.target_id == node_id]

    def detect_cycles(self) -> dict[str, Any]:
        sccs = self._tarjan_scc()
        cycles = [scc for scc in sccs if len(scc) > 1]
        self._cycle_cache = cycles
        self._last_cycle_detection = datetime.now(UTC)
        return {"has_cycles": len(cycles) > 0, "cycles": cycles, "cycle_count": len(cycles)}

    def get_cycle_detection_timestamp(self) -> datetime | None:
        return self._last_cycle_detection

    def resolve_cycle(self, cycle: list[str], strategy: str | None = None) -> dict[str, Any]:
        strategy = strategy or self._cycle_resolution_strategy
        if strategy == "notify":
            return {"resolved": False, "action": "notify", "details": "Steward notified of cycle"}
        if strategy == "remove":
            return self._resolve_cycle_by_remove(cycle)
        if strategy == "break":
            return self._resolve_cycle_by_break(cycle)
        return {"resolved": False, "action": "none", "details": "Unknown strategy"}

    def _resolve_cycle_by_remove(self, cycle: list[str]) -> dict[str, Any]:
        if len(cycle) < 2:
            return {"resolved": False, "action": "remove", "details": "No edge to remove"}
        source, target = cycle[0], cycle[1]
        for edge_id, edge in list(self._edges.items()):
            if edge.source_id == source and edge.target_id == target:
                self.remove_edge(edge_id)
                return {"resolved": True, "action": "remove", "details": f"Removed edge {edge_id}"}
        return {"resolved": False, "action": "remove", "details": "No edge to remove"}

    def _resolve_cycle_by_break(self, cycle: list[str]) -> dict[str, Any]:
        if cycle:
            self.remove_node(cycle[0])
            return {"resolved": True, "action": "break", "details": f"Removed node {cycle[0]}"}
        return {"resolved": False, "action": "break", "details": "No node to remove"}

    def get_topological_order(self) -> list[str]:
        if self._topo_order_cache is not None:
            return self._topo_order_cache
        in_degree = {node_id: self._nodes[node_id].in_degree for node_id in self._nodes}
        queue = [n for n, d in in_degree.items() if d == 0]
        result = []
        while queue:
            queue.sort(
                key=lambda x: (
                    -self._nodes.get(x, GraphNode(x)).priority
                    if hasattr(self._nodes.get(x), "priority")
                    else 0
                )
            )
            node = queue.pop(0)
            result.append(node)
            for neighbor in self._adjacency.get(node, set()):
                if neighbor in in_degree:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
        if len(result) != len(self._nodes):
            raise ValueError("Graph contains cycles")
        self._topo_order_cache = result
        return result

    def calculate_critical_path(self) -> dict[str, Any]:
        if not self._nodes:
            return {"critical_path": [], "path_length": 0.0, "estimated_duration": 0.0}
        dist: dict[str, float] = dict.fromkeys(self._nodes, 0.0)
        prev: dict[str, str | None] = dict.fromkeys(self._nodes)
        for node_id in self.get_topological_order():
            for edge in self.get_outgoing_edges(node_id):
                weight = edge.weight
                new_dist = dist[node_id] + weight
                if new_dist > dist[edge.target_id]:
                    dist[edge.target_id] = new_dist
                    prev[edge.target_id] = node_id
        max_node = max(dist, key=dist.get)
        path = []
        current = max_node
        while current is not None:
            path.append(current)
            current = prev[current]
        path.reverse()
        return {
            "critical_path": path,
            "path_length": len(path),
            "estimated_duration": dist[max_node],
        }

    def get_graph_metrics(self) -> dict[str, Any]:
        if not self._nodes:
            return {
                "node_count": 0,
                "edge_count": 0,
                "max_depth": 0,
                "avg_depth": 0.0,
                "complexity_score": 0.0,
                "parallelism_factor": 0.0,
            }
        depths = [n.depth for n in self._nodes.values()]
        max_depth = max(depths) if depths else 0
        avg_depth = sum(depths) / len(depths) if depths else 0.0
        node_count = len(self._nodes)
        edge_count = len(self._edges)
        complexity_score = (edge_count / node_count) if node_count > 0 else 0.0
        sources = sum(1 for n in self._nodes.values() if n.in_degree == 0)
        sinks = sum(1 for n in self._nodes.values() if n.out_degree == 0)
        parallelism_factor = (sources * sinks) / node_count if node_count > 0 else 0.0
        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "max_depth": max_depth,
            "avg_depth": avg_depth,
            "complexity_score": complexity_score,
            "parallelism_factor": parallelism_factor,
        }

    def calculate_load(self) -> float:
        return len(self._edges) / self._max_nodes if self._max_nodes > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges.values()],
            "max_nodes": self._max_nodes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskGraph":
        graph = cls(max_nodes=data.get("max_nodes", 10000))
        for node_data in data.get("nodes", []):
            graph.add_node(
                node_data["node_id"],
                GraphNodeType(node_data.get("node_type", "task")),
                node_data.get("metadata"),
            )
        for edge_data in data.get("edges", []):
            graph.add_edge(
                edge_data["source_id"],
                edge_data["target_id"],
                EdgeType(edge_data.get("edge_type", "dependency")),
                edge_data.get("weight", 1.0),
            )
        return graph

    def _tarjan_scc(self) -> list[list[str]]:
        index = 0
        stack: list[str] = []
        on_stack: set[str] = set()
        indices: dict[str, int] = {}
        lowlinks: dict[str, int] = {}
        sccs: list[list[str]] = []

        def strongconnect(node_id: str) -> None:
            nonlocal index
            indices[node_id] = index
            lowlinks[node_id] = index
            index += 1
            stack.append(node_id)
            on_stack.add(node_id)
            for neighbor in self._adjacency.get(node_id, set()):
                if neighbor not in indices:
                    strongconnect(neighbor)
                    lowlinks[node_id] = min(lowlinks[node_id], lowlinks[neighbor])
                elif neighbor in on_stack:
                    lowlinks[node_id] = min(lowlinks[node_id], indices[neighbor])
            if lowlinks[node_id] == indices[node_id]:
                scc: list[str] = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == node_id:
                        break
                sccs.append(scc)

        for node_id in self._nodes:
            if node_id not in indices:
                strongconnect(node_id)
        return sccs
