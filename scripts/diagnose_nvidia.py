#!/usr/bin/env python3
"""Diagnostic script for NVIDIA API integration."""
import os
import sys
import json
import httpx
from urllib.parse import urljoin


def load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.exists(env_path):
        return {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def mask(value: str) -> str:
    if not value:
        return "MISSING"
    return f"PRESENT ({len(value)} chars)"


def main():
    load_env()

    api_key = os.getenv("NVIDIA_API_KEY", "")
    base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
    model = os.getenv("NVIDIA_MODEL", "")

    print("=" * 60)
    print("RUNTIME CONFIGURATION")
    print("=" * 60)
    print(f"NVIDIA_BASE_URL: {base_url}")
    print(f"NVIDIA_MODEL:    {model}")
    print(f"NVIDIA_API_KEY:  {mask(api_key)}")
    print()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    results = []

    # Test 1: GET /v1/models
    print("=" * 60)
    print("TEST 1: GET /v1/models")
    print("=" * 60)
    models_url = urljoin(base_url + "/", "models")
    print(f"URL: {models_url}")
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(models_url, headers=headers)
        print(f"HTTP Status: {resp.status_code}")
        body_preview = resp.text[:500] if resp.text else ""
        print(f"Response body (truncated): {body_preview}")
        model_found = False
        if resp.status_code == 200:
            try:
                data = resp.json()
                model_ids = [
                    m.get("id") for m in data.get("data", []) if isinstance(m, dict)
                ]
                print(f"Model count: {len(model_ids)}")
                if model in model_ids:
                    print(f"MODEL_FOUND = YES")
                    model_found = True
                else:
                    print(f"MODEL_FOUND = NO")
                    llama_models = [m for m in model_ids if "llama" in m.lower()]
                    print(f"Closest Llama-family models: {llama_models[:10]}")
            except Exception:
                print("Could not parse models response as JSON")
        results.append(("GET /v1/models", resp.status_code, body_preview[:100]))
    except Exception as exc:
        print(f"Request failed: {type(exc).__name__}: {exc}")
        results.append(("GET /v1/models", "ERROR", str(exc)[:100]))
    print()

    # Test 2: POST /v1/chat/completions with configured model
    print("=" * 60)
    print("TEST 2: POST /v1/chat/completions (configured model)")
    print("=" * 60)
    chat_url = urljoin(base_url + "/", "chat/completions")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Say hello in one sentence."}],
        "temperature": 0.2,
        "max_tokens": 50,
        "stream": False,
    }
    print(f"URL: {chat_url}")
    print(f"Model: {model}")
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(chat_url, json=payload, headers=headers)
        print(f"HTTP Status: {resp.status_code}")
        body_preview = resp.text[:500] if resp.text else ""
        print(f"Response body (truncated): {body_preview}")
        results.append(("Configured model chat", resp.status_code, body_preview[:100]))
    except Exception as exc:
        print(f"Request failed: {type(exc).__name__}: {exc}")
        results.append(("Configured model chat", "ERROR", str(exc)[:100]))
    print()

    # Test 3: POST /v1/chat/completions with a confirmed catalog model
    print("=" * 60)
    print("TEST 3: POST /v1/chat/completions (confirmed catalog model)")
    print("=" * 60)
    catalog_model = "meta/llama-3.3-70b-instruct"
    payload["model"] = catalog_model
    print(f"URL: {chat_url}")
    print(f"Model: {catalog_model}")
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(chat_url, json=payload, headers=headers)
        print(f"HTTP Status: {resp.status_code}")
        body_preview = resp.text[:500] if resp.text else ""
        print(f"Response body (truncated): {body_preview}")
        results.append(("Catalog model chat", resp.status_code, body_preview[:100]))
    except Exception as exc:
        print(f"Request failed: {type(exc).__name__}: {exc}")
        results.append(("Catalog model chat", "ERROR", str(exc)[:100]))
    print()

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, status, body in results:
        print(f"{name}: HTTP {status}")
    print()

    sys.exit(0)


if __name__ == "__main__":
    main()
