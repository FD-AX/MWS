from __future__ import annotations

import os
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path

import streamlit as st

from tz_review.api_client import api_url, result_from_payload, submit_review, wait_for_review
from tz_review.config import ENV_VARS, load_dotenv, settings_or_die
from tz_review.document import parse
from tz_review.input import DocumentInputError, extract_text
from tz_review.pipeline import ReviewResult, review
from tz_review.report import to_json, to_markdown, verdict
from tz_review.rubric import load_rubric
from tz_review.schema import Finding


ROOT = Path(__file__).resolve().parent
EXAMPLES = {
    "Витрина-агрегат устройств": ROOT / "casedata" / "doc3_mart_devices.md",
    "Поток геоданных": ROOT / "casedata" / "doc1_stream_geo.md",
    "Источник CDR": ROOT / "casedata" / "doc2_source_cdr.md",
}
SEVERITY_LABEL = {
    "critical": "Критичные",
    "high": "Важные",
    "medium": "Умеренные",
    "advisory": "Информационные",
}
SEVERITY_SHORT = {
    "critical": "Критичное",
    "high": "Важное",
    "medium": "Умеренное",
    "advisory": "Информационное",
}
SEVERITY_COLOR = {
    "critical": "#ff625f",
    "high": "#f5a24b",
    "medium": "#f4cf4f",
    "advisory": "#a3a3a3",
}


