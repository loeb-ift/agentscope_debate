#!/usr/bin/env python3
import argparse
import json
import sys
from urllib.parse import urljoin

import requests


def check_api(api_base: str) -> bool:
    try:
        url_tools = urljoin(api_base, "/api/v1/tools")
        r = requests.get(url_tools, timeout=5)
        r.raise_for_status()
        tools = r.json()
        names = [t.get("name") for t in tools] if isinstance(tools, list) else []
        print(f"[API] tools count={len(names)} has_chinatimes={any(n and n.startswith('chinatimes') for n in names)}")
        # check new endpoint
        url_new = urljoin(api_base, "/api/v1/debates/new")
        print(f"[API] new debate endpoint: {url_new}")
        try:
            r2 = requests.post(url_new, json={}, timeout=5)
            print(f"[API] /debates/new status={r2.status_code} (expected 422 for missing body)")
        except requests.RequestException as e:
            print(f"[API] /debates/new request failed: {e}")
        return True
    except requests.RequestException as e:
        print(f"[API] error: {e}")
        return False


def check_redis(redis_url: str) -> bool:
    try:
        import redis
        r = redis.from_url(redis_url)
        pong = r.ping()
        print(f"[Redis] ping={pong}")
        return True
    except Exception as e:
        print(f"[Redis] error: {e}")
        return False


def check_searx(searx_url: str) -> bool:
    try:
        r = requests.get(urljoin(searx_url, "/"), timeout=5)
        print(f"[SearXNG] status={r.status_code}")
        return r.ok
    except requests.RequestException as e:
        print(f"[SearXNG] error: {e}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True, help="API base url, e.g., http://127.0.0.1:8000")
    ap.add_argument("--redis", required=False, help="Redis url, e.g., redis://127.0.0.1:6379/0")
    ap.add_argument("--searx", required=False, help="SearXNG base url, e.g., http://127.0.0.1:8080")
    args = ap.parse_args()

    ok_api = check_api(args.api)
    ok_redis = True if not args.redis else check_redis(args.redis)
    ok_searx = True if not args.searx else check_searx(args.searx)

    if ok_api and ok_redis and ok_searx:
        print("\n[OK] Deploy readiness checks passed.")
        return 0
    else:
        print("\n[!] Some checks failed. See logs above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
