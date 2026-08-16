"""Инъекция спайна+эпизодов в FalkorDB НАПРЯМУЮ (Cypher MERGE), минуя Graphiti.

Почему не Graphiti add_triplet: в graphiti-core 0.29 add_triplet вызывает LLM
(dedup/атрибуты) -> несовместимо с нашим контрактом «ноль ключей, экстракция
агентом Claude Code». Пишем детерминированно сами: спайн владеет identity
(узел = канонический node_id), тип ребра = SERVES/DELIVERS/MENTIONS, эпизодные
рёбра несут valid_at (temporal). Идемпотентно (MERGE). Graphiti остаётся опцией
под temporal-query позже, если оправдает свой LLM.
"""
from __future__ import annotations
import logging
import pathlib
from falkordb import FalkorDB
from poh_memory.config import FALKOR_HOST, FALKOR_PORT
from poh_memory.edges import SEM_FIELDS, semantic_edges, node_titles
from poh_memory.supersede import reconcile_edges
from poh_memory.claims import episode_claims
from poh_memory.communities import detect_communities
from poh_memory.query import _load_graph

log = logging.getLogger(__name__)

# Допустимые типы рёбер = значения SEM_FIELDS (хребет + ценностная ось PAF).
# Множество константное и закрытое: тип подставляется в шаблон Cypher, поэтому
# whitelist остаётся гейтом инъекции. Расходись он с SEM_FIELDS — рёбра ценностной
# оси доходили бы сюда и молча отбрасывались (было так до Issue #9).
_REL = frozenset(SEM_FIELDS.values())


def _episode_date(node_id: str) -> str | None:
    if node_id.startswith("pulse-"):
        d = node_id[len("pulse-"):][:10]
        return d if len(d) == 10 and d[4] == "-" else None
    return None


def ingest(nexus_root: pathlib.Path, graph_name: str = "poh",
           host: str = FALKOR_HOST, port: int = FALKOR_PORT,
           ingest_at: str | None = None) -> int:
    g = FalkorDB(host=host, port=port).select_graph(graph_name)
    titles = node_titles(nexus_root)
    seen_nodes: set[str] = set()

    def ensure(nid: str):
        if nid in seen_nodes:
            return
        g.query("MERGE (n:Entity {name:$name}) SET n.summary=$s",
                {"name": nid, "s": titles.get(nid, nid)})
        seen_nodes.add(nid)

    asserted: set[tuple[str, str, str]] = set()
    n = 0
    for src, dst, etype in semantic_edges(nexus_root):
        if etype not in _REL:
            continue
        ensure(src)
        ensure(dst)
        valid = _episode_date(src) or _episode_date(dst)
        # тип ребра = etype (из фикс. множества -> безопасно в шаблоне)
        g.query(
            f"MATCH (a:Entity {{name:$s}}), (b:Entity {{name:$d}}) "
            f"MERGE (a)-[r:{etype}]->(b) "
            f"SET r.valid_at=$v, r.invalid_at=$iv, r.expired_at=$ex, r.ingest_at=$ing",
            {"s": src, "d": dst, "v": valid, "iv": None, "ex": None, "ing": ingest_at},
        )
        asserted.add((src, etype, dst))   # порядок как RETURN a.name, type(r), b.name
        n += 1

    if ingest_at is not None:
        invalidated = reconcile_edges(g, asserted, ingest_at)
        log.info("poh ingest reconcile: %d edges invalidated (ingest_at=%s)", invalidated, ingest_at)
    else:
        log.info("poh ingest: ingest_at=None -> reconciliation skipped")

    claims = episode_claims(nexus_root)
    grounded = ungrounded = 0
    for c in claims:
        ensure(c["episode"])
        g.query(
            "MERGE (c:Claim {name:$id}) "
            "SET c.subject=$subj, c.aspect=$aspect, c.value=$val, c.polarity=$pol, "
            "c.speaker=$spk, c.confidence=$conf, "
            "c.valid_at=$valid, c.invalid_at=$iv, c.expired_at=$ex, c.superseded_by=$sby, c.ingest_at=$ing",
            {"id": c["id"], "subj": c["subject"], "aspect": c["aspect"], "val": c["value"],
             "pol": c["polarity"], "spk": c["speaker"], "conf": c["confidence"],
             "valid": _episode_date(c["episode"]), "iv": c.get("invalid_at"),
             "ex": c.get("expired_at"), "sby": c.get("superseded_by"), "ing": ingest_at},
        )
        g.query(
            "MATCH (e:Entity {name:$ep}) MATCH (c:Claim {name:$id}) MERGE (e)-[:ASSERTS]->(c)",
            {"ep": c["episode"], "id": c["id"]},
        )
        gn = c.get("grounded_node")
        if gn and gn in seen_nodes:
            g.query(
                "MATCH (c:Claim {name:$id}) MATCH (n:Entity {name:$gn}) MERGE (c)-[:ABOUT]->(n)",
                {"id": c["id"], "gn": gn},
            )
            grounded += 1
        else:
            ungrounded += 1
    if claims:
        log.info("poh ingest claims: %d total, %d grounded, %d ungrounded", len(claims), grounded, ungrounded)

    superseded_missing = 0
    for c in claims:
        sby = c.get("superseded_by")
        if not sby:
            continue
        # MATCH оба (НЕ MERGE sup) — если вытесняющего нет, ребро не создаётся и фантом не минтится
        res = g.query(
            "MATCH (c:Claim {name:$id}), (sup:Claim {name:$sby}) "
            "MERGE (c)-[:SUPERSEDED_BY]->(sup) RETURN count(*)",
            {"id": c["id"], "sby": sby},
        )
        if res.result_set[0][0] == 0:
            superseded_missing += 1
    if superseded_missing:
        log.info("poh ingest claims: %d SUPERSEDED_BY edges skipped (superseding claim absent)",
                 superseded_missing)

    # community-проход (#3): кластеры по текущему семантич. графу -> community_id на Entity
    Gc = _load_graph(graph_name, host=host, port=port)   # as_of=None -> активные рёбра
    communities = detect_communities(Gc)
    for node_id, community_id in communities.items():
        g.query("MATCH (n:Entity {name:$id}) SET n.community_id=$cid",
                {"id": node_id, "cid": community_id})
    if communities:
        log.info("poh ingest communities: %d nodes, %d communities",
                 len(communities), len(set(communities.values())))

    return n
