"""Запечатанный held-out набор (METRICS_VALIDITY.md): базы и инъекции, которых разработчик конвейера НЕ ВИДЕЛ.

    python synth/heldout_gen.py [--name cdr_source] [--kind source|mart] [--n 12]

Что делает:
1. GPT пишет чистое ТЗ по официальному шаблону МТС на НОВУЮ тему (другой тип документа, чем базы it1–it7);
   документ никем не вычитывается и не «чистится» под ревьюер — это и есть смысл held-out.
2. GPT пишет рецепт инъекций в формате synth/inject.py (find — дословная уникальная подстрока); скрипт
   валидирует find'ы и при ошибках возвращает их модели на исправление (до 3 раундов).
3. synth/inject.py собирает испорченный документ и голд. В stdout печатаются ТОЛЬКО размеры, число дефектов,
   распределение по классам и sha256 — содержимое не выводится, чтобы разработчик его не увидел до финальной оценки.

Открывать файлы synth/heldout/ можно только при финальном прогоне на теге protocol-freeze-*.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tz_review.config import load_dotenv  # noqa: E402

OUT = ROOT / "synth" / "heldout"

KINDS = {
    "source": ("поток данных «источник → RAW-слой»: приём CDR-подобных событий биллинга из Kafka-топиков в HDFS "
               "с первичной валидацией, без агрегатов (тип документа как у потоковых ТЗ, НЕ витрина)"),
    "mart": ("витрина-агрегат по услугам и тарифным планам абонентов: ежедневный расчёт из RAW-таблиц биллинга и "
             "справочника тарифов, с контролем качества и публикацией потребителям (тема НЕ про трафик и НЕ про устройства)"),
}

CODES = ("A1 официальные пункты МТС (сериализация/каталог/NOT NULL/фильтры/кластер/путь/справочники/ключ), "
         "A3 обработка отсутствующих значений/справочников, A5 ключи и гранулярность, A6 регламент/SLA, A7 сбои/бэкфилл, "
         "B1 дубли/неоднозначные поля, B2 ошибки формул и группировок, B6 канцелярская пустышка вместо правила, "
         "B9 «последняя запись» без поля упорядочивания, C1 битые ссылки на разделы, C2 поле используется, но не описано, "
         "D1 перегруженная категория, D2 несовместимые величины/сроки между разделами, D3 границы периода/часовые пояса, "
         "D4 термин-дрейф, E1 противоречие пример↔правило, F1 отсутствующий раздел шаблона")


def _client():
    from openai import OpenAI
    load_dotenv()
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("нет OPENAI_API_KEY")
    return OpenAI(base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"), api_key=key), \
        os.environ.get("OPENAI_MODEL", "gpt-5.5")


def _ask(client, model, system, user, max_out=24000) -> str:
    r = client.chat.completions.create(model=model, messages=[{"role": "system", "content": system},
                                                              {"role": "user", "content": user}],
                                       max_completion_tokens=max_out)
    return r.choices[0].message.content or ""


def gen_base(client, model, kind: str) -> str:
    template = (ROOT / "casedata" / "template_official.md").read_text(encoding="utf-8")
    keypoints = (ROOT / "casedata" / "keypoints_official.md").read_text(encoding="utf-8")
    system = ("Ты — системный аналитик команды данных МТС. Пишешь техническое задание строго по официальному шаблону "
              "и «Основным моментам документации». Пишешь по-русски, конкретно, без воды.")
    user = (f"Напиши ПОЛНОЕ и ВНУТРЕННЕ СОГЛАСОВАННОЕ техническое задание на {KINDS[kind]}.\n\n"
            "Требования:\n"
            "- все разделы шаблона присутствуют и заполнены содержательно (неприменимые — явно «не применимо» с причиной);\n"
            "- все 8 «Основных моментов» закрыты явно (форматы/сериализация, ссылки на Data Catalog, NOT NULL/NULLABLE для каждого поля, "
            "типовые фильтры, кластеры Kafka и пути HDFS, справочники, ключи/партиции);\n"
            "- обезличенные имена: TABLE_*, FIELD_*, TOPIC_*, SCHEMA_*, LINK_*, CLUSTER_*, PATH_*, DAG_*; никаких реальных названий;\n"
            "- есть структура каждой таблицы (поле, тип, обязательность, описание), DDL, пример данных, алгоритм по шагам с формулами, "
            "регламент с временем запуска и сроком готовности, ретеншен, контроль качества с порогами, FAQ и история версий;\n"
            "- документ должен быть без противоречий: одни и те же величины (сроки, пороги, ретеншен, часовые пояса, ключи) "
            "совпадают во всех разделах; каждое используемое поле описано в структуре; ссылки на разделы — на существующие;\n"
            "- объём 12–18 тысяч символов, markdown с заголовками разделов как в шаблоне.\n\n"
            f"Шаблон:\n---\n{template}\n---\n\nОсновные моменты:\n---\n{keypoints}\n---\n\n"
            "Верни только markdown документа.")
    return _ask(client, model, system, user).strip()


def gen_recipe(client, model, base: str, n: int, feedback: str = "") -> dict:
    system = "Ты — методолог тестового набора для ревьюера ТЗ. Возвращаешь только валидный YAML без пояснений."
    user = (f"Ниже чистый документ. Придумай {n} независимых дефектов и опиши их как рецепт инъекций.\n\n"
            "Правила рецепта (строго):\n"
            "- defects: список; у каждого id (латиница, уникален), code (из списка ниже), difficulty (easy|medium|hard|expert), "
            "description (одна строка), categories (список, можно пустой), keywords (3–6 коротких основ слов в нижнем регистре, "
            "по которым в тексте НАХОДКИ ревьюера можно узнать этот дефект — не слова из самого дефекта, а как ревьюер его назовёт), "
            "и правка: либо op/find/replace(или text), либо edits: [ {op, find, replace|text}, ... ].\n"
            "- op ∈ replace | delete | insert_after. find — ДОСЛОВНАЯ подстрока документа (копируй символ в символ, включая «|», "
            "пробелы и знаки), которая встречается в документе РОВНО ОДИН РАЗ; длина 20–200 символов.\n"
            "- Правка минимальна и правдоподобна: убрать правило, заменить число, сломать согласованность двух разделов, убрать описание "
            "поля, сослаться на несуществующий раздел по имени, заменить правило канцелярской пустышкой и т.п. Никаких пометок вроде «(дефект)».\n"
            "- Распредели дефекты по классам: не менее 3 официальных пунктов МТС (A1/A3/A5/A6/A7), не менее 3 межсекционных (D1–D4), "
            "не менее 2 семантических (B*), 1–2 структурных (C*), 1 из E/F.\n"
            f"- Коды: {CODES}.\n"
            + (f"\nОШИБКИ ПРЕДЫДУЩЕЙ ВЕРСИИ (исправь именно их, остальное сохрани):\n{feedback}\n" if feedback else "")
            + f"\nДокумент:\n---\n{base}\n---\n\nВерни YAML вида:\ndefects:\n  - id: ...\n    code: ...\n    difficulty: ...\n"
              "    description: ...\n    categories: []\n    keywords: [...]\n    op: replace\n    find: \"...\"\n    replace: \"...\"\n")
    text = _ask(client, model, system, user)
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("yaml"):
            text = text[4:]
    return yaml.safe_load(text)


def validate(recipe: dict, base: str) -> list[str]:
    errs = []
    ids = Counter()
    for d in recipe.get("defects", []):
        ids[d.get("id")] += 1
        for e in d.get("edits") or [d]:
            f = e.get("find")
            if not f:
                errs.append(f"[{d.get('id')}] нет find"); continue
            n = base.count(f)
            if n != 1:
                errs.append(f"[{d.get('id')}] find встречается {n} раз (нужно 1): {f[:70]!r}")
            op = e.get("op", "replace")
            if op == "replace" and "replace" not in e:
                errs.append(f"[{d.get('id')}] op=replace без replace")
            if op == "insert_after" and "text" not in e:
                errs.append(f"[{d.get('id')}] op=insert_after без text")
    errs += [f"дубль id {i}" for i, c in ids.items() if c > 1]
    return errs


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def main() -> int:
    args = sys.argv[1:]
    name = args[args.index("--name") + 1] if "--name" in args else "cdr_source"
    kind = args[args.index("--kind") + 1] if "--kind" in args else "source"
    n = int(args[args.index("--n") + 1]) if "--n" in args else 12
    OUT.mkdir(parents=True, exist_ok=True)
    client, model = _client()

    base_p = OUT / f"{name}_clean.md"
    if not base_p.exists():
        base = gen_base(client, model, kind)
        base_p.write_text(base, encoding="utf-8")
    base = base_p.read_text(encoding="utf-8")
    print(f"база: {base_p.name} {len(base)} симв., разделов(##): {base.count(chr(10) + '## ')}, sha {sha(base_p)}")

    recipe, feedback = None, ""
    for round_ in range(1, 4):
        recipe = gen_recipe(client, model, base, n, feedback)
        errs = validate(recipe, base)
        print(f"рецепт, раунд {round_}: дефектов {len(recipe.get('defects', []))}, ошибок find {len(errs)}")
        if not errs:
            break
        feedback = "\n".join(errs[:20])
    else:
        # оставляем только валидные дефекты
        recipe["defects"] = [d for d in recipe["defects"] if not validate({"defects": [d]}, base)]
        print(f"оставлено валидных дефектов: {len(recipe['defects'])}")

    recipe = {"base": f"synth/heldout/{name}_clean.md", "out_doc": f"synth/heldout/{name}_inj.md",
              "out_gold": f"synth/heldout/{name}_inj.gold.yaml", "defects": recipe["defects"]}
    rec_p = OUT / f"{name}_recipe.yaml"
    rec_p.write_text(yaml.safe_dump(recipe, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    r = subprocess.run([sys.executable, "synth/inject.py", str(rec_p)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print("inject.py:", (r.stderr or r.stdout)[-400:]); return 1
    codes = Counter(str(d.get("code", "?"))[:1] for d in recipe["defects"])
    diffs = Counter(d.get("difficulty", "?") for d in recipe["defects"])
    print(f"инъекция ок: {name}_inj.md sha {sha(OUT / f'{name}_inj.md')}, голд {len(recipe['defects'])} дефектов, "
          f"классы {dict(sorted(codes.items()))}, сложность {dict(diffs)}")
    seal = OUT / "SEALED.json"
    data = json.loads(seal.read_text(encoding="utf-8")) if seal.exists() else {}
    data[name] = {"kind": kind, "model": model, "base_sha": sha(base_p), "inj_sha": sha(OUT / f"{name}_inj.md"),
                  "defects": len(recipe["defects"]), "classes": dict(sorted(codes.items()))}
    seal.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
