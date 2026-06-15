# Guia Completo: Reconstruir Sistema do Zero
**Data:** 2026-02-22
**Autor:** Claude Code (Sonnet 4.5) — Conhecimento acumulado de 7 dias de desenvolvimento

---

## 📋 Índice

1. [Hardware e Especificações](#1-hardware-e-especificações)
2. [Lições Críticas Aprendidas](#2-lições-críticas-aprendidas)
3. [Arquitetura Escolhida e Por Quê](#3-arquitetura-escolhida-e-por-quê)
4. [Setup do Sistema Base](#4-setup-do-sistema-base)
5. [Instalação do ComfyUI](#5-instalação-do-comfyui)
6. [Modelos: O Que Funciona e O Que Não](#6-modelos-o-que-funciona-e-o-que-não)
7. [Custom Nodes e Dependências](#7-custom-nodes-e-dependências)
8. [Interface Web: Evolução e Decisões](#8-interface-web-evolução-e-decisões)
9. [Problemas Comuns e Soluções](#9-problemas-comuns-e-soluções)
10. [Otimizações de Performance](#10-otimizações-de-performance)
11. [Checklist de Validação](#11-checklist-de-validação)

---

## 1. Hardware e Especificações

### 1.1 Hardware Real Detectado

```
GPU:      NVIDIA GB10 (Blackwell Architecture)
Driver:   580.95.05
VRAM:     122 GB (GB10 spec: 128 GB total, ~6 GB reservado pelo sistema)
RAM:      120 GB (125511744 kB = ~119.7 GB)
CPU:      ARM64 (arquitetura aarch64 — IMPORTANTE!)
OS:       Ubuntu 24.04.3 LTS
Kernel:   6.14.0-1015-nvidia
Disco:    NVMe 3.7 TB total · 1.8 TB usado · 1.7 TB livre
```

### 1.2 Características Únicas do DGX Spark

**Memória Unificada (128 GB total):**
- GPU e CPU compartilham pool de memória
- Permite modelos grandes sem offloading CPU→GPU
- GB10 acessa RAM diretamente via NVLink

**Arquitetura ARM64:**
- ⚠️ **CRÍTICO:** Alguns Docker images x86_64 NÃO funcionam
- ⚠️ Binários pré-compilados podem falhar
- ✅ Python puro funciona normalmente
- ✅ PyTorch 2.10+ tem suporte nativo ARM64

**Blackwell GB10 — Recursos Especiais:**
- FP4/FP8 nativo em hardware (NVFP4)
- Tensor cores de 5ª geração
- CUDA 13.0 (retrocompatível com 12.x)
- Performance: ~1 PFLOP FP4 · ~0.5 PFLOP FP8 · ~60 TFLOPS FP16

---

## 2. Lições Críticas Aprendidas

### 2.1 O Que NÃO Funciona (Economize Horas)

#### ❌ Docker Multi-Container Approach
**Tentativa:** 4 containers (LTX-2, Wan, MAGI, Waver) com Docker Compose
**Problema:** `torch.xpu` não funciona em ARM64, conflitos de CUDA runtime
**Tempo perdido:** 4+ horas
**Lição:** Evitar Docker no DGX Spark para modelos de vídeo. Python venv funciona melhor.

#### ❌ Diffusers Library Direto (sem ComfyUI)
**Tentativa:** Usar `diffusers` library direto do HuggingFace
**Problema:** Suporte incompleto para LTX-2, faltam pipelines customizados
**Lição:** ComfyUI é **recomendação oficial da NVIDIA** para DGX Spark. Usar sempre.

#### ❌ Wan 2.1 14B
**Problema:** Safetensors header >48 KB → `safetensors 0.7.0` não lê
**Erro:** `"Error while deserializing header: header too large"`
**Modelo:** `wan2.1_t2v_14B.safetensors` (65 GB) → **INUTILIZÁVEL**
**Solução:** Migrar para Wan 2.2 (arquitetura MoE, headers menores)

#### ❌ Text Encoder FP8 para Wan (safetensors)
**Arquivo:** `umt5_xxl_fp8_e4m3fn_scaled.safetensors` (6.3 GB)
**Problema:** Mesmo erro de header >48 KB
**Workaround:** Usar versão `.pth` BF16 (11 GB) — funciona perfeitamente
**Trade-off:** +4.7 GB de VRAM, mas compatível

#### ❌ I2V com Prefix de Busca Errado
**Bug:** Jobs I2V ficavam travados em `processing` indefinidamente
**Causa:**
```python
# ERRADO (código original)
prefix = f"web_{req.model}_{job_id}"  # "web_wan22_5b_4efcde4a"
# Arquivo gerado: "web_wan22_5b_i2v_4efcde4a_00001.mp4"
# → prefix NÃO está contido no filename!

# CORRETO (fix aplicado)
videos = [f for f in OUTPUT_DIR.glob("*.mp4") if job_id in f.name]
```
**Lição:** Usar `job_id` diretamente (sempre único), não construir prefix manualmente.

---

### 2.2 O Que Funciona Perfeitamente

#### ✅ ComfyUI + Python venv
**Stack:**
```
Python 3.12.3
PyTorch 2.10.0+cu130
ComfyUI (clone direto do GitHub)
Custom nodes via git clone
```
**Por quê funciona:**
- ComfyUI é wrapper universal para qualquer modelo de difusão
- Abstrai complexidade de quantização, sampling, VAE
- Custom nodes da comunidade cobrem 90% dos modelos

#### ✅ Wan 2.2 (5B e 14B MoE)
**Arquitetura:** Mixture of Experts — 2 modelos trabalhando juntos
- High Noise Expert (primeiros 15 steps)
- Low Noise Expert (últimos 15 steps)
**Por quê funciona:**
- Headers safetensors normais (<48 KB)
- FP8 scaled nativo (economiza VRAM)
- Melhor qualidade que 2.1

#### ✅ LTX-2 19B Distilled com FP4
**Modelo:** `ltx-2-19b-distilled.safetensors` (41 GB)
**Custom Node:** `ComfyUI-LTXVideo` (oficial)
**Áudio:** `LTX2_audio_vae_bf16.safetensors` (208 MB)
**Por quê funciona:**
- FP4 quantization nativa no GB10
- Único modelo que gera áudio sincronizado
- Distilled version = mesma qualidade, metade do tamanho

#### ✅ Interface Web com Fila de Jobs
**Versão atual:** v4.2 (porta 7862)
**Arquitetura:** FastAPI + threading.Queue + background worker
**Por quê funciona:**
- Um job por vez (evita OOM por modelos simultâneos)
- Cancelamento gracioso via set() compartilhado
- Refresh adaptativo (4s ativo, 20s idle) — DOM só muda se dados mudaram
- Galeria só recarrega quando novo vídeo completa

---

## 3. Arquitetura Escolhida e Por Quê

### 3.1 Decisões Arquiteturais

```
┌─────────────────────────────────────────────┐
│  Interface Web (FastAPI - porta 7862)      │
│  - Multi-modelo selector (3 modelos)       │
│  - Job queue (threading.Queue)             │
│  - Background worker (daemon thread)       │
└─────────────┬───────────────────────────────┘
              │ Subprocess calls
              ▼
┌─────────────────────────────────────────────┐
│  Scripts CLI Python (gerar_video_*.py)     │
│  - Wan 2.2 14B, 5B, LTX-2                  │
│  - T2V e I2V                                │
│  - Constroem workflow JSON dinamicamente    │
└─────────────┬───────────────────────────────┘
              │ HTTP POST /prompt
              ▼
┌─────────────────────────────────────────────┐
│  ComfyUI Server (porta 8188)               │
│  - Carrega modelos sob demanda              │
│  - Executa workflow de difusão              │
│  - Salva MP4 em output/                     │
└─────────────────────────────────────────────┘
```

### 3.2 Por Que Não Usar...

**Docker?**
- ARM64 complica tudo
- Overhead desnecessário (já temos venv)
- NVIDIA recomenda ComfyUI direto

**Gradio/Streamlit?**
- Menos controle sobre job queue
- FastAPI permite background processing melhor
- HTML/CSS customizado = UX superior

**API Direto (sem ComfyUI)?**
- Reinventar a roda (sampling, scheduling, VAE)
- ComfyUI já tem 1000+ nodes prontos
- Comunidade ativa atualiza custom nodes

---

## 4. Setup do Sistema Base

### 4.1 Preparação do Ambiente

```bash
# 1. Verificar GPU
nvidia-smi
# Deve mostrar: NVIDIA GB10, Driver 580.95+

# 2. Atualizar sistema (opcional mas recomendado)
sudo apt update && sudo apt upgrade -y

# 3. Instalar dependências base
sudo apt install -y \
  python3.12 \
  python3.12-venv \
  python3-pip \
  git \
  wget \
  curl \
  ffmpeg \
  build-essential

# 4. Verificar Python
python3 --version  # Deve ser 3.12.x

# 5. Criar diretório do projeto
mkdir -p /home/nmaldaner/projetos/VideosDGX
cd /home/nmaldaner/projetos/VideosDGX
```

### 4.2 Criar Ambiente Virtual

```bash
# IMPORTANTE: venv SEPARADO do sistema
python3 -m venv comfyui-env

# Ativar
source comfyui-env/bin/activate

# Verificar isolamento
which python3  # Deve mostrar /home/nmaldaner/.../comfyui-env/bin/python3

# Atualizar pip
pip install --upgrade pip setuptools wheel
```

---

## 5. Instalação do ComfyUI

### 5.1 Clone e Instalação Base

```bash
cd /home/nmaldaner/projetos/VideosDGX

# Clone do ComfyUI
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

# Instalar dependências
pip install -r requirements.txt

# ⚠️ IMPORTANTE: PyTorch específico para CUDA 13.0
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130

# Verificar instalação
python3 -c "import torch; print('CUDA:', torch.cuda.is_available(), '| GPU:', torch.cuda.get_device_name(0))"
# Output esperado: CUDA: True | GPU: NVIDIA GB10
```

### 5.2 Estrutura de Diretórios

```bash
ComfyUI/
├── models/
│   ├── checkpoints/     # LTX-2 checkpoint (41 GB)
│   ├── unet/            # Wan 2.2 models (42 GB total)
│   ├── vae/             # VAEs (2 GB)
│   ├── clip/            # Text encoders (9 GB)
│   └── text_encoders/   # UMT5-XXL (11 GB)
├── custom_nodes/        # Custom nodes (git clone aqui)
├── output/              # Vídeos gerados aparecem aqui
└── main.py              # Entry point
```

### 5.3 Iniciar ComfyUI (Teste)

```bash
# Dentro de ComfyUI/, com venv ativado
python main.py --listen 0.0.0.0

# Acesse: http://localhost:8188
# Deve abrir interface gráfica do ComfyUI
```

**Se der erro "no module named 'torch'":**
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu130
```

---

## 6. Modelos: O Que Funciona e O Que Não

### 6.1 LTX-2 19B — Setup Completo

#### Modelos Necessários

| Arquivo | Tamanho | Localização | HuggingFace Repo |
|---------|---------|-------------|------------------|
| `ltx-2-19b-distilled.safetensors` | 41 GB | `models/checkpoints/` | `Lightricks/LTX-Video` |
| `gemma_3_12B_it_fp8_e4m3fn.safetensors` | 6 GB | `models/clip/` | `city96/gemma-3-12B-it-GGUF` ou similar |
| `ltx-2-19b-dev-fp4_projections_only.safetensors` | 2.7 GB | `models/clip/` | `Lightricks/LTX-Video` |
| `LTX2_audio_vae_bf16.safetensors` | 208 MB | `models/vae/` | `Lightricks/LTX-Video` |

#### Download via wget (recomendado)

```bash
cd /home/nmaldaner/projetos/VideosDGX/ComfyUI/models

# Checkpoint
cd checkpoints/
wget https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltx-2-19b-distilled.safetensors

# Text encoder (FP8)
cd ../clip/
wget <URL_DO_GEMMA_FP8>

# Projections
wget https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltx-2-19b-dev-fp4_projections_only.safetensors

# Audio VAE
cd ../vae/
wget https://huggingface.co/Lightricks/LTX-Video/resolve/main/LTX2_audio_vae_bf16.safetensors
```

**Tempo estimado:** 2-4 horas (dependendo da internet)

#### Custom Node LTX-Video

```bash
cd /home/nmaldaner/projetos/VideosDGX/ComfyUI/custom_nodes
git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git

# Instalar dependências do node
cd ComfyUI-LTXVideo
pip install -r requirements.txt
```

**Verificação:**
- Reiniciar ComfyUI
- Interface deve mostrar nodes "LTXVideo..." no menu

---

### 6.2 Wan 2.2 — Setup Completo

#### Modelos Necessários

**Wan 2.2 5B (T2V + I2V):**
```bash
cd /home/nmaldaner/projetos/VideosDGX/ComfyUI/models/unet/
wget https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/wan2.2_ti2v_5B_fp16.safetensors
# Tamanho: 9.4 GB
```

**Wan 2.2 14B MoE (Dual-Expert T2V):**
```bash
cd /home/nmaldaner/projetos/VideosDGX/ComfyUI/models/unet/

# High Noise Expert
wget https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors

# Low Noise Expert
wget https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors

# Cada um: ~14 GB (total 28 GB)
```

**VAE (compartilhado entre 5B e 14B):**
```bash
cd /home/nmaldaner/projetos/VideosDGX/ComfyUI/models/vae/
wget https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/wan2.2_vae.safetensors
# Tamanho: 1.4 GB
```

**Text Encoder (compartilhado):**
```bash
cd /home/nmaldaner/projetos/VideosDGX/ComfyUI/models/text_encoders/
wget https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/models_t5_umt5-xxl-enc-bf16.pth
# Tamanho: 11 GB
```

**⚠️ EVITAR:** `umt5_xxl_fp8_e4m3fn_scaled.safetensors` — header muito grande, não funciona.

#### Custom Node WanVideo

```bash
cd /home/nmaldaner/projetos/VideosDGX/ComfyUI/custom_nodes
git clone https://github.com/kijai/ComfyUI-WanVideoKsampler.git

cd ComfyUI-WanVideoKsampler
pip install -r requirements.txt
```

---

### 6.3 Resumo de Espaço em Disco

| Modelo | Arquivos | Espaço Total |
|--------|----------|--------------|
| LTX-2 19B | Checkpoint + text encoder + projections + audio VAE | ~50 GB |
| Wan 2.2 5B | UNet + VAE + text encoder (compartilhado) | ~22 GB |
| Wan 2.2 14B MoE | 2× UNet + VAE + text encoder (compartilhado) | ~54 GB |
| **Total mínimo (todos 3 modelos)** | — | **~110 GB** |

Com 1.7 TB livre, há espaço de sobra.

---

## 7. Custom Nodes e Dependências

### 7.1 Custom Nodes Essenciais

```bash
cd /home/nmaldaner/projetos/VideosDGX/ComfyUI/custom_nodes

# 1. LTX-Video (obrigatório para LTX-2)
git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git

# 2. Wan Video Ksampler (obrigatório para Wan 2.2)
git clone https://github.com/kijai/ComfyUI-WanVideoKsampler.git

# 3. Video Helper Suite (utilitários de vídeo)
git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git

# 4. ComfyUI Manager (recomendado — facilita instalação de nodes)
git clone https://github.com/ltdrdata/ComfyUI-Manager.git
```

### 7.2 Instalar Dependências de Cada Node

```bash
cd /home/nmaldaner/projetos/VideosDGX/ComfyUI/custom_nodes

# Para cada node que tenha requirements.txt:
for dir in */; do
  if [ -f "$dir/requirements.txt" ]; then
    echo "Instalando $dir..."
    cd "$dir"
    pip install -r requirements.txt
    cd ..
  fi
done
```

### 7.3 Bibliotecas Python Críticas (Versões Testadas)

```bash
# Já instaladas pelo requirements.txt do ComfyUI, mas confirmar:
pip install \
  torch==2.10.0 \
  torchvision==0.25.0 \
  torchaudio==2.10.0 \
  transformers==5.1.0 \
  diffusers==0.36.0 \
  safetensors==0.7.0 \
  accelerate \
  einops \
  pillow \
  opencv-python \
  imageio \
  imageio-ffmpeg \
  scipy \
  numpy
```

**⚠️ Versão do safetensors:** 0.7.0 tem limite de 48 KB para headers. Versões mais novas (0.8+) podem resolver, mas não testado.

---

## 8. Interface Web: Evolução e Decisões

### 8.1 Histórico de Versões

| Versão | Porta | Principais Mudanças |
|--------|-------|---------------------|
| v1 | 7860 | Protótipo básico, 1 modelo |
| v2 | 7860 | Multi-modelo (LTX-2 + Wan) |
| v3 | 7860 | UI redesenhada, progress bar |
| v4.0 | 7860 | Multi-modelo completo (3 modelos) |
| v4.1 | 7861 | **Image-to-Video (I2V)** para LTX-2 e Wan 5B |
| **v4.2** | **7862** | **Fila de jobs + cancelamento** |

### 8.2 v4.2 — Arquitetura Final

#### Por Que Threading + Queue (não asyncio)?

**Decisão:**
```python
job_queue = queue.Queue()  # Thread-safe FIFO queue

def queue_worker():
    while True:
        job_id = job_queue.get()  # Bloqueia até ter trabalho
        run_job(job_id, req)      # Executa sequencialmente
        job_queue.task_done()

# Iniciar worker thread (daemon)
threading.Thread(target=queue_worker, daemon=True).start()
```

**Por quê não asyncio?**
- `subprocess.run()` é **bloqueante** (não async-friendly)
- ComfyUI API não é assíncrona
- Threading + Queue = mais simples, zero race conditions

#### Cancelamento de Jobs

**Implementação:**
```python
cancelled_jobs = set()  # Thread-safe (GIL protege)

# No loop de run_job:
while time.time() - start < JOB_TIMEOUT:
    if job_id in cancelled_jobs:  # Verifica a cada 5s
        cancelled_jobs.discard(job_id)
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = "Cancelado pelo usuário"
        save_jobs()
        return
    # ... polling de vídeo
    time.sleep(5)
```

**Por quê funciona:**
- `set()` é thread-safe para add/discard
- Worker thread verifica a cada 5s (granularidade aceitável)
- Jobs na fila (`queued`) são pulados instantaneamente

#### Refresh Adaptativo (Fix de Piscar)

**Problema original:** DOM rebuilding a cada 3s → vídeos param, scroll pula

**Solução:**
```python
let _lastJobsFingerprint = '';

function jobsFingerprint(jobs) {
  return Object.entries(jobs).map(([id, j]) =>
    `${id}:${j.status}:${j.progress_pct || 0}`
  ).sort().join('|');
}

async function loadJobs() {
  const jobs = await fetch('/api/jobs').then(r => r.json());
  const fp = jobsFingerprint(jobs);

  if (fp === _lastJobsFingerprint && domExists) {
    return;  // Nada mudou → não toca no DOM
  }
  _lastJobsFingerprint = fp;
  // ... rebuild DOM apenas se mudou
}
```

**Resultado:** Zero flicker quando jobs estão estáveis (ex: processing sem mudança de progresso).

---

## 9. Problemas Comuns e Soluções

### 9.1 ComfyUI Não Inicia

**Sintoma:** `python main.py` trava ou erro de import

**Causa Provável:** PyTorch não instalado ou versão errada

**Solução:**
```bash
source comfyui-env/bin/activate
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130

# Verificar
python3 -c "import torch; print(torch.__version__, torch.cuda.is_available())"
# Esperado: 2.10.0+cu130 True
```

---

### 9.2 Modelo Não Aparece no Dropdown do ComfyUI

**Sintoma:** Modelo baixado, mas não aparece na lista de UNetLoader/CheckpointLoader

**Causa:** Arquivo na pasta errada ou nome incorreto

**Solução:**
```bash
# Verificar estrutura
ls -lh ComfyUI/models/checkpoints/  # LTX-2 checkpoint aqui
ls -lh ComfyUI/models/unet/         # Wan 2.2 unets aqui
ls -lh ComfyUI/models/vae/          # VAEs aqui
ls -lh ComfyUI/models/clip/         # Text encoders aqui

# Reiniciar ComfyUI (recarrega lista de modelos)
pkill -f "python main.py"
python main.py --listen 0.0.0.0
```

---

### 9.3 "Header Too Large" em Safetensors

**Sintoma:** `Error while deserializing header: header too large`

**Arquivos afetados:**
- `wan2.1_t2v_14B.safetensors` (65 GB)
- `umt5_xxl_fp8_e4m3fn_scaled.safetensors` (6.3 GB)

**Causa:** safetensors 0.7.0 tem limite de 48 KB para metadata header

**Solução (curto prazo):**
- Wan 2.1 → migrar para **Wan 2.2** (headers normais)
- UMT5 FP8 → usar versão **BF16 .pth** (funciona perfeitamente)

**Solução (longo prazo):**
```bash
pip install safetensors>=0.8.0  # Versões futuras podem suportar
```
⚠️ **Não testado ainda** — pode quebrar ComfyUI.

---

### 9.4 Job Travado em "Processing" (I2V)

**Sintoma:** Job fica em `processing` para sempre, vídeo já existe em `output/`

**Causa:** Bug no prefix de busca (já corrigido em v4.2)

**Como evitar:**
```python
# ✅ CORRETO (v4.2)
videos = [f for f in OUTPUT_DIR.glob("*.mp4") if job_id in f.name]

# ❌ ERRADO (v4.0, v4.1)
prefix = f"web_{req.model}_{job_id}"  # Falha em I2V
videos = [f for f in OUTPUT_DIR.glob("*.mp4") if prefix in f.name]
```

**Verificar se bug existe:**
```bash
# Se usar v4.1, aplicar patch:
cd /home/nmaldaner/projetos/VideosDGX
grep "prefix in f.name" web_interface_v4_1.py
# Se encontrar, substituir por "job_id in f.name"
```

---

### 9.5 Out of Memory (OOM) — GPU

**Sintoma:** ComfyUI crashou, `nvidia-smi` mostra VRAM cheia

**Causa:** Modelos muito grandes ou múltiplos jobs simultâneos

**Soluções:**

1. **Verificar fila de jobs:**
```bash
curl http://localhost:7862/api/jobs | python3 -m json.tool
# Deve ter apenas 1 "processing" por vez
```

2. **Limpar VRAM manualmente:**
```bash
# Reiniciar ComfyUI (libera tudo)
pkill -f "python main.py"
sleep 2
source comfyui-env/bin/activate
cd ComfyUI
python main.py --listen 0.0.0.0
```

3. **Reduzir resolução/frames:**
```python
# Na interface web, usar presets menores:
# 720P 2s (57 frames) → 480P 2s (33 frames)
```

4. **Evitar Wan 14B se VRAM crítica:**
- Wan 14B MoE: ~90 GB
- Wan 5B: ~25 GB
- LTX-2: ~45 GB

---

### 9.6 ComfyUI Lento (>10 min por vídeo)

**Causa provável:** GPU não está sendo usada (CPU fallback)

**Diagnóstico:**
```bash
# Durante geração:
watch -n 1 nvidia-smi

# Se "GPU-Util" ficar em 0-5%, GPU não está sendo usada
```

**Solução:**
```bash
# Verificar CUDA
python3 -c "import torch; print(torch.cuda.is_available())"
# Deve ser True

# Se False:
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
```

---

## 10. Otimizações de Performance

### 10.1 Otimizações Já Aplicadas

**Interface Web:**
- ✅ Refresh adaptativo (4s ativo, 20s idle)
- ✅ DOM só muda se dados mudaram (fingerprint)
- ✅ Galeria só recarrega quando novo vídeo completa
- ✅ Jobs processados sequencialmente (evita OOM)

**ComfyUI:**
- ✅ Auto-restart após cada job (libera VRAM)
- ✅ FP8 quantization (Wan 14B: 14 GB vs. 28 GB em FP16)
- ✅ Modelos carregados sob demanda (lazy loading)

### 10.2 Possíveis Melhorias Futuras

**1. Model Caching Inteligente**
- Atualmente: cada job recarrega modelo
- Melhoria: manter modelo em VRAM se próximo job usa o mesmo
- Ganho: -30% tempo total (evita reload)

**2. Presets de Qualidade**
- Rápido: 480P 33f CFG 5.0 → ~1 min
- Balanced: 720P 57f CFG 6.0 → ~3 min
- Qualidade: 720P 121f CFG 7.0 → ~8 min

**3. Batch Processing (Wan 5B)**
- Gerar múltiplos vídeos em paralelo (se couber VRAM)
- Ex: 4× 480P ao invés de 1× 720P

---

## 11. Checklist de Validação

### 11.1 Após Setup Completo

```bash
# 1. ComfyUI responde
curl http://localhost:8188/system_stats
# Deve retornar JSON com info do sistema

# 2. Interface web responde
curl http://localhost:7862/
# Deve retornar HTML (código 200)

# 3. Modelos aparecem
# Acessar http://localhost:8188 (UI gráfica)
# Adicionar node "UNETLoader" → dropdown deve mostrar:
# - wan2.2_ti2v_5B_fp16.safetensors
# - wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors
# - wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors

# Adicionar node "CheckpointLoaderSimple" → deve mostrar:
# - ltx-2-19b-distilled.safetensors

# 4. GPU ativa
nvidia-smi
# Deve mostrar NVIDIA GB10, 0% utilização (idle)

# 5. VRAM livre
nvidia-smi --query-gpu=memory.free --format=csv,noheader
# Deve mostrar ~120000 MB livre

# 6. Disco com espaço
df -h /home/nmaldaner/projetos/VideosDGX
# Deve mostrar >500 GB livre
```

### 11.2 Teste de Geração (Wan 5B — Mais Rápido)

```bash
cd /home/nmaldaner/projetos/VideosDGX
source comfyui-env/bin/activate

# Testar script CLI
python3 gerar_video_wan22_5b.py \
  "A cat walking on a beach at sunset" \
  --width 720 \
  --height 480 \
  --frames 33 \
  --output test_wan5b

# Deve levar ~2 minutos
# Verificar output:
ls -lh ComfyUI/output/test_wan5b_*.mp4
```

### 11.3 Teste da Interface Web

```bash
# 1. Acessar http://localhost:7862

# 2. Selecionar "Wan 2.2 5B" (rápido)

# 3. Preset "480P · 2s"

# 4. Prompt: "A simple test video"

# 5. Clicar "Gerar Vídeo"

# 6. Job deve aparecer com status "Gerando..." (~2 min)

# 7. Quando completar, vídeo aparece inline no card

# 8. Galeria deve mostrar o vídeo também
```

---

## 12. Arquivos de Referência

### 12.1 Documentação Gerada Durante Desenvolvimento

```
doc/
├── ANALISE_RISCO_SKYREELS_V3.md         # Análise de risco (SkyReels V3)
├── ANALISE_SKYREELS_V3.md               # Análise técnica completa
├── PLANO_WAN22_IMPLEMENTACAO.md         # Plano original Wan 2.2
├── RELATORIO_CONFIGURACAO_ATUAL.md      # Estado atual do sistema
├── WAN22_14B_LIMITES_FRAMES.md          # Limites técnicos Wan 14B
├── WAN22_SETUP_STATUS.md                # Status de setup Wan 2.2
└── GUIA_COMPLETO_DO_ZERO.md             # Este documento
```

### 12.2 Scripts Principais

```
/home/nmaldaner/projetos/VideosDGX/
├── gerar_video_ltx2.py                  # LTX-2 T2V CLI
├── gerar_video_ltx2_i2v.py              # LTX-2 I2V CLI
├── gerar_video_wan22_5b.py              # Wan 5B T2V CLI
├── gerar_video_wan22_5b_i2v.py          # Wan 5B I2V CLI
├── gerar_video_wan22_14b.py             # Wan 14B MoE T2V CLI
├── web_interface_v4_2.py                # Interface web (ATUAL)
├── iniciar_interface_web_v4_2.sh        # Startup script
└── reiniciar_comfyui.sh                 # ComfyUI restart helper
```

---

## 13. Comandos de Manutenção

### 13.1 Rotina Diária

```bash
# Verificar espaço em disco
df -h /

# Verificar processos ativos
ps aux | grep -E "python|comfyui" | grep -v grep

# Ver últimos vídeos gerados
ls -lth ComfyUI/output/*.mp4 | head -5

# Verificar jobs
curl -s http://localhost:7862/api/jobs | python3 -m json.tool | grep -E "job_id|status"
```

### 13.2 Limpeza de Espaço

```bash
# Remover vídeos antigos (>30 dias)
find ComfyUI/output/*.mp4 -mtime +30 -delete

# Remover modelos não usados (opcional)
# Wan 2.1 (não funciona):
rm ComfyUI/models/unet/wan2.1_t2v_14B.safetensors  # Libera 65 GB

# UMT5 FP16 duplicado:
rm ComfyUI/models/text_encoders/umt5_xxl_fp16.safetensors  # Libera 11 GB

# UMT5 FP8 quebrado:
rm ComfyUI/models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors.BROKEN  # Libera 6.3 GB
```

### 13.3 Backup Essencial

```bash
# Jobs database
cp /tmp/dgx_jobs_v4_2.json ~/backup/jobs_$(date +%Y%m%d).json

# Workflows personalizados
tar -czf ~/backup/workflows_$(date +%Y%m%d).tar.gz \
  /home/nmaldaner/projetos/VideosDGX/workflow_*.json

# Scripts CLI
tar -czf ~/backup/scripts_$(date +%Y%m%d).tar.gz \
  /home/nmaldaner/projetos/VideosDGX/gerar_video_*.py \
  /home/nmaldaner/projetos/VideosDGX/web_interface_v4_2.py
```

---

## 14. Troubleshooting Rápido

| Problema | Comando de Diagnóstico | Solução Rápida |
|----------|------------------------|----------------|
| ComfyUI não responde | `curl http://localhost:8188/` | `pkill -f main.py && python main.py` |
| Interface web down | `curl http://localhost:7862/` | `./iniciar_interface_web_v4_2.sh` |
| Job travado | `curl http://localhost:7862/api/jobs` | Cancelar via botão ✕ na interface |
| VRAM cheia | `nvidia-smi` | Reiniciar ComfyUI |
| Disco cheio | `df -h /` | Remover vídeos antigos ou modelos não usados |
| GPU não detectada | `nvidia-smi` | Verificar driver, reiniciar sistema |

---

## 15. Próximos Passos Sugeridos

Se reconstruindo do zero:

1. ✅ **Dia 1:** Setup base + ComfyUI + 1 modelo (Wan 5B — mais rápido)
2. ✅ **Dia 2:** Adicionar LTX-2 + Wan 14B
3. ✅ **Dia 3:** Interface web v4.2 + testes
4. ✅ **Dia 4:** Otimizações + documentação
5. 🔄 **Dia 5+:** SkyReels V3 (opcional — testes isolados)

---

**FIM DO GUIA**

**Criado por:** Claude Code (Sonnet 4.5)
**Baseado em:** 7 dias de desenvolvimento iterativo no DGX Spark 2026
**Última atualização:** 2026-02-22
