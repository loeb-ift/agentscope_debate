#!/usr/bin/env python3
import os, sys, socket
from urllib.request import urlopen

REQUIRED_ENVS = [
    # add critical keys here when needed, keep minimal to not block local runs
    # 'FINNHUB_API_KEY',
]

REDIS_URL = os.getenv('REDIS_URL') or os.getenv('REDIS_HOST')


def check_env():
    missing = [k for k in REQUIRED_ENVS if not os.getenv(k)]
    if missing:
        print(f"[FAIL] Missing env vars: {missing}")
        return False
    print("[OK] Env vars present")
    return True


def check_docker():
    try:
        import subprocess
        subprocess.run(["docker", "version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[OK] Docker available")
        return True
    except Exception as e:
        print(f"[WARN] Docker not available or not running: {e}")
        return False


def check_redis():
    if not REDIS_URL:
        print("[INFO] Redis not configured (using memory cache by default)")
        return True
    try:
        if REDIS_URL.startswith("redis://"):
            # try basic TCP connect
            import urllib.parse
            u = urllib.parse.urlparse(REDIS_URL)
            host = u.hostname or 'localhost'; port = int(u.port or 6379)
        else:
            host = os.getenv('REDIS_HOST', 'localhost')
            port = int(os.getenv('REDIS_PORT', '6379'))
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
        print(f"[OK] Redis reachable at {host}:{port}")
        return True
    except Exception as e:
        print(f"[FAIL] Redis not reachable: {e}")
        return False


def main():
    ok = True
    ok &= check_env()
    ok &= check_docker()
    ok &= check_redis()
    if not ok:
        sys.exit(1)
    print("[OK] Preflight passed")

if __name__ == '__main__':
    main()
