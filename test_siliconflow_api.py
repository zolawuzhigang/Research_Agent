import json
import sys
import time
from typing import List

import requests


API_KEY = "sk-hwcnbmzkafcexxqedhhdrocicavcekdkojfuqumvdcfxquqg"
BASE_URL = "https://api.siliconflow.cn/v1"
MODELS: List[str] = ["deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-V3.2"]


def _chat_completions_url(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def test_model(model: str) -> int:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "用一句话简单介绍一下你自己。"},
        ],
        "max_tokens": 64,
    }

    try:
        url = _chat_completions_url(BASE_URL)
        t0 = time.time()
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        dt_ms = int((time.time() - t0) * 1000)
    except Exception as e:
        print(f"[{model}] request_error", str(e))
        return 1

    print(f"[{model}] status", resp.status_code, f"latency_ms={dt_ms}")
    try:
        j = resp.json()
    except Exception:
        print(f"[{model}] body", resp.text[:800])
        return 1

    print(f"[{model}] raw", json.dumps(j, ensure_ascii=False)[:800])

    if resp.status_code == 200 and isinstance(j, dict) and "choices" in j:
        print(f"[{model}] OK: API and model call succeeded")
        return 0

    print(f"[{model}] FAIL: unexpected response structure or status")
    return 1


if __name__ == "__main__":
    rc = 0
    for m in MODELS:
        rc |= test_model(m)
        print()
    sys.exit(rc)

