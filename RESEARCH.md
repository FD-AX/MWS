# Рисёрч: как решали автоматическое ревью ТЗ (кейс NET, хакатон)

Дата: 2026-09-02. Три направления: академия (RE + NLP/LLM), коммерческие инструменты, инженерная практика LLM-ревью в смежных доменах.

**Главный вывод:** задача изучается 25+ лет, но готового публичного решения «LLM ревьюит ТЗ на data-пайплайн» нет — ниша открыта. Документированный failure mode №1 у всех подходов (и правил, и LLM) — over-flagging: high recall / low precision. Все выжившие решения сходятся к одному набору паттернов (см. §5).

---

## 1. Академия: таксономии, pre-LLM инструменты, LLM-статьи

### 1.1 Таксономии дефектов (готовые списки классов)

**Berry & Kamsties, «Ambiguity Handbook» (2003)** — базовая таксономия неоднозначности:
лексическая (полисемия), синтаксическая (attachment/coordination/scope), семантическая (кванторы «все/каждый»), прагматическая (анафора «оно/это»), плюс vagueness («быстрый») и generality (гипероним вместо конкретики).
https://cs.uwaterloo.ca/~dberry/handbook/ambiguityHandbook.pdf

**ISO/IEC/IEEE 29148:2018** — 9 характеристик отдельного требования (unambiguous, complete, singular, verifiable, …) + **5 характеристик набора** (complete, consistent, feasible, comprehensible, able to be validated) + список запрещённой лексики (superlatives, vague pronouns, open-ended terms, loopholes).
https://www.iso.org/standard/72089.html

**INCOSE Guide to Writing Requirements v4 (2023)** — 15 характеристик + 42 правила (vague terms «adequate/reasonable», escape clauses «where possible», open-ended «including but not limited to», запрет местоимений, одна мысль на требование, измеримые значения с допусками, и т.д.).
https://www.incose.org/docs/default-source/working-groups/requirements-wg/guidetowritingrequirements/incose_rwg_gtwr_v4_summary_sheet.pdf
Разбор 42 правил: https://reqi.io/articles/incose-requirements-quality-42-rule-guide

**Requirements Smells (Femmer et al., 2017)** — 9 запахов из ISO 29148: subjective language, ambiguous adverbs/adjectives, loopholes, open-ended non-verifiable terms, superlatives, comparatives, negative statements, vague pronouns, incomplete references.
https://arxiv.org/abs/1611.08847

**NASA ARM** — счётчики: imperatives, continuances, directives, weak phrases («capability to», «at a minimum»), options («can», «optionally»), incompletes (TBD/TBR).
https://sceweb.sce.uhcl.edu/helm/Risk_Man_WEB/Track%20Notes_files/rmfrid.htm

**QuARS** — optionality, subjectivity, vagueness, weakness, implicity (неявные субъекты), multiplicity, under-specification.
https://iris.cnr.it/bitstream/20.500.14243/450785/1/prod_160278-doc_62891.pdf

### 1.2 Pre-LLM инструменты: подходы и цифры

| Работа | Подход | Цифры | Почему не взлетело |
|---|---|---|---|
| NASA ARM (~1996) | подсчёт слов по категориям | P/R не публиковали | поверхностно; закрыт к 2011 |
| QuARS (2005) | словари + shallow parsing | в позднем сравнении: R<66%, P<57% | словари надо сопровождать под домен |
| Smella (Femmer, 2017) | POS + словари, 9 smells | **P=59%, R=82%** (разброс большой) | FP-нагрузка |
| Rosadini/Ferrari (railway, 2018) | JAPE-правила, цель R≈100% | P до **85.6%** — только после «discard patterns» (правил-глушилок FP) | ручная доменная настройка |
| REVV-Light (Dalpiaz, 2019) | эмбеддинги для near-synonymy | не обошёл ручную инспекцию | итог самих авторов |
| Ezzini (ICSE 2022) | ML + SpanBERT, анафора | детекция P≈60% при R=100% | узкий класс; «recall дёшев, precision дорог» |
| Paska (TSE 2023) | Tregex-паттерны + глоссарии | **P=89%, R=89%** на 1321 треб. | лучший pre-LLM, но заточен под 1 домен |

