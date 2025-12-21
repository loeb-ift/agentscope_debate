#!/usr/bin/env python3
import json, sys, urllib.request, os

API_URL = os.getenv('API_URL', 'http://localhost:8000')
OUT_PATH = os.getenv('OUT_PATH', 'docs/deploy_baseline.json')

url = f"{API_URL}/api/v1/health/deploy-check"
with urllib.request.urlopen(url) as r:
    data = json.loads(r.read().decode('utf-8'))

baseline = {
    "cache_backend": data.get("cache_backend"),
    "prompts_checksum": data.get("prompts_checksum"),
    "toolsets_fingerprint": data.get("toolsets_fingerprint"),
}

with open(OUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(baseline, f, ensure_ascii=False, indent=2)

print(f"Baseline written to {OUT_PATH}")
