#!/usr/bin/env python3
"""
Interface Web para Geração de Vídeos - v4.2 Fila de Jobs + Cancelamento
Suporta: Wan 2.2 5B | Wan 2.2 14B MoE
I2V: Wan 2.2 5B (WanImageToVideo)
Acesse em: http://localhost:7862
"""

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import requests as _requests
import shutil
import tempfile
from pydantic import BaseModel
import uvicorn
import json
import subprocess
import time
import threading
import queue as _queue
from pathlib import Path
from datetime import datetime
import uuid

app = FastAPI(title="DGX Video Studio v4.2")

BASE_DIR       = Path(__file__).resolve().parent
OUTPUT_DIR     = BASE_DIR / "ComfyUI" / "output"
RESTART_SCRIPT = BASE_DIR / "reiniciar_comfyui.sh"
JOBS_FILE      = Path("/tmp/dgx_jobs_v4_2.json")
JOB_TIMEOUT    = 7200  # 2 horas
COMFYUI_URL    = "http://127.0.0.1:8188"

# Estimativa de VRAM por modelo (GB)
VRAM_ESTIMATE = {
    "wan22_14b": 90,
    "wan22_5b":  25,
    "ltx23":     70,
}

SCRIPTS = {
    "wan22_5b":      BASE_DIR / "gerar_video_wan22_5b.py",
    "wan22_5b_i2v":  BASE_DIR / "gerar_video_wan22_5b_i2v.py",
    "wan22_14b":     BASE_DIR / "gerar_video_wan22_14b.py",
    "ltx23":         BASE_DIR / "gerar_video_ltx23.py",
}

jobs = {}
comfyui_progress = {}  # prompt_id -> {"value": int, "max": int}

# ---------------------------------------------------------------------------
# Fila de execução
# ---------------------------------------------------------------------------

job_queue = _queue.Queue()      # fila de job_ids
cancelled_jobs = set()          # job_ids marcados para cancelamento
jobs_lock = threading.Lock()    # protege acesso ao dict `jobs`


# ---------------------------------------------------------------------------
# Persistência
# ---------------------------------------------------------------------------

def load_jobs():
    global jobs
    if JOBS_FILE.exists():
        try:
            with open(JOBS_FILE) as f:
                jobs = json.load(f)
        except Exception:
            jobs = {}

def save_jobs():
    with open(JOBS_FILE, 'w') as f:
        json.dump(jobs, f, indent=2)

load_jobs()


# ---------------------------------------------------------------------------
# WebSocket watcher para progresso real do ComfyUI
# ---------------------------------------------------------------------------

def start_progress_watcher():
    try:
        import websocket
    except ImportError:
        print("  [info] websocket-client não instalado - progresso por estimativa de tempo")
        return

    client_id = str(uuid.uuid4())

    def on_message(ws_app, message):
        try:
            data = json.loads(message)
            if data.get("type") == "progress":
                pd = data.get("data", {})
                pid = pd.get("prompt_id")
                if pid:
                    comfyui_progress[pid] = {
                        "value": pd.get("value", 0),
                        "max":   max(pd.get("max", 1), 1),
                    }
        except Exception:
            pass

    def run():
        while True:
            try:
                ws_app = websocket.WebSocketApp(
                    f"ws://127.0.0.1:8188/ws?clientId={client_id}",
                    on_message=on_message,
                )
                ws_app.run_forever()
            except Exception:
                pass
            time.sleep(5)

    threading.Thread(target=run, daemon=True).start()


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def restart_comfyui():
    try:
        result = subprocess.run([str(RESTART_SCRIPT)], capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except Exception:
        return False


def upload_image_to_comfyui(image_path: str) -> str:
    """Faz upload de uma imagem para o ComfyUI e retorna o nome do arquivo."""
    p = Path(image_path)
    with open(p, "rb") as f:
        files = {"image": (p.name, f, "image/png")}
        r = _requests.post(f"{COMFYUI_URL}/upload/image", files=files, timeout=30)
    r.raise_for_status()
    return r.json()["name"]


def build_cmd(job_id: str, req):
    # Determina se é I2V (tem imagem + modelo suporta)
    has_image = bool(getattr(req, "image_name", None))
    model_key = req.model
    if has_image and req.model == "wan22_5b":
        model_key = f"{req.model}_i2v"

    script = str(SCRIPTS[model_key])
    prefix = f"web_{model_key}_{job_id}"

    base = ["python3", script, req.prompt,
            "--width",  str(req.width),
            "--height", str(req.height),
            "--frames", str(req.frames),
            "--fps",    str(req.fps),
            "--cfg",    str(req.cfg),
            "--seed",   str(req.seed),
            "--output", prefix]

    if req.model == "wan22_5b":
        base += ["--negative", req.negative]
        if has_image:
            base += ["--image-name", req.image_name]
        return base

    elif req.model == "wan22_14b":
        base += ["--steps", str(req.steps), "--split-step", str(req.split_step)]
        return base

    elif req.model == "ltx23":
        base += ["--negative", req.negative]
        return base


def estimate_seconds(req) -> int:
    """Estimativa grosseira de segundos de geração baseada em frames e modelo."""
    factors = {"wan22_14b": 6, "wan22_5b": 2, "ltx23": 5}
    return req.frames * factors.get(req.model, 4)


def calc_progress_pct(job: dict) -> int:
    """Retorna 0-100. Usa WS se disponível, senão estimativa por tempo."""
    prompt_id = job.get("prompt_id")
    if prompt_id and prompt_id in comfyui_progress:
        p = comfyui_progress[prompt_id]
        return int(p["value"] / p["max"] * 100) if p["max"] else 0

    # Fallback: estimativa temporal
    started = job.get("started_at")
    estimated = job.get("estimated_seconds", 300)
    if not started:
        return 0
    elapsed = (datetime.now() - datetime.fromisoformat(started)).total_seconds()
    return min(95, int(elapsed / estimated * 100))


# ---------------------------------------------------------------------------
# Job runner
# ---------------------------------------------------------------------------

def run_job(job_id: str, req):
    # Verificar cancelamento antes de iniciar
    if job_id in cancelled_jobs:
        cancelled_jobs.discard(job_id)
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"]  = "Cancelado pelo usuário"
        save_jobs()
        return

    try:
        jobs[job_id]["status"]            = "processing"
        jobs[job_id]["started_at"]        = datetime.now().isoformat()
        jobs[job_id]["estimated_seconds"] = estimate_seconds(req)
        save_jobs()

        cmd    = build_cmd(job_id, req)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=JOB_TIMEOUT)

        # Capturar prompt_id do stdout
        for line in result.stdout.splitlines():
            if "Prompt ID:" in line:
                jobs[job_id]["prompt_id"] = line.split("Prompt ID:")[-1].strip()
                break

        # Guardar stdout/stderr para diagnóstico
        jobs[job_id]["stdout"] = result.stdout[-2000:] if result.stdout else ""
        jobs[job_id]["stderr"] = result.stderr[-2000:] if result.stderr else ""

        if result.returncode != 0 or "SUCESSO" not in result.stdout:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"]  = (result.stderr or result.stdout or "Erro desconhecido")[:500]
            save_jobs()
            restart_comfyui()
            return

        # Aguardar vídeo aparecer (com verificação de cancelamento)
        start  = time.time()
        # Usar job_id como critério (único e presente em qualquer variante T2V/I2V)
        video_found = None

        while time.time() - start < JOB_TIMEOUT:
            # Verificar cancelamento durante polling
            if job_id in cancelled_jobs:
                cancelled_jobs.discard(job_id)
                jobs[job_id]["status"] = "error"
                jobs[job_id]["error"]  = "Cancelado pelo usuário"
                save_jobs()
                return

            videos = [f for f in OUTPUT_DIR.glob("*.mp4") if job_id in f.name]
            if videos:
                video_found = sorted(videos, key=lambda x: x.stat().st_mtime, reverse=True)[0]
                break
            time.sleep(5)

        elapsed = time.time() - start

        if video_found:
            stat = video_found.stat()
            jobs[job_id]["status"]          = "completed"
            jobs[job_id]["video_file"]      = video_found.name
            jobs[job_id]["completed_at"]    = datetime.now().isoformat()
            jobs[job_id]["generation_time"] = f"{elapsed:.0f}s"
            jobs[job_id]["video_size_mb"]   = round(stat.st_size / 1048576, 2)
        else:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"]  = f"Timeout: vídeo não encontrado após {elapsed:.0f}s"

        save_jobs()
        restart_comfyui()
        time.sleep(15)

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"]  = str(e)
        save_jobs()
        restart_comfyui()


