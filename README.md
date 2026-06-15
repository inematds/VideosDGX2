# VideosDGX2 — Geração de Vídeo no DGX Spark

Geração de vídeo com **Wan 2.2** rodando localmente no **NVIDIA DGX Spark 2026**
(GB10 Blackwell · 128 GB de memória unificada · ~1 PFLOP FP4), via **ComfyUI** e uma
interface web própria com fila de jobs.

> Continuação reorganizada do repositório original
> [`inematds/VideosDGX`](https://github.com/inematds/VideosDGX) (mantido como backup
> histórico). Aqui ficou só o stack ativo: ComfyUI + Wan 2.2. Os pipelines antigos
> (LTX-2, Wan 2.1, MAGI-1, Waver) e o approach Docker foram removidos.

---

## Modelos ativos

| Modelo | Arquivo (em `ComfyUI/models/`) | VRAM | Uso |
|---|---|---|---|
| **Wan 2.2 14B MoE** | `unet/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors` + `…_low_noise_…` | ~90 GB | Qualidade máxima (dual-expert), T2V |
| **Wan 2.2 5B** | `unet/wan2.2_ti2v_5B_fp16.safetensors` | ~25 GB | Rápido, T2V **+ I2V** |
| Text encoder (UMT5) | `text_encoders/umt5_xxl_fp16.safetensors` | — | Compartilhado |
| VAE | `vae/wan2.2_vae.safetensors` (5B) · `vae/Wan2.1_VAE.pth` (14B) | — | — |

> **Os pesos NÃO ficam no git** (são ~50 GB, ignorados pelo `.gitignore`). Para baixá-los
> num ambiente novo, veja **[`doc/GUIA_COMPLETO_DO_ZERO.md`](doc/GUIA_COMPLETO_DO_ZERO.md)**.

---

## Início rápido

```bash
# Sobe ComfyUI (se não estiver rodando) + a interface web
./iniciar_interface_web.sh
```

Acesse **http://localhost:7862** (ComfyUI fica em `:8188`).

Acesso remoto: descubra o IP do DGX com `hostname -I` e abra `http://<IP>:7862`
(libere a porta 7862 no firewall, se houver).

### Interface web (porta 7862)

- **Fila de jobs**: submeta vários vídeos seguidos; processam em sequência.
- **Cancelamento**: cancela job na fila (imediato) ou em processamento.
- **I2V** (só Wan 2.2 5B): faça upload de uma imagem inicial.
- **Presets** de resolução/frames por modelo + parâmetros avançados (CFG, steps, split step).
- **Galeria** dos vídeos gerados.

| Endpoint | Método | Descrição |
|---|---|---|
| `/api/generate` | POST | Enfileira um job (corpo = `VideoRequest`) |
| `/api/jobs` | GET | Lista jobs + posição na fila + progresso |
| `/api/cancel/{job_id}` | POST | Cancela um job |
| `/api/video/{filename}` | GET | Serve um vídeo do output |
| `/api/all-videos` | GET | Lista a galeria |
| `/api/upload-image` | POST | Upload de imagem para I2V |

Estado da fila persistido em `/tmp/dgx_jobs_v4_2.json`.

### Linha de comando (CLI)

Cada modelo tem um gerador que submete o workflow ao ComfyUI:

```bash
# Wan 2.2 5B (T2V)
python3 gerar_video_wan22_5b.py "um gato astronauta flutuando na ISS" \
  --width 1280 --height 720 --frames 33 --fps 24 --cfg 6.0 --seed -1

# Wan 2.2 14B MoE (T2V, máxima qualidade)
python3 gerar_video_wan22_14b.py "cidade cyberpunk à noite, chuva, neon" \
  --width 1280 --height 704 --frames 81 --steps 30 --split-step 15

# Wan 2.2 5B (I2V) — anime a partir de uma imagem
python3 gerar_video_wan22_5b_i2v.py "a câmera afasta lentamente" --help
```

Rode qualquer script com `--help` para todas as opções.

### Dicas de prompt

- Fórmula: **`[SUJEITO] + [AÇÃO] + [CENÁRIO] + [ESTILO] + [QUALIDADE]`**.
- Largura/altura: múltiplos de **32**.
- **Wan 2.2 14B**: máximo **81 frames** (acima disso aparecem artefatos) — detalhes em
  [`doc/WAN22_LIMITES_FRAMES.md`](doc/WAN22_LIMITES_FRAMES.md).

---

## Estrutura do projeto

```
.
├── web_interface.py              # Interface web (FastAPI, fila + cancel + I2V) — porta 7862
├── iniciar_interface_web.sh      # Sobe ComfyUI + interface web
├── reiniciar_comfyui.sh          # Reinicia o ComfyUI (usado entre jobs)
├── gerar_video_wan22_14b.py      # Gerador CLI — Wan 2.2 14B MoE (T2V)
├── gerar_video_wan22_5b.py       # Gerador CLI — Wan 2.2 5B (T2V)
├── gerar_video_wan22_5b_i2v.py   # Gerador CLI — Wan 2.2 5B (I2V)
├── workflow_wan22_14b_t2v.json   # Workflow ComfyUI — 14B
├── workflow_wan22_5b_t2v.json    # Workflow ComfyUI — 5B
├── requirements.txt
├── doc/                          # Documentação (ver abaixo)
├── ComfyUI/                      # App + modelos (ignorado pelo git)
└── comfyui-env/                  # venv Python (ignorado pelo git)
```

## Documentação

| Doc | Conteúdo |
|---|---|
| [`doc/CONFIGURACAO_ATUAL.md`](doc/CONFIGURACAO_ATUAL.md) | Estado atual: hardware, modelos, portas, scripts |
| [`doc/GUIA_COMPLETO_DO_ZERO.md`](doc/GUIA_COMPLETO_DO_ZERO.md) | Montar tudo do zero (ComfyUI + Wan 2.2 + download dos pesos) |
| [`doc/WAN22_LIMITES_FRAMES.md`](doc/WAN22_LIMITES_FRAMES.md) | Limites de frames/duração do Wan 2.2 |
| [`doc/research-findings.md`](doc/research-findings.md) | Pesquisa de modelos de vídeo p/ DGX Spark |
| [`doc/skyreels-v3/`](doc/skyreels-v3/) | Avaliação do candidato SkyReels V3 (+ risco) |
| [`doc/arquivo/`](doc/arquivo/) | Histórico (por que o Docker foi abandonado, plano Wan 2.2, marcos) |

---

## Hardware

- **Plataforma**: NVIDIA DGX Spark 2026
- **GPU**: Blackwell GB10 · **Memória**: 128 GB unificada (CPU+GPU) · **~1 PFLOP FP4**
- A memória unificada permite carregar modelos grandes sem offload para CPU; quantização
  FP8 é usada no 14B para caber com folga.
