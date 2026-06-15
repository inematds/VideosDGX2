# Changelog

Mudanças notáveis do projeto. Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

## [5.0] - 2026-06-15 — Reorganização e migração para VideosDGX2

### Removido
- Pipelines **LTX-2**, **Wan 2.1**, **MAGI-1** e **Waver** (código, workflows e modelos).
- **Approach Docker** inteiro: `docker-compose*.yml`, `Makefile`, `common/`, `scripts/`,
  `frontend/`, `magi1/`, `waver/` — abandonado por incompatibilidade do `torch.xpu` em ARM64
  (ver [`doc/arquivo/PROCEDIMENTOS_DETALHADOS.md`](doc/arquivo/PROCEDIMENTOS_DETALHADOS.md)).
- Interfaces web antigas (v1–v4.1) e launchers correspondentes.
- ~20 docs obsoletos (LTX-2/Docker/relatórios de status pontuais) e logs soltos.

### Modificado
- Stack reduzido ao que está ativo: **ComfyUI + Wan 2.2 (5B + 14B MoE)**.
- `web_interface_v4_2.py` → **`web_interface.py`** (canônico); código LTX-2 morto removido.
- Paths absolutos → **relativos** (`$SCRIPT_DIR` / `Path(__file__).parent`).
- Documentação consolidada em `doc/` (canônicos + `doc/arquivo/` histórico).
- **~105 GB de disco liberados** (pipelines descontinuados ~73 GB + modelos
  quebrados/incompletos/duplicados ~20 GB + backup `.OLD` 11 GB).

### Infra
- Repositório original preservado como backup em
  [`inematds/VideosDGX`](https://github.com/inematds/VideosDGX); este repo (`VideosDGX2`)
  começa com histórico limpo.

---

## [4.2] - 2026-02-18 — Interface web: fila de jobs + cancelamento

- **Fila ilimitada** de jobs (thread worker sequencial via `queue.Queue`); ciclo
  `queued → processing → completed/error`.
- **Cancelamento** de jobs na fila (imediato) ou em processamento (`POST /api/cancel/{job_id}`).
- Posição na fila em `/api/jobs`; botão ✕ Cancelar; contadores na sidebar.
- Porta **7862**; estado em `/tmp/dgx_jobs_v4_2.json`.

---

## [1.0.0] - 2026-02-15 — Tentativa inicial (Docker, abandonada)

Primeira implementação: 4 containers Docker (LTX-2 / Wan 2.1 / MAGI-1 / Waver) com
camada FastAPI compartilhada. **Abandonado** — `torch.xpu` não funciona em ARM64 e a GPU
não era detectada nos containers. Substituído pelo ComfyUI. Histórico completo no repo
backup `inematds/VideosDGX`.
