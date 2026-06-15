# Relatório de Configuração e Estrutura — DGX Video Studio
**Data:** 2026-02-18
**Status:** Sistema em produção

---

## 1. Hardware

| Item | Valor |
|------|-------|
| Plataforma | NVIDIA DGX Spark 2026 |
| GPU | NVIDIA GB10 (Blackwell) |
| Memória unificada CPU+GPU | 128 GB |
| Performance FP4 | ~1 PFLOP |
| Disco NVMe | 3.7 TB total · 1.8 TB usado · 1.7 TB livre |

---

## 2. Software Base

| Item | Versão |
|------|--------|
| OS | Linux 6.14.0-1015-nvidia |
| Python | 3.12.3 |
| PyTorch | 2.10.0+cu130 |
| CUDA | 13.0 |
| Ambiente virtual | `comfyui-env` (venv em `/home/nmaldaner/projetos/VideosDGX/`) |
| Backend de inferência | **ComfyUI** (oficial NVIDIA) |

---

## 3. Serviços em Execução

| Serviço | Porta | PID | Arquivo |
|---------|-------|-----|---------|
| ComfyUI | 8188 | 500958 | `ComfyUI/main.py --listen 0.0.0.0` |
| Interface Web v4.2 | **7862** | 966347 | `web_interface_v4_2.py` |

> v4.1 (7861) também pode estar rodando em background — usar apenas v4.2.

---

## 4. Modelos Instalados

### 4.1 Modelos de Difusão / UNet — `ComfyUI/models/unet/` (101 GB)

| Arquivo | Tamanho | Status | Uso |
|---------|---------|--------|-----|
| `wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors` | 14 GB | ✅ Ativo | Wan 2.2 14B — expert ruído alto |
| `wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors` | 14 GB | ✅ Ativo | Wan 2.2 14B — expert ruído baixo |
| `wan2.2_ti2v_5B_fp16.safetensors` | 9.4 GB | ✅ Ativo | Wan 2.2 5B T2V + I2V |
| `wan2.1_t2v_14B.safetensors` | 65 GB | ❌ Inativo | Wan 2.1 — header muito grande (safetensors bug) |

### 4.2 Checkpoint — `ComfyUI/models/checkpoints/` (41 GB)

| Arquivo | Tamanho | Status |
|---------|---------|--------|
| `ltx-2-19b-distilled.safetensors` | 41 GB | ✅ Ativo |

### 4.3 Text Encoders — `ComfyUI/models/clip/` + `text_encoders/` (39 GB)

