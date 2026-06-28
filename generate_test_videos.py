#!/usr/bin/env python3
"""
Smoke test — enfileira 1 vídeo curto de cada modelo na interface web (7862),
pra validar que o pipeline (ComfyUI + Wan + LTX) está respondendo.

Uso: python3 generate_test_videos.py
"""
import sys
import requests

WEB_URL = "http://127.0.0.1:7862"

TESTS = [
    {"model": "wan22_5b",  "prompt": "a calm ocean wave at sunset, cinematic",
     "width": 720, "height": 480, "frames": 33, "cfg": 6.0, "seed": 1},
    {"model": "wan22_14b", "prompt": "a calm ocean wave at sunset, cinematic",
     "width": 832, "height": 480, "frames": 33, "cfg": 3.5, "seed": 1,
     "steps": 30, "split_step": 15},
    {"model": "ltx23",     "prompt": "a calm ocean wave at sunset, cinematic",
     "width": 512, "height": 512, "frames": 49, "cfg": 3.0, "seed": 1},
]


def main():
    try:
        requests.get(f"{WEB_URL}/api/jobs", timeout=5)
    except Exception:
        print(f"❌ Interface web não responde em {WEB_URL} — suba com ./iniciar_interface_web.sh")
        sys.exit(1)

    print(f"🧪 Enfileirando {len(TESTS)} testes em {WEB_URL}\n")
    for t in TESTS:
        try:
            r = requests.post(f"{WEB_URL}/api/generate", json=t, timeout=30)
            d = r.json() if r.ok else {}
            print(f"  {'✅' if r.ok else '❌'} {t['model']:10} job {d.get('job_id','-')}")
        except Exception as e:
            print(f"  ❌ {t['model']:10} {e}")

    print(f"\nAcompanhe: python3 check_jobs_status.py   ou   {WEB_URL}")


if __name__ == "__main__":
    main()