Восприятие практиков (Montgomery 2024): ambiguity и verifiability — самые тяжёлые классы (по 80%), ambiguity и complexity — самые частые (по 70%). https://arxiv.org/html/2404.11106v1

### 1.3 LLM-эра (2023–2025) — ключевые статьи

- **Ronanki 2023** (user stories, GPT vs rule-based AQUSA): GPT-4 совпал с человеком лучше правил; нестабильность лечится «best of three». https://arxiv.org/abs/2306.12132
- **Lubos, RE 2024** (Llama-2-70b по 9 характеристикам ISO): на 10 требованиях P/R=0.50/0.89; на реалистичных 63 — **обвал до P=0.13, κ=0.05**. Вывод: не скармливать весь документ разом, человек обязателен. https://arxiv.org/abs/2408.10886
- **Bashir, ICSME 2025** (индустрия, Alstom/Westermo): без доменного заземления LLM = тот же over-flagging; **10-shot на реальных дефектах даёт +20.2%** против zero-shot. https://www.ipr.mdu.se/pdf_publications/7221.pdf
- **HLC 2026** (Mercedes-Benz, QuRE): few-shot из валидированных аналитиком примеров **с объяснениями** — значимый прирост уже с **~20 примеров**, бьёт fine-tuned BERT. https://arxiv.org/abs/2601.01952
- **Luitel** (полнота): «чего не хватает» ищется иначе, чем «что написано плохо» — отдельная задача/проход. https://arxiv.org/abs/2302.04792
- **SLR по LLM4RE** (74 работы): zero-shot ревью «слишком generic»; дефект-детекция недоразвита = наша ниша. https://arxiv.org/html/2509.11446v1
- **Krishna 2024**: GPT-4 ревьюит SRS «на уровне джуна», конструктивно. https://arxiv.org/abs/2404.17842

### 1.4 Датасеты

- **PURE**: 79 публичных SRS, 34k предложений (без разметки дефектов). DOI 10.5281/zenodo.1414117
- **QuRE** (2025): 1266 индустриальных требований Mercedes-Benz с разметкой дефектов. https://arxiv.org/pdf/2508.08868
- PROMISE NFR (625/969 треб.), артефакты TAPHSIR (анафора): https://zenodo.org/records/5903104
- Общепринятого gold standard по ambiguity для SRS нет — известная дыра.

---

## 2. Коммерческие инструменты

### 2.1 IBM RQA (Watson) — ЗАКРЫТ, поучительно почему

10 индикаторов (из INCOSE): unclear actor, compound requirement, negative requirement, escape clause, missing units, missing tolerances, ambiguity, passive voice, incomplete (TBD), unspecific quantities. Score 0–100 на требование, batch-анализ в DOORS.
**Кейс Bosch (REFSQ 2021, независимый): 132/158 находок не совпали с ручным ревью.** Синтаксис предложения ≠ реальные проблемы (полнота/консистентность — свойства набора). SaaS закрыт в 2023.
https://ceur-ws.org/Vol-2857/nlp4re8.pdf • https://www.ibm.com/docs/en/erqa?topic=assistant-overview

### 2.2 QVscribe (QRA Corp) — жив, лидер ниши

Индикаторы скора: one and only one imperative, no negative imperatives, no vagueness, no escape clauses, no open-ended clauses («including but not limited to», «etc.»), no superfluous infinitives, no cross-referencing pronouns, no immeasurable quantification, no non-specific temporal words, few continuances. Плюс документ-уровень: консистентность терминологии и единиц, дубли, **EARS-конформность**.
Скор 1–5 на требование, светофор; подсветка прямо в тексте (Word/Jama/DOORS); LLM только в rewrite-модуле.
https://edu.qracorp.com/knowledge/understanding-the-quality-analysis-score

### 2.3 ScopeMaster — документ-уровень как главная фишка

350+ тестов; уникальное: **omissions** (CRUD-матрица: «есть create/read, нет delete»), дубли, разные имена одной сущности. Схема находки: `{type: POSITIVE|NEGATIVE|ADVISORY, category, severity: Critical..Advisory, description+fix}`.
https://help.scopemaster.com/article/49-requirements

### 2.4 Jama Connect Advisor

~40 правил INCOSE + 6 паттернов EARS; slide-over панель: INCOSE-score в %, нарушенные правила, рекомендации.
https://help.jamasoftware.com/ah/en/jama-connect-advisor-.html

