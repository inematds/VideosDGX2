#!/usr/bin/env python3
"""
Batch de geração — lê uma LISTA de jobs (JSON) e enfileira todos na interface web (porta 7862).
A interface processa em sequência (fila), com cancelamento e galeria.

Uso:
  python3 generate_all_videos.py [lista.json]     # default: lote.json

Cada item da lista é um job; campos faltantes usam o default:
  {"model": "wan22_14b|wan22_5b|ltx23", "prompt": "...", "width":..., "height":...,
   "frames":..., "fps":..., "cfg":..., "seed":..., "steps":..., "split_step":...}

Veja lote.exemplo.json para um exemplo.
"""
import json
import sys
import requests
from pathlib import Path

WEB_URL = "http://127.0.0.1:7862"
DEFAULTS = {
    "model": "wan22_14b", "negative": "", "width": 1280, "height": 704,
    "frames": 57, "fps": 24, "cfg": 3.5, "seed": -1,
    "steps": 30, "split_step": 15, "image_name": "",
}


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "lote.json"
    if not path.exists():
        print(f"❌ Lote não encontrado: {path}")
        print("   Crie um JSON com uma lista de jobs (veja lote.exemplo.json).")
        sys.exit(1)

    try:
        jobs = json.loads(path.read_text())
    except Exception as e:
        print(f"❌ JSON inválido em {path}: {e}")
        sys.exit(1)

    if not isinstance(jobs, list):
        print("❌ O arquivo deve conter uma LISTA de jobs.")
        sys.exit(1)

    # Checa se a interface web está no ar
    try:
        requests.get(f"{WEB_URL}/api/jobs", timeout=5)
    except Exception:
        print(f"❌ Interface web não responde em {WEB_URL}")
        print("   Suba com: ./iniciar_interface_web.sh")
        sys.exit(1)

    print(f"📋 Enfileirando {len(jobs)} job(s) em {WEB_URL}\n")
    ok = 0
    for i, j in enumerate(jobs, 1):
        req = {**DEFAULTS, **j}
        if not req.get("prompt"):
            print(f"  [{i}] ⚠️  sem 'prompt', pulando")
            continue
        try:
            r = requests.post(f"{WEB_URL}/api/generate", json=req, timeout=30)
            if r.ok:
                d = r.json()
                ok += 1
                print(f"  [{i}] ✅ {req['model']:10} job {d.get('job_id')} "
                      f"(fila #{d.get('queue_position')}) — {req['prompt'][:50]}")
            else:
                print(f"  [{i}] ❌ HTTP {r.status_code}: {r.text[:120]}")
        except Exception as e:
            print(f"  [{i}] ❌ {e}")

    print(f"\n✅ {ok}/{len(jobs)} enfileirados.")
    print(f"   Acompanhe: python3 check_jobs_status.py   ou   {WEB_URL}")


if __name__ == "__main__":
    main()