st.set_page_config(
    page_title="DocReview AI",
    page_icon=":material/fact_check:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --bg: #0d0d0d;
        --sidebar: #080808;
        --panel: #151515;
        --panel-soft: #191919;
        --line: #2b2b2b;
        --line-soft: #202020;
        --text: #f2f2f2;
        --muted: #9a9a9a;
        --muted-2: #6f6f6f;
        --violet: #d8d8d8;
        --violet-2: #d8d8d8;
        --green: #39c8a5;
        --red: #ff625f;
        --orange: #f5a24b;
        --yellow: #f4cf4f;
        --blue: #a3a3a3;
    }
    html, body, [class*="css"] { color: var(--text); }
    .stApp, [data-testid="stAppViewContainer"] { background: var(--bg); color: var(--text); }
    [data-testid="stHeader"] { background: transparent; height: 0; min-height:0; }
    [data-testid="stToolbar"], #MainMenu, footer { visibility: hidden; }
    [data-testid="stSidebar"] {
        background: var(--sidebar); border-right: 1px solid var(--line-soft);
        width: 240px !important;
    }
    [data-testid="stSidebar"][aria-expanded="false"] {
        display:block !important; visibility:visible !important; transform:none !important;
        min-width:240px !important; max-width:240px !important; margin-left:0 !important;
    }
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarContent"] {
        display:block !important; visibility:visible !important;
    }
    [data-testid="stSidebar"] > div:first-child { width: 240px !important; }
    [data-testid="stSidebarContent"] { padding-left:10px !important; padding-right:10px !important; }
    [data-testid="stSidebarHeader"] { display:none; height:0; min-height:0; }
    [data-testid="stSidebar"] .block-container { padding: 1.15rem .95rem 1rem; }
    .block-container { max-width: 1480px; padding: .8rem 1rem 2.5rem 1.35rem; }
    [data-testid="stSidebar"] { display:none !important; }
    [data-testid="stMain"] { margin-left:240px; width:calc(100vw - 240px); flex:none; }
    .fixed-sidebar { position:fixed; inset:0 auto 0 0; width:240px; z-index:9999;
        background:var(--sidebar); border-right:1px solid var(--line-soft); }
    [data-testid="stElementContainer"]:has(.fixed-sidebar) {
        position:fixed !important; width:0 !important; height:0 !important;
        margin:0 !important; padding:0 !important;
    }
    .fixed-sidebar .brand { position:absolute; top:19px; left:20px; width:200px;
        margin:0; padding:0; }
    .fixed-nav { position:absolute; top:132px; left:12px; width:216px; }
    .fixed-sidebar .nav-stack { margin:0; }
    .fixed-sidebar .side-card { position:absolute; left:20px; width:200px; box-sizing:border-box;
        margin:0; }
    .fixed-tip { top:484px; }
    .fixed-about { top:626px; }
    .st-key-sidebar_new_analysis { position:fixed !important; top:79px; left:20px;
        width:200px !important; z-index:10001; }
    h1, h2, h3, h4, p, label, [data-testid="stMarkdownContainer"] {
        color: var(--text); letter-spacing: 0;
    }
    h1 { font-size: 1.34rem; line-height: 1.3; margin: 0 0 1rem; }
    h2 { font-size: 1.05rem; line-height: 1.3; }
    h3 { font-size: 0.94rem; line-height: 1.3; }
    p, label, [data-testid="stMarkdownContainer"] { font-size: 0.92rem; }
    .brand { display:flex; align-items:center; gap:.48rem; margin-top:1rem;
        padding:.2rem .3rem 1.85rem;
        font-weight:750; font-size:.96rem; color:var(--text); white-space:nowrap; }
    .brand-mark { width:30px; height:30px; display:grid; place-items:center; color:var(--violet-2);
        border:0; font-size:1.55rem; font-weight:500; }
    .beta { margin-left:auto; padding:.12rem .3rem; border-radius:4px; color:#d6d6d6;
        background:#292929; font-size:.58rem; font-weight:700; }
    .nav-stack { display:grid; gap:.32rem; margin:.15rem -.5rem 0; }
    .nav-item { display:flex; align-items:center; gap:.65rem; min-height:42px; padding:.55rem .72rem;
        border-radius:6px; color:#a3a3a3; font-size:.82rem; border:1px solid transparent; }
    .nav-item.active { color:#f5f5f5; background:#1b1b1b; border-color:#303030; }
    .nav-glyph { width:22px; color:#c5c5c5; font-size:1.05rem; text-align:center; }
    .side-spacer { height:86px; }
    .side-card { margin-top:.75rem; padding:.9rem; background:var(--panel); border:1px solid var(--line);
        border-radius:7px; }
    .side-card strong { display:block; font-size:.78rem; margin-bottom:.55rem; }
    .side-card span { color:var(--muted); font-size:.72rem; line-height:1.55; }
    .side-more { display:inline-block; margin-top:1rem; padding:.5rem .7rem; color:#e0e0e0;
        background:#242424; border-radius:5px; font-size:.71rem; }
    .topbar { min-height:34px; display:flex; align-items:flex-start; justify-content:space-between;
        padding:.12rem .4rem 0; }
    .workspace-title { font-size:1.08rem; font-weight:720; color:var(--text); }
    .user-tools { display:flex; align-items:center; gap:.68rem; color:var(--muted); font-size:.74rem; }
    .workspace-title, .user-tools { transform:translateY(-10px); }
    .moon { font-size:1.05rem; color:#a6aec0; padding-right:.65rem; border-right:1px solid var(--line); }
    .avatar { width:32px; height:32px; display:grid; place-items:center; border-radius:50%;
        color:#cbc7ff; background:#25263e; font-size:.72rem; }
    .shell-card { background:var(--panel); border:1px solid var(--line); border-radius:8px;
        padding:1rem 1.1rem; }
    .doc-header { display:flex; align-items:center; gap:.85rem; min-height:54px; }
    .doc-icon { width:42px; height:46px; display:grid; place-items:center; border-radius:6px;
        background:#242424; border:1px solid #383838; color:white; font-size:.7rem; font-weight:800; }
    .doc-name { font-size:.94rem; font-weight:700; color:var(--text); overflow-wrap:anywhere; }
    .doc-meta { color:var(--muted); font-size:.72rem; margin-top:.18rem; }
    .status-ok { display:inline-flex; align-items:center; gap:.42rem; color:var(--green);
        background:#0c2b2c; border:1px solid #15403f; border-radius:6px; padding:.5rem .7rem;
        font-size:.75rem; font-weight:650; }
    .status-dot { width:8px; height:8px; border:2px solid var(--green); border-radius:50%; }
    .st-key-document_shell { background:var(--panel); border-color:var(--line) !important;
        border-radius:8px 8px 0 0 !important;
        padding:1rem .85rem 1.65rem 1.45rem !important; }
    .st-key-document_shell [data-testid="stVerticalBlock"] { gap:.45rem; }
    .panel { min-height:302px; height:100%; box-sizing:border-box; background:var(--panel);
        border:1px solid var(--line); border-radius:8px; padding:1rem; }
    .panel-title { font-size:.9rem; font-weight:700; margin-bottom:.8rem; }
    .overview-grid { display:grid; grid-template-columns:minmax(145px,.72fr) minmax(250px,1.28fr);
        gap:1rem; align-items:center; }
    .donut-wrap { display:grid; place-items:center; }
    .donut { width:142px; height:142px; border-radius:50%; display:grid; place-items:center;
        position:relative; transform:rotate(-90deg); }
    .donut::after { content:""; position:absolute; inset:15px; border-radius:50%; background:var(--panel); }
    .donut-center { position:relative; z-index:1; text-align:center; transform:rotate(90deg); }
    .donut-number { font-size:2rem; font-weight:760; line-height:1; }
    .donut-label { color:var(--muted); font-size:.68rem; margin-top:.28rem; }
    .legend { display:grid; gap:.36rem; }
    .legend-row { display:grid; grid-template-columns:10px 1fr auto; gap:.58rem; align-items:center;
        padding:.28rem .58rem; border:1px solid var(--line); border-radius:6px; background:#121212; }
    .legend-dot { width:8px; height:8px; border-radius:3px; }
    .legend-copy strong { display:block; font-size:.74rem; }
    .legend-copy span { display:block; color:var(--muted); font-size:.63rem; }
    .legend-count { font-weight:720; font-size:.82rem; }
    .panel-note { color:var(--muted); font-size:.72rem; margin-top:.85rem; }
    .summary-copy { color:var(--muted); font-size:.74rem; line-height:1.55; margin-bottom:.9rem; }
    .summary-panel { position:relative; }
    .summary-panel::after { content:"✧"; position:absolute; top:.8rem; right:1rem;
        color:#cfcfcf; font-size:1.5rem; }
    .summary-list { display:grid; gap:.72rem; }
    .summary-item { display:grid; grid-template-columns:10px 1fr; gap:.62rem; align-items:start; }
    .summary-item .marker { width:7px; height:7px; border-radius:50%; margin-top:.38rem; }
    .summary-item span { color:#b8b8b8; font-size:.72rem; line-height:1.45; }
    .summary-button { display:inline-flex; align-items:center; margin-top:1rem; padding:.55rem .72rem;
        color:#e0e0e0 !important; background:#242424; border:1px solid #343434;
        border-radius:5px; font-size:.72rem; text-decoration:none !important; }
    .remarks-title { font-size:.9rem; font-weight:700; margin-bottom:.05rem; }
    .st-key-remarks_panel { margin-top:.65rem; background:var(--panel);
        border-color:var(--line) !important; border-radius:8px !important; padding:.8rem 1rem .25rem !important; }
    .st-key-remarks_panel [data-testid="stVerticalBlock"] { gap:.38rem; }
    .findings-head { display:grid; grid-template-columns:112px 165px 1fr 90px; gap:.75rem;
        color:var(--muted-2); font-size:.68rem; padding:.55rem .7rem; border-bottom:1px solid var(--line); }
    .finding-row { display:grid; grid-template-columns:112px 165px 1fr 90px; gap:.75rem;
        align-items:center; padding:.72rem; border-bottom:1px solid var(--line-soft); }
    .finding-row:last-child { border-bottom:0; }
    .level-pill { display:inline-flex; align-items:center; width:fit-content; border-radius:5px;
        padding:.26rem .46rem; font-size:.66rem; font-weight:700; }
    .section-name { font-size:.75rem; font-weight:620; color:#dddddd; }
    .section-code { color:var(--muted-2); font-size:.63rem; margin-top:.16rem; }
    .finding-copy { color:#c8c8c8; font-size:.72rem; line-height:1.4; overflow-wrap:anywhere; }
    .finding-ask { display:inline-block; margin-top:.22rem; padding:.12rem .32rem; color:#9b9b9b;
        background:#1d1d1d; border-radius:3px; font-size:.62rem; }
    .new-status { color:#b8b8b8; font-size:.68rem; white-space:nowrap; }
    .new-status::before { content:""; display:inline-block; width:6px; height:6px; margin-right:.38rem;
        border-radius:50%; background:var(--blue); box-shadow:0 0 8px rgba(180,180,180,.25); }
    .empty-state { min-height:290px; display:grid; place-items:center; text-align:center;
        border:1px dashed #3d3d3d; border-radius:8px; color:var(--muted); background:var(--panel); }
    .empty-state strong { display:block; color:var(--text); font-size:1rem; margin-bottom:.35rem; }
    .empty-state span { font-size:.76rem; }
    .stButton > button, .stDownloadButton > button { border-radius:6px; min-height:2.55rem;
        border-color:#383838; background:#1d1d1d; color:#eeeeee; font-weight:650; }
    .stDownloadButton > button { font-size:.75rem; }
    .stButton > button:hover, .stDownloadButton > button:hover { border-color:var(--violet);
        color:white; background:#292929; }
    .stButton > button[kind="primary"] { background:#242424;
        border-color:#424242; color:white; }
    [data-testid="stSidebar"] .stButton > button { justify-content:flex-start; min-height:2.25rem; }
    [data-testid="stSidebar"] hr { border-color:var(--line-soft); }
    [data-testid="stFileUploaderDropzone"] { background:#151515; border:1px dashed #444444;
        border-radius:8px; min-height:155px; }
    [data-testid="stFileUploaderDropzone"] button { background:#242424; color:#eeeeee; }
    [data-testid="stTabs"] { margin-top:-16px; }
    [role="tablist"] { gap:2.15rem; min-height:46px; padding:0 1.8rem;
        background:var(--panel); border:1px solid var(--line); border-radius:0 0 8px 8px; }
    [data-baseweb="tab"] { color:var(--muted); background:transparent; padding-left:.72rem;
        padding-right:.72rem; }
    [data-baseweb="tab"][aria-selected="true"] { color:#ffffff; }
    [data-baseweb="tab-highlight"] { background:var(--violet) !important; }
    [data-baseweb="input"] > div, [data-baseweb="select"] > div, textarea, .stTextArea textarea {
        background:#121212 !important; color:var(--text) !important; border-color:var(--line) !important;
        border-radius:6px !important; }
    [data-baseweb="input"] { background:#121212 !important; border:1px solid var(--line) !important;
        border-radius:6px !important; }
    [data-testid="stTextInputRootElement"],
    .st-key-result_level .react-aria-ComboBox > div,
    .st-key-result_sort .react-aria-ComboBox > div {
        background:#121212 !important; border:1px solid var(--line) !important;
        border-radius:6px !important;
    }
    .st-key-remarks_panel [data-testid="stTextInput"] input,
    .st-key-remarks_panel [data-baseweb="select"] > div { min-height:34px; height:34px; font-size:.72rem; }
    [data-testid="stExpander"] { background:var(--panel); border-color:var(--line); border-radius:7px; }
    [data-testid="stAlert"] { border-radius:6px; }
    .stCodeBlock { border:1px solid var(--line); border-radius:6px; }
    @media (max-width:980px) {
        [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child { width:210px !important; }
        .block-container { padding-left:.9rem; padding-right:.9rem; }
        [role="tablist"] { gap:.4rem; padding-left:.5rem; padding-right:.5rem; overflow-x:auto; }
        .overview-grid { grid-template-columns:1fr; }
        .findings-head { display:none; }
        .finding-row { grid-template-columns:105px 1fr; }
        .finding-copy { grid-column:1 / -1; }
        .new-status { justify-self:end; }
    }
    @media (max-width:720px) {
        .fixed-sidebar { display:none; }
        [data-testid="stMain"] { margin-left:0; width:100vw; }
        .st-key-sidebar_new_analysis { position:relative !important; inset:auto !important;
            width:100% !important; margin-bottom:.7rem; }
        [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {
            width:min(82vw,260px) !important; }
        [data-testid="stHorizontalBlock"] { flex-wrap:wrap; gap:.75rem !important; }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            flex:1 1 100% !important; width:100% !important; min-width:100% !important; }
        .block-container { padding:.8rem .7rem 2rem; }
        .topbar { padding-left:0; }
        .user-tools { display:none; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def build_demo_review() -> dict:
    specs = [
        ("critical", "2. Источники данных", "Стр. 12", "Источники данных",
         "Не указано расписание и периодичность поставки данных от источника.",
         "Расписание обновления, формат инкремента и правила повторной загрузки."),
        ("critical", "4. Преобразования", "Стр. 18", "Преобразования",
         "Описание логики расчёта показателя не содержит формулы и условий.",
         "Формулу расчёта, условия применения и используемые фильтры."),
        ("high", "5. Выходные данные", "Стр. 25", "Выходные данные",
         "Не описан формат данных для поля «status».",
         "Тип данных, допустимые значения и пример заполнения."),
        ("critical", "6. Контроль качества", "Стр. 31", "Контроль качества",
         "Не определены проверки качества и допустимые пороги отклонений.",
         "Набор проверок, пороги и действия при нарушении качества."),
        ("high", "3. Схема данных", "Стр. 15", "Схема данных",
         "Для части атрибутов не указаны обязательность и значения по умолчанию.",
         "Обязательность полей, ограничения и значения по умолчанию."),
        ("high", "7. Обработка ошибок", "Стр. 34", "Обработка ошибок",
         "Не определено поведение системы при частичной загрузке данных.",
         "Сценарии повтора, отката и уведомления ответственных."),
        ("high", "8. Мониторинг", "Стр. 38", "Мониторинг",
         "Не перечислены метрики, по которым контролируется работа потока.",
         "Метрики, пороги предупреждений и каналы оповещения."),
        ("high", "9. SLA", "Стр. 41", "SLA",
         "Требования к доступности и времени восстановления сформулированы неоднозначно.",
         "Целевые значения доступности, RTO и RPO."),
        ("medium", "1. Назначение", "Стр. 4", "Назначение",
         "Бизнес-цель документа не связана с измеримым результатом.",
         "Ожидаемый эффект и критерий достижения цели."),
        ("medium", "10. Безопасность", "Стр. 44", "Безопасность",
         "Не уточнены роли доступа к исходным и итоговым наборам данных.",
         "Роли, права чтения и изменения, правила аудита."),
        ("medium", "11. Ограничения", "Стр. 47", "Ограничения",
         "Не указаны предельные объёмы обрабатываемых данных.",
         "Максимальный объём пакета и ожидаемый суточный прирост."),
        ("medium", "12. Приёмка", "Стр. 50", "Критерии приёмки",
         "Критерии приёмки не содержат проверяемых примеров.",
         "Тестовые сценарии, входные данные и ожидаемый результат."),
    ]
    findings = [
        Finding(
            fid=page,
            category=category,
            severity=severity,
            section=section,
            missing=True,
            why=why,
            ask=ask,
            suggested_fix=ask,
            source_pass="demo",
            verified=True,
        )
        for severity, section, page, category, why, ask in specs
    ]
    result = ReviewResult(findings=findings, anchoring=1.0, passes_run=["demo"])
    name = "ТЗ_новый_поток_данных_v1.2.docx"
    text = "\n".join(f"{item.section}\n{item.why}" for item in findings)
    return {
        "result": result,
        "name": name,
        "size": 128 * 1024,
        "text": text,
        "markdown": to_markdown(result, name),
        "json": to_json(result),
        "mode": "Демонстрация",
        "created": "12 мая 2024 в 14:32",
        "demo": True,
    }


STAGE_RU = {
    "queued": "в очереди", "deterministic": "детерминированный слой", "doc_graph": "граф сущностей",
    "checklist": "чеклист полноты", "document_level": "согласованность разделов",
    "developer_sim": "взгляд разработчика", "spec_compile": "компиляция ТЗ",
    "uncertainty": "семантическая энтропия", "uncertainty_lp": "логит-зонд",
    "verify": "верификация цитат", "critic": "критик", "done": "готово",
}


def model_is_configured() -> bool:
    # Режим API (TZR_API_URL): модель настроена на стороне сервиса — воркер, очередь, история.
    if api_url():
        return True
    load_dotenv()
    return all(os.environ.get(name) for name in ENV_VARS)


def _store_review(result, name: str, size: int, text: str, mode: str, **extra) -> None:
    st.session_state["review"] = {
        "result": result,
        "name": name,
        "size": size,
        "text": text,
        "markdown": to_markdown(result, name),
        "json": to_json(result),
        "mode": mode,
        "created": datetime.now().strftime("%d.%m.%Y в %H:%M"),
        **extra,
    }
    st.session_state["show_uploader"] = False


def _run_via_api(text: str, name: str, size: int, mode: str) -> None:
    """Ревью через API: очередь → воркер → история в Postgres; прогресс по этапам конвейера."""
    bar = st.progress(0, text="Отправляем документ…")
    try:
        job = submit_review(text, name)
    except Exception as exc:  # noqa: BLE001 — показать аналитику, а не падать
        bar.empty()
        st.error(f"Сервис ревью недоступен: {exc}")
        return
    job_id = job["job_id"]
    if job.get("status") == "done":  # такой документ с таким конфигом уже проверен
        payload = wait_for_review(job_id, poll_s=0.5, timeout_s=30)
    else:
        def on_progress(info: dict) -> None:
            pct = int(info.get("pct") or 0)
            stage = STAGE_RU.get(info.get("stage") or info.get("status") or "", info.get("stage") or "")
            live = " · ".join(x for x in (
                f"батч {info['batch']}/{info['batches']}" if info.get("batch") else "",
                f"вызовов {info['calls']}" if info.get("calls") else "",
                f"{info['elapsed_s']} с" if info.get("elapsed_s") else "",
            ) if x)
            bar.progress(min(max(pct, 1), 100) / 100, text=f"{stage} · {pct}%" + (f" · {live}" if live else ""))

        try:
            payload = wait_for_review(job_id, on_progress=on_progress)
        except Exception as exc:  # noqa: BLE001
            bar.empty()
            st.error(f"Ревью не завершилось: {exc}")
            return
    bar.empty()
    if payload.get("status") != "done":
        st.error(f"Ревью завершилось с ошибкой: {payload.get('error') or 'неизвестно'}")
        return
    result = result_from_payload(payload)
    model = payload.get("model") or ""
    _store_review(result, name, size, text, f"{mode} · {model}".strip(" ·"),
                  job_id=job_id, duration_s=payload.get("duration_s"),
                  cached=bool(job.get("cached") or payload.get("cached_from")))


def run_analysis(text: str, name: str, size: int, mode: str, threshold: float) -> None:
    if mode == "Полная с LLM" and api_url():
        _run_via_api(text, name, size, mode)
        st.rerun()
        return
    with st.spinner("Анализируем документ..."):
        llm = None
        if mode == "Полная с LLM":
            from tz_review.llm import LLM

            llm = LLM(settings_or_die())
        result = review(text, load_rubric(), llm, use_graph=True, critic_threshold=threshold)
        _store_review(result, name, size, text, mode)
    st.rerun()


def donut_gradient(counts: Counter, total: int) -> str:
    if total == 0:
        return "#2b2b2b 0 100%"
    cursor = 0.0
    parts = []
    for severity in ("critical", "high", "medium", "advisory"):
        end = cursor + 100 * counts[severity] / total
        if end > cursor:
            parts.append(f"{SEVERITY_COLOR[severity]} {cursor:.2f}% {end:.2f}%")
        cursor = end
    return ", ".join(parts) or "#2b2b2b 0 100%"


def clipped(text: str, limit: int) -> str:
    value = text.strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def issue_text(item, limit: int = 145) -> str:
    return clipped(item.why or item.ask or "Требуется уточнение", limit)


def render_overview(result) -> None:
    counts = Counter(item.severity for item in result.findings)
    total = len(result.findings)
    descriptions = {
        "critical": "Требуют обязательного уточнения",
        "high": "Могут привести к разному пониманию",
        "medium": "Рекомендуется уточнить",
        "advisory": "Дополнительные рекомендации",
    }
    legend = []
    for severity in ("critical", "high", "medium", "advisory"):
        legend.append(
            '<div class="legend-row">'
            f'<span class="legend-dot" style="background:{SEVERITY_COLOR[severity]}"></span>'
            f'<div class="legend-copy"><strong>{SEVERITY_LABEL[severity]}</strong>'
            f'<span>{descriptions[severity]}</span></div>'
            f'<span class="legend-count">{counts[severity]}</span></div>'
        )
    st.markdown(
        '<div class="panel"><div class="panel-title">Общий результат</div>'
        '<div class="overview-grid"><div class="donut-wrap">'
        f'<div class="donut" style="background:conic-gradient({donut_gradient(counts, total)})">'
        f'<div class="donut-center"><div class="donut-number">{total}</div>'
        '<div class="donut-label">замечаний</div></div></div></div>'
        f'<div class="legend">{"".join(legend)}</div></div>'
        '<div class="panel-note">Система нашла потенциально проблемные места. '
        'Финальное решение остаётся за аналитиком.</div></div>',
        unsafe_allow_html=True,
    )


def render_summary(result, demo: bool = False) -> None:
    _, verdict_text = verdict(result)
    summary_copy = (
        "Документ в целом структурирован, но содержит ряд мест, которые могут вызвать "
        "вопросы у разработчиков."
        if demo
        else f"{verdict_text}. Ниже перечислены главные места, которые стоит проверить "
             "перед передачей документа."
    )
    items = []
    if demo:
        summary_specs = (
            ("critical", "Не хватает деталей в описании источников данных и правил преобразования."),
            ("high", "Часть логики обработки и бизнес-правил описана неформально."),
            ("medium", "Отсутствуют некоторые нефункциональные требования."),
            ("advisory", "Рекомендуется уточнить формат и примеры выходных данных."),
        )
        for severity, copy in summary_specs:
            items.append(
                '<div class="summary-item">'
                f'<span class="marker" style="background:{SEVERITY_COLOR[severity]}"></span>'
                f'<span>{escape(copy)}</span></div>'
            )
    else:
        for finding in result.findings[:4]:
            items.append(
                '<div class="summary-item">'
                f'<span class="marker" style="background:{SEVERITY_COLOR[finding.severity]}"></span>'
                f'<span>{escape(issue_text(finding, 125))}</span></div>'
            )
    if not items:
        items.append('<div class="summary-item"><span class="marker" style="background:#39c8a5"></span>'
                     '<span>Существенных проблем не найдено.</span></div>')
    st.markdown(
        '<div class="panel summary-panel"><div class="panel-title">Краткое резюме</div>'
        f'<div class="summary-copy">{escape(summary_copy)}</div>'
        f'<div class="summary-list">{"".join(items)}</div>'
        '<a class="summary-button" href="#remarks">Посмотреть все замечания&nbsp;&nbsp;→</a></div>',
        unsafe_allow_html=True,
    )


def render_findings_table(findings, framed: bool = True, show_title: bool = True) -> None:
    rows = []
    for item in findings:
        color = SEVERITY_COLOR[item.severity]
        ask = clipped(item.ask or "Уточнить формулировку", 115)
        rows.append(
            '<div class="finding-row">'
            f'<div><span class="level-pill" style="color:{color};background:{color}22">'
            f'{SEVERITY_SHORT[item.severity]}</span></div>'
            f'<div><div class="section-name">{escape(item.section or "Документ в целом")}</div>'
            f'<div class="section-code">{escape(item.fid or item.category)}</div></div>'
            f'<div class="finding-copy">{escape(issue_text(item))}'
            f'<div class="finding-ask">Что уточнить: {escape(ask)}</div></div>'
            '<div class="new-status">Новое</div></div>'
        )
    if not rows:
        rows.append('<div class="empty-state"><div><strong>Замечаний нет</strong>'
                    '<span>Документ прошёл выбранные проверки.</span></div></div>')
    wrapper_class = "shell-card" if framed else "findings-table"
    title = '<div class="panel-title">Замечания</div>' if show_title else ""
    st.markdown(
        f'<div class="{wrapper_class}">{title}'
        '<div class="findings-head"><span>Уровень</span><span>Раздел документа</span>'
        '<span>Замечание</span><span>Статус</span></div>'
        f'{"".join(rows)}</div>',
        unsafe_allow_html=True,
    )


def filter_findings(findings, query: str, level: str, sort_order: str):
    filtered = list(findings)
    level_map = {value: key for key, value in SEVERITY_SHORT.items()}
    if level != "Все уровни":
        filtered = [item for item in filtered if item.severity == level_map[level]]
    if query:
        needle = query.casefold()
        filtered = [
            item for item in filtered
            if needle in " ".join((item.section, item.category, item.why, item.ask)).casefold()
        ]
    if sort_order == "Сначала важные":
        order = {"critical": 0, "high": 1, "medium": 2, "advisory": 3}
        filtered.sort(key=lambda item: order[item.severity])
    return filtered


def render_finding_details(findings) -> None:
    if not findings:
        st.success("Существенных проблем не найдено.")
        return
    for item in findings:
        title = f"{SEVERITY_SHORT[item.severity]} · {item.section or 'Документ в целом'} · {issue_text(item, 90)}"
        with st.expander(title, expanded=item.severity == "critical"):
            if item.quote:
                st.markdown(f"> {item.quote}")
            elif item.missing:
                st.caption("Информация в документе отсутствует.")
            st.markdown(f"**Почему это важно:** {item.why}")
            if item.ask:
                st.markdown(f"**Что уточнить:** {item.ask}")
            if item.suggested_fix:
                st.markdown(f"**Вариант формулировки:** {item.suggested_fix}")


reset_token = st.session_state.setdefault("reset_token", 0)
llm_ready = model_is_configured()
review_mode = st.session_state.get("review_mode", "Быстрая")
threshold = st.session_state.get("threshold", 4.0)
if "review" not in st.session_state and not st.session_state.get("show_uploader", False):
    st.session_state["review"] = build_demo_review()

st.markdown(
    '<aside class="fixed-sidebar">'
    '<div class="brand"><div class="brand-mark">◎</div><span>DocReview AI</span>'
    '<span class="beta">BETA</span></div>'
    '<div class="fixed-nav"><div class="nav-stack">'
    '<div class="nav-item active"><span class="nav-glyph">▤</span>Анализ документации</div>'
    '<div class="nav-item"><span class="nav-glyph">◷</span>История проверок</div>'
    '<div class="nav-item"><span class="nav-glyph">▧</span>Шаблоны документов</div>'
    '<div class="nav-item"><span class="nav-glyph">✧</span>Рекомендации</div>'
    '<div class="nav-item"><span class="nav-glyph">⚙</span>Настройки</div></div></div>'
    '<div class="side-card fixed-tip"><strong>Совет</strong><span>Перед анализом убедитесь, '
    'что документ соответствует актуальному шаблону.</span></div>'
    '<div class="side-card fixed-about"><strong>О решении</strong><span>Система находит '
    'неясные и неполные места в технической документации до передачи в разработку.'
    '</span><span class="side-more">Подробнее&nbsp;&nbsp;→</span></div></aside>',
    unsafe_allow_html=True,
)
if st.button("Новый анализ", icon=":material/add:", type="primary",
             use_container_width=True, key="sidebar_new_analysis"):
    st.session_state.pop("review", None)
    st.session_state["show_uploader"] = True
    st.session_state["reset_token"] = reset_token + 1
    st.rerun()

st.markdown(
    '<div class="topbar"><div class="workspace-title">Анализ документации</div></div>',
    unsafe_allow_html=True,
)
payload = st.session_state.get("review")

if payload is None:
    st.markdown('<div class="shell-card"><div class="doc-header"><div class="doc-icon">DOC</div>'
                '<div><div class="doc-name">Новый анализ</div><div class="doc-meta">'
                'Выберите документ или используйте тестовый пример</div></div></div></div>',
                unsafe_allow_html=True)
    mode_col, threshold_col = st.columns((1, 1), gap="small")
    with mode_col:
        review_mode = st.radio("Режим анализа", ("Быстрая", "Полная с LLM"),
                               horizontal=True, key="review_mode")
    with threshold_col:
        threshold = st.slider("Порог полезности", 0.0, 10.0, 4.0, 0.5,
                              disabled=review_mode == "Быстрая", key="threshold")
    if review_mode == "Полная с LLM" and not llm_ready:
        st.warning("Модель не настроена. Заполните `.env`.")
    file_tab, text_tab, example_tab = st.tabs(("Файл", "Текст документа", "Пример"))

    with file_tab:
        uploaded = st.file_uploader("Загрузите техническое задание",
                                    type=("pdf", "docx", "txt", "md"),
                                    key=f"upload_{reset_token}")
        file_text = ""
        file_error = None
        if uploaded is not None:
            try:
                file_text = extract_text(uploaded.name, uploaded.getvalue())
                st.caption(f"{uploaded.name} · {len(file_text):,} символов".replace(",", " "))
            except DocumentInputError as exc:
                file_error = str(exc)
                st.error(file_error)
        if st.button("Запустить анализ", key=f"run_file_{reset_token}", type="primary",
                     icon=":material/fact_check:", disabled=not file_text or file_error is not None
                     or (review_mode == "Полная с LLM" and not llm_ready)):
            try:
                run_analysis(file_text, uploaded.name, len(uploaded.getvalue()), review_mode, threshold)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Проверка не завершена: {exc}")

    with text_tab:
        pasted = st.text_area("Текст технического задания", height=330,
                              key=f"pasted_{reset_token}",
                              placeholder="Вставьте сюда текст документа...")
        if st.button("Запустить анализ", key=f"run_text_{reset_token}", type="primary",
                     icon=":material/fact_check:", disabled=not pasted.strip()
                     or (review_mode == "Полная с LLM" and not llm_ready)):
            try:
                run_analysis(pasted, "Вставленный текст.txt", len(pasted.encode("utf-8")),
                             review_mode, threshold)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Проверка не завершена: {exc}")

    with example_tab:
        example_name = st.selectbox("Тестовый документ", tuple(EXAMPLES),
                                    key=f"example_{reset_token}")
        example_path = EXAMPLES[example_name]
        example_text = example_path.read_text(encoding="utf-8")
        st.text_area("Предпросмотр", value=example_text, height=330,
                     key=f"preview_{reset_token}", disabled=True)
        if st.button("Проверить пример", key=f"run_example_{reset_token}", type="primary",
                     icon=":material/fact_check:",
                     disabled=review_mode == "Полная с LLM" and not llm_ready):
            try:
                run_analysis(example_text, example_path.name, len(example_text.encode("utf-8")),
                             review_mode, threshold)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Проверка не завершена: {exc}")
else:
    result = payload["result"]
    size_kb = max(1, round(payload.get("size", 0) / 1024))
    with st.container(border=True, key="document_shell"):
        header_left, header_status, header_download = st.columns((6.5, 1.45, 1.5), gap="small",
                                                                  vertical_alignment="center")
        with header_left:
            st.markdown('<div class="doc-header"><div class="doc-icon">DOC</div>'
                        f'<div><div class="doc-name">{escape(payload["name"])}</div>'
                        f'<div class="doc-meta">{size_kb} КБ · Загружен '
                        f'{escape(payload.get("created", "сейчас"))}</div></div></div>',
                        unsafe_allow_html=True)
        with header_status:
            st.markdown('<div class="status-ok"><span class="status-dot"></span>'
                        'Анализ завершён</div>', unsafe_allow_html=True)
        with header_download:
            st.download_button("Скачать отчёт", payload["markdown"],
                               file_name=f"{Path(payload['name']).stem}.report.md",
                               mime="text/markdown", icon=":material/download:",
                               use_container_width=True)

    result_tab, findings_tab, text_tab, structure_tab, recommendations_tab = st.tabs(
        ("Результат", f"Замечания  {len(result.findings)}", "Текст документа",
         "Структура", "Рекомендации"))

    with result_tab:
        overview_col, summary_col = st.columns((1.2, .88), gap="small")
        with overview_col:
            render_overview(result)
        with summary_col:
            render_summary(result, demo=payload.get("demo", False))
        with st.container(border=True, key="remarks_panel"):
            st.markdown('<div id="remarks" class="remarks-title">Замечания</div>',
                        unsafe_allow_html=True)
            search_col, spacer_col, level_col, sort_col = st.columns((1.7, 3.7, 1.25, 1.25),
                                                                      gap="small")
            with search_col:
                result_query = st.text_input("Поиск", placeholder="Поиск замечаний...",
                                             label_visibility="collapsed", key="result_search")
            with spacer_col:
                st.empty()
            with level_col:
                result_level = st.selectbox(
                    "Уровень", ("Все уровни", "Критичное", "Важное", "Умеренное",
                                "Информационное"),
                    label_visibility="collapsed", key="result_level")
            with sort_col:
                result_sort = st.selectbox(
                    "Сортировка", ("Сначала важные", "Сначала новые"),
                    label_visibility="collapsed", key="result_sort")
            result_filtered = filter_findings(
                result.findings, result_query, result_level, result_sort)
            if payload.get("demo") and result_sort == "Сначала важные" and not result_query \
                    and result_level == "Все уровни":
                result_filtered = list(result.findings)
            render_findings_table(result_filtered[:6], framed=False, show_title=False)

    with findings_tab:
        search_col, level_col, sort_col = st.columns((2.4, 1, 1), gap="small")
        with search_col:
            query = st.text_input("Поиск", placeholder="Поиск замечаний...",
                                  label_visibility="collapsed")
        with level_col:
            level = st.selectbox("Уровень", ("Все уровни", "Критичное", "Важное",
                                                   "Умеренное", "Информационное"),
                                 label_visibility="collapsed")
        with sort_col:
            sort_order = st.selectbox("Сортировка", ("Сначала важные", "Сначала новые"),
                                      label_visibility="collapsed")
        filtered = filter_findings(result.findings, query, level, sort_order)
        render_finding_details(filtered)

    with text_tab:
        st.text_area("Извлечённый текст", payload.get("text", ""), height=560, disabled=True)

    with structure_tab:
        document = parse(payload.get("text", ""))
        st.markdown("### Разделы документа")
        for index, section in enumerate(document.sections, 1):
            st.markdown(f"**{index}. {section.title}**  ·  {len(section.body)} символов")
        if result.statuses:
            st.markdown("### Покрытие чек-листа")
            ok_count = sum(status == "OK" for status in result.statuses.values())
            st.progress(ok_count / max(len(result.statuses), 1),
                        text=f"Закрыто {ok_count} из {len(result.statuses)} пунктов")

    with recommendations_tab:
        st.markdown("### Что уточнить в первую очередь")
        for index, item in enumerate(result.findings[:8], 1):
            st.markdown(f"**{index}. {item.ask or item.why}**")
            if item.suggested_fix:
                st.caption(item.suggested_fix)
        st.download_button("Скачать JSON", payload["json"],
                           file_name=f"{Path(payload['name']).stem}.findings.json",
                           mime="application/json", icon=":material/data_object:")
