"""Сборка промежуточной презентации (PPTX) из тезисов журнала экспериментов.

    python deliverables/interim/build_slides.py  → deliverables/interim/TZ_Review_interim.pptx
Схема архитектуры рисуется matplotlib'ом в PNG рядом.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.util import Emu, Inches, Pt  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "TZ_Review_interim.pptx"
DIAGRAM = HERE / "architecture.png"

INK = RGBColor(0x1F, 0x23, 0x28)
MUTED = RGBColor(0x6B, 0x72, 0x80)
ACCENT = RGBColor(0x25, 0x63, 0xEB)


def draw_architecture(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(13, 6.2), dpi=150)
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 6.2)
    ax.axis("off")

    def box(x, y, w, h, title, sub="", color="#eef2ff", edge="#2563eb"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    fc=color, ec=edge, lw=1.4))
        ax.text(x + w / 2, y + h - 0.32, title, ha="center", va="center", fontsize=11, weight="bold", color="#1f2328")
        if sub:
            ax.text(x + w / 2, y + h / 2 - 0.22, sub, ha="center", va="center", fontsize=8.6, color="#374151", linespacing=1.35)

    def arrow(x1, y1, x2, y2, label=""):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14, lw=1.2, color="#6b7280"))
        if label:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.16, label, ha="center", fontsize=8, color="#6b7280")

    box(0.2, 4.2, 2.1, 1.4, "Аналитик", "UI / Swagger\nmd · txt · docx · pdf", color="#f9fafb", edge="#9ca3af")
    box(2.8, 4.2, 2.1, 1.4, "api", "FastAPI · UI · история\n:18080")
    box(2.8, 2.2, 2.1, 1.4, "docs", "pdf/docx → markdown\nсекции, таблицы")
    box(5.4, 4.2, 2.1, 1.4, "RabbitMQ", "review.jobs (durable)\nDLQ review.dead")
    box(8.0, 4.2, 2.4, 1.4, "worker", "prefetch 1 · ack после записи\nидемпотентность · прогресс")
    box(10.9, 4.2, 2.0, 1.4, "LLM", "gpt-oss-120b (vLLM/ollama)\nGPT-5.5 (референс)", color="#fef3c7", edge="#d97706")
    box(5.4, 2.2, 2.1, 1.4, "Postgres", "documents · reviews\nfindings · feedback", color="#ecfdf5", edge="#059669")
    box(8.0, 2.2, 2.4, 1.4, "Prometheus + Grafana", "поток, p95, вызовы, токены,\nнаходки по классам, UNKNOWN", color="#ecfdf5", edge="#059669")

    box(0.2, 0.15, 12.7, 1.6, "Конвейер tz_review (внутри worker)",
        "детерминированный слой (шаблон МТС, паттерны, граф сущностей) → чеклист 27 слотов (OK / MISSING / UNCLEAR / NA) → "
        "согласованность разделов → взгляд разработчика\n→ энтропия / логит-зонд → верификация цитат → критик "
        "(официальные пункты и детерминированные находки не режутся)", color="#f3f4f6", edge="#4b5563")

    arrow(2.3, 4.9, 2.8, 4.9)
    arrow(3.85, 4.2, 3.85, 3.6, "normalize")
    arrow(4.9, 4.9, 5.4, 4.9, "job")
    arrow(7.5, 4.9, 8.0, 4.9)
    arrow(10.4, 4.9, 10.9, 4.9, "OpenAI API")
    arrow(9.2, 4.2, 6.6, 3.6, "результат")
    arrow(3.85, 4.2, 5.4, 3.3, "история")
    arrow(9.2, 4.2, 9.2, 3.6, "/metrics")
    arrow(10.4, 4.5, 12.0, 1.75, "review()")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def add_title(prs, title, subtitle=""):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(0.7), Inches(2.2), Inches(11.9), Inches(1.4))
    p = tb.text_frame.paragraphs[0]
    p.text = title
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = INK
    if subtitle:
        tb2 = s.shapes.add_textbox(Inches(0.7), Inches(3.7), Inches(11.9), Inches(1.6))
        tb2.text_frame.word_wrap = True
        p2 = tb2.text_frame.paragraphs[0]
        p2.text = subtitle
        p2.font.size = Pt(18)
        p2.font.color.rgb = MUTED
    return s


def add_bullets(prs, title, bullets, note=""):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    t = s.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12), Inches(0.9))
    p = t.text_frame.paragraphs[0]
    p.text = title
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = INK
    body = s.shapes.add_textbox(Inches(0.7), Inches(1.35), Inches(11.9), Inches(5.4))
    tf = body.text_frame
    tf.word_wrap = True
    first = True
    for b in bullets:
        level = 1 if b.startswith("  ") else 0
        text = b.strip()
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.text = ("• " if level == 0 else "– ") + text
        p.level = level
        p.font.size = Pt(18 if level == 0 else 15)
        p.font.color.rgb = INK if level == 0 else MUTED
        p.space_after = Pt(6)
    if note:
        n = s.shapes.add_textbox(Inches(0.7), Inches(6.85), Inches(11.9), Inches(0.5))
        pn = n.text_frame.paragraphs[0]
        pn.text = note
        pn.font.size = Pt(11)
        pn.font.color.rgb = MUTED
    return s


def add_table(prs, title, header, rows, note="", col_widths=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    t = s.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12), Inches(0.9))
    p = t.text_frame.paragraphs[0]
    p.text = title
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = INK
    n_rows, n_cols = len(rows) + 1, len(header)
    shape = s.shapes.add_table(n_rows, n_cols, Inches(0.6), Inches(1.4), Inches(12.1), Inches(0.4) * n_rows)
    table = shape.table
    for j, h in enumerate(header):
        c = table.cell(0, j)
        c.text = h
        c.text_frame.paragraphs[0].font.size = Pt(13)
        c.text_frame.paragraphs[0].font.bold = True
    for i, row in enumerate(rows, 1):
        for j, val in enumerate(row):
            c = table.cell(i, j)
            c.text = str(val)
            c.text_frame.paragraphs[0].font.size = Pt(13)
    if col_widths:
        for j, w in enumerate(col_widths):
            table.columns[j].width = Inches(w)
    if note:
        n = s.shapes.add_textbox(Inches(0.6), Inches(6.7), Inches(12), Inches(0.6))
        n.text_frame.word_wrap = True
        pn = n.text_frame.paragraphs[0]
        pn.text = note
        pn.font.size = Pt(11)
        pn.font.color.rgb = MUTED
    return s


def main() -> int:
    draw_architecture(DIAGRAM)
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    add_title(prs, "TZ Review — предварительное ревью ТЗ на потоки и витрины данных",
              "Кейс МТС NET · промежуточная версия · 04.09.2026 · github.com/FD-AX/MWS")

    add_bullets(prs, "Проблема", [
        "Аналитик NET пишет ТЗ на поток или витрину; разработчик и тестировщик вычитывают вручную",
        "Часть проблем доживает до разработки и возвращается: повторные согласования, переделки, перепроверки",
        "Три класса проблем в документах МТС:",
        "  пропуски — нет ключа витрины, правила для NULL, расписания и SLA",
        "  неоднозначности — «последний по времени IMEI»: по какому полю, из какой таблицы",
        "  противоречия — «Инкремент» и «только полная перезагрузка месяца» в одном документе",
        "Кейсодатель: 4 зоны внимания, 8 обязательных пунктов документации, тест на новом документе типа «витрина»",
    ])

    add_bullets(prs, "Постановка задачи", [
        "Вход: текст ТЗ (markdown, txt, docx, pdf). Выход: места, требующие уточнения",
        "Каждая находка: дословная цитата · почему это проблема здесь · что уточнить · критичность",
        "Плюс: покрытие чеклиста полноты и общий вердикт готовности; решение всегда за аналитиком",
        "Наши требования к себе:",
        "  замечание без привязки к тексту — не замечание (верификация цитат)",
        "  обезличивание — не дефект; официальные пункты МТС проверяются всегда",
        "  качество измеряется на размеченных данных; любая смена модели или промпта — через бенч",
    ])

    add_bullets(prs, "Подход: конвейер, а не промпт", [
        "Детерминированное ядро: шаблон МТС (20 разделов, «не применимо»), языковые паттерны, граф сущностей — 0 шума",
        "Чеклист полноты: 27 бинарных слотов, включая 8 «Основных моментов» МТС; исходы OK / MISSING / UNCLEAR / NA",
        "Межсекционная согласованность, «взгляд разработчика»: что придётся угадывать",
        "Неоднозначность как число: семантическая энтропия ответов и вероятности из логитов",
        "Верификация цитат (галлюцинации отбрасываются) и критик-ранжировщик, который не вправе резать пункты кейсодателя",
        "Модель — параметр: GPT-5.5 как референс, self-hosted gpt-oss-120b как ярус заказчика",
    ], note="Что взяли у сильных решений: PR-Agent (бинарные вопросы с цитатой), CodeRabbit (этажи конвейера), Greptile (критик), QVscribe (детерминированное ядро), Bugbot (консенсус)")

    s = prs.slides.add_slide(prs.slide_layouts[6])
    t = s.shapes.add_textbox(Inches(0.6), Inches(0.3), Inches(12), Inches(0.8))
    p = t.text_frame.paragraphs[0]
    p.text = "Схема решения"
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = INK
    s.shapes.add_picture(str(DIAGRAM), Inches(0.4), Inches(1.15), width=Inches(12.5))

    add_table(prs, "Выполненные этапы", ["Этап", "Состояние"], [
        ["Рисёрч: академия RE, коммерческие ревьюеры кода/требований, таксономия дефектов (35 кодов)", "готово"],
        ["Конвейер tz_review, 7 проходов, 46 юнит-тестов", "готово, main"],
        ["Официальная рубрика МТС: шаблон 20 разделов + 8 пунктов как слоты", "готово"],
        ["Голды документов МТС (36 дефектов) + фабрика синтетики (33 инъекции, 7 итераций)", "готово, разметка черновая"],
        ["Бенч, матрица ошибок «вариант × класс», канарейка, журнал 16 экспериментов", "готово"],
        ["Compose-контур: api + UI, docs, RabbitMQ, worker, Postgres, Prometheus, Grafana", "работает"],
        ["Self-hosted gpt-oss-120b (RunPod H100); сквозной сценарий PDF → отчёт", "работает; vLLM — план"],
    ], col_widths=[9.3, 2.8])

    add_table(prs, "Первые результаты: recall по размеченным дефектам",
              ["Вариант", "doc3 витрина (16)", "пункты МТС, synth (13)", "synth v1 (12)", "v2hard (8)", "шум на чистом"], [
        ["Детерминированный слой", "3", "3", "6", "0", "0"],
        ["Промпт-бейзлайн GPT-5.5", "11", "6", "10", "8", "15"],
        ["Конвейер GPT-5.5 (v2g)", "14–16", "12", "7–9", "7", "9"],
        ["Конвейер + энтропия (v2e)", "16", "12", "10", "7", "7"],
        ["Конвейер + логит-зонд (v2l)", "16", "12", "7", "7", "7"],
        ["Конвейер gpt-oss-120b (self-hosted)", "12–14", "11", "9", "7", "11"],
    ], note="Промпт слеп к шаблону (0/6) и промахивает лёгкое; конвейер закрывает все 8 пунктов МТС. Разброс GPT между прогонами ±2 → консенсус двух прогонов. Источник: experiments/EXP-13…16.",
       col_widths=[3.6, 1.7, 2.1, 1.5, 1.4, 1.6])

    add_bullets(prs, "Что показали эксперименты (и что починили по ним)", [
        "Критик резал правду: верным замечаниям по Data Catalog, кластеру Kafka, типовым фильтрам ставил 0 → официальные слоты не подлежат порогу (3/7 → 7/7)",
        "Треть слотов чеклиста терялась молча из-за схемы ответа → починено; зонды получили свои слоты: doc3 14/16 → 16/16",
        "«Шум» на чистой синтетике трижды оказывался реальными дефектами базы → правило: читать сырые выводы глазами",
        "Разрыв self-hosted 120b и GPT-5.5 — 4 «выводных» дефекта целевого документа; у GPT их добирают зонды → путь: vLLM + логиты на 120b",
        "Демо на документах МТС через контур: doc3 14/16, doc1 12/12 на 120b",
    ])

    add_bullets(prs, "Демонстрация: сквозной сценарий", [
        "PDF выгрузки Confluence → сервис документов: секции и таблицы восстановлены (doc1 11, doc2 8, doc3 14 секций)",
        "Загрузка в UI → очередь → воркер: прогресс по этапам, кандидаты, вызовы, токены, оценка остатка",
        "Отчёт: светофор, покрытие чеклиста, находки по разделам с цитатой / почему / что уточнить",
        "История версий документа: что закрылось между версиями; 👍/👎 по каждой находке",
        "Мониторинг: RabbitMQ (очередь, DLQ), Grafana (длительность, вызовы, находки по классам, UNKNOWN)",
        "Сверка с разметкой одним скриптом: recall и список «лишних» для разметки",
    ])

    add_table(prs, "Риски и как их закрываем", ["Риск", "Мера"], [
        ["Галлюцинация цитаты", "программная верификация: нет в документе → отбрасываем; anchoring 96–100%"],
        ["Фильтр режет правду", "официальные пункты и детерминированные находки вне порога критика"],
        ["Разброс модели ±2", "консенсус двух прогонов, числа как диапазон"],
        ["Ложные срабатывания на обезличивании", "правило в промптах + score 0 в критике (EXP-16)"],
        ["Слабая self-hosted модель", "зонды неоднозначности через vLLM/logprobs; лестница моделей на одном бенче"],
        ["Синтетика ≠ реальность", "вычитка сырых выводов, тройная разметка голдов до финала"],
        ["Длинные документы", "обрыв на ~28k символов → чанкование по секциям (план)"],
    ], col_widths=[4.2, 7.9])

    add_bullets(prs, "План до финала (07.09)", [
        "vLLM вместо ollama для gpt-oss-120b → логит-зонд и энтропия на self-hosted модели; цель doc3 ≥ 15/16",
        "Тройная разметка голдов документов МТС, пересчёт всех таблиц",
        "Детерминированные детекторы для оставшихся слепых зон (ссылка на раздел, таблица без структуры, тип против значений)",
        "Дашборд качества: recall по итерациям рядом с эксплуатационными метриками",
        "Отчёт-обоснование архитектуры по журналу экспериментов; финальное демо на новом документе кейсодателя",
    ])

    add_table(prs, "Команда и распределение задач", ["Участник", "Роль", "Зона ответственности", "Степень участия"], [
        ["Коротков Леонид (@fDAFX)", "AI Engineer, лид",
         "архитектура и конвейер ревью, эксперименты и оценка, self-hosted модель, инфраструктура (compose, очередь, история, мониторинг), описание и презентация",
         "ведущая (≈70%)"],
        ["Сокол Тимофей (@xcmgg)", "AI Product",
         "пользователь и гипотеза, границы MVP, критерии успеха и риски; фронтенд аналитика (интеграция с API к финалу)",
         "≈20%"],
        ["Рыженко Виктор (@RyzhenkoViktor)", "AI Engineer",
         "вычитка документов МТС и разметка дефектов (второй размётчик), проверка демо-сценария",
         "≈10%"],
    ], note="Степени участия — оценка на 04.09; в финальной версии уточняются по фактическому вкладу.", col_widths=[3.0, 2.0, 5.3, 1.8])

    prs.save(OUT)
    print("saved", OUT, "slides:", len(prs.slides))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
