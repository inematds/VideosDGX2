# Plano: Implementação do Wan 2.2 no DGX Spark

## Context

O usuário está atualmente configurando Wan 2.1 14B no DGX Spark 2026 e quer entender as diferenças com Wan 2.2 para decidir qual implementar. O Wan 2.1 está 99% pronto (aguardando download do T5 encoder safetensors). É necessário analisar Wan 2.2, comparar com 2.1, e criar um plano de implementação que não afete o LTX-2 já funcional.

**Hardware disponível:**
- DGX Spark 2026
- 128GB memória unificada (CPU+GPU)
- ~1 PFLOP FP4 (Blackwell GB10)
- Suporte nativo a FP4/FP8

**Estado atual:**
- ✅ LTX-2 19B funcionando 100%
- ✅ Wan 2.1 14B 100% pronto (T5 FP8 baixado)
- 🔍 Wan 2.2 em análise

---

## Wan 2.1 vs Wan 2.2: Comparação Técnica

### Arquitetura

| Aspecto | Wan 2.1 | Wan 2.2 |
|---------|---------|---------|
| **Arquitetura** | Diffusion Transformer denso | Mixture-of-Experts (MoE) |
| **Parâmetros** | 14B (todos ativos) | 27B total, 14B ativos por etapa |
| **Especialização** | Um modelo único | Dois experts: High Noise + Low Noise |
| **Workflow** | Single sampler | Dual sampler (2 modelos) |

### Modelos e Componentes

#### Wan 2.1
```
Componentes:
- wan2.1_t2v_14B.safetensors (65 GB) - modelo único
- umt5_xxl_fp8_e4m3fn_scaled.safetensors (6.74 GB) - text encoder
- wan_2.1_vae.pth (485 MB) - VAE

Total: ~72 GB
```

#### Wan 2.2 (14B MoE)
```
Componentes:
- wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors (~35 GB) - expert baixo ruído
- wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors (~35 GB) - expert alto ruído
- umt5_xxl_fp8_e4m3fn_scaled.safetensors (6.74 GB) - text encoder (MESMO do 2.1)
- wan2.2_vae.safetensors (~500 MB) - VAE novo com compressão 64x

Total: ~77 GB
```

#### Wan 2.2 (5B Denso)
```
Componentes:
- wan2.2_ti2v_5b.safetensors (~20 GB) - modelo híbrido T2V+I2V
- umt5_xxl_fp8_e4m3fn_scaled.safetensors (6.74 GB) - text encoder
- wan2.2_vae.safetensors (~500 MB) - VAE

Total: ~27 GB
```

### Recursos e Capacidades

| Recurso | Wan 2.1 | Wan 2.2 |
|---------|---------|---------|
| **Text-to-Video** | ✅ Sim | ✅ Sim (melhorado) |
| **Image-to-Video** | ⚠️ Limitado | ✅ Modelo dedicado (I2V-A14B) |
| **First-Last Frame** | ❌ Não | ✅ Sim (exclusivo) |
| **Audio-Driven** | ❌ Não | ✅ Sim (S2V-14B) |
| **Character Animation** | ❌ Não | ✅ Sim (Animate-14B) |
| **Geração de texto em cena** | ✅ Sim | ✅ Sim (melhorado) |
| **Controle cinematográfico** | ⚠️ Básico | ✅ Avançado (iluminação, cor, composição) |

### Performance e Qualidade

| Aspecto | Wan 2.1 | Wan 2.2 |
|---------|---------|---------|
| **Velocidade (14B)** | Baseline | 2x mais lento (2 modelos) |
| **Velocidade (5B)** | N/A | ~6 min/vídeo (RTX 4090) |
| **Qualidade visual** | Atmosférico, fluido | Nítido, estruturado, cinematográfico |
| **Aderência ao prompt** | Boa | Excelente |
| **Movimentos complexos** | Bom | Muito melhor (+83% dados de vídeo) |
| **Detalhes finos** | Bom | Superior em 720P |

### Hardware Requirements

