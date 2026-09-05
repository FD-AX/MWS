from __future__ import annotations

import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from ..document import Document
from ..llm import LLM
from ..schema import Finding
from . import load_prompt
from .uncertainty import ENTROPY_THRESHOLD, N_SAMPLES, TEMPERATURE, _canon, semantic_entropy

# H16 (IDEAS.md, EXP-23): неоднозначность мерить там, где живёт сущность документа, а не по 27 слотам.
# Узел = сущность (FIELD_/TABLE_/TOPIC_… или кодовая категория вроде UNKNOWN, NO_REGION, CHECK_*),
# которая встречается в ≥2 разделах: именно между разделами возникают разночтения (термин-дрейф D4,
# перегруженная категория D1, «последняя запись» без поля B9, UTC vs региональное время D3).
# Вопрос узлу задаётся N раз с температурой; расходящиеся определения = документ читается по-разному.

ENT = re.compile(r"\b(?:TABLE|FIELD|TOPIC|SCHEMA|DAG|PATH|CLUSTER)_[A-Z0-9_]+\b")
CODE = re.compile(r"\b[A-Z][A-Z0-9]{2,}(?:_[A-Z0-9]+)*\b")
PLACEHOLDER_PREFIX = ("USER_", "REGION_NAME", "PROVIDER_", "LINK_", "KAFKA_", "SCHEMA_")
STOP_CODES = {
    "NULL", "NOT", "AND", "OR", "JOIN", "SELECT", "FROM", "WHERE", "GROUP", "ORDER", "DDL", "SLA", "API",
    "HDFS", "SFTP", "CSV", "ORC", "JSON", "UTC", "MSK", "GMT", "TBD", "TODO", "RAW", "CDM", "ETL", "IMEI",
    "IMSI", "TAC", "LAC", "MCC", "MNC", "RAT", "URL", "HTTP", "HTTPS", "SQL", "HIVE", "SPARK", "KAFKA",
    "MERGE", "UPSERT", "STORED", "PARQUET", "SNAPPY", "PARTITIONED", "STRING", "BIGINT", "DECIMAL",
    "TIMESTAMP", "DATE", "INT", "DOUBLE", "BOOLEAN", "FAQ", "PDF", "CRM", "DPI", "MSC", "CDR", "GB", "MB",
    "COMMENT", "CREATE", "TABLE", "EXTERNAL", "LOCATION", "INSERT", "OVERWRITE", "COUNT", "SUM", "AVG",
    "MAX", "MIN", "DISTINCT", "CASE", "WHEN", "THEN", "ELSE", "END", "LEFT", "INNER", "OUTER", "TRUE", "FALSE",
    "CLUSTER", "GPRS", "LTE", "UMTS", "GSM", "VOLTE", "SMS", "MMS", "USSD", "SIM", "VPN", "DNS", "IP",
}
MAX_NODES = 24


def select_nodes(doc: Document, max_nodes: int = MAX_NODES) -> list[dict]:
    """Сущности, живущие в ≥2 разделах; ранжирование по числу разделов. Заглушки обезличивания
    (USER_*, REGION_NAME_*, LINK_*) — не узлы: спрашивать «что такое USER_A» бессмысленно."""
    occ: dict[str, dict[str, str]] = defaultdict(dict)
    for s in doc.sections:
        for line in s.text.splitlines():
            for m in ENT.finditer(line):
                name = m.group(0)
                if not name.startswith(PLACEHOLDER_PREFIX):
                    occ[name].setdefault(s.title, line.strip())
            for m in CODE.finditer(line):
                name = m.group(0)
                if ENT.fullmatch(name) or name in STOP_CODES or len(name) < 4 or name.startswith(PLACEHOLDER_PREFIX):
                    continue
                if name.isdigit() or not re.search(r"[A-Z]{3}", name):
                    continue
                occ[name].setdefault(s.title, line.strip())
    nodes = [{"name": n, "kind": "entity" if ENT.fullmatch(n) else "code",
              "sections": list(secs.keys()), "quote": next(iter(secs.values()))[:200]}
             for n, secs in occ.items() if len(secs) >= 2]
    nodes.sort(key=lambda x: (-len(x["sections"]), x["name"]))
    return nodes[:max_nodes]


def canon_node(answer: str, name: str) -> str:
    """Ключ кластера для определения сущности: имя узла убираем (оно есть в каждом ответе),
    дальше — общая канонизация (жёсткие токены, иначе основы слов)."""
    a = re.sub(re.escape(name), " ", answer, flags=re.IGNORECASE)
    return _canon(a)


def node_entropy(answers: list[str], name: str) -> tuple[float, list[list[str]]]:
    clusters: dict[str, list[str]] = {}
    for ans in answers:
        clusters.setdefault(canon_node(ans, name), []).append(ans)
    import math
    total = sum(len(v) for v in clusters.values())
    entropy = -sum((len(v) / total) * math.log2(len(v) / total) for v in clusters.values())
    return entropy, list(clusters.values())


def run(doc: Document, llm: LLM, max_nodes: int = MAX_NODES) -> list[Finding]:
    nodes = select_nodes(doc, max_nodes)
    if not nodes:
        return []
    doc_text = doc.raw

    def sample_node(node: dict) -> tuple[dict, list[str]]:
        prompt = load_prompt("graph_entropy_answer", entity=node["name"], document=doc_text)
        return node, llm.sample("Отвечай одной короткой фразой строго по документу.", prompt,
                                n=N_SAMPLES, temperature=TEMPERATURE)

    with ThreadPoolExecutor(max_workers=6) as pool:
        sampled = list(pool.map(sample_node, nodes))

    findings: list[Finding] = []
    for node, answers in sampled:
        entropy, clusters = node_entropy(answers, node["name"])
        if entropy < ENTROPY_THRESHOLD:
            continue
        variants = " | ".join(sorted({c[0].strip()[:80] for c in clusters})[:4])
        findings.append(Finding(
            category=f"gentropy:{node['kind']}",
            severity="medium",
            section=node["sections"][0],
            quote=node["quote"],
            why=(f"Сущность «{node['name']}» встречается в разделах {', '.join(node['sections'][:4])}; "
                 f"{N_SAMPLES} независимых прочтений дали разные определения ({variants}). "
                 f"Semantic entropy = {entropy:.2f} бит — сущность читается по-разному."),
            ask=f"Дай единственное определение «{node['name']}» в одном месте и используй его во всех разделах.",
            source_pass="uncertainty_graph",
            entropy=round(entropy, 3),
        ))
    return findings
