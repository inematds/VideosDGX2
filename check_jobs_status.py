#!/usr/bin/env python3
"""
Status dos jobs da interface web (porta 7862) — substitui a versão antiga que
batia nas portas do Docker (8001-8004, descontinuadas).

Uso: python3 check_jobs_status.py
"""
import sys
import requests
from collections import Counter

WEB_URL = "http://127.0.0.1:7862"
ICON = {"queued": "⏳", "processing": "⚙️ ", "completed": "✅", "error": "❌"}


def main():
    try:
        jobs = requests.get(f"{WEB_URL}/api/jobs", timeout=10).json()
    except Exception as e:
        print(f"❌ Interface web não respondeu ({WEB_URL}): {e}")
        print("   Suba com: ./iniciar_interface_web.sh")
        sys.exit(1)

    if not jobs:
        print("(nenhum job na fila)")
        return

    rows = sorted(jobs.values(), key=lambda j: j.get("created_at", ""), reverse=True)
    print(f"  {'STATUS':12} {'MODELO':10} {'INFO':22} PROMPT")
    print("  " + "-" * 78)
    for j in rows[:30]:
        st = j.get("status", "?")
        req = j.get("request", {})
        if st == "queued":
            info = f"posição #{j.get('queue_position', '?')}"
        elif st == "processing":
            info = f"{j.get('progress_pct', 0)}%"
        elif st == "completed":
            info = j.get("video_file", "")[:22]
        else:
            info = (j.get("error", "") or "")[:22]
        print(f"  {ICON.get(st,'·')} {st:10} {req.get('model','?'):10} "
              f"{info:22} {req.get('prompt','')[:42]}")

    c = Counter(j.get("status") for j in jobs.values())
    print("\n  Resumo: " + " · ".join(f"{ICON.get(k,'')}{k}={v}" for k, v in c.items()))


if __name__ == "__main__":
    main()