| Configuração | Wan 2.1 14B | Wan 2.2 14B MoE | Wan 2.2 5B |
|--------------|-------------|-----------------|------------|
| **VRAM mínima** | 12 GB (FP8) | 24 GB (FP8) | 8 GB |
| **VRAM recomendada** | 16 GB | 24+ GB | 12 GB |
| **RAM mínima** | 32 GB | 64 GB | 32 GB |
| **Modelos em memória** | 1 | 2 (simultâneos) | 1 |
| **Tempo geração (480P)** | ~3 min | ~6 min | ~6 min |

**Para DGX Spark (128GB unificada):**
- ✅ Wan 2.1 14B: Confortável
- ✅ Wan 2.2 14B MoE: Confortável (memória sobra)
- ✅ Wan 2.2 5B: Muito confortável

### Ecossistema e Compatibilidade

| Aspecto | Wan 2.1 | Wan 2.2 |
|---------|---------|---------|
| **LoRAs disponíveis** | Ecossistema maduro | Poucos LoRAs nativos |
| **Compatibilidade LoRA 2.1** | N/A | ⚠️ Parcial (requer ajustes) |
| **VAE compartilhado** | N/A | ❌ VAEs diferentes |
| **Text encoder** | uMT5-XXL | ✅ MESMO (uMT5-XXL) |
| **Custom nodes** | Múltiplos | ComfyUI nativo + alguns |

### Trade-offs Críticos

#### **Escolha Wan 2.1 se:**
- ✅ Prioriza velocidade (2x mais rápido)
- ✅ Quer workflow simples (1 modelo)
- ✅ Planeja usar LoRAs do ecossistema 2.1
- ✅ Prefere atmosfera fluida a estrutura rígida
- ✅ Hardware mais limitado

#### **Escolha Wan 2.2 se:**
- ✅ Prioriza qualidade cinematográfica máxima
- ✅ Precisa de recursos exclusivos (I2V, First-Last Frame, Audio-Driven)
- ✅ Tem hardware robusto (DGX Spark qualifica!)
- ✅ Quer melhor aderência ao prompt
- ✅ Não depende de LoRAs existentes

---

## Estratégia Recomendada para DGX Spark

### Opção 1: Implementar Ambos Wan 2.1 + Wan 2.2 (RECOMENDADO)

**Justificativa:**
- Memória unificada 128GB suporta ambos confortavelmente
- Uso intercalado: carregar apenas o necessário
- Flexibilidade máxima para diferentes casos de uso
- Text encoder compartilhado (economia de espaço/tempo)

**Estrutura de arquivos:**
```
ComfyUI/models/
├── unet/
│   ├── wan2.1_t2v_14B.safetensors (65 GB)                    ← 2.1
│   ├── wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors (35 GB)  ← 2.2
│   ├── wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors (35 GB) ← 2.2
│   └── wan2.2_ti2v_5b.safetensors (20 GB)                    ← 2.2 (5B)
├── text_encoders/
│   └── umt5_xxl_fp8_e4m3fn_scaled.safetensors (6.74 GB)      ← COMPARTILHADO
├── vae/
│   ├── wan_2.1_vae.pth (485 MB)                              ← 2.1
│   └── wan2.2_vae.safetensors (500 MB)                       ← 2.2
```

**Espaço total:** ~162 GB de modelos Wan (2.1 + 2.2 14B + 2.2 5B)

**Scripts dedicados:**
- `gerar_video_wan21.py` (já existe)
- `gerar_video_wan22_14b.py` (criar)
- `gerar_video_wan22_5b.py` (criar)

### Opção 2: Apenas Wan 2.2 14B MoE

**Justificativa:**
- Máxima qualidade cinematográfica
- Recursos mais avançados
- Ainda viável no DGX Spark

**Espaço:** ~77 GB

### Opção 3: Apenas Wan 2.2 5B

**Justificativa:**
- Mais leve e rápido
- Híbrido T2V+I2V em um modelo
- Menor footprint

**Espaço:** ~27 GB

---

## Plano de Implementação: Wan 2.2 (Dual Track)

### Fase 1: Completar Wan 2.1 ✅ COMPLETO

