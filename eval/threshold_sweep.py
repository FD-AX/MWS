"""Офлайн-подбор порога критика: score-ы уже сняты (--threshold 0), LLM не нужна.

    python eval/threshold_sweep.py \
        --clean out/gpt_thr0/mart_traffic_clean.findings.json \
        --pair out/gpt_thr0/mart_traffic_v1.findings.json:synth/out/mart_traffic_v1.gold.yaml \
        --pair out/gpt_thr0/doc3_mart_devices.findings.json:eval/gold_doc3.yaml

Для каждого порога θ: оставляем детерминированные находки + LLM-находки со
score >= θ; считаем recall по голдам и шум (medium+) на чистом документе.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_eval import finding_matches  # noqa: E402


def candidates(path: str) -> list[dict]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return d["findings"] + d["rejected"]  # всё, что пережило verify, с score-ами


def kept_at(cands: list[dict], theta: float) -> list[dict]:
    return [f for f in cands
            if f.get("score") is None or f["score"] >= theta]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", required=True)
    ap.add_argument("--pair", action="append", default=[],
                    help="findings.json:gold.yaml")
    args = ap.parse_args()

    clean = candidates(args.clean)
    pairs = []
    for p in args.pair:
        fpath, gpath = p.split(":")
        gold = yaml.safe_load(Path(gpath).read_text(encoding="utf-8"))["defects"]
        pairs.append((Path(fpath).stem.replace(".findings", ""), candidates(fpath), gold))

    header = "| θ | " + " | ".join(f"recall {n}" for n, _, _ in pairs) + " | noise@clean | находок |"
    print(header)
    print("|" + "---|" * (len(pairs) + 3))
    best = None
    for theta in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]:
        recs = []
        for _, cands, gold in pairs:
            kept = kept_at(cands, theta)
            n_hit = sum(1 for d in gold if any(finding_matches(d, f) for f in kept))
            recs.append((n_hit, len(gold)))
        noise = [f for f in kept_at(clean, theta)
                 if f["severity"] in ("critical", "high", "medium")]
        total = sum(len(kept_at(c, theta)) for _, c, _ in pairs)
        row = (f"| {theta} | "
               + " | ".join(f"{h}/{t}" for h, t in recs)
               + f" | {len(noise)} | {total} |")
        print(row)
        # лучший θ: максимальный суммарный recall при noise<=3
        score = (sum(h for h, _ in recs), -len(noise))
        if len(noise) <= 3 and (best is None or score > best[0]):
            best = (score, theta)
    if best:
        print(f"\nРекомендация: θ* = {best[1]} (noise<=3, recall максимален)")
    else:
        print("\nНи один θ не даёт noise<=3 — критик не разделяет; чинить промпт критика.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
