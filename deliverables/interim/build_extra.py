"""Дополнительные материалы (промежуточная версия): 8 файлов с явным статусом в шапке.

    python deliverables/interim/build_extra.py  → deliverables/interim/extra/
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
import yaml  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / "extra"
OUT.mkdir(exist_ok=True)

HEAD = ("> Дополнительные материалы — промежуточная версия · 04.09.2026 · команда TZ Review (кейс МТС NET) · "
        "github.com/FD-AX/MWS\n> Статус: {status}\n\n")


def w(name: str, status: str, body: str) -> None:
    (OUT / name).write_text(HEAD.format(status=status) + body, encoding="utf-8")
    print("  ", name, len(body) // 1024, "КБ")


def read(p: str) -> str:
    return (ROOT / p).read_text(encoding="utf-8")


def summary_table(bench_md: str) -> str:
    """Только сводная таблица из отчёта бенча (без разбора промахов)."""
    m = re.search(r"## Сводка\n\n(.*?)(?:\n\n## |\Z)", bench_md, flags=re.S)
    return m.group(1).strip() if m else bench_md


def main() -> int:
    # 1. Журнал экспериментов
    w("01_experiments_journal.md", "завершено на 04.09; EXP-01…16 закрыты, EXP-12 — идея",
      read("experiments/README.md"))

    # 2. Матрицы ошибок
    parts = []
    for exp, path, note in [("EXP-14 (GPT-5.5, все фиксы, it6)", "eval/night/error_matrix_exp14.md", "3 варианта, 49 голдов"),
                            ("EXP-15 (gpt-oss-120b, it6)", "eval/night/error_matrix_exp15.md", "v1g + v2g, 49 голдов"),
                            ("EXP-13 (5 вариантов, it5 — до фиксов)", "eval/error_matrix.md", "исторический срез: 4 пункта МТС не ловил никто")]:
        parts.append(f"# {exp} · {note}\n\n" + read(path).replace("# Матрица ошибок (вариант × класс дефекта)", "").strip())
    w("02_error_matrices_exp13_14_15.md", "завершено; матрица «вариант × класс» и слепые зоны по трём прогонам",
      "\n\n---\n\n".join(parts))

    # 3. Сводные таблицы бенчей
    parts = []
    for exp, path in [("EXP-13 — it5, 5 вариантов × 7 целей", "eval/night/bench_exp13.md"),
                      ("EXP-14 — GPT-5.5 после фиксов", "eval/night/bench_exp14.md"),
                      ("EXP-14 повтор v2g (разброс)", "eval/night/bench_exp14_rerun.md"),
                      ("EXP-15 — gpt-oss-120b", "eval/night/bench_exp15.md"),
                      ("EXP-16 — 120b с исходом NA", "eval/night/bench_exp16_120b.md")]:
        parts.append(f"# {exp}\n\n" + summary_table(read(path)))
    w("03_bench_summaries_exp13_16.md", "завершено; recall по группам/сложности, находки, лишние, anchoring",
      "Колонки: recall = пойманные голд-дефекты; «по группам» A пропуск, B неоднозначность, C ссылка, D противоречие, E измеримость, F шаблон; "
      "«лишних» = находки вне голда (кандидаты на разметку); anchoring = доля верифицированных цитат.\n\n" + "\n\n---\n\n".join(parts))

    # 4. Графики одним PDF
    pdf = OUT / "04_charts_interim.pdf"
    with PdfPages(pdf) as pp:
        for name, title in [("architecture.png", "Схема контура"), ("pipeline.png", "Конвейер: этапы и что доказано"),
                            ("recall.png", "Recall по размеченным дефектам"), ("noise.png", "Шум и порог критика"),
                            ("fixes.png", "Три дыры и лестница промпт → конвейер"), ("models.png", "Лестница моделей")]:
            img = mpimg.imread(HERE / "charts" / name)
            h, wd = img.shape[:2]
            fig = plt.figure(figsize=(13, 13 * h / wd + 0.6), dpi=150)
            fig.suptitle(title, fontsize=13, y=0.995)
            ax = fig.add_axes([0.01, 0.01, 0.98, 0.93]); ax.imshow(img); ax.axis("off")
            pp.savefig(fig); plt.close(fig)
    print("  ", pdf.name, pdf.stat().st_size // 1024, "КБ")

    # 5. Пример синтетики: документ с 13 инъекциями + голд
    doc = read("synth/out/mart_traffic_v3o.md")
    gold = yaml.safe_load(read("synth/out/mart_traffic_v3o.gold.yaml"))["defects"]
    gold_md = "| id | код | сложность | дефект |\n|---|---|---|---|\n" + "\n".join(
        f"| {d['id']} | {d['code']} | {d['difficulty']} | {d['description']} |" for d in gold)
    w("05_synthetic_sample_v3official.md", "завершено (итерация it7); документ сгенерирован фабрикой из чистой базы в официальном шаблоне",
      "# Синтетический документ v3official: витрина в официальном шаблоне МТС с 13 подсаженными дефектами\n\n"
      "Рецепт: `synth/recipes/mart_traffic_v3official.yaml` (8 инъекций по «Основным моментам» + DDL/пример/FAQ/история). "
      "Чистая база даёт 0 находок детерминированного слоя.\n\n## Голд (что подсажено)\n\n" + gold_md +
      "\n\n## Документ\n\n" + doc)

    # 6. Голд-разметка документов МТС
    parts = []
    for name, path in [("doc1 — поток геоданных (12)", "eval/gold_doc1.yaml"), ("doc2 — источник CDR (8)", "eval/gold_doc2.yaml"),
                       ("doc3 — витрина-агрегат, целевой тип (16)", "eval/gold_doc3.yaml")]:
        g = yaml.safe_load(read(path))["defects"]
        parts.append(f"## {name}\n\n| id | код | сложность | дефект | категории для матчинга |\n|---|---|---|---|---|\n" + "\n".join(
            f"| {d['id']} | {d.get('code', '?')} | {d.get('difficulty', '?')} | {str(d['description']).replace(chr(10), ' ')} | {', '.join(d.get('categories', []))} |" for d in g))
    w("06_gold_markup_mts_docs.md", "черновик (один размётчик); тройная разметка запланирована до финала",
      "# Разметка дефектов на обезличенных документах МТС (36 позиций, 9 — официальные пункты)\n\n"
      "Коды: A пропуск, B неоднозначность, C ссылка в пустоту, D противоречие, E измеримость, F шаблон (MATRIX.md).\n\n" + "\n\n".join(parts))

    # 7. Демо-отчёт с self-hosted модели + сверка с голдом
    try:
        with urllib.request.urlopen("http://localhost:18080/reviews/07190ce6b716/report.md", timeout=20) as r:
            report = r.read().decode("utf-8")
    except Exception:  # noqa: BLE001
        report = "(отчёт недоступен: API не запущен)"
    w("07_demo_report_doc3_gpt-oss-120b.md",
      "завершено; реальный отчёт из контура (RabbitMQ → worker → Postgres), модель gpt-oss-120b self-hosted, 414 с, 9 вызовов; по голду 14/16",
      "# Отчёт ревью doc3 (витрина-агрегат) на self-hosted gpt-oss-120b\n\n"
      "Сверка с голдом (scripts/eval_api_result.py): **14/16**; пропущены G3-6 (TAC не найден → vendor?) и G3-7 (бэкфилл не описан); "
      "9 находок вне голда, из них 5 — реальные пробелы doc3 (фильтрация, удалённые записи, объёмы, Data Catalog, состав полей).\n\n---\n\n" + report)

    # 8. Демо-сценарий + контракт API (из ветки arch)
    arch = ROOT.parent / "mws-arch"
    demo = (arch / "DEMO.md").read_text(encoding="utf-8") if (arch / "DEMO.md").exists() else "(DEMO.md — в ветке arch/compose-stack)"
    api = (arch / "services/api/API.md").read_text(encoding="utf-8") if (arch / "services/api/API.md").exists() else "(API.md — в ветке arch/compose-stack)"
    w("08_demo_scenario_and_api.md", "работает локально (docker compose, ветка arch/compose-stack); фронтенд аналитика — к финалу",
      demo + "\n\n---\n\n" + api)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