**Status:** 100% completo
- ✅ T5 FP8 safetensors baixado (6.2GB)
- ✅ Modelo principal wan2.1_t2v_14B.safetensors (65GB)
- ✅ VAE Wan2.1_VAE.pth (485MB)
- ✅ LTX-2 não afetado
- 🔄 Pronto para testes

### Fase 2: Implementar Wan 2.2 5B (Primeiro)

**Por quê começar com 5B:**
- Modelo menor = download mais rápido
- Testar arquitetura 2.2 sem overhead dual-model
- Validar VAE novo
- Verificar compatibilidade com hardware

**Passos:**

#### 2.1. Download do Modelo 5B
```bash
cd /home/nmaldaner/projetos/VideosDGX/ComfyUI/models/unet/
huggingface-cli download Wan-AI/Wan2.2-TI2V-5B \
  --include "*.safetensors" \
  --local-dir-use-symlinks False \
  --local-dir ./wan22_5b_temp

# Mover arquivo principal
mv wan22_5b_temp/*.safetensors wan2.2_ti2v_5b.safetensors
```

#### 2.2. Download do VAE 2.2
```bash
cd /home/nmaldaner/projetos/VideosDGX/ComfyUI/models/vae/
wget https://huggingface.co/wangkanai/wan22-vae/resolve/main/wan2.2_vae.safetensors
```

#### 2.3. Criar Workflow 5B
- Arquivo: `workflow_wan22_5b_t2v.json`
- Baseado em template oficial ComfyUI
- Single sampler (mais simples que 14B MoE)

#### 2.4. Criar Script CLI
- Arquivo: `gerar_video_wan22_5b.py`
- Similar ao wan21.py mas usando workflow 5B

#### 2.5. Testar
```bash
./gerar_video_wan22_5b.py "a cat walking on a beach at sunset"
```

### Fase 3: Implementar Wan 2.2 14B MoE (Segundo)

**Apenas se Fase 2 for bem-sucedida**

#### 3.1. Download dos Dual Models
```bash
cd /home/nmaldaner/projetos/VideosDGX/ComfyUI/models/unet/

# Low Noise Expert
huggingface-cli download Wan-AI/Wan2.2-T2V-A14B \
  --include "*low_noise*fp8*.safetensors" \
  --local-dir-use-symlinks False

# High Noise Expert
huggingface-cli download Wan-AI/Wan2.2-T2V-A14B \
  --include "*high_noise*fp8*.safetensors" \
  --local-dir-use-symlinks False
```

#### 3.2. Criar Workflow Dual-Model
- Arquivo: `workflow_wan22_14b_t2v.json`
- Requer dois samplers: high noise → low noise
- Baseado em template oficial

#### 3.3. Criar Script CLI
- Arquivo: `gerar_video_wan22_14b.py`
- Mais complexo: gerencia dois modelos

#### 3.4. Testar
```bash
./gerar_video_wan22_14b.py "a cat walking on a beach at sunset"
```

### Fase 4: Adicionar à Interface Web

#### 4.1. Expandir web_interface_v3.py
- Adicionar dropdown de seleção de modelo:
  - LTX-2 19B
  - Wan 2.1 14B
  - Wan 2.2 5B
  - Wan 2.2 14B MoE
- Ajustar parâmetros UI baseado no modelo selecionado

#### 4.2. Gerenciamento de Recursos
- Apenas um modelo Wan carregado por vez
- Auto-restart entre trocas de modelo (mesma estratégia LTX-2)

### Fase 5: Recursos Avançados (Opcional)

Se houver interesse, implementar:

#### 5.1. Image-to-Video (I2V)
- Download: Wan2.2-I2V-A14B
- Workflow dedicado
- Script CLI separado

#### 5.2. First-Last Frame
- Usa modelo 5B
- Workflow específico
- Upload de duas imagens

#### 5.3. Audio-Driven (S2V)
- Download: Wan2.2-S2V-14B
- Workflow com input de áudio
- Processamento de lip-sync

---

## Arquivos a Criar

### Scripts Python
1. `gerar_video_wan22_5b.py` - CLI para Wan 2.2 5B
2. `gerar_video_wan22_14b.py` - CLI para Wan 2.2 14B MoE
3. `gerar_video_wan22_i2v.py` - CLI para Image-to-Video (opcional)

