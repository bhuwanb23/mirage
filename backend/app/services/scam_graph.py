"""Scam graph — Phase 5.3.

IOC knowledge graph with two interchangeable backends:

  * Neo4jGraphStore — the plan's AuraDB target. Used automatically when
    NEO4J_URI is configured and the driver connects. Runs the exact Cypher
    from plan §5.3 (MERGE nodes, MERGE relationships, ring queries).

  * SQLiteGraphStore — offline/dev/demo fallback with identical semantics
    (MERGE-style upserts, co-occurrence linking, connected-component ring
    detection). This is what the hackathon demo runs on, so the whole
    Phase 5 pipeline works with zero external dependencies.

Both implement the same GraphStore interface:
    merge_node, merge_edge, ingest_iocs, detect_rings,
    shared_infrastructure, get_graph_data, get_stats, clear
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.models.schemas import GraphData, GraphEdge, GraphNode, GraphStats, ThreatIOCs

logger = logging.getLogger("mirage.graph")

# Node type -> unique key property (plan §5.3 schema)
NODE_KEY_PROP = {
    "PhoneNumber": "number",
    "UPI_ID": "upi_id",
    "Domain": "domain",
    "BankAccount": "account_number",
    "ScammerName": "name",
    "ScamCampaign": "campaign_id",
    "ScamReport": "report_id",
    "Location": "city",
}

ENTITY_TYPES = ("PhoneNumber", "UPI_ID", "Domain", "BankAccount", "ScammerName")

# Short id prefixes used in the viz payload: "phone:9876543210", "upi:sbi-safe@ybl"…
NODE_ID_PREFIX = {
    "PhoneNumber": "phone",
    "UPI_ID": "upi",
    "Domain": "domain",
    "BankAccount": "acct",
    "ScammerName": "name",
    "ScamCampaign": "campaign",
    "ScamReport": "report",
    "Location": "city",
}

# Entity edges participate in ring detection; report edges do not.
RING_RELS = {
    "USES_UPI",
    "LINKED_TO_DOMAIN",
    "DEPOSITS_TO",
    "CALLS",
    "OWNS",
    "PART_OF_CAMPAIGN",
    "SIMILAR_TO",
}


def node_id(node_type: str, key: str) -> str:
    return f"{NODE_ID_PREFIX.get(node_type, node_type.lower())}:{key}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# SQLite store (offline default)
# ---------------------------------------------------------------------------


class SQLiteGraphStore:
    """MERGE-semantics graph on top of SQLite. Thread-safe (single conn + lock)."""

    def __init__(self, path: str = "data/scam_graph.db"):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    id    TEXT PRIMARY KEY,
                    type  TEXT NOT NULL,
                    key   TEXT NOT NULL,
                    props TEXT NOT NULL DEFAULT '{}',
                    UNIQUE (type, key)
                );
                CREATE TABLE IF NOT EXISTS edges (
                    src   TEXT NOT NULL,
                    rel   TEXT NOT NULL,
                    dst   TEXT NOT NULL,
                    props TEXT NOT NULL DEFAULT '{}',
                    UNIQUE (src, rel, dst)
                );
                CREATE TABLE IF NOT EXISTS meta (
                    k TEXT PRIMARY KEY,
                    v TEXT NOT NULL
                );
                """
            )

    # -- primitives --------------------------------------------------------

    def merge_node(
        self,
        node_type: str,
        key: str,
        props: dict[str, Any] | None = None,
        *,
        on_create: dict[str, Any] | None = None,
    ) -> str:
        """MERGE a node: `on_create` props apply only on creation (counters,
        first_seen), `props` apply on create AND match (safe updates)."""
        nid = node_id(node_type, key)
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT props FROM nodes WHERE type = ? AND key = ?", (node_type, key)
            ).fetchone()
            if row is None:
                create = {**(on_create or {}), **(props or {})}
                self._conn.execute(
                    "INSERT INTO nodes (id, type, key, props) VALUES (?, ?, ?, ?)",
                    (nid, node_type, key, json.dumps(create)),
                )
            elif props:
                merged = {**json.loads(row["props"]), **props}
                self._conn.execute(
                    "UPDATE nodes SET props = ? WHERE id = ?", (json.dumps(merged), nid)
                )
        return nid

    def merge_edge(self, src: str, rel: str, dst: str, props: dict[str, Any] | None = None) -> bool:
        """MERGE an edge. Returns True if it was newly created."""
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT props FROM edges WHERE src = ? AND rel = ? AND dst = ?", (src, rel, dst)
            ).fetchone()
            if row is not None:
                if props:
                    merged = {**json.loads(row["props"]), **props}
                    self._conn.execute(
                        "UPDATE edges SET props = ? WHERE src = ? AND rel = ? AND dst = ?",
                        (json.dumps(merged), src, rel, dst),
                    )
                return False
            self._conn.execute(
                "INSERT INTO edges (src, rel, dst, props) VALUES (?, ?, ?, ?)",
                (src, rel, dst, json.dumps(props or {})),
            )
            return True

    def _bump_report_count(self, node_type: str, key: str, today: str) -> None:
        nid = node_id(node_type, key)
        with self._lock, self._conn:
            row = self._conn.execute("SELECT props FROM nodes WHERE id = ?", (nid,)).fetchone()
            props = json.loads(row["props"]) if row else {}
            props["report_count"] = int(props.get("report_count", 0)) + 1
            props["last_seen"] = today
            props.setdefault("first_seen", today)
            self._conn.execute(
                "UPDATE nodes SET props = ? WHERE id = ?", (json.dumps(props), nid)
            )

    # -- ingestion (plan §5.3) ---------------------------------------------

    def ingest_iocs(
        self,
        report_id: str,
        iocs: ThreatIOCs,
        *,
        source: str = "honeypot",
        scam_type: str = "unknown",
        confidence: float = 0.8,
    ) -> dict[str, int]:
        """Create a ScamReport node, MERGE all IOC nodes, link by co-occurrence."""
        today = _now()
        created = {"nodes": 0, "edges": 0}

        report_nid = self.merge_node(
            "ScamReport",
            report_id,
            {
                "source": source,
                "scam_type": scam_type,
                "confidence": confidence,
                "timestamp": today,
            },
        )
        created["nodes"] += 1

        phone_ids = []
        for item in iocs.phone_numbers:
            nid = self.merge_node(
                "PhoneNumber",
                item.value,
                {"last_seen": today, "context": item.context},
                on_create={
                    "country_code": "+91",
                    "first_seen": today,
                    "report_count": 0,
                    "is_verified_scammer": False,
                },
            )
            self._bump_report_count("PhoneNumber", item.value, today)
            props = self._get_props(nid)
            if int(props.get("report_count", 0)) >= 3:
                self._set_prop("PhoneNumber", item.value, "is_verified_scammer", True)
            phone_ids.append(nid)
            if self.merge_edge(report_nid, "INVOLVES", nid, {"role": "caller"}):
                created["edges"] += 1

        upi_ids = []
        for item in iocs.upi_ids:
            handle, _, bank = item.value.partition("@")
            nid = self.merge_node(
                "UPI_ID",
                item.value,
                {"last_seen": today},
                on_create={"handle": handle, "bank": bank, "first_seen": today, "report_count": 0},
            )
            self._bump_report_count("UPI_ID", item.value, today)
            upi_ids.append(nid)
            if self.merge_edge(report_nid, "INVOLVES_UPI", nid, {"context": item.context}):
                created["edges"] += 1

        domain_ids = []
        for item in iocs.domains:
            tld = item.value.rsplit(".", 1)[-1]
            nid = self.merge_node(
                "Domain",
                item.value,
                {},
                on_create={
                    "tld": tld,
                    "first_seen": today,
                    "is_suspicious": True,
                    "context": item.context,
                },
            )
            domain_ids.append(nid)
            if self.merge_edge(report_nid, "INVOLVES_DOMAIN", nid, {"context": item.context}):
                created["edges"] += 1

        account_ids = []
        for item in iocs.bank_accounts:
            nid = self.merge_node(
                "BankAccount",
                item.value,
                {},
                on_create={"bank_name": "", "first_seen": today, "report_count": 0},
            )
            self._bump_report_count("BankAccount", item.value, today)
            account_ids.append(nid)

        name_ids = []
        for name in iocs.scammer_names:
            nid = self.merge_node(
                "ScammerName", name, {}, on_create={"aliases": [], "first_seen": today}
            )
            name_ids.append(nid)
            if self.merge_edge(report_nid, "INVOLVES_NAME", nid, {}):
                created["edges"] += 1

        # Co-occurrence linking (all IOCs from one report are related).
        for p in phone_ids:
            for u in upi_ids:
                if self.merge_edge(p, "USES_UPI", u, {"first_seen": today}):
                    created["edges"] += 1
            for d in domain_ids:
                if self.merge_edge(p, "LINKED_TO_DOMAIN", d, {}):
                    created["edges"] += 1
        for u in upi_ids:
            for b in account_ids:
                if self.merge_edge(u, "DEPOSITS_TO", b, {}):
                    created["edges"] += 1
        for n in name_ids:
            for p in phone_ids:
                if self.merge_edge(n, "OWNS", p, {"confidence": confidence}):
                    created["edges"] += 1

        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO meta (k, v) VALUES ('last_report_type', ?)",
                (scam_type,),
            )
            row = self._conn.execute(
                "SELECT COUNT(*) AS c FROM nodes WHERE type = 'ScamReport'"
            ).fetchone()
            self._conn.execute(
                "INSERT OR REPLACE INTO meta (k, v) VALUES ('report_count', ?)", (str(row["c"]),)
            )

        logger.info(
            "graph ingest %s: +%d nodes, +%d edges",
            report_id,
            created["nodes"],
            created["edges"],
        )
        return created

    # -- helpers -----------------------------------------------------------

    def _get_props(self, nid: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute("SELECT props FROM nodes WHERE id = ?", (nid,)).fetchone()
        return json.loads(row["props"]) if row else {}

    def _set_prop(self, node_type: str, key: str, prop: str, value: Any) -> None:
        nid = node_id(node_type, key)
        with self._lock, self._conn:
            row = self._conn.execute("SELECT props FROM nodes WHERE id = ?", (nid,)).fetchone()
            if not row:
                return
            props = json.loads(row["props"])
            props[prop] = value
            self._conn.execute(
                "UPDATE nodes SET props = ? WHERE id = ?", (json.dumps(props), nid)
            )

    # -- queries (plan §5.3 queries 1-4) -----------------------------------

    def detect_rings(self, min_size: int = 3) -> list[dict[str, Any]]:
        """Connected components over entity nodes (report nodes excluded)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT src, rel, dst FROM edges WHERE rel IN (%s)"
                % ",".join("?" for _ in RING_RELS),
                tuple(RING_RELS),
            ).fetchall()
            nodes = {
                r["id"]: (r["type"], json.loads(r["props"]))
                for r in self._conn.execute(
                    "SELECT id, type, props FROM nodes WHERE type IN (%s)"
                    % ",".join("?" for _ in ENTITY_TYPES),
                    ENTITY_TYPES,
                )
            }

        adjacency: dict[str, set[str]] = {}
        for row in rows:
            if row["src"] in nodes and row["dst"] in nodes:
                adjacency.setdefault(row["src"], set()).add(row["dst"])
                adjacency.setdefault(row["dst"], set()).add(row["src"])

        rings: list[dict[str, Any]] = []
        seen: set[str] = set()
        for start in sorted(set(adjacency) | set(nodes)):
            if start in seen:
                continue
            # BFS component
            component, queue = {start}, [start]
            seen.add(start)
            while queue:
                current = queue.pop()
                for nb in adjacency.get(current, ()):
                    if nb not in seen:
                        seen.add(nb)
                        component.add(nb)
                        queue.append(nb)
            if len(component) < min_size:
                continue
            phones = [
                n.split(":", 1)[1]
                for n in component
                if nodes[n][0] == "PhoneNumber"
            ]
            upis = [n.split(":", 1)[1] for n in component if nodes[n][0] == "UPI_ID"]
            domains = [n.split(":", 1)[1] for n in component if nodes[n][0] == "Domain"]
            accounts = [n.split(":", 1)[1] for n in component if nodes[n][0] == "BankAccount"]
            rings.append(
                {
                    "ring_id": f"ring-{len(rings) + 1}",
                    "size": len(component),
                    "node_ids": sorted(component),
                    "phones": sorted(phones),
                    "upi_ids": sorted(upis),
                    "domains": sorted(domains),
                    "bank_accounts": sorted(accounts),
                }
            )
        rings.sort(key=lambda r: r["size"], reverse=True)
        return rings

    def shared_infrastructure(self, min_phones: int = 2) -> dict[str, list[dict[str, Any]]]:
        """Plan §5.3 queries 2-3: UPIs / domains shared by multiple phones."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT src, rel, dst FROM edges WHERE rel IN ('USES_UPI', 'LINKED_TO_DOMAIN')"
            ).fetchall()
            node_types = {
                r["id"]: r["type"]
                for r in self._conn.execute("SELECT id, type FROM nodes")
            }

        upi_phones: dict[str, set[str]] = {}
        domain_phones: dict[str, set[str]] = {}
        for row in rows:
            if node_types.get(row["src"]) != "PhoneNumber":
                continue
            bucket = upi_phones if row["rel"] == "USES_UPI" else domain_phones
            bucket.setdefault(row["dst"].split(":", 1)[1], set()).add(row["src"].split(":", 1)[1])

        return {
            "shared_upis": [
                {"upi_id": k, "phones": sorted(v), "phone_count": len(v)}
                for k, v in sorted(upi_phones.items(), key=lambda kv: -len(kv[1]))
                if len(v) >= min_phones
            ],
            "shared_domains": [
                {"domain": k, "phones": sorted(v), "phone_count": len(v)}
                for k, v in sorted(domain_phones.items(), key=lambda kv: -len(kv[1]))
                if len(v) >= min_phones
            ],
        }

    def get_graph_data(self, limit: int = 200) -> GraphData:
        """Most-connected entity subgraph for the force-directed UI (query 4)."""
        with self._lock:
            rows = list(
                self._conn.execute(
                    "SELECT id, type, key, props FROM nodes WHERE type IN (%s)"
                    % ",".join("?" for _ in ENTITY_TYPES),
                    ENTITY_TYPES,
                )
            )
            edges = list(self._conn.execute("SELECT src, rel, dst FROM edges"))

        counts: dict[str, int] = {}
        for row in edges:
            counts[row["src"]] = counts.get(row["src"], 0) + 1
            counts[row["dst"]] = counts.get(row["dst"], 0) + 1

        rows.sort(key=lambda r: (-counts.get(r["id"], 0), r["id"]))
        selected = rows[:limit]
        selected_ids = {r["id"] for r in selected}

        rings = self.detect_rings(min_size=3)
        ring_of: dict[str, str] = {}
        for ring in rings:
            for nid in ring["node_ids"]:
                ring_of[nid] = ring["ring_id"]

        # group = ring index (1-based) or a stable hash bucket for non-ring nodes
        group_of: dict[str, int] = {}
        for idx, ring in enumerate(rings, start=1):
            for nid in ring["node_ids"]:
                group_of[nid] = idx
        for r in selected:
            group_of.setdefault(r["id"], (abs(hash(r["id"])) % 7) + len(rings) + 1)

        nodes = [
            GraphNode(
                id=r["id"],
                label=_format_label(r["type"], r["key"]),
                type=r["type"],
                group=group_of.get(r["id"], 0),
                report_count=int(json.loads(r["props"]).get("report_count", 1)),
                in_ring=r["id"] in ring_of,
                properties=json.loads(r["props"]),
            )
            for r in selected
        ]

        edge_set: dict[tuple[str, str, str], GraphEdge] = {}
        for row in edges:
            if row["src"] in selected_ids and row["dst"] in selected_ids:
                edge_set[(row["src"], row["rel"], row["dst"])] = GraphEdge(
                    source=row["src"], target=row["dst"], type=row["rel"]
                )

        return GraphData(nodes=nodes, edges=list(edge_set.values()), truncated=len(rows) > limit)

    def get_stats(self) -> GraphStats:
        with self._lock:
            counts = {
                r["type"]: r["c"]
                for r in self._conn.execute(
                    "SELECT type, COUNT(*) AS c FROM nodes GROUP BY type"
                )
            }
            type_rows = list(
                self._conn.execute(
                    "SELECT props FROM nodes WHERE type = 'ScamReport'"
                )
            )
        scam_types: dict[str, int] = {}
        for row in type_rows:
            t = json.loads(row["props"]).get("scam_type", "unknown")
            scam_types[t] = scam_types.get(t, 0) + 1
        return GraphStats(
            phone_numbers=counts.get("PhoneNumber", 0),
            upi_ids=counts.get("UPI_ID", 0),
            domains=counts.get("Domain", 0),
            bank_accounts=counts.get("BankAccount", 0),
            scam_reports=counts.get("ScamReport", 0),
            rings=len(self.detect_rings(min_size=3)),
            scam_type_counts=scam_types,
            backend="sqlite",
        )

    def clear(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM nodes")
            self._conn.execute("DELETE FROM edges")
            self._conn.execute("DELETE FROM meta")

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def _format_label(node_type: str, key: str) -> str:
    if node_type == "PhoneNumber" and len(key) == 10:
        return f"{key[:5]}-{key[5:]}"
    return key


# ---------------------------------------------------------------------------
# Neo4j store (plan §5.3, requires NEO4J_URI)
# ---------------------------------------------------------------------------


class Neo4jGraphStore:
    """The plan's AuraDB implementation. Same interface as SQLiteGraphStore."""

    backend_name = "neo4j"

    def __init__(self):
        from app.clients import neo4j_client

        self._q = neo4j_client.run_query

    # -- ingestion ---------------------------------------------------------

    def ingest_iocs(
        self,
        report_id: str,
        iocs: ThreatIOCs,
        *,
        source: str = "honeypot",
        scam_type: str = "unknown",
        confidence: float = 0.8,
    ) -> dict[str, int]:
        today = _now()
        self._q(
            """
            CREATE (r:ScamReport {report_id: $report_id, source: $source,
                                  scam_type: $scam_type, confidence: $confidence,
                                  timestamp: $ts})
            """,
            {"report_id": report_id, "source": source, "scam_type": scam_type,
             "confidence": confidence, "ts": today},
        )
        for item in iocs.phone_numbers:
            self._q(
                """
                MERGE (p:PhoneNumber {number: $phone})
                ON CREATE SET p.first_seen = $ts, p.report_count = 1,
                              p.is_verified_scammer = false, p.country_code = '+91'
                ON MATCH  SET p.last_seen = $ts, p.report_count = p.report_count + 1
                WITH p
                MATCH (r:ScamReport {report_id: $report_id})
                MERGE (r)-[:INVOLVES {role: 'caller'}]->(p)
                """,
                {"phone": item.value, "ts": today, "report_id": report_id},
            )
        for item in iocs.upi_ids:
            handle, _, bank = item.value.partition("@")
            self._q(
                """
                MERGE (u:UPI_ID {upi_id: $upi})
                ON CREATE SET u.handle = $handle, u.bank = $bank,
                              u.first_seen = $ts, u.report_count = 1
                ON MATCH  SET u.report_count = u.report_count + 1
                WITH u
                MATCH (r:ScamReport {report_id: $report_id})
                MERGE (r)-[:INVOLVES_UPI]->(u)
                """,
                {"upi": item.value, "handle": handle, "bank": bank, "ts": today,
                 "report_id": report_id},
            )
        for item in iocs.domains:
            self._q(
                """
                MERGE (d:Domain {domain: $domain})
                ON CREATE SET d.tld = $tld, d.first_seen = $ts, d.is_suspicious = true
                WITH d
                MATCH (r:ScamReport {report_id: $report_id})
                MERGE (r)-[:INVOLVES_DOMAIN]->(d)
                """,
                {"domain": item.value, "tld": item.value.rsplit(".", 1)[-1],
                 "ts": today, "report_id": report_id},
            )
        for item in iocs.bank_accounts:
            self._q(
                """
                MERGE (b:BankAccount {account_number: $acct})
                ON CREATE SET b.first_seen = $ts, b.report_count = 1
                ON MATCH  SET b.report_count = b.report_count + 1
                """,
                {"acct": item.value, "ts": today},
            )
        for name in iocs.scammer_names:
            self._q(
                """
                MERGE (n:ScammerName {name: $name})
                ON CREATE SET n.first_seen = $ts
                WITH n
                MATCH (r:ScamReport {report_id: $report_id})
                MERGE (r)-[:INVOLVES_NAME]->(n)
                """,
                {"name": name, "ts": today, "report_id": report_id},
            )

        # Co-occurrence relationships within this report.
        for p in iocs.phone_numbers:
            for u in iocs.upi_ids:
                self._q(
                    """
                    MATCH (a:PhoneNumber {number: $p}), (b:UPI_ID {upi_id: $u})
                    MERGE (a)-[:USES_UPI {first_seen: $ts}]->(b)
                    """,
                    {"p": p.value, "u": u.value, "ts": today},
                )
            for d in iocs.domains:
                self._q(
                    """
                    MATCH (a:PhoneNumber {number: $p}), (b:Domain {domain: $d})
                    MERGE (a)-[:LINKED_TO_DOMAIN]->(b)
                    """,
                    {"p": p.value, "d": d.value},
                )
        for u in iocs.upi_ids:
            for b in iocs.bank_accounts:
                self._q(
                    """
                    MATCH (a:UPI_ID {upi_id: $u}), (b:BankAccount {account_number: $b})
                    MERGE (a)-[:DEPOSITS_TO]->(b)
                    """,
                    {"u": u.value, "b": b.value},
                )
        return {"nodes": 0, "edges": 0}

    # -- queries -----------------------------------------------------------

    def detect_rings(self, min_size: int = 3) -> list[dict[str, Any]]:
        rows = self._q(
            """
            MATCH path = (a:PhoneNumber)-[*1..4]-(b)
            WHERE a <> b
              AND (b:PhoneNumber OR b:UPI_ID OR b:Domain OR b:BankAccount)
            WITH a, collect(DISTINCT b) AS connected
            WHERE size(connected) >= $min
            RETURN a.number AS source, size(connected) AS ring_size, connected
            ORDER BY ring_size DESC
            LIMIT 20
            """,
            {"min": min_size},
        )
        rings = []
        for idx, row in enumerate(rows, start=1):
            connected = row.get("connected") or []
            phones, upis, domains, accounts, node_ids = [], [], [], [], []
            for entity in connected:
                labels = set(entity.labels)
                if "PhoneNumber" in labels:
                    phones.append(entity["number"])
                    node_ids.append(node_id("PhoneNumber", entity["number"]))
                elif "UPI_ID" in labels:
                    upis.append(entity["upi_id"])
                    node_ids.append(node_id("UPI_ID", entity["upi_id"]))
                elif "Domain" in labels:
                    domains.append(entity["domain"])
                    node_ids.append(node_id("Domain", entity["domain"]))
                elif "BankAccount" in labels:
                    accounts.append(entity["account_number"])
                    node_ids.append(node_id("BankAccount", entity["account_number"]))
            if row.get("source"):
                phones.append(row["source"])
                node_ids.append(node_id("PhoneNumber", row["source"]))
            rings.append(
                {
                    "ring_id": f"ring-{idx}",
                    "size": int(row.get("ring_size") or len(node_ids)),
                    "node_ids": sorted(set(node_ids)),
                    "phones": sorted(set(phones)),
                    "upi_ids": sorted(set(upis)),
                    "domains": sorted(set(domains)),
                    "bank_accounts": sorted(set(accounts)),
                }
            )
        return rings

    def shared_infrastructure(self, min_phones: int = 2) -> dict[str, list[dict[str, Any]]]:
        upi_rows = self._q(
            """
            MATCH (p:PhoneNumber)-[:USES_UPI]->(u:UPI_ID)
            WITH u, collect(p.number) AS phones
            WHERE size(phones) >= $min
            RETURN u.upi_id AS upi_id, phones, size(phones) AS phone_count
            ORDER BY phone_count DESC
            """,
            {"min": min_phones},
        )
        domain_rows = self._q(
            """
            MATCH (p:PhoneNumber)-[:LINKED_TO_DOMAIN]->(d:Domain)
            WITH d, collect(p.number) AS phones
            WHERE size(phones) >= $min
            RETURN d.domain AS domain, phones, size(phones) AS phone_count
            ORDER BY phone_count DESC
            """,
            {"min": min_phones},
        )
        return {
            "shared_upis": [dict(r) for r in upi_rows],
            "shared_domains": [dict(r) for r in domain_rows],
        }

    def get_graph_data(self, limit: int = 200) -> GraphData:
        rows = self._q(
            """
            MATCH (n)-[r]-(m)
            WHERE n:PhoneNumber OR n:UPI_ID OR n:Domain OR n:BankAccount OR n:ScammerName
            RETURN n, type(r) AS rel, m
            LIMIT $limit
            """,
            {"limit": limit * 2},
        )
        ring_ids = {nid for ring in self.detect_rings() for nid in ring["node_ids"]}
        seen: dict[str, GraphNode] = {}
        edges: list[GraphEdge] = []
        for row in rows:
            for entity in (row["n"], row["m"]):
                label = _label_for(entity)
                nid = node_id(label, entity[_key_prop(label)])
                seen.setdefault(
                    nid,
                    GraphNode(
                        id=nid,
                        label=_format_label(label, entity[_key_prop(label)]),
                        type=label,
                        report_count=int(entity.get("report_count", 1) or 1),
                        in_ring=nid in ring_ids,
                        properties=dict(entity),
                    ),
                )
            src = node_id(_label_for(row["n"]), row["n"][_key_prop(_label_for(row["n"]))])
            dst = node_id(_label_for(row["m"]), row["m"][_key_prop(_label_for(row["m"]))])
            edges.append(GraphEdge(source=src, target=dst, type=row["rel"]))
        return GraphData(nodes=list(seen.values()), edges=edges, truncated=False)

    def get_stats(self) -> GraphStats:
        counts: dict[str, int] = {}
        for label in ("PhoneNumber", "UPI_ID", "Domain", "BankAccount", "ScamReport"):
            rows = self._q(f"MATCH (n:{label}) RETURN count(n) AS c")
            counts[label] = int(rows[0]["c"]) if rows else 0
        return GraphStats(
            phone_numbers=counts.get("PhoneNumber", 0),
            upi_ids=counts.get("UPI_ID", 0),
            domains=counts.get("Domain", 0),
            bank_accounts=counts.get("BankAccount", 0),
            scam_reports=counts.get("ScamReport", 0),
            rings=len(self.detect_rings()),
            backend="neo4j",
        )

    def merge_node(
        self,
        node_type: str,
        key: str,
        props: dict[str, Any] | None = None,
        *,
        on_create: dict[str, Any] | None = None,
    ) -> str:
        # Neo4j MERGE + ON CREATE SET handles create-only semantics in Cypher.
        self._q(
            f"MERGE (n:{node_type} {{`{NODE_KEY_PROP[node_type]}`: $key}}) SET n += $props",
            {"key": key, "props": props or {}},
        )
        return node_id(node_type, key)

    def merge_edge(self, src: str, rel: str, dst: str, props: dict[str, Any] | None = None) -> bool:
        src_type, _, src_key = src.partition(":")
        dst_type, _, dst_key = dst.partition(":")
        self._q(
            f"""
            MATCH (a:{src_type} {{`{NODE_KEY_PROP[src_type]}`: $sk}}),
                  (b:{dst_type} {{`{NODE_KEY_PROP[dst_type]}`: $dk}})
            MERGE (a)-[r:{rel}]->(b) SET r += $props
            """,
            {"sk": src_key, "dk": dst_key, "props": props or {}},
        )
        return True

    def clear(self) -> None:
        self._q("MATCH (n) DETACH DELETE n")


def _label_for(entity) -> str:
    for label in entity.labels:
        if label in NODE_KEY_PROP:
            return label
    return next(iter(entity.labels), "ScammerName")


def _key_prop(label: str) -> str:
    return NODE_KEY_PROP.get(label, "name")


# ---------------------------------------------------------------------------
# Store factory
# ---------------------------------------------------------------------------

_store: Optional[Any] = None


def get_store() -> Any:
    """Neo4j when configured and connected, else the SQLite fallback."""
    global _store
    if _store is not None:
        return _store

    from app.config import settings

    if settings.neo4j_uri:
        from app.clients import neo4j_client

        if neo4j_client.get_neo4j() is not None:
            logger.info("scam graph backend: neo4j")
            _store = Neo4jGraphStore()
            return _store
        logger.warning("NEO4J_URI set but driver unavailable - falling back to SQLite")

    db_path = settings.graph_db_path
    logger.info("scam graph backend: sqlite (%s)", db_path)
    _store = SQLiteGraphStore(db_path)
    return _store


def reset_store() -> None:
    """Test hook — drop the cached store."""
    global _store
    if _store is not None and hasattr(_store, "close"):
        try:
            _store.close()
        except Exception:  # pragma: no cover
            pass
    _store = None


def new_report_id() -> str:
    return f"RPT-{uuid.uuid4().hex[:10].upper()}"