# ---------------------------------------------------------------------------
# Queue worker (thread única que processa jobs sequencialmente)
# ---------------------------------------------------------------------------

def queue_worker():
    """Thread única que processa jobs sequencialmente da fila."""
    while True:
        job_id = job_queue.get()   # bloqueia até ter trabalho

        if job_id in cancelled_jobs:
            cancelled_jobs.discard(job_id)
            if job_id in jobs:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["error"]  = "Cancelado pelo usuário"
                save_jobs()
            job_queue.task_done()
            continue

        if job_id in jobs:
            # Reconstruir req a partir dos dados salvos
            req_data = jobs[job_id].get("request", {})
            req = VideoRequest(**req_data)
            run_job(job_id, req)

        job_queue.task_done()


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home():
    html = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DGX Video Studio</title>
<style>
  :root {
    --bg: #0f1117; --card: #1a1d2e; --card2: #1e2235; --border: #2a2d3e;
    --accent: #6c63ff; --accent2: #a855f7; --text: #e2e8f0; --muted: #94a3b8;
    --green: #10b981; --yellow: #f59e0b; --red: #ef4444; --blue: #3b82f6;
    --indigo: #6366f1;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: 'Inter', system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
  .layout { display: grid; grid-template-columns: 380px 1fr; min-height: 100vh; }
  .sidebar { background: var(--card); border-right: 1px solid var(--border); padding: 24px; overflow-y: auto; }
  .main { padding: 24px; overflow-y: auto; }

  .logo { font-size: 22px; font-weight: 700; margin-bottom: 6px; display: flex; align-items: baseline; gap: 8px; }
  .logo span.name { background: linear-gradient(135deg, var(--accent), var(--accent2)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .logo span.ver { font-size: 12px; color: var(--muted); font-weight: 400; }
  .logo-sub { font-size: 12px; color: var(--muted); margin-bottom: 24px; }

  .model-grid { display: grid; gap: 8px; margin-bottom: 24px; }
  .model-btn { padding: 12px 16px; border-radius: 10px; border: 2px solid var(--border); background: var(--card2); cursor: pointer; text-align: left; transition: all 0.2s; }
  .model-btn:hover { border-color: var(--accent); }
  .model-btn.active { border-color: var(--accent); background: rgba(108,99,255,0.15); }
  .model-btn .model-name { font-weight: 600; font-size: 14px; }
  .model-btn .model-desc { font-size: 11px; color: var(--muted); margin-top: 2px; }
  .model-badge { float: right; font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
  .badge-fast  { background: rgba(16,185,129,0.2); color: var(--green); }
  .badge-best  { background: rgba(168,85,247,0.2); color: var(--accent2); }
  .badge-audio { background: rgba(59,130,246,0.2); color: var(--blue); }

  label { display: block; font-size: 12px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
  textarea, input, select { width: 100%; padding: 10px 12px; background: var(--card2); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-size: 14px; outline: none; transition: border 0.2s; }
  textarea:focus, input:focus { border-color: var(--accent); }
  textarea { resize: vertical; min-height: 90px; }
  .form-group { margin-bottom: 16px; }
  .form-row  { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .hint { font-size: 11px; color: var(--muted); margin-top: 4px; }

  .presets { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 16px; }
  .preset { padding: 5px 12px; border-radius: 6px; border: 1px solid var(--border); background: var(--card2); font-size: 12px; cursor: pointer; transition: all 0.2s; }
  .preset:hover { border-color: var(--accent); color: var(--accent); }

  .btn-generate { width: 100%; padding: 14px; border-radius: 10px; border: none; background: linear-gradient(135deg, var(--accent), var(--accent2)); color: white; font-size: 16px; font-weight: 700; cursor: pointer; transition: all 0.2s; margin-top: 8px; }
  .btn-generate:hover { transform: translateY(-1px); box-shadow: 0 8px 25px rgba(108,99,255,0.4); }
  .btn-generate:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

  .main-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
  .main-title { font-size: 20px; font-weight: 700; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); display: inline-block; margin-right: 6px; animation: pulse-dot 2s infinite; }
  @keyframes pulse-dot { 0%,100%{opacity:1} 50%{opacity:0.4} }

  .tabs { display: flex; gap: 4px; margin-bottom: 20px; border-bottom: 1px solid var(--border); }
  .tab { padding: 8px 16px; font-size: 14px; cursor: pointer; border-bottom: 2px solid transparent; color: var(--muted); transition: all 0.2s; }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); }
  .section { display: none; }
  .section.active { display: block; }

  .jobs-grid { display: grid; gap: 16px; }

  /* Job card */
  .job-card { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 18px; transition: border 0.2s; }
  .job-card:hover { border-color: var(--accent); }
  .job-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
  .job-prompt { font-size: 14px; font-weight: 500; line-height: 1.4; flex: 1; }
  .job-meta { font-size: 11px; color: var(--muted); margin-top: 4px; }

  .job-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

  .status-pill { padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; white-space: nowrap; }
  .s-processing { background: rgba(245,158,11,0.2); color: var(--yellow); }
  .s-completed  { background: rgba(16,185,129,0.2); color: var(--green); }
  .s-error      { background: rgba(239,68,68,0.2); color: var(--red); }
  .s-queued     { background: rgba(99,102,241,0.2); color: #818cf8; }

  /* Cancel button */
  .btn-cancel {
    background: rgba(239,68,68,0.15);
    color: #ef4444;
    border: 1px solid rgba(239,68,68,0.3);
    padding: 4px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 600;
    transition: all 0.2s;
  }
  .btn-cancel:hover { background: rgba(239,68,68,0.3); }

  /* Progress */
  .progress-wrap { height: 6px; background: var(--border); border-radius: 3px; margin: 10px 0 6px; overflow: hidden; position: relative; }
  .progress-fill { height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent2)); border-radius: 3px; transition: width 0.8s ease; }
  .progress-pct  { font-size: 11px; color: var(--yellow); font-weight: 600; margin-bottom: 8px; }

  /* Details section */
  .details-toggle { font-size: 12px; color: var(--accent); cursor: pointer; margin-top: 10px; display: inline-block; user-select: none; }
  .details-body { display: none; margin-top: 10px; padding: 12px; background: var(--card2); border-radius: 8px; border: 1px solid var(--border); }
  .details-body.open { display: block; }

  .detail-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 8px; margin-bottom: 10px; }
  .detail-item { }
  .detail-label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
  .detail-value { font-size: 13px; font-weight: 500; margin-top: 2px; }

  .prompt-full { font-size: 12px; color: var(--text); background: var(--bg); padding: 8px 10px; border-radius: 6px; border: 1px solid var(--border); line-height: 1.5; white-space: pre-wrap; word-break: break-word; margin-bottom: 8px; }
  .error-box { font-size: 12px; color: var(--red); background: rgba(239,68,68,0.08); padding: 8px 10px; border-radius: 6px; border: 1px solid rgba(239,68,68,0.3); white-space: pre-wrap; word-break: break-word; }

  /* Resource badge */
  .res-badge { display: inline-block; font-size: 10px; padding: 2px 8px; border-radius: 6px; background: rgba(108,99,255,0.15); color: var(--accent); font-weight: 600; margin-left: 6px; }

  /* Queue info banner */
  .queue-info { font-size: 12px; color: #818cf8; background: rgba(99,102,241,0.1); border: 1px solid rgba(99,102,241,0.3); border-radius: 8px; padding: 6px 12px; margin: 8px 0; }

  /* Image upload */
  .upload-zone {
    border: 2px dashed var(--border); border-radius: 10px; padding: 16px 12px;
    text-align: center; cursor: pointer; transition: all 0.2s; margin-bottom: 16px;
    position: relative; background: var(--card2);
  }
  .upload-zone:hover, .upload-zone.drag { border-color: var(--accent); background: rgba(108,99,255,0.08); }
  .upload-zone input[type=file] { position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%; }
  .upload-icon { font-size: 28px; margin-bottom: 6px; }
  .upload-text { font-size: 13px; color: var(--muted); }
  .upload-hint { font-size: 11px; color: var(--muted); margin-top: 4px; }
  .img-preview { width: 100%; border-radius: 8px; margin-top: 8px; max-height: 160px; object-fit: contain; display: none; }
  .img-clear { font-size: 11px; color: var(--red); cursor: pointer; margin-top: 6px; display: none; }
  .upload-name { font-size: 12px; color: var(--green); margin-top: 4px; display: none; }
  .i2v-badge { display: inline-block; font-size: 10px; padding: 2px 8px; border-radius: 6px; background: rgba(16,185,129,0.2); color: var(--green); font-weight: 600; margin-left: 4px; }

  video { width: 100%; border-radius: 10px; margin-top: 12px; max-height: 360px; background: #000; }

  /* Gallery */
  .gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; margin-top: 20px; }
  .gallery-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
  .gallery-card video { width: 100%; max-height: 180px; display: block; background: #000; }
  .gallery-info { padding: 10px 12px; }
  .gallery-name { font-size: 11px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .gallery-meta { font-size: 11px; color: var(--muted); margin-top: 4px; }
  .gallery-prompt { font-size: 11px; color: var(--text); margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  .advanced-toggle { font-size: 12px; color: var(--accent); cursor: pointer; margin-bottom: 12px; }
  .advanced-section { display: none; }
  .advanced-section.open { display: block; }

  .empty { text-align: center; padding: 60px; color: var(--muted); }
  .empty-icon { font-size: 48px; margin-bottom: 12px; }

  @media (max-width: 768px) {
    .layout { grid-template-columns: 1fr; }
    .sidebar { border-right: none; border-bottom: 1px solid var(--border); }
  }
</style>
</head>
<body>
<div class="layout">

<!-- SIDEBAR -->
<div class="sidebar">
  <div class="logo">DGX <span class="name">&#9654; v4.2</span> <span class="ver">Fila + Cancel</span></div>
  <div class="logo-sub">NVIDIA GB10 · 128GB · 1 PFLOP FP4</div>

  <label>Modelo</label>
  <div class="model-grid">
    <div class="model-btn active" onclick="selectModel('wan22_14b', this)">
      <span class="model-badge badge-best">MELHOR</span>
      <div class="model-name">Wan 2.2 14B MoE</div>
      <div class="model-desc">Qualidade cinematográfica · Dual-Expert · ~8 min</div>
    </div>
    <div class="model-btn" onclick="selectModel('wan22_5b', this)">
      <span class="model-badge badge-fast">RÁPIDO</span>
      <div class="model-name">Wan 2.2 5B</div>
      <div class="model-desc">Leve · T2V + I2V · ~2 min</div>
    </div>
    <div class="model-btn" onclick="selectModel('ltx23', this)">
      <span class="model-badge badge-audio">ÁUDIO</span>
      <div class="model-name">LTX-2.3 22B</div>
      <div class="model-desc">Vídeo + áudio + lipsync · ~5 min</div>
    </div>
  </div>

  <!-- Image upload (só aparece para Wan 2.2 5B) -->
  <div id="i2v-section" style="display:none;">
    <label>Imagem Inicial <span class="i2v-badge">I2V</span></label>
    <div class="upload-zone" id="uploadZone">
      <input type="file" id="imageFile" accept="image/*" onchange="onFileSelect(this)">
      <div class="upload-icon">🖼️</div>
      <div class="upload-text">Clique ou arraste uma imagem</div>
      <div class="upload-hint">PNG, JPG, WebP · Opcional (sem imagem = T2V)</div>
      <img id="imgPreview" class="img-preview">
      <div class="upload-name" id="uploadName"></div>
    </div>
    <div class="img-clear" id="clearBtn" onclick="clearImage()">✕ Remover imagem</div>
  </div>

  <label>Resolução</label>
  <div class="presets" id="presets"></div>

  <div class="form-group">
    <label>Prompt</label>
    <textarea id="prompt" placeholder="Descreva o vídeo que deseja gerar..."></textarea>
  </div>

  <div class="form-row">
    <div class="form-group"><label>Largura</label><input type="number" id="width" value="1280" step="32"></div>
    <div class="form-group"><label>Altura</label><input type="number" id="height" value="704" step="32"></div>
  </div>

  <div class="form-row">
    <div class="form-group">
      <label>Frames</label>
      <input type="number" id="frames" value="57">
      <div class="hint" id="frames-hint">57 frames = ~2.4s @ 24fps</div>
    </div>
    <div class="form-group">
      <label>Seed (-1 = aleatório)</label>
      <input type="number" id="seed" value="-1">
    </div>
  </div>

  <div class="advanced-toggle" onclick="toggleAdvanced()">⚙️ Parâmetros avançados ▾</div>
  <div class="advanced-section" id="advanced">
    <div class="form-row">
      <div class="form-group"><label>CFG Scale</label><input type="number" id="cfg" value="3.5" step="0.5" min="1" max="20"></div>
      <div class="form-group"><label>Steps</label><input type="number" id="steps" value="30" min="10" max="60"></div>
    </div>
    <div class="form-group" id="split-group">
      <label>Split Step (High→Low Noise)</label>
      <input type="number" id="split_step" value="15">
      <div class="hint">Ponto de troca entre os dois experts do MoE</div>
    </div>
    <div class="form-group">
      <label>Prompt Negativo</label>
      <input type="text" id="negative" placeholder="(opcional)">
    </div>
  </div>

  <button class="btn-generate" id="genBtn" onclick="generate()">Gerar Vídeo</button>
  <div id="gen-status" style="margin-top:10px; font-size:13px; color:var(--muted); text-align:center;"></div>
</div>

<!-- MAIN -->
<div class="main">
  <div class="main-header">
    <div class="main-title">Vídeos</div>
    <div style="font-size:13px; color:var(--muted)"><span class="status-dot"></span>ComfyUI ativo</div>
  </div>

  <div class="tabs">
    <div class="tab active" onclick="switchTab('queue', this)">Fila de Jobs</div>
    <div class="tab" onclick="switchTab('gallery', this)">Galeria</div>
  </div>

  <div class="section active" id="sec-queue">
    <div class="jobs-grid" id="jobsList">
      <div class="empty"><div class="empty-icon">🎬</div>Nenhum vídeo gerado ainda.<br>Crie seu primeiro vídeo ao lado!</div>
    </div>
  </div>

  <div class="section" id="sec-gallery">
    <div class="gallery-grid" id="galleryList">
      <div class="empty"><div class="empty-icon">📂</div>Carregando galeria...</div>
    </div>
  </div>
</div>
</div>

<script>
let currentModel = 'wan22_14b';
const expandedJobs = new Set();
let uploadedImageName = '';  // nome do arquivo no ComfyUI após upload

const MODEL_PRESETS = {
  wan22_14b: [
    { label:'480P · 2s',  w:832,  h:480, f:33,  cfg:3.5, steps:30, split:15 },
    { label:'720P · 2.4s',w:1280, h:704, f:57,  cfg:3.5, steps:30, split:15 },
    { label:'720P · 5s',  w:1280, h:720, f:81, cfg:3.5, steps:30, split:15 },  // 14B MoE: max 81 frames @ 16fps (acima = artefatos)
  ],
  wan22_5b: [
    { label:'480P · 2s',  w:720,  h:480, f:33,  cfg:6.0, steps:20, split:10 },
    { label:'720P · 2s',  w:1280, h:720, f:33,  cfg:6.0, steps:20, split:10 },
    { label:'480P · 5s',  w:720,  h:480, f:80,  cfg:6.0, steps:20, split:10 },
  ],
  ltx23: [
    { label:'512P · 2s',  w:512,  h:512, f:49,  cfg:3.0, steps:8, split:0 },
    { label:'768P · 3s',  w:768,  h:512, f:73,  cfg:3.0, steps:8, split:0 },
    { label:'HD · 5s',    w:1024, h:576, f:121, cfg:3.0, steps:8, split:0 },
  ],
};

const MODEL_LABELS = { wan22_5b:'Wan 2.2 5B', wan22_14b:'Wan 2.2 14B MoE', ltx23:'LTX-2.3 22B' };
const VRAM_MAP     = { wan22_14b:'~90 GB', wan22_5b:'~25 GB', ltx23:'~70 GB' };

function selectModel(model, el) {
  currentModel = model;
  document.querySelectorAll('.model-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  renderPresets();
  applyPreset(MODEL_PRESETS[model][0]);
  document.getElementById('split-group').style.display = model === 'wan22_14b' ? 'block' : 'none';
  // Mostrar/ocultar seção de imagem
  const i2vSupport = ['wan22_5b'].includes(model);
  document.getElementById('i2v-section').style.display = i2vSupport ? 'block' : 'none';
  if (!i2vSupport) clearImage();
}

async function onFileSelect(input) {
  if (!input.files || !input.files[0]) return;
  const file = input.files[0];

  // Preview local imediato
  const preview = document.getElementById('imgPreview');
  preview.src = URL.createObjectURL(file);
  preview.style.display = 'block';
  document.getElementById('clearBtn').style.display = 'block';
  document.getElementById('uploadName').style.display = 'block';
  document.getElementById('uploadName').textContent = '⏳ Enviando para ComfyUI...';

  // Upload para o servidor
  try {
    const formData = new FormData();
    formData.append('file', file);
    const res  = await fetch('/api/upload-image', { method: 'POST', body: formData });
    const data = await res.json();
    if (res.ok) {
      uploadedImageName = data.name;
      document.getElementById('uploadName').textContent = '✅ ' + data.name;
    } else {
      document.getElementById('uploadName').textContent = '❌ ' + (data.error || 'Erro no upload');
      uploadedImageName = '';
    }
  } catch(e) {
    document.getElementById('uploadName').textContent = '❌ ' + e.message;
    uploadedImageName = '';
  }
}

function clearImage() {
  uploadedImageName = '';
  document.getElementById('imageFile').value = '';
  document.getElementById('imgPreview').style.display = 'none';
  document.getElementById('imgPreview').src = '';
  document.getElementById('clearBtn').style.display = 'none';
  document.getElementById('uploadName').style.display = 'none';
  document.getElementById('uploadName').textContent = '';
}

function renderPresets() {
  const div = document.getElementById('presets');
  div.innerHTML = '';
  MODEL_PRESETS[currentModel].forEach(p => {
    const btn = document.createElement('button');
    btn.className = 'preset';
    btn.textContent = p.label;
    btn.onclick = () => applyPreset(p);
    div.appendChild(btn);
  });
}

function applyPreset(p) {
  document.getElementById('width').value      = p.w;
  document.getElementById('height').value     = p.h;
  document.getElementById('frames').value     = p.f;
  document.getElementById('cfg').value        = p.cfg;
  document.getElementById('steps').value      = p.steps;
  document.getElementById('split_step').value = p.split;
  updateFramesHint();
}

function updateFramesHint() {
  const f = parseInt(document.getElementById('frames').value) || 0;
  document.getElementById('frames-hint').textContent = `${f} frames = ~${(f/24).toFixed(1)}s @ 24fps`;
}
document.getElementById('frames').addEventListener('input', updateFramesHint);

function toggleAdvanced() {
  document.getElementById('advanced').classList.toggle('open');
}

function switchTab(tab, el) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('sec-' + tab).classList.add('active');
}

function toggleDetails(jobId) {
  if (expandedJobs.has(jobId)) expandedJobs.delete(jobId);
  else expandedJobs.add(jobId);
  const body = document.getElementById('details-' + jobId);
  const lnk  = document.getElementById('toggle-' + jobId);
  if (body) body.classList.toggle('open', expandedJobs.has(jobId));
  if (lnk)  lnk.textContent = expandedJobs.has(jobId) ? '▲ Ocultar detalhes' : '▼ Ver detalhes';
}

async function generate() {
  const prompt = document.getElementById('prompt').value.trim();
  if (!prompt) { alert('Escreva um prompt!'); return; }

  const btn = document.getElementById('genBtn');
  btn.disabled = true;
  document.getElementById('gen-status').textContent = 'Submetendo...';

  const data = {
    model:      currentModel,
    prompt,
    negative:   document.getElementById('negative').value,
    width:      parseInt(document.getElementById('width').value),
    height:     parseInt(document.getElementById('height').value),
    frames:     parseInt(document.getElementById('frames').value),
    fps:        24,
    cfg:        parseFloat(document.getElementById('cfg').value),
    seed:       parseInt(document.getElementById('seed').value),
    steps:      parseInt(document.getElementById('steps').value),
    split_step: parseInt(document.getElementById('split_step').value),
    image_name: uploadedImageName,
  };

  try {
    const res    = await fetch('/api/generate', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data) });
    const result = await res.json();
    if (res.ok) {
      document.getElementById('gen-status').textContent = '';
      document.querySelectorAll('.tab')[0].click();
    } else {
      document.getElementById('gen-status').textContent = '❌ ' + (result.error || 'Erro');
    }
  } catch(e) {
    document.getElementById('gen-status').textContent = '❌ ' + e.message;
  }
  btn.disabled = false;
}

async function cancelJob(jobId) {
  if (!confirm('Cancelar este job?')) return;
  try {
    const res  = await fetch(`/api/cancel/${jobId}`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) {
      alert('Erro ao cancelar: ' + (data.error || res.status));
    }
  } catch(e) {
    alert('Erro ao cancelar: ' + e.message);
  }
  loadJobs();
}

function fmt(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('pt-BR', { day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit' });
}

function elapsed(a, b) {
  if (!a || !b) return '—';
  const s = Math.round((new Date(b) - new Date(a)) / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s/60)}m ${s%60}s`;
}

function buildDetailGrid(req, job) {
  if (!req) return '';
  const vram = VRAM_MAP[req.model] || '—';
  const dur  = req.frames && req.fps ? `${(req.frames/req.fps).toFixed(1)}s` : '—';
  const items = [
    ['Modelo',      MODEL_LABELS[req.model] || req.model],
    ['Resolução',   `${req.width}×${req.height}`],
    ['Frames',      `${req.frames} (${dur} @ ${req.fps}fps)`],
    ['CFG',         req.cfg],
    ['Steps',       req.steps || '—'],
    ['Split Step',  req.split_step || '—'],
    ['Seed',        req.seed],
    ['VRAM est.',   vram],
    ['Submetido',   fmt(job.created_at)],
    ['Iniciado',    fmt(job.started_at)],
    ['Concluído',   fmt(job.completed_at)],
    ['Duração',     job.generation_time || elapsed(job.started_at, job.completed_at)],
    ['Tamanho',     job.video_size_mb ? `${job.video_size_mb} MB` : '—'],
    ['Prompt ID',   job.prompt_id || '—'],
  ];
  return `<div class="detail-grid">${items.map(([l,v]) =>
    `<div class="detail-item"><div class="detail-label">${l}</div><div class="detail-value">${v}</div></div>`
  ).join('')}</div>`;
}

let _lastJobsFingerprint = '';
let _lastCompletedCount  = 0;

function jobsFingerprint(jobs) {
  // Representa o que realmente muda: status + progresso por job
  return Object.entries(jobs).map(([id, j]) =>
    `${id}:${j.status}:${j.progress_pct || 0}:${j.queue_position || 0}`
  ).sort().join('|');
}

async function loadJobs() {
  try {
    const res  = await fetch('/api/jobs');
    const jobs = await res.json();
    const container = document.getElementById('jobsList');

    // Só rebuilda o DOM se algo mudou
    const fp = jobsFingerprint(jobs);
    const domExists = container.querySelector('.job-card');
    if (fp === _lastJobsFingerprint && domExists) {
      return; // Nada mudou, não toca no DOM
    }
    _lastJobsFingerprint = fp;

    // Disparar galeria apenas quando surgiu um novo vídeo completado
    const completedNow = Object.values(jobs).filter(j => j.status === 'completed').length;
    if (completedNow > _lastCompletedCount) {
      _lastCompletedCount = completedNow;
      loadGallery();
    }

    const sorted = Object.entries(jobs)
      .sort((a,b) => new Date(b[1].created_at) - new Date(a[1].created_at))
      .slice(0, 30);

    if (!sorted.length) {
      container.innerHTML = '<div class="empty"><div class="empty-icon">🎬</div>Nenhum vídeo gerado ainda.<br>Crie seu primeiro vídeo ao lado!</div>';
      return;
    }

    // Botão de gerar sempre habilitado; mostrar contador de fila
    const queuedCount = sorted.filter(([,j]) => j.status === 'queued').length;
    const processingCount = sorted.filter(([,j]) => j.status === 'processing').length;
    document.getElementById('genBtn').disabled = false;
    if (queuedCount > 0) {
      document.getElementById('gen-status').textContent = `${queuedCount} job(s) na fila · ${processingCount} processando`;
    } else if (processingCount > 0) {
      document.getElementById('gen-status').textContent = `${processingCount} job(s) processando...`;
    } else {
      document.getElementById('gen-status').textContent = '';
    }

    container.innerHTML = sorted.map(([id, job]) => {
      const req = job.request || {};

      const statusClass = {
        queued:     's-queued',
        processing: 's-processing',
        completed:  's-completed',
        error:      's-error'
      }[job.status] || 's-queued';

      const statusText = {
        queued:     `Na fila (#${job.queue_position || '?'})`,
        processing: 'Gerando...',
        completed:  'Concluído',
        error:      'Erro'
      }[job.status] || job.status;

      const modelLabel = MODEL_LABELS[req.model] || req.model || '';
      const vram       = VRAM_MAP[req.model] || '';
      const isOpen     = expandedJobs.has(id);

      // Botão cancelar para queued ou processing
      const canCancel = job.status === 'queued' || job.status === 'processing';
      const cancelBtn = canCancel
        ? `<button onclick="cancelJob('${id}')" class="btn-cancel">✕ Cancelar</button>`
        : '';

      // Progress bar (só para processing)
      let progressHtml = '';
      if (job.status === 'processing') {
        const pct = job.progress_pct || 0;
        progressHtml = `
          <div class="progress-pct">${pct}% concluído</div>
          <div class="progress-wrap"><div class="progress-fill" style="width:${pct}%"></div></div>`;
      }

      // Indicador de fila
      let queueHtml = '';
      if (job.status === 'queued') {
        queueHtml = `<div class="queue-info">⏳ Aguardando na fila — posição #${job.queue_position || '?'}</div>`;
      }

      // Video
      let videoHtml = '';
      if (job.status === 'completed' && job.video_file) {
        videoHtml = `<video controls loop><source src="/api/video/${job.video_file}" type="video/mp4"></video>`;
      }

      // Meta line
      const dur = req.frames && req.fps ? `${(req.frames/req.fps).toFixed(1)}s` : '';
      const mode = req.image_name ? '<span class="i2v-badge">I2V</span>' : '';
      const metaParts = [modelLabel + mode, req.width ? `${req.width}×${req.height}` : '', dur ? `${req.frames}f (${dur})` : '', job.generation_time ? `⏱ ${job.generation_time}` : ''].filter(Boolean);

      // Details section
      const promptText = req.prompt || '';
      const negText    = req.negative ? `<div style="margin-top:6px;"><span style="color:var(--muted);font-size:11px;">Negativo: </span><span style="font-size:12px;">${req.negative}</span></div>` : '';
      const errorHtml  = job.error   ? `<div class="error-box" style="margin-top:8px;"><strong>Erro:</strong> ${job.error}</div>` : '';
      const stdoutHtml = (job.stdout || job.stderr) && isOpen ? `
        <details style="margin-top:8px;">
          <summary style="font-size:11px;color:var(--muted);cursor:pointer;">Log do processo</summary>
          <pre style="font-size:10px;color:var(--muted);margin-top:6px;white-space:pre-wrap;word-break:break-all;max-height:150px;overflow-y:auto;">${(job.stdout || '') + (job.stderr ? '\n--- stderr ---\n' + job.stderr : '')}</pre>
        </details>` : '';

      return `<div class="job-card">
        <div class="job-header">
          <div style="flex:1">
            <div class="job-prompt">${promptText.substring(0,120)}${promptText.length>120?'…':''}</div>
            <div class="job-meta">${metaParts.join(' · ')}${vram ? `<span class="res-badge">${vram} VRAM</span>` : ''}</div>
          </div>
          <div class="job-actions">
            ${cancelBtn}
            <div class="status-pill ${statusClass}">${statusText}</div>
          </div>
        </div>
        ${queueHtml}
        ${progressHtml}
        ${videoHtml}
        ${job.status === 'error' ? `<div style="color:var(--red);font-size:12px;margin-top:8px;">❌ ${(job.error||'').substring(0,120)}</div>` : ''}
        <span class="details-toggle" id="toggle-${id}" onclick="toggleDetails('${id}')">${isOpen ? '▲ Ocultar detalhes' : '▼ Ver detalhes'}</span>
        <div class="details-body ${isOpen?'open':''}" id="details-${id}">
          <div class="prompt-full">${promptText}</div>
          ${negText}
          ${buildDetailGrid(req, job)}
          ${errorHtml}
          ${stdoutHtml}
        </div>
      </div>`;
    }).join('');
  } catch(e) { console.error(e); }
}

async function loadGallery() {
  try {
    const res    = await fetch('/api/all-videos');
    const videos = await res.json();
    const container = document.getElementById('galleryList');

    if (!videos.length) {
      container.innerHTML = '<div class="empty"><div class="empty-icon">📂</div>Nenhum vídeo no output ainda.</div>';
      return;
    }

    container.innerHTML = videos.map(v => {
      const job = v.job || {};
      const req = job.request || {};
      const promptSnippet = req.prompt ? req.prompt.substring(0,80) + (req.prompt.length>80?'…':'') : '';
      const metaParts = [
        MODEL_LABELS[req.model] || '',
        req.width ? `${req.width}×${req.height}` : '',
        job.generation_time ? `⏱ ${job.generation_time}` : '',
        v.size_mb ? `${v.size_mb} MB` : '',
      ].filter(Boolean);

      return `<div class="gallery-card">
        <video controls loop muted><source src="/api/video/${v.filename}" type="video/mp4"></video>
        <div class="gallery-info">
          ${promptSnippet ? `<div class="gallery-prompt" title="${req.prompt || ''}">${promptSnippet}</div>` : ''}
          <div class="gallery-meta">${metaParts.join(' · ')}</div>
          <div class="gallery-name">${v.filename}</div>
          <div class="gallery-meta">${v.modified_str}</div>
        </div>
      </div>`;
    }).join('');
  } catch(e) { console.error(e); }
}

// Init
renderPresets();
applyPreset(MODEL_PRESETS['wan22_14b'][0]);
document.getElementById('split-group').style.display = 'block';
document.getElementById('i2v-section').style.display = 'none';  // 14B = T2V only

// Refresh adaptativo: 4s com jobs ativos, 20s quando tudo parado
let _jobsTimer = null;
function scheduleJobsRefresh(hasActive) {
  clearTimeout(_jobsTimer);
  _jobsTimer = setTimeout(async () => {
    await loadJobs();
  }, hasActive ? 4000 : 20000);
}

// Sobrescrever loadJobs para encadear o próximo refresh
const _loadJobsOrig = loadJobs;
loadJobs = async function() {
  await _loadJobsOrig();
  const active = document.querySelectorAll('.s-processing, .s-queued').length > 0;
  scheduleJobsRefresh(active);
};

// Galeria: só recarrega ao trocar de aba ou quando um job completa
const _switchTabOrig = switchTab;
switchTab = function(tab, el) {
  _switchTabOrig(tab, el);
  if (tab === 'gallery') loadGallery();
};

loadJobs();
loadGallery();
</script>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

class VideoRequest(BaseModel):
    model:      str   = "wan22_14b"
    prompt:     str
    negative:   str   = ""
    width:      int   = 1280
    height:     int   = 704
    frames:     int   = 57
    fps:        int   = 24
    cfg:        float = 3.5
    seed:       int   = -1
    steps:      int   = 30
    split_step: int   = 15
    image_name: str   = ""   # nome do arquivo já uploaded no ComfyUI (I2V)


@app.post("/api/generate")
async def generate(request: VideoRequest):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "job_id":     job_id,
        "status":     "queued",
        "request":    request.model_dump(),
        "created_at": datetime.now().isoformat(),
    }
    save_jobs()
    job_queue.put(job_id)
    queue_pos = job_queue.qsize()
    return {"job_id": job_id, "status": "queued", "queue_position": queue_pos}