| Arquivo | Tamanho | Status | Uso |
|---------|---------|--------|-----|
| `gemma_3_12B_it_fp8_e4m3fn.safetensors` | 6.0 GB | ✅ Ativo | LTX-2 text encoder (FP8) |
| `ltx-2-19b-dev-fp4_projections_only.safetensors` | 2.7 GB | ✅ Ativo | LTX-2 projections (FP4) |
| `models_t5_umt5-xxl-enc-bf16.pth` | 11 GB | ✅ Ativo | Wan 2.2 text encoder (BF16) |
| `umt5_xxl_fp16.safetensors` | 11 GB | ⚠️ Redundante | Duplicata do T5 em FP16 |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors.BROKEN` | 6.3 GB | ❌ Corrompido | FP8 — header grande, não funciona |

### 4.4 VAE — `ComfyUI/models/vae/` (2 GB)

| Arquivo | Tamanho | Status | Uso |
|---------|---------|--------|-----|
| `wan2.2_vae.safetensors` | 1.4 GB | ✅ Ativo | Wan 2.2 (5B e 14B) |
| `LTX2_audio_vae_bf16.safetensors` | 208 MB | ✅ Ativo | LTX-2 áudio VAE |
| `Wan2.1_VAE.pth` | 485 MB | ❌ Inativo | Wan 2.1 (obsoleto) |

**Total em disco (models/):** 222 GB

---

## 5. Modelos Ativos — Capacidades

### Wan 2.2 14B MoE — `MELHOR QUALIDADE`
- **Arquitetura:** Mixture of Experts com 2 modelos especializados
  - High Noise Expert (primeiros steps)
  - Low Noise Expert (steps finais)
- **Quantização:** FP8 scaled (14 GB cada, total 28 GB)
- **VRAM estimada:** ~90 GB
- **Text encoder:** UMT5-XXL BF16
- **Workflow:** `workflow_wan22_14b_t2v.json`
- **Script:** `gerar_video_wan22_14b.py`
- **Parâmetros padrão:** 720×480 · 33f · CFG 3.5 · Steps 30 · Split step 15
- **Tempo estimado:** ~8 min para 57f @ 720P

### Wan 2.2 5B — `RÁPIDO · T2V + I2V`
- **Arquitetura:** Modelo híbrido único (Text-to-Video + Image-to-Video)
- **Quantização:** FP16 (9.4 GB)
- **VRAM estimada:** ~25 GB
- **Text encoder:** UMT5-XXL BF16 (compartilhado com 14B)
- **Workflow:** `workflow_wan22_5b_t2v.json`
- **Scripts:** `gerar_video_wan22_5b.py` · `gerar_video_wan22_5b_i2v.py`
- **Parâmetros padrão:** 720×480 · 33f · CFG 6.0 · Steps 20
- **Tempo estimado:** ~2 min para 33f @ 480P

### LTX-2 19B — `ÚNICO COM ÁUDIO`
- **Arquitetura:** Diffusion transformer full (áudio + vídeo)
- **Quantização:** Checkpoint distilled (FP4 nativo)
- **VRAM estimada:** ~45 GB
- **Text encoder:** Gemma 3 12B FP8 + projections FP4
- **Custom node:** `ComfyUI-LTXVideo`
- **Scripts:** `gerar_video_ltx2.py` · `gerar_video_ltx2_i2v.py`
- **Parâmetros padrão:** 1024×576 · 49f · CFG 3.0 · Steps 30
- **Tempo estimado:** ~3 min para 49f

---

## 6. Interface Web v4.2

### Acesso
```
http://localhost:7862
```

### Funcionalidades
- **Seleção de modelo:** Wan 2.2 14B / Wan 2.2 5B / LTX-2
- **Presets de resolução** por modelo
- **Image-to-Video (I2V):** LTX-2 e Wan 2.2 5B (upload de imagem)
- **Fila de jobs ilimitada:** múltiplos jobs em sequência (`queued → processing → completed`)
- **Cancelamento:** botão ✕ para jobs na fila ou em processamento
- **Refresh adaptativo:** 4s com jobs ativos · 20s quando ocioso · galeria 30s
- **Galeria:** todos os vídeos gerados com preview inline
- **Log de progresso:** barra de progresso via WebSocket do ComfyUI

### Arquivo de estado dos jobs
```
/tmp/dgx_jobs_v4_2.json
```

### Histórico de versões da interface

| Versão | Porta | Novidade principal |
|--------|-------|--------------------|
| v1 | 7860 | Primeiro protótipo |
| v2/v3 | 7860 | Múltiplos modelos |
| v4.0 | 7860 | Redesign completo |
| v4.1 | 7861 | Image-to-Video (I2V) |
| **v4.2** | **7862** | **Fila + Cancelamento** |

---

## 7. Custom Nodes do ComfyUI

| Node | Uso |
|------|-----|
| `ComfyUI-LTXVideo` | Nodes específicos para LTX-2 (LTXVImgToVideoConditionOnly, etc.) |
| `ComfyUI-VideoHelperSuite` | Utilitários de vídeo (combine frames, etc.) |
| `ComfyUI-WanVideoKsampler` | KSampler especializado para Wan 2.x |
| `MAGI-1` | Node do modelo MAGI-1 (instalado, modelo não baixado) |

---

## 8. Scripts de Geração (CLI)

| Script | Modelo | Modo |
|--------|--------|------|
| `gerar_video_wan22_14b.py` | Wan 2.2 14B MoE | T2V |
| `gerar_video_wan22_5b.py` | Wan 2.2 5B | T2V |
| `gerar_video_wan22_5b_i2v.py` | Wan 2.2 5B | I2V |
| `gerar_video_ltx2.py` | LTX-2 19B | T2V |
| `gerar_video_ltx2_i2v.py` | LTX-2 19B | I2V |
| `gerar_video_wan21.py` | Wan 2.1 14B | T2V (inativo — bug safetensors) |

---

## 9. Output

- **Diretório:** `/home/nmaldaner/projetos/VideosDGX/ComfyUI/output/`
- **Total de vídeos gerados:** 14 arquivos `.mp4`
- **Naming:** `web_{modelo}_{job_id}_{n}.mp4`
- **Último vídeo:** `web_wan22_5b_i2v_4efcde4a_00001.mp4` (976 KB · 18/02 19:29)

---

## 10. Problemas Conhecidos / Limitações

| Problema | Causa | Status |
|----------|-------|--------|
| `wan2.1_t2v_14B.safetensors` não funciona | Header safetensors >48 KB — incompatível com v0.7.0 | ⚠️ Ignorado (usando 2.2) |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors.BROKEN` | Header grande (mesmo problema) | ⚠️ Ignorado (usando BF16 .pth) |
| `umt5_xxl_fp16.safetensors` (11 GB) | Duplicata do BF16 — pode ser removido | 🗑️ Candidato a remoção |
| Jobs I2V travavam em `processing` | Bug: prefix de busca não incluía `_i2v` no nome | ✅ Corrigido em v4.1 e v4.2 |
| Wan 2.2 5B usa FP16 em vez de FP8 | Arquivo disponível no HuggingFace é FP16 | ℹ️ Aceitável (9.4 GB, cabe bem) |

---

## 11. Inicialização do Sistema

```bash
# 1. Verificar se ComfyUI está rodando
curl http://127.0.0.1:8188/system_stats

# 2. Iniciar interface web (recomendado)
cd /home/nmaldaner/projetos/VideosDGX
./iniciar_interface_web_v4_2.sh

# Acesse: http://localhost:7862
```

```bash
# Verificar GPU
nvidia-smi

# Ver logs da interface
tail -f web_v4_2.log
```

---

**Autor:** Claude Code Agent (Sonnet 4.5)
**Última atualização:** 2026-02-18