### 2.5 Новая LLM-волна

- Siemens Polarion AI Optimizer (валидация против INCOSE), PTC Codebeamer Copilot (с Microsoft/VW, Azure OpenAI), Visure AI, reqSuite rm (детерминированный слой + LLM-слой).
- **Copilot4DevOps**: Analyze оценивает work item по чеклист-фреймворкам 6C / INVEST / INCOSE / EARS — LLM даёт рейтинг+фидбек по каждому измерению. https://copilot4devops.com/product/

### 2.6 Кейсы с цифрами (для питча)

- **RCAF + QVscribe**: время ревью −50…−75%; гейт «75–85% требований со скором 5/5»; финальное ревью идёт по отчёту тула. https://qracorp.com/whitepapers/rcaf-case-study/
- Bosch: инспекция ~неделя → секунды, но 132/158 мимо (предостережение).
- Отраслевое: 70–85% переделок — из-за дефектных требований.

---

## 3. Инженерная практика LLM-ревью (смежные домены)

### 3.1 AI code review — уроки продов

- **Cursor Bugbot**: 8 параллельных проходов с перемешанным порядком файлов → majority voting → модель-валидатор → фильтры. Resolution rate 52%→70%+. Контринтуитивно: генератор промптуется **агрессивнее** («флагай всё»), потому что шум режут фильтры ниже по конвейеру. https://cursor.com/blog/building-bugbot
- **Greptile «How to Make LLMs Shut Up»**: 19% полезных комментов исходно. НЕ сработали: few-shot на стиль, **LLM-judge поверх изолированных находок** («nearly random»). Сработало: эмбеддинги прошлых комментов с даунвоутами (19%→55%). https://www.greptile.com/blog/make-llms-shut-up
- **Qodo PR-Agent** (open source): self-reflection — судья скорит 0–10 **видя все находки сразу** (сравнительная оценка), порог отсечки, ранжирование. Контраст с Greptile = изолированный vs сравнительный судья. https://docs.pr-agent.ai/core-abilities/self_reflection/
- **CodeRabbit**: «verification scripts» — перед публикацией находки модель генерит проверку, подтверждающую предположение фактом; Learnings из фидбека. https://www.coderabbit.ai/blog/how-coderabbit-delivers-accurate-ai-code-reviews-on-massive-codebases
- **GitHub Copilot CR**: **молчание — валидный выход** (29% ревью без замечаний); группировка однотипных находок; severity High/Medium/Low; привязка к логическим диапазонам. https://github.blog/ai-and-ml/github-copilot/60-million-copilot-code-reviews-and-counting/
- **Anchoring**: LLM галлюцинирует номера строк → нумеровать строки в подаваемом тексте, требовать дословную цитату, верифицировать substring-match снаружи, при провале — переанкорить или дроп.

### 3.2 Критика и grounding

- **CriticGPT (OpenAI)**: критик на данных с намеренно внесёнными багами; трейдофф precision vs comprehensiveness. Методика подсаженных дефектов = наша методика оценки. https://openai.com/index/finding-gpt4s-mistakes-with-gpt-4/
- **Self-correction не работает интринсик** (ICLR 2024): критик — отдельный вызов с другой рамкой, не «перечитай себя».
- **CheckEval (EMNLP 2025)**: декомпозиция критерия в бинарные чеклист-вопросы → +0.45 согласованности оценщиков. https://arxiv.org/abs/2403.18771
- **Anthropic Citations API**: цитата извлекается, а не генерируется; +15% recall против промптовых цитат. Паттерн воспроизводим вручную (quote в JSON + substring-верификация). https://www.anthropic.com/news/introducing-citations-api

### 3.3 Ревью design-doc / PRD

- **arxiv 2509.09975** (индустриальный кейс): 11 ревью-перспектив, LLM надёжно ловит **междокументные/межсекционные несоответствия**; главная техническая боль — таблицы в доках (у ТЗ на витрины маппинги — это таблицы!). https://arxiv.org/abs/2509.09975
- PM-практика сходится к рамке: «прочитай PRD как инженер, который должен это реализовать — где придётся угадывать?»
- Продукта-лидера «PRD review AI» нет — рынок фрагментирован.

### 3.4 Доменный чеклист для ТЗ на потоки/витрины