@app.post("/api/cancel/{job_id}")
async def cancel_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job não encontrado"})

    if job["status"] == "queued":
        # Cancelamento imediato: marcar para pular no worker
        cancelled_jobs.add(job_id)
        job["status"] = "error"
        job["error"]  = "Cancelado pelo usuário"
        save_jobs()
        return {"ok": True, "message": "Job cancelado"}

    elif job["status"] == "processing":
        # Sinaliza cancelamento; run_job vai detectar no próximo ciclo de polling
        cancelled_jobs.add(job_id)
        return {"ok": True, "message": "Cancelamento solicitado"}

    return JSONResponse(
        status_code=400,
        content={"error": f"Job em status '{job['status']}' não pode ser cancelado"}
    )


@app.get("/api/jobs")
async def get_jobs():
    # Calcular posições na fila
    queued_ids = [jid for jid, j in jobs.items() if j["status"] == "queued"]
    for i, jid in enumerate(queued_ids):
        jobs[jid]["queue_position"] = i + 1

    for job in jobs.values():
        # Marcar timeouts
        if job["status"] == "processing":
            started = datetime.fromisoformat(job.get("started_at", job["created_at"]))
            if (datetime.now() - started).total_seconds() > JOB_TIMEOUT:
                job["status"] = "error"
                job["error"]  = "Timeout"
            else:
                # Injetar progresso ao retornar
                job["progress_pct"] = calc_progress_pct(job)
    save_jobs()
    return jobs


