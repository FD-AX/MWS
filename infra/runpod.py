"""Управление RunPod-подом с vLLM (OpenAI-совместимый endpoint).

Использование (ключ берётся из RUNPOD_API_KEY в .env / окружении):
    python infra/runpod.py create [--gpu "NVIDIA GeForce RTX 4090"] [--model Qwen/Qwen2.5-14B-Instruct-AWQ]
    python infra/runpod.py status <pod_id>
    python infra/runpod.py list
    python infra/runpod.py terminate <pod_id>

После create/status, когда под RUNNING и модель загрузилась, endpoint:
    https://<pod_id>-8000.proxy.runpod.net/v1
Авторизация запросов к vLLM — токен TZR_API_KEY (передаётся поду как VLLM_API_KEY).

Путь через ollama (проверен ночью 03.09; vLLM-образ на RunPod не поднимался):
    python infra/runpod.py create-ollama [--gpu "NVIDIA H100 80GB HBM3"]   # по умолчанию список 80 ГБ
    python infra/runpod.py pull <pod_id> gpt-oss:120b                       # докачка потоком
    python infra/runpod.py tags <pod_id>
    endpoint: https://<pod_id>-11434.proxy.runpod.net/v1, TZR_MODEL=gpt-oss:120b, ключ любой.
vLLM для gpt-oss-120b — только Hopper (MXFP4); на A100 bf16 не влезает.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tz_review.config import load_dotenv  # noqa: E402

API = "https://rest.runpod.io/v1"


def _req(method: str, path: str, body: dict | None = None) -> dict:
    key = os.environ.get("RUNPOD_API_KEY")
    if not key:
        raise SystemExit("RUNPOD_API_KEY не задан (положи в net-review/.env)")
    req = urllib.request.Request(
        API + path, method=method,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body is not None else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"RunPod API {e.code}: {e.read().decode()[:500]}")


def create(gpu: str, model: str, cloud: str = "SECURE") -> None:
    vllm_key = os.environ.get("TZR_API_KEY", "tzr-local-token")
    body = {
        "name": "tzr-vllm",
        "imageName": "vllm/vllm-openai:latest",
        "cloudType": cloud,
        "gpuTypeIds": [gpu],
        "gpuCount": 1,
        "containerDiskInGb": 60,
        "volumeInGb": 0,
        "ports": ["8000/http"],
        "env": {"VLLM_API_KEY": vllm_key, "HF_HUB_ENABLE_HF_TRANSFER": "1"},
        # Явные entrypoint+cmd: не полагаемся на семантику наследования CMD у образа
        "dockerEntrypoint": ["python3", "-m", "vllm.entrypoints.openai.api_server"],
        "dockerStartCmd": [
            "--host", "0.0.0.0", "--port", "8000",
            "--model", model,
            "--max-model-len", "16384",
            "--gpu-memory-utilization", "0.92",
            "--disable-log-requests",
        ],
    }
    pod = _req("POST", "/pods", body)
    pid = pod.get("id")
    print(json.dumps(pod, indent=1)[:600])
    print(f"\npod_id: {pid}")
    print(f"endpoint (после загрузки модели): https://{pid}-8000.proxy.runpod.net/v1")


OLLAMA_GPUS_80GB = [
    "NVIDIA H100 80GB HBM3", "NVIDIA H100 PCIe", "NVIDIA H100 NVL",
    "NVIDIA A100 80GB PCIe", "NVIDIA A100-SXM4-80GB",
]


def create_ollama(gpus: list[str], cloud: str = "SECURE", disk_gb: int = 120,
                  ctx: int = 32768) -> None:
    """Проверенный ночью путь: лёгкий ollama-образ, модель докачивается по HTTP
    (см. `pull`). Для gpt-oss:120b нужен GPU на 80 ГБ (MXFP4 ≈ 65 ГБ VRAM)."""
    body = {
        "name": "tzr-ollama",
        "imageName": "ollama/ollama:latest",
        "cloudType": cloud,
        "gpuTypeIds": gpus,
        "gpuCount": 1,
        "containerDiskInGb": disk_gb,
        "volumeInGb": 0,
        "ports": ["11434/http"],
        "env": {
            "OLLAMA_HOST": "0.0.0.0",
            "OLLAMA_KEEP_ALIVE": "-1",          # держать модель в VRAM между вызовами
            "OLLAMA_CONTEXT_LENGTH": str(ctx),  # дефолтный контекст для OpenAI-совместимого API
            "OLLAMA_NUM_PARALLEL": "4",         # параллельные слоты (энтропия в 6 потоков)
        },
    }
    pod = _req("POST", "/pods", body)
    pid = pod.get("id")
    print(json.dumps(pod, indent=1)[:600])
    print(f"\npod_id: {pid}")
    print(f"ollama: https://{pid}-11434.proxy.runpod.net  (OpenAI-совместимый: /v1)")


def _ollama(pod_id: str, path: str, body: dict | None = None, stream: bool = False):
    url = f"https://{pod_id}-11434.proxy.runpod.net{path}"
    # Cloudflare перед прокси RunPod отдаёт 403 на User-Agent «Python-urllib» — шлём свой.
    req = urllib.request.Request(url, method="POST" if body is not None else "GET",
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "tzr-infra/1.0 (curl-compatible)"},
                                 data=json.dumps(body).encode() if body is not None else None)
    return urllib.request.urlopen(req, timeout=600 if stream else 120)


def pull(pod_id: str, model: str) -> None:
    """Докачка модели через ollama API потоком (прокси RunPod рвёт тихие запросы >120s,
    поток прогресса держит соединение живым)."""
    import time
    last = 0.0
    with _ollama(pod_id, "/api/pull", {"name": model, "stream": True}, stream=True) as r:
        for line in r:
            try:
                ev = json.loads(line.decode())
            except json.JSONDecodeError:
                continue
            if ev.get("total") and time.time() - last > 15:
                done = ev.get("completed", 0)
                print(f"  {ev.get('status')}: {done / 2**30:.1f} / {ev['total'] / 2**30:.1f} GiB",
                      flush=True)
                last = time.time()
            elif "total" not in ev:
                print(" ", ev.get("status") or ev, flush=True)
    print("pull done:", model)


def tags(pod_id: str) -> None:
    with _ollama(pod_id, "/api/tags") as r:
        for m in json.loads(r.read().decode()).get("models", []):
            print(m.get("name"), round(m.get("size", 0) / 2**30, 1), "GiB")


def main() -> int:
    load_dotenv()
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    cmd = args[0]
    if cmd == "create-ollama":
        gpus = [args[args.index("--gpu") + 1]] if "--gpu" in args else OLLAMA_GPUS_80GB
        cloud = args[args.index("--cloud") + 1] if "--cloud" in args else "SECURE"
        create_ollama(gpus, cloud)
    elif cmd == "pull":
        pull(args[1], args[2])
    elif cmd == "tags":
        tags(args[1])
    elif cmd == "create":
        gpu = args[args.index("--gpu") + 1] if "--gpu" in args else "NVIDIA GeForce RTX 4090"
        model = args[args.index("--model") + 1] if "--model" in args else "Qwen/Qwen2.5-14B-Instruct-AWQ"
        cloud = args[args.index("--cloud") + 1] if "--cloud" in args else "SECURE"
        create(gpu, model, cloud)
    elif cmd == "status":
        print(json.dumps(_req("GET", f"/pods/{args[1]}"), indent=1)[:1200])
    elif cmd == "list":
        pods = _req("GET", "/pods")
        for p in (pods if isinstance(pods, list) else pods.get("pods", [])):
            print(p.get("id"), p.get("name"), p.get("desiredStatus"),
                  (p.get("machine") or {}).get("gpuTypeId", ""))
    elif cmd == "terminate":
        _req("DELETE", f"/pods/{args[1]}")
        print("terminated", args[1])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
