"""
Neo4j 持久化封装（可选）：
- 通过环境变量 NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD 配置；缺失则自动禁用。
- 提供 upsert_nodes_edges 供知识图谱写入。
- 轻量封装，便于在扩充/补全接口中调用。
"""
import os
from typing import List, Dict, Optional

try:
	from neo4j import GraphDatabase
except ImportError:  # 未安装 neo4j 时，保持可用但不报错
	GraphDatabase = None


class Neo4jStore:
	def __init__(self):
		self.uri = os.getenv("NEO4J_URI")
		self.user = os.getenv("NEO4J_USER")
		self.password = os.getenv("NEO4J_PASSWORD")
		self.enabled = bool(self.uri and self.user and self.password and GraphDatabase)
		self.driver = None
		if self.enabled:
			self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
		else:
			print("Neo4j 未配置或驱动未安装，持久化将被跳过。")

	def close(self):
		if self.driver:
			self.driver.close()

	def upsert_nodes_edges(self, nodes: List[Dict], edges: List[Dict]) -> bool:
		"""将节点和边写入 Neo4j；若未启用则返回 False。"""
		if not self.enabled:
			return False
		if not nodes and not edges:
			return True
		with self.driver.session() as session:
			if nodes:
				session.execute_write(self._merge_nodes, nodes)
			if edges:
				session.execute_write(self._merge_edges, edges)
		return True

	def fetch_subgraph(self, center: Optional[str] = None, depth: int = 1, limit_nodes: int = 200, limit_edges: int = 800, include_props: bool = False):
		"""按中心节点与深度读取子图，未启用时返回 None。"""
		if not self.enabled:
			return None
		depth = max(0, min(depth, 5))
		limit_nodes = max(1, min(limit_nodes, 2000))
		limit_edges = max(1, min(limit_edges, 5000))
		with self.driver.session() as session:
			return session.execute_read(self._fetch_subgraph, center, depth, limit_nodes, limit_edges, include_props)

	@staticmethod
	def _merge_nodes(tx, nodes: List[Dict]):
		query = (
			"UNWIND $nodes AS n "
			"MERGE (c:Concept {name: n.name}) "
			"SET c.type = coalesce(n.type, 'Concept'), "
			"    c.description = coalesce(n.description, c.description), "
			"    c.bloom_level = coalesce(n.bloom_level, c.bloom_level), "
			"    c.difficulty = coalesce(n.difficulty, c.difficulty), "
			"    c.status = coalesce(n.status, c.status, 'Generated')"
		)
		tx.run(query, nodes=nodes)

	@staticmethod
	def _merge_edges(tx, edges: List[Dict]):
		query = (
			"UNWIND $edges AS e "
			"WITH e WHERE e.source IS NOT NULL AND e.target IS NOT NULL "
			"MATCH (s:Concept {name: e.source}) "
			"MATCH (t:Concept {name: e.target}) "
			"MERGE (s)-[r:PREREQUISITE_OF]->(t) "
			"SET r.confidence = coalesce(e.confidence, r.confidence), "
			"    r.reasoning = coalesce(e.reasoning, r.reasoning)"
		)
		tx.run(query, edges=edges)

	@staticmethod
	def _fetch_subgraph(tx, center: Optional[str], depth: int, limit_nodes: int, limit_edges: int, include_props: bool):
		"""读取中心节点的邻域子图；若 center 为空则随机采样部分节点。"""
		if include_props:
			node_projection = "{name:n.name, type:n.type, bloom_level:n.bloom_level, difficulty:n.difficulty, status:n.status, description:n.description}"
			edge_projection = "{source:startNode(r).name, target:endNode(r).name, relation:type(r), confidence:r.confidence, reasoning:r.reasoning}"
		else:
			node_projection = "{name:n.name, type:n.type, bloom_level:n.bloom_level, difficulty:n.difficulty, status:n.status}"
			edge_projection = "{source:startNode(r).name, target:endNode(r).name, relation:type(r)}"
		# Neo4j 5+ 对模式中的参数有更严格限制，这里将深度与上限值内联为字面量
		depth = int(depth)
		limit_nodes = int(limit_nodes)
		limit_edges = int(limit_edges)
		if center:
			query = (
				"MATCH (c:Concept {name: $center}) "
				f"MATCH p=(c)-[r:PREREQUISITE_OF*0..{depth}]-(n) "
				"WITH collect(DISTINCT c)+collect(DISTINCT n) AS nodes, "
				"     collect(DISTINCT relationships(p)) AS rel_lists "
				"WITH nodes, reduce(acc = [], rlist IN rel_lists | acc + rlist) AS rels "
				f"WITH nodes[0..{limit_nodes}] AS nodes, rels[0..{limit_edges}] AS rels "
				"RETURN [n IN nodes | " + node_projection + "] AS nodes, "
				"       [r IN rels  | " + edge_projection + "] AS edges"
			)
		else:
			query = (
				"MATCH (c:Concept) "
				f"WITH c ORDER BY rand() LIMIT {limit_nodes} "
				f"MATCH p=(c)-[r:PREREQUISITE_OF*0..{depth}]-(n) "
				"WITH collect(DISTINCT c)+collect(DISTINCT n) AS nodes, "
				"     collect(DISTINCT relationships(p)) AS rel_lists "
				"WITH nodes, reduce(acc = [], rlist IN rel_lists | acc + rlist) AS rels "
				f"WITH nodes[0..{limit_nodes}] AS nodes, rels[0..{limit_edges}] AS rels "
				"RETURN [n IN nodes | " + node_projection + "] AS nodes, "
				"       [r IN rels  | " + edge_projection + "] AS edges"
			)
		result = tx.run(query, center=center).single()
		return {
			'nodes': result['nodes'] if result else [],
			'edges': result['edges'] if result else []
		}


def get_store_if_configured() -> Optional[Neo4jStore]:
	store = Neo4jStore()
	return store if store.enabled else None