@app.get("/api/video/{filename}")
async def get_video(filename: str):
    # Confina a OUTPUT_DIR — previne path traversal (ex: ../../etc/passwd)
    fp = (OUTPUT_DIR / filename).resolve()
    if OUTPUT_DIR.resolve() in fp.parents and fp.is_file():
        return FileResponse(fp)
    return JSONResponse(status_code=404, content={"error": "Não encontrado"})


@app.get("/api/all-videos")
async def all_videos():
    # Mapa filename -> job para enriquecer galeria
    filename_to_job = {j.get("video_file"): j for j in jobs.values() if j.get("video_file")}

    videos = []
    for f in OUTPUT_DIR.glob("*.mp4"):
        s = f.stat()
        entry = {
            "filename":     f.name,
            "size_mb":      round(s.st_size / 1048576, 2),
            "modified":     datetime.fromtimestamp(s.st_mtime).isoformat(),
            "modified_str": datetime.fromtimestamp(s.st_mtime).strftime("%d/%m %H:%M"),
            "job":          filename_to_job.get(f.name, {}),
        }
        videos.append(entry)
    videos.sort(key=lambda x: x["modified"], reverse=True)
    return videos


@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """Recebe uma imagem da interface web e faz upload para o ComfyUI."""
    try:
        suffix = Path(file.filename).suffix or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        image_name = upload_image_to_comfyui(tmp_path)
        Path(tmp_path).unlink(missing_ok=True)
        return {"name": image_name}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/restart")
async def restart():
    ok = restart_comfyui()
    return {"status": "ok" if ok else "error"}


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  DGX Video Studio v4.2 - Fila de Jobs + Cancelamento")
    print("=" * 60)
    print()
    print("  Modelos disponíveis:")
    print("  - Wan 2.2 14B MoE (qualidade máxima)")
    print("  - Wan 2.2 5B     (rápido, híbrido T2V+I2V)")
    print("  - LTX-2.3 22B    (vídeo + áudio + lipsync)")
    print()
    print("  Novidades v4.2:")
    print("  - Múltiplos jobs em fila (queued → processing → completed)")
    print("  - Cancelar job na fila ou em processamento")
    print()
    print("  Acesse: http://localhost:7862")
    print()
    # Iniciar thread worker da fila
    threading.Thread(target=queue_worker, daemon=True).start()
    start_progress_watcher()
    uvicorn.run(app, host="0.0.0.0", port=7862, log_level="warning")
