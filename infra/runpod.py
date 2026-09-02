"""Управление RunPod-подом с vLLM (OpenAI-совместимый endpoint).

Использование (ключ берётся из RUNPOD_API_KEY в .env / окружении):
    python infra/runpod.py create [--gpu "NVIDIA GeForce RTX 4090"] [--model Qwen/Qwen2.5-14B-Instruct-AWQ]
    python infra/runpod.py status <pod_id>
    python infra/runpod.py list
    python infra/runpod.py terminate <pod_id>

После create/status, когда под RUNNING и модель загрузилась, endpoint:
    https://<pod_id>-8000.proxy.runpod.net/v1
Авторизация запросов к vLLM — токен TZR_API_KEY (передаётся поду как VLLM_API_KEY).
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


def create(gpu: str, model: str) -> None:
    vllm_key = os.environ.get("TZR_API_KEY", "tzr-local-token")
    body = {
        "name": "tzr-vllm",
        "imageName": "vllm/vllm-openai:latest",
        "cloudType": "COMMUNITY",
        "gpuTypeIds": [gpu],
        "gpuCount": 1,
        "containerDiskInGb": 40,
        "volumeInGb": 0,
        "ports": ["8000/http"],
        "env": {"VLLM_API_KEY": vllm_key, "HF_HUB_ENABLE_HF_TRANSFER": "1"},
        "dockerStartCmd": [
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


def main() -> int:
    load_dotenv()
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    cmd = args[0]
    if cmd == "create":
        gpu = args[args.index("--gpu") + 1] if "--gpu" in args else "NVIDIA GeForce RTX 4090"
        model = args[args.index("--model") + 1] if "--model" in args else "Qwen/Qwen2.5-14B-Instruct-AWQ"
        create(gpu, model)
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
