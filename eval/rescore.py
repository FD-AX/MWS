"""Офлайн-пересчёт recall по сырым JSON бенча текущими голдами (PROTOCOL п.4: поправка на матчер).

    python eval/rescore.py eval/night/m_pod_key.json [...] [--out eval/night/m_pod_key.rescored.json]

Записи с полными находками (`findings`) пересчитываются точно; легаси-записи (только `extras`,
why обрезан до 160 символов) — приближённо: попадание можно только добавить, не снять.
Печатает, что изменилось (какие дефекты стали hit), и пишет пересчитанный JSON — его можно
отдавать в eval/matrix.py. Голды берутся по имени цели (doc1/doc2/doc3/synth_*).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "eval"))
from run_eval import finding_matches  # noqa: E402

GOLDS = {
    "doc1": "eval/gold_doc1.yaml", "doc2": "eval/gold_doc2.yaml", "doc3": "eval/gold_doc3.yaml",
    "synth_v1": "synth/out/mart_traffic_v1.gold.yaml", "synth_v2hard": "synth/out/mart_traffic_v2h.gold.yaml",
    "synth_v3official": "synth/out/mart_traffic_v3o.gold.yaml",
}


def gold_for(target: str) -> list[dict] | None:
    base = re.sub(r"\s*#\d+$", "", target)
    for key, path in GOLDS.items():
        if base.startswith(key) or key in base:
            return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))["defects"]
    return None


def main() -> int:
    args = sys.argv[1:]
    out = None
    if "--out" in args:
        i = args.index("--out"); out = args[i + 1]; args = args[:i] + args[i + 2:]
    changed = 0
    all_recs: list[dict] = []
    for p in args:
        recs = json.loads(Path(p).read_text(encoding="utf-8"))
        for r in recs:
            if not r.get("defects"):
                all_recs.append(r); continue
            gold = gold_for(r["target"])
            if gold is None:
                all_recs.append(r); continue
            fs = r.get("findings")
            exact = fs is not None
            pool = fs if exact else r.get("extras", [])
            by_id = {d["id"]: d for d in gold}
            new_extras = []
            for did, rec in r["defects"].items():
                d = by_id.get(did)
                if d is None:
                    continue
                hit_now = any(finding_matches(d, f) for f in pool)
                was = bool(rec.get("hit"))
                new = hit_now if exact else (was or hit_now)
                if new != was:
                    changed += 1
                    print(f"{Path(p).name} · {r['variant']} · {r['target']}: {did} {'✗→✓' if new else '✓→✗'}")
                rec["hit"] = new
            if exact:
                matched = {f.get("fid") for d in gold for f in fs if finding_matches(d, f)}
                new_extras = [{"category": f["category"], "severity": f["severity"], "why": (f.get("why") or "")[:160]}
                              for f in fs if f.get("fid") not in matched]
                r["extras"] = new_extras
            all_recs.append(r)
    print(f"\nизменений попаданий: {changed}")
    if out:
        Path(out).write_text(json.dumps(all_recs, ensure_ascii=False, indent=1), encoding="utf-8")
        print("записано:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