### Workflows JSON
1. `workflow_wan22_5b_t2v.json` - Text-to-Video 5B
2. `workflow_wan22_14b_t2v.json` - Text-to-Video 14B dual-model
3. `workflow_wan22_i2v.json` - Image-to-Video (opcional)
4. `workflow_wan22_first_last.json` - First-Last Frame (opcional)

### Documentação
1. `WAN22_INFO.md` - Especificações e comparação com 2.1
2. `WAN22_GUIA_USO.md` - Como usar os diferentes modelos
3. Atualizar `SETUP_COMPLETO_LTX2_DGX_SPARK.md` para incluir Wan 2.2

### Interface Web (Opcional)
- Expandir `web_interface_v3.py` ou criar `web_interface_v4.py`

---

## Comparação de Casos de Uso

### Quando Usar Cada Modelo

#### LTX-2 19B
- ✅ **Vídeo + Áudio** (único que gera áudio)
- ✅ Vídeos curtos a médios (até ~10s)
- ✅ Qualidade balanceada

#### Wan 2.1 14B
- ✅ **Velocidade** (2x mais rápido que 2.2 14B)
- ✅ **Ecossistema LoRA** (se usar LoRAs no futuro)
- ✅ Atmosfera fluida, orgânica
- ✅ Workflow simples

#### Wan 2.2 5B
- ✅ **Híbrido T2V + I2V** em um modelo
- ✅ **Leve e rápido** (~6 min, ~20GB)
- ✅ First-Last Frame
- ✅ Bom para experimentação rápida

#### Wan 2.2 14B MoE
- ✅ **Máxima qualidade cinematográfica**
- ✅ **Melhor aderência ao prompt**
- ✅ **Controle estético avançado**
- ✅ Movimentos complexos superiores
- ⚠️ 2x mais lento que 2.1
- ⚠️ Workflow mais complexo

---

## Riscos e Mitigações

### Risco 1: Compatibilidade ComfyUI
- **Descrição:** Wan 2.2 pode ter problemas com versão atual do ComfyUI
- **Mitigação:**
  - Testar primeiro com 5B (mais simples)
  - Atualizar ComfyUI antes de começar
  - Verificar custom nodes necessários

### Risco 2: Consumo de RAM Excessivo
- **Descrição:** Relatórios de 100GB+ RAM para I2V 2.2
- **Mitigação:**
  - DGX Spark tem 128GB (suficiente)
  - Começar com resoluções menores
  - Usar tiled VAE decode se necessário

### Risco 3: Qualidade do Modelo 5B
- **Descrição:** Comunidade reporta qualidade inferior, deformações
- **Mitigação:**
  - Testar com expectativas realistas
  - Se insatisfatório, pular para 14B MoE
  - 5B serve como validação de setup, não modelo final

### Risco 4: Workflow Dual-Model Complexo
- **Descrição:** Dois samplers podem ser difíceis de configurar
- **Mitigação:**
  - Usar templates oficiais ComfyUI
  - Documentar detalhadamente
  - Criar scripts CLI que abstraem complexidade

### Risco 5: Não Afetar LTX-2
- **Descrição:** Mudanças podem quebrar LTX-2 funcionando
- **Mitigação:**
  - ✅ Novos arquivos em unet/ não afetam checkpoints/
  - ✅ VAE 2.2 separado do LTX-2
  - ✅ Text encoder compartilhado (já usado por ambos)
  - ✅ Custom nodes são aditivos
  - ✅ Testar LTX-2 após cada fase

---

## Cronograma Estimado

### Fase 1: Completar Wan 2.1 ✅ COMPLETO
- **Status:** 100% pronto para testes

### Fase 2: Wan 2.2 5B
- **Download:** ~20 GB → ~30 minutos
- **Configuração:** ~1 hora (workflow + script + teste)
- **Total:** ~1.5 horas

### Fase 3: Wan 2.2 14B MoE
- **Download:** ~70 GB (dois modelos) → ~1 hora
- **Configuração:** ~1.5 horas (workflow dual-model + script + teste)
- **Total:** ~2.5 horas