Источники: data contracts (datacontract.com), dbt model contracts, DWH-testing чеклисты (Datagaps, guru99):

- схема: поля/типы/констрейнты + **семантика полей**
- source-to-target mapping: покрытие каждого поля
- инкрементальная логика: по какому полю, late-arriving data, удаления в источнике
- null-обработка per-field (default/flag/reject), дедупликация (бизнес-ключ, какая запись выживает)
- ключи витрины (surrogate/business)
- SLA: freshness/completeness/availability, частота и окно загрузки
- обработка ошибок/ретраи/идемпотентность, реконсиляция row counts
- объёмы данных, ретеншен
- ownership, версионирование, процесс изменений
- мониторинг/алертинг

---

## 4. Сводные выводы (кросс-подтверждённые всеми тремя треками)

1. **Фиксированная таксономия + бинарный чеклист вместо «найди проблемы»** (Smella/Paska/Lubos + CheckEval + Copilot4DevOps). Каждый пункт — вопрос с обязательным evidence-quote или вердиктом MISSING.
2. **Документ-уровень — главный differentiator.** Bosch похоронил sentence-level подход; ScopeMaster выжил на omissions/консистентности; LLM доказанно ловит межсекционные противоречия. Отдельный проход «по документу целиком»: каждое поле маппинга описано в источнике? термины консистентны? у каждого шага есть вход и выход?
3. **Генерация ≠ фильтрация.** Генератор агрессивно на recall; отдельный критик (другой вызов/рамка) режет precision; судья скорит **все находки сразу**, сравнительно. Consensus из 2–3 прогонов с перемешанным порядком секций — дёшево.
4. **Обязательная дословная цитата + программная substring-верификация.** Не матчится → дроп; матчится в другом месте → переанкорить. Убивает класс галлюцинаций и закрывает критерий кейса «показывает, к какой части документа относится».
5. **Не скармливать весь документ одним промптом** (Lubos: κ 0.75→0.22 при росте 10→63 треб.). По секциям, отдельные проходы на кластеры проверок.
6. **Доменное заземление + few-shot на реальных прошлых дефектах** (+20% ICSME; ~20 валидированных примеров с объяснениями достаточно). Этап 3 кейса (корректировки разработчиков) = ровно этот датасет.
7. **Детерминированный слой окупается**: TBD/«и т.д.»/числа без единиц/пустые разделы — бесплатно, объяснимо, precision 100%. LLM — на семантику, полноту, консистентность.
8. **Подача**: severity (Critical/High/Medium/Advisory) + светофорный скор документа + группировка однотипных + явное «замечаний нет» по чистым секциям + suggested fix (вариант переписывания / конкретный вопрос).
9. **Оценка = методика подсаженных дефектов** (CriticGPT): 2–3 ТЗ с внесёнными дефектами разных классов → recall по подсаженным + precision@k + anchoring rate; чистое ТЗ → проверка отсутствия шума.

## 5. Маппинг на этапы кейса

| Этап кейса | Что берём из рисёрча |
|---|---|
| 1. Анализ шаблона | структурный детерминированный проход: обязательные разделы, пустые/формальные |
| 2. Примеры ТЗ | few-shot «хорошее описание» + калибровка чеклиста |
| 3. Корректировки разработчиков | таксономия дефектов из реальных правок + 10–20 few-shot примеров с объяснениями (главный рычаг precision) |
| 4. Модель/агент | пайплайн: детерминированный слой → чеклист-проходы по секциям → документ-уровень (консистентность/полнота) → «персона разработчика» → критик-ранжировщик → верификация цитат → отчёт |
| 5. Тестирование | подсаженные дефекты + чистое ТЗ, метрики: recall по подсаженным, precision@k, anchoring rate |

## 6. Цифры для питча

- 70–85% переделок в проектах — из-за дефектных требований; до 80% дефектов закладываются на этапе требований.
- RCAF: −50…−75% времени ревью со скоринг-гейтом; ревью-инспекция ~неделя → секунды.
- Bosch/RQA: 132/158 ложных — почему наивный подход не работает и что мы делаем иначе.
- Bugbot: resolution rate 52→70%+ за счёт разделения генерации и фильтрации; Greptile: 19→55% полезности за счёт обучения на фидбеке.
- Позиционирование: pre-review (чистим дешёвые дефекты до людей), не замена аналитика — ровно как в кейсе.