### Fase 4: Interface Web
- **Desenvolvimento:** ~2 horas
- **Teste:** ~30 minutos
- **Total:** ~2.5 horas

### Fase 5: Recursos Avançados (Opcional)
- **Por recurso:** ~1-2 horas cada

**Total Mínimo (Fases 2-3):** ~4 horas
**Total Completo (Fases 2-4):** ~6.5 horas

---

## Recomendação Final

### Para DGX Spark: **Opção 1 (Implementar Ambos)**

**Justificativa:**
1. **Memória unificada 128GB** suporta todos os modelos confortavelmente
2. **Flexibilidade máxima**: Cada modelo tem seus pontos fortes
3. **Text encoder compartilhado**: Economia significativa
4. **Casos de uso diferentes**: LTX-2 (áudio), Wan 2.1 (velocidade + LoRAs), Wan 2.2 (qualidade cinematográfica)
5. **DGX Spark é hardware premium**: Aproveitar ao máximo

### Ordem de Implementação:
1. ✅ Completar Wan 2.1 (100% pronto)
2. 🔄 Testar Wan 2.2 5B (validar setup)
3. 🔄 Implementar Wan 2.2 14B MoE (qualidade máxima)
4. ⚠️ Interface web unificada (opcional mas recomendado)
5. ⚠️ Recursos avançados I2V/First-Last/Audio (conforme necessidade)

### Resultado Final:
```
DGX Spark com 3+ modelos funcionais:
- LTX-2 19B: Vídeo + Áudio
- Wan 2.1 14B: Velocidade + Ecossistema
- Wan 2.2 5B: Leveza + Híbrido T2V+I2V
- Wan 2.2 14B MoE: Qualidade Cinematográfica Máxima

Total: ~250 GB modelos (128GB memória unificada OK)
Interface Web: Seleção de modelo dropdown
Scripts CLI: Todos os modelos acessíveis
```

---

## Verificação End-to-End

### Teste Wan 2.1 (Atual)
```bash
./gerar_video_wan21.py "test prompt"
ls -lh ComfyUI/output/wan21_*.mp4
```

### Teste Wan 2.2 5B
```bash
./gerar_video_wan22_5b.py "test prompt"
ls -lh ComfyUI/output/wan22_5b_*.mp4
```

### Teste Wan 2.2 14B MoE
```bash
./gerar_video_wan22_14b.py "test prompt"
ls -lh ComfyUI/output/wan22_14b_*.mp4
```

### Verificação LTX-2 (Não Afetado)
```bash
./gerar_video_ltx2.py "test prompt" --frames 49
ls -lh ComfyUI/output/ltx2_*.mp4
```

### Teste Interface Web
```bash
./iniciar_interface_web_v3.sh
# Acessar http://localhost:7860
# Testar cada modelo via dropdown
```

---

## Arquivos Críticos (Não Modificar)

**Garantir integridade:**
- ✅ `ComfyUI/models/checkpoints/ltx-2-19b-distilled.safetensors`
- ✅ `ComfyUI/models/text_encoders/gemma-3-12b-it-qat-q4_0-unquantized/`
- ✅ `ComfyUI/models/vae/LTX2_audio_vae_bf16.safetensors`
- ✅ `ComfyUI/custom_nodes/ComfyUI-LTXVideo/`
- ✅ `gerar_video_ltx2.py`
- ✅ `reiniciar_comfyui.sh`
- ✅ `web_interface_v3.py`

---

## Status de Implementação

**Data:** 2026-02-16
**Última atualização:** Fase 1 completa, iniciando Fase 2

| Fase | Status | Notas |
|------|--------|-------|
| Fase 1: Wan 2.1 | ✅ COMPLETO | T5 FP8, modelo 14B, VAE todos baixados |
| Fase 2: Wan 2.2 5B | 🔄 EM PROGRESSO | Iniciando downloads |
| Fase 3: Wan 2.2 14B MoE | ⏸️ AGUARDANDO | Depende de Fase 2 |
| Fase 4: Interface Web | ⏸️ AGUARDANDO | Após validação dos modelos |
| Fase 5: Recursos Avançados | ⏸️ OPCIONAL | Conforme demanda |
