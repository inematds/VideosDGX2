# DGX Spark 2026 - Pesquisa sobre Geração de Vídeo e Imagem

**Data da Pesquisa:** 16 de Fevereiro de 2026
**Hardware Alvo:** NVIDIA DGX Spark com GB10 Grace Blackwell Superchip (128GB memória unificada, ~1 PFLOP FP4)

---

## Resumo Executivo

A pesquisa revelou que o DGX Spark é **otimizado principalmente para inferência de LLMs e fine-tuning**, com capacidades de geração de vídeo/imagem **secundárias mas viáveis**. O gargalo principal é que o GB10 usa memória LPDDR5x compartilhada (baixa largura de banda) ao invés de GDDR7 dedicada, tornando-o mais lento que GPUs dedicadas (RTX 5090) para geração criativa, mas excelente para modelos massivos devido aos 128GB unificados.

### Principais Descobertas

✅ **Modelos que FUNCIONAM bem:**
- **LTX-2** (19B parâmetros) - NVFP8 otimizado, áudio+vídeo, desempenho confirmado
- **FLUX.1/FLUX.2** - NVFP4 otimizado para imagens, 2.6s/imagem 1K
- **Wan 2.1/2.2** (14B) - NVFP4 disponível, 3.2x mais rápido em Blackwell vs Hopper
- **ComfyUI workflows** - Suporte oficial, 8x aceleração vs MacBook M4

⚠️ **Limitações Conhecidas:**
- Geração de vídeo é 2-3x **mais lenta** que RTX 5090 devido à largura de banda de memória
- Ecossistema ARM64 + CUDA 13 é **frágil** com dependências instáveis
- Alguns backends (FlashInfer throughput) têm problemas com SM12.1
- PyTorch/diffusers requerem versões específicas (PyTorch 2.9.1+cu130)

❌ **Sem Evidências de Suporte:**
- **MAGI-1** - Nenhuma menção de deployment em Blackwell/DGX Spark encontrada
- **Waver 1.0** - Nenhuma informação específica sobre DGX Spark/GB10

---

## 1. Modelos de Geração de Vídeo Confirmados

### 1.1 LTX-2 (Lightricks) ✅ RECOMENDADO

**Status:** Oficialmente suportado e otimizado para DGX Spark

**Especificações:**
- 19B parâmetros (14B vídeo + 5B áudio)
- Dual-stream diffusion transformer com atenção cruzada áudio-vídeo
- Pesos NVFP8-otimizados disponíveis

**Performance:**
- Ganhos substanciais de performance vs geração anterior
- Geração de vídeo+áudio unificada
- Aproveita bem os 128GB de memória unificada

**Documentação:**
- Mencionado no blog oficial da NVIDIA como modelo destacado
- Exemplo de deployment em Jetson Thor documentado (pipeline open-source)
- Disponível via ComfyUI

**Referências:**
- [NVIDIA Technical Blog - DGX Spark Optimizations](https://developer.nvidia.com/blog/new-software-and-model-optimizations-supercharge-nvidia-dgx-spark/)
- [LTX-2 Model Page](https://ltx.io/model/ltx-2)
- [Jetson Thor Deployment](https://forums.developer.nvidia.com/t/running-ltx-2-19b-on-a-jetson-thor-open-source-pipeline-with-full-memory-lifecycle-management/360141)

---

### 1.2 Wan 2.1 / 2.2 (14B) ✅ SUPORTADO

**Status:** Suportado com otimizações NVFP4 para Blackwell

**Especificações:**
- 14B parâmetros
- Arquitetura Mixture-of-Experts (MoE) no Wan 2.2
- Expert de alto ruído (estrutura) + expert de baixo ruído (texturas)

**Performance:**
- **3.2x mais rápido** em B200 vs runtime padrão
- **2.6x mais rápido** em H100 com Baseten inference stack
- 67% redução de custo em deployments dedicados de alto volume
- Com 24GB VRAM: 20s a 720p em 2 minutos (modelo destilado)

**Quantização:**
- NVFP4 disponível em Hugging Face (lightx2v/Wan-NVFP4)
- Mantém qualidade superior do Wan 2.1 com velocidade sem precedentes

**Referências:**
- [Wan 2.2 Optimization - Baseten](https://www.baseten.co/blog/wan-2-2-video-generation-in-less-than-60-seconds/)
- [Wan2GP GitHub (GPU Poor)](https://github.com/deepbeepmeep/Wan2GP)
- [Wan NVFP4 Weights](https://huggingface.co/lightx2v/Wan-NVFP4)

---

### 1.3 Hunyuan Video 1.5 ⚠️ FUNCIONA MAS LENTO

**Status:** Funciona mas com performance inferior vs GPUs dedicadas

**Performance Benchmarks:**
- RTX 5090: 1,310 segundos
- GB10: 3,606 segundos (2.75x mais lento)

**Conclusão:** Não recomendado para produção em DGX Spark

**Referência:**
- [ProxPC Performance Tests](https://www.proxpc.com/blogs/nvidia-dgx-spark-gb10-performance-test-vs-5090-llm-image-and-video-generation)

---

### 1.4 MAGI-1 ❌ SEM EVIDÊNCIAS

**Status:** Nenhuma documentação encontrada sobre deployment em Blackwell/DGX Spark

**Especificações do Modelo:**
- 24B parâmetros (versão maior)
- Geração autoregressive de vídeo por chunks
- Suporta contextos de até 4 milhões de tokens
- MagiAttention para contextos ultra-longos

**Problema:**
- Nenhuma menção de suporte NVFP4/FP8
- Sem playbooks ou tutoriais para DGX Spark
- Sem confirmação de compatibilidade com memória unificada

**Recomendação:** Requer pesquisa experimental antes de assumir viabilidade

**Referências:**
- [MAGI-1 arXiv Paper](https://arxiv.org/abs/2505.13211)
- [MAGI-1 GitHub](https://github.com/SandAI-org/MAGI-1)

---

### 1.5 Waver 1.0 (ByteDance) ❌ SEM EVIDÊNCIAS ESPECÍFICAS

**Status:** Nenhuma informação específica sobre DGX Spark encontrada

**Especificações:**
- Foundation model baseado em Rectified Flow Transformers
- Suporta batch processing com aceleração GPU enterprise
- Resoluções até 1080p
- Vídeos de 2-10 segundos

**Performance (genérica):**
- Superior a Kling 2.0 e Wan 2.1 em benchmarks internos da ByteDance
- Excelente em motion quality e prompt following

**Problema:** Sem métricas de batch processing quantitativas para Blackwell

**Referências:**
- [Waver Official Site](https://waver1.org/)
- [Waver GitHub](https://github.com/FoundationVision/Waver)

---

## 2. Geração de Imagens (Status Forte)

### 2.1 FLUX.1 / FLUX.2 ✅ ALTAMENTE OTIMIZADO

**Status:** Modelo principal com otimizações NVFP4 oficiais

**Performance:**
- 1K image a cada 2.6 segundos (FLUX.1 12B, FP4)
- Otimizações colaborativas NVIDIA + Black Forest Labs
- ~2x speedup via NVFP4 quantization
- ~2x speedup adicional via TeaCache

**Suporte:**
- TensorRT Model Optimizer para PTQ e QAT
- Hugging Face diffusers compatível
- ComfyUI workflows disponíveis

**Referências:**
- [FLUX.2 NVFP4 Scaling](https://developer.nvidia.com/blog/scaling-nvfp4-inference-for-flux-2-on-nvidia-blackwell-data-center-gpus/)
- [TensorRT FP4 Image Generation](https://developer.nvidia.com/blog/nvidia-tensorrt-unlocks-fp4-image-generation-for-nvidia-blackwell-geforce-rtx-50-series-gpus/)

### 2.2 Stable Diffusion ✅ SUPORTADO

**Status:** Suporte local via ComfyUI

**Referências:**
- Mencionado como workload suportado em múltiplas fontes
- Parte do ecossistema padrão de difusão

---

## 3. Frameworks e Bibliotecas

### 3.1 PyTorch ⚠️ VERSÃO ESPECÍFICA NECESSÁRIA

**Versão Recomendada:** PyTorch 2.9.1 + CUDA 13.0

**Status:**
- PyTorch 2.9.0 compilado com SM_121 + CUDA 13.0 disponível
- Wheels para aarch64 em pytorch.org/whl/cu130
- **Requisito crítico:** PyTorch 2.9.1+ para aproveitar NVFP4 (30% mais rápido)

**Desafios:**
- Compilação manual pode ser necessária
- ARM64 + CUDA 13 é combinação rara, pouca cobertura em CI/CD
- torchaudio teve incompatibilidades no container NGC PyTorch 25.12

**Solução para Vídeo:**
- Usar `torchvision_av` como backend de vídeo (funciona com pyAV em aarch64)

**Referências:**
- [PyTorch Forums - DGX Spark Support](https://discuss.pytorch.org/t/nvidia-dgx-spark-support/223677)
- [DGX Spark Setup Guide](https://github.com/natolambert/dgx-spark-setup)

---

### 3.2 Hugging Face Diffusers ⚠️ COMPATÍVEL COM RESSALVAS

**Status:** Funciona mas requer configuração cuidadosa

**Modelos Otimizados:**
- FLUX.1/FLUX.2 com NVFP4
- LTX-2 com NVFP8
- Suporte geral para diffusion transformers

**Técnicas de Otimização:**
- NVFP4 quantization via microscaling data formats
- TeaCache (~2x speedup)
- FP8 quantization do text encoder

**Desafios:**
- Deployment de modelos quantizados pode ser complexo
- Requer versões específicas para compatibilidade Blackwell

**Referências:**
- [FLUX.2 Diffusers Optimization](https://developer.nvidia.com/blog/scaling-nvfp4-inference-for-flux-2-on-nvidia-blackwell-data-center-gpus/)

---

### 3.3 ComfyUI ✅ RECOMENDADO

**Status:** Suporte oficial com playbook dedicado

**Recursos:**
- Interface visual para modelos generativos
- Workflow FLUX.1-dev + WAN 2.2 + upscalers testado
- RTX Video node para upscaling 4K

**Performance:**
- 40% otimização de performance em GPUs NVIDIA
- NVFP4: 3x mais rápido, 60% redução de VRAM
- NVFP8: 2x mais rápido, 40% redução de VRAM
- **8x aceleração** vs MacBook M4 Max (workflow completo em ~1min vs 8min)

**Limitações Conhecidas:**
- Memória limitada a 64GB em alguns workflows (issue reportado)
- Crashes possíveis, mas há soluções documentadas

**Referências:**
- [ComfyUI Official Blog](https://blog.comfy.org/p/comfyui-on-nvidia-dgx-spark)
- [NVIDIA DGX Spark Playbook - ComfyUI](https://build.nvidia.com/spark/comfy-ui)
- [Forum: Unlocking Power in ComfyUI](https://forums.developer.nvidia.com/t/unlocking-the-power-of-the-spark-in-comfyui-no-crashes/360336)

---

### 3.4 NVIDIA TensorRT ✅ ALTAMENTE RECOMENDADO

**Status:** Framework de otimização primário para Blackwell

**Capacidades:**
- FP4 (NVFP4) quantization nativa
- PTQ (Post-Training Quantization)
- QAT (Quantization-Aware Training)
- Model Optimizer unificado

**Aplicações:**
- Image generation (FLUX)
- Video generation (diffusion transformers)
- Otimização de 98% da latência (transformer backbone)

**Processo:**
1. Quantizar para FP4/FP8 com Model Optimizer
2. Converter para ONNX
3. Compilar TensorRT engine para GB10

**Referências:**
- [TensorRT Model Optimizer](https://github.com/NVIDIA/Model-Optimizer)
- [TensorRT Blackwell FP4](https://developer.nvidia.com/blog/nvidia-tensorrt-unlocks-fp4-image-generation-for-nvidia-blackwell-geforce-rtx-50-series-gpus/)
- [GTC 2025 Session](https://www.nvidia.com/en-us/on-demand/session/gtc25-S72609/)

---

### 3.5 vLLM ⚠️ ECOSSISTEMA FRÁGIL

**Status:** Suporte experimental, ainda sem releases estáveis

**Desafios:**
- Sem releases cu130 aarch64 estáveis
- Dependência de nightly wheels que podem desaparecer
- FlashInfer throughput backend tem problemas SM12.1
- Suporte SM121 (Blackwell) em tracking (Issue #31128)

**Soluções:**
- Usar latency backend do FlashInfer
- Reduzir GPU memory utilization para 0.75 ou menos
- Verificar CUDA graphs habilitados

**Referências:**
- [vLLM Issue #31128](https://github.com/vllm-project/vllm/issues/31128)
- [DGX Spark ML Guide](https://github.com/martimramos/dgx-spark-ml-guide)

---

### 3.6 Outros Frameworks Suportados

**JAX (Otimizado):**
- Playbook oficial disponível
- Arrays de alta performance

**NeMo (NVIDIA):**
- Fine-tuning e training
- Parte do ecossistema NVIDIA oficial

**Isaac Sim/Lab:**
- Simulação de robótica
- Aproveitamento de memória unificada

**Referência:**
- [DGX Spark Playbooks](https://github.com/NVIDIA/dgx-spark-playbooks)

---

## 4. Estratégias de Quantização

### 4.1 NVFP4 (4-bit Floating Point)

**O que é:**
- Formato de 4 bits exclusivo de Blackwell
- Mantém precisão próxima a FP8 (<1% degradação)
- Reduz memory bandwidth e storage

**Quando Usar:**
- LTX-2 full version (maior capacidade de contexto)
- MAGI-1 (se suportado - sequências longas de vídeo)
- FLUX modelos (máxima velocidade)
- Wan 2.1/2.2 (otimizações disponíveis)

**Performance:**
- Até 3x mais rápido que FP8
- 60% redução de VRAM
- ~1 PFLOP teórico no GB10

**Ferramentas:**
- TensorRT Model Optimizer (PTQ/QAT)
- Diffusers com suporte NVFP4
- ComfyUI com NVFP4 nodes

**Referências:**
- [NVFP4 Quantization Guide](https://build.nvidia.com/spark/nvfp4-quantization)
- [SatGeo NVFP4 Guide](https://satgeo.blog/2026/01/22/dgx-spark-quantization-guide-nvfp4-blackwell/)

---

### 4.2 FP8 (8-bit Floating Point)

**O que é:**
- Suporte nativo em Blackwell Tensor Cores
- Precisão mixed com FP16 para acumulação

**Quando Usar:**
- Wan 2.1 (máximo contexto sem compressão)
- Waver 1.0 (qualidade+performance balanceados)
- LTX-2 variantes menores

**Performance:**
- ~2x mais rápido que FP16
- 40% redução de VRAM
- Boa preservação de qualidade

**Referências:**
- [DGX Spark Performance Guide](https://developer.nvidia.com/blog/how-nvidia-dgx-sparks-performance-enables-intensive-ai-tasks/)

---

### 4.3 BF16/FP16 (Full Precision)

**Quando Usar:**
- Máxima qualidade necessária
- Debugging e baseline comparisons
- Modelos <70B parâmetros que cabem em 128GB

**Trade-off:**
- Usa 128GB unified memory como vantagem
- Sem compromise de qualidade
- Menor throughput vs quantizados

---

### 4.4 Problemas Conhecidos com Quantização

**Issue: FP4 Não Escala Como Esperado**

**Sintomas:**
- Speedup real menor que teórico
- Performance inconsistente

**Causas:**
- Memory bandwidth bottleneck (LPDDR5x vs GDDR7)
- Overhead de decompressão
- Kernel optimization ainda em desenvolvimento

**Soluções:**
- Usar FP8 para workloads memory-bound
- Aproveitar batch processing quando possível
- Aguardar updates de drivers e kernels

**Referências:**
- [NVIDIA Forums - FP4 Scaling Issues](https://forums.developer.nvidia.com/t/fp4-on-dgx-spark-why-it-doesnt-scale-like-youd-expect/360142)

---

## 5. Arquitetura de Memória Unificada (128GB)

### 5.1 Vantagens

**Eliminação de Bottlenecks:**
- Transferência CPU-GPU a 900 GB/s via NVLink-C2C
- Todo o pool de 128GB compartilhado instantaneamente
- Sem cópias de dados entre memórias separadas

**Casos de Uso Ideais:**
- Modelos até 200B parâmetros localmente
- Fine-tuning de modelos massivos
- Inference de LLMs com contexto longo
- Modelos multi-modal grandes (vídeo+áudio+texto)

**Referências:**
- [HPCwire - Unified Memory](https://www.hpcwire.com/2025/01/09/nvidias-little-desktop-ai-box-with-big-unified-gpu-cpu-memory/)

---

### 5.2 Limitações para Geração de Vídeo

**Problema: Largura de Banda**
- LPDDR5x: Menor bandwidth que GDDR7
- Geração criativa é memory-bandwidth intensive
- RTX 5090 é 2-3x mais rápido para vídeo

**Conclusão do Benchmarking:**
> "For pure media creation, the RTX 5090's raw CUDA performance is superior."

**Trade-offs:**
- GB10: Capacidade massiva (128GB) vs Velocidade
- RTX 5090: Velocidade vs Capacidade (24GB)

**Recomendação:**
- DGX Spark: Inference, fine-tuning, modelos massivos
- RTX 5090: Produção de vídeo em tempo real

**Referência:**
- [ProxPC Benchmarks](https://www.proxpc.com/blogs/nvidia-dgx-spark-gb10-performance-test-vs-5090-llm-image-and-video-generation)

---

## 6. Recursos Oficiais e Documentação

### 6.1 NVIDIA DGX Spark Playbooks ✅ ESSENCIAL

**URL:** https://github.com/NVIDIA/dgx-spark-playbooks

**Conteúdo:**
- 35+ playbooks passo-a-passo
- ComfyUI setup
- FLUX.1 Dreambooth LoRA fine-tuning
- Video Search and Summarization (VSS) Agent
- vLLM, TRT-LLM, SGLang para inference
- NeMo, PyTorch fine-tuning
- Multi-modal inference

**Valor:**
- Troubleshooting guidance
- Código de exemplo
- Best practices

---

### 6.2 DGX Spark User Guide

**URL:** https://docs.nvidia.com/dgx/dgx-spark/dgx-spark.pdf

**Última Atualização:** 12 de Fevereiro de 2026

**Conteúdo:**
- Hardware overview
- Deployment guide
- Libraries e frameworks
- Enterprise support

---

### 6.3 NVIDIA Build Platform

**URL:** https://build.nvidia.com/spark

**Recursos:**
- Playbooks interativos
- NVFP4 Quantization guides
- VSS Agent blueprints
- ComfyUI workflows

---

### 6.4 Community GitHub Repos

**Setup Guides:**
- [natolambert/dgx-spark-setup](https://github.com/natolambert/dgx-spark-setup) - ML training, CUDA 13, aarch64
- [martimramos/dgx-spark-ml-guide](https://github.com/martimramos/dgx-spark-ml-guide) - Soluções para problemas comuns

**Forks e Adaptações:**
- Várias versões de vLLM adaptadas para GB10
- Community playbooks

---

## 7. Histórias de Sucesso e Tutoriais

### 7.1 ComfyUI + DGX Spark Workflow (NVIDIA Official)

**Caso de Uso:**
- Geração de vídeo 4K de carro esportivo em cidade futurista
- FLUX.1-dev + WAN 2.2 + GPU upscalers

**Setup:**
- MacBook Pro M4 Max + DGX Spark via ComfyUI

**Resultados:**
- MacBook sozinho: ~8 minutos
- Com DGX Spark: ~1 minuto
- **8x de aceleração**

**Componentes:**
- RTX Video node para upscaling 4K
- Processamento pesado offloaded para DGX Spark

**Referência:**
- [NVIDIA RTX AI Garage](https://blogs.nvidia.com/blog/rtx-ai-garage-ces-2026-open-models-video-generation/)

---

### 7.2 LTX-2 em Jetson Thor (Similar Architecture)

**Relevância:**
- Jetson Thor também usa arquitetura Blackwell
- Pipeline open-source com gerenciamento completo de memória

**Aprendizados:**
- Lifecycle de memória crítico para modelos grandes
- Técnicas aplicáveis a DGX Spark

**Referência:**
- [NVIDIA Forums - LTX-2 Jetson Thor](https://forums.developer.nvidia.com/t/running-ltx-2-19b-on-a-jetson-thor-open-source-pipeline-with-full-memory-lifecycle-management/360141)

---

### 7.3 Fine-tuning com Unsloth

**Caso de Uso:**
- Fine-tuning eficiente de LLMs em RTX GPUs

**Aplicabilidade:**
- Técnicas transferíveis para DGX Spark
- Aproveitamento de memória unificada

**Referência:**
- [NVIDIA Blog - Unsloth](https://blogs.nvidia.com/blog/rtx-ai-garage-fine-tuning-unsloth-dgx-spark/)

---

## 8. Issues e Workarounds Conhecidos

### 8.1 ComfyUI Memory Limitation (64GB)

**Problema:**
- Alguns workflows limitados a 64GB ao invés de 128GB

**Status:**
- Reportado nos forums
- Soluções workaround disponíveis

**Referências:**
- [Forum Thread](https://forums.developer.nvidia.com/t/buyers-beware-dgx-spark-limited-to-64gb-in-comfyui/356573)
- [Solutions Thread](https://forums.developer.nvidia.com/t/unlocking-the-power-of-the-spark-in-comfyui-no-crashes/360336)

---

### 8.2 PyTorch ARM64 + CUDA 13 Ecosystem

**Problema:**
- Combinação rara com pouca cobertura de CI/CD
- Dependências podem quebrar

**Workarounds:**
- Usar containers NGC quando disponíveis
- Fixar versões específicas de dependências
- Compilação manual quando necessário

**Exemplo - torchaudio:**
- Incompatibilidade no NGC PyTorch 25.12
- Solução: usar torchvision_av backend

---

### 8.3 vLLM Instability

**Problema:**
- Sem releases estáveis cu130 aarch64
- Nightly wheels podem desaparecer

**Workarounds:**
- Cachear wheels localmente
- Usar versões fixas conhecidas
- Considerar TRT-LLM como alternativa

---

### 8.4 FlashInfer Backend Issues

**Problema:**
- Throughput backend com problemas em SM12.1

**Solução:**
- Usar latency backend
- Configurar explicitamente no código

---

## 9. Comparação: DGX Spark vs RTX 5090

### 9.1 Geração de Imagem

| Modelo | RTX 5090 | GB10 (DGX Spark) | Winner |
|--------|----------|------------------|--------|
| Qwen3 4B + Image 2 Turbo FP16 (Gen 1) | 6.1s | 10.8s | RTX 5090 |
| Qwen3 4B + Image 2 Turbo FP16 (Gen 2) | 1.69s | 6.17s | RTX 5090 |
| Flux Dev Mixed Precision | 50-56.6s | 237-129s | RTX 5090 |

### 9.2 Geração de Vídeo

| Modelo | RTX 5090 | GB10 (DGX Spark) | Diferença |
|--------|----------|------------------|-----------|
| Hunyuan Video 1.5 FP16 | 1,310s | 3,606s | 2.75x mais lento |

### 9.3 Conclusão

**RTX 5090 Vence em:**
- Velocidade pura de geração
- Media creation workflows
- Real-time rendering

**DGX Spark Vence em:**
- Capacidade de modelo (128GB vs 24GB)
- Modelos até 200B parâmetros
- Fine-tuning de modelos massivos
- Inference de LLMs longos
- Custo por token (inference)

**Referência:**
- [ProxPC Comprehensive Tests](https://www.proxpc.com/blogs/nvidia-dgx-spark-gb10-performance-test-vs-5090-llm-image-and-video-generation)

---

## 10. Recomendações para o Projeto VideosDGX

### 10.1 Modelos Priorizados (Ordem de Viabilidade)

1. **LTX-2 (NVFP8)** ✅
   - Suporte oficial confirmado
   - Pesos otimizados disponíveis
   - Vídeo + áudio unificado
   - Melhor escolha para produção

2. **FLUX.1/FLUX.2 (NVFP4)** ✅
   - Excelente para imagens
   - Pode ser componente de pipeline de vídeo
   - Performance muito boa

3. **Wan 2.1/2.2 (NVFP4)** ✅
   - Pesos NVFP4 disponíveis
   - Performance 3.2x melhor em Blackwell
   - Boa opção secundária

4. **Hunyuan Video** ⚠️
   - Funciona mas lento
   - Considerar apenas se qualidade específica necessária

5. **MAGI-1** ❌
   - Pesquisa experimental necessária
   - Sem garantia de funcionamento
   - Baixa prioridade

6. **Waver 1.0** ❌
   - Informação insuficiente
   - Testar apenas se tempo permitir

---

### 10.2 Stack Tecnológico Recomendado

**Framework Principal:**
```
ComfyUI
├── NVFP4/NVFP8 quantization
├── PyTorch 2.9.1 + CUDA 13
├── TensorRT backends
└── diffusers integration
```

**Alternativa (Programática):**
```
Python Application
├── PyTorch 2.9.1 + CUDA 13
├── Hugging Face diffusers
├── TensorRT Model Optimizer
└── Custom inference pipeline
```

**Bibliotecas Core:**
- PyTorch 2.9.1+cu130 (aarch64)
- torchvision com torchvision_av backend
- transformers (Hugging Face)
- diffusers com NVFP4 support
- TensorRT (via NGC containers)

---

### 10.3 Estratégia de Quantização por Modelo

| Modelo | Quantização | Justificativa |
|--------|-------------|---------------|
| LTX-2 Full | NVFP8 | Pesos oficiais, melhor balanço |
| LTX-2 Lite | FP16 | Se couber em memória, máxima qualidade |
| Wan 2.1/2.2 | NVFP4 | Pesos disponíveis, máxima velocidade |
| FLUX.1/2 | NVFP4 | Otimizações oficiais NVIDIA |

---

### 10.4 Próximos Passos (Prioridade)

1. **Setup Básico:**
   - [ ] Instalar PyTorch 2.9.1+cu130
   - [ ] Configurar ComfyUI via playbook oficial
   - [ ] Testar FLUX.1 como baseline

2. **Validação de Modelos:**
   - [ ] Download e teste de LTX-2 (NVFP8)
   - [ ] Benchmark de performance (tempo/frame)
   - [ ] Teste de qualidade visual

3. **Pipeline de Produção:**
   - [ ] Configurar workflow ComfyUI para LTX-2
   - [ ] Integração de upscaling (RTX Video node)
   - [ ] Automação de batch processing

4. **Otimização:**
   - [ ] Experimentar NVFP4 vs NVFP8
   - [ ] Tuning de memory utilization
   - [ ] Documentar parâmetros ótimos

5. **Exploração Avançada:**
   - [ ] Testar Wan 2.2 (se LTX-2 não atender)
   - [ ] Pesquisar MAGI-1 viability
   - [ ] Custom fine-tuning se necessário

---

### 10.5 Recursos de Referência Rápida

**Começar Aqui:**
1. [DGX Spark Playbooks](https://github.com/NVIDIA/dgx-spark-playbooks) - ComfyUI playbook
2. [NVFP4 Quantization Guide](https://build.nvidia.com/spark/nvfp4-quantization)
3. [LTX-2 Model Page](https://ltx.io/model/ltx-2)

**Troubleshooting:**
1. [NVIDIA DGX Spark Forums](https://forums.developer.nvidia.com/c/dgx-spark-gb10/)
2. [PyTorch Forums - DGX Spark](https://discuss.pytorch.org/t/nvidia-dgx-spark-support/223677)
3. [Community Setup Guide](https://github.com/natolambert/dgx-spark-setup)

**Performance Benchmarking:**
1. [ProxPC Tests](https://www.proxpc.com/blogs/nvidia-dgx-spark-gb10-performance-test-vs-5090-llm-image-and-video-generation)
2. [LMSYS Review](https://lmsys.org/blog/2025-10-13-nvidia-dgx-spark/)

---

## 11. Limitações e Considerações Importantes

### 11.1 Hardware

- **Bandwidth:** LPDDR5x < GDDR7 → geração de vídeo mais lenta que GPUs dedicadas
- **Cooling:** Workloads prolongados podem thermal throttle
- **Power:** ~350W max, considerar para batch processing

### 11.2 Software

- **Ecossistema ARM64:** Menos maduro que x86_64, algumas bibliotecas podem faltar
- **CUDA 13:** Novo, alguns bugs ainda sendo descobertos
- **Container Support:** Preferir NGC containers quando possível

### 11.3 Custos

- **DGX Spark:** ~$2,000 (preço aproximado)
- **Trade-off:** Investimento inicial maior, mas reduz custos de cloud a longo prazo
- **Amortização:** Viável para uso frequente (>100h/mês)

---

## 12. Conclusão

O **NVIDIA DGX Spark com GB10 é viável para geração de vídeo/imagem**, mas com ressalvas importantes:

**Pontos Fortes:**
- ✅ Excelente para modelos massivos (até 200B parâmetros)
- ✅ LTX-2 e FLUX têm otimizações oficiais NVFP4/NVFP8
- ✅ ComfyUI suportado oficialmente com workflows prontos
- ✅ 128GB unified memory é vantagem única
- ✅ Ecossistema de playbooks e documentação em crescimento

**Pontos Fracos:**
- ⚠️ 2-3x mais lento que RTX 5090 para geração pura
- ⚠️ Ecossistema ARM64+CUDA13 ainda frágil
- ⚠️ Alguns modelos (MAGI-1, Waver) sem suporte confirmado
- ⚠️ Requer conhecimento técnico para otimizar

**Veredicto Final:**
Para o projeto **VideosDGX**, o DGX Spark é uma escolha **sólida** se o foco for:
1. **Experimentação** com modelos grandes (LTX-2, Wan)
2. **Fine-tuning** e customização
3. **Inference local** com privacidade
4. **Batch processing** overnight

Se o objetivo for **produção em tempo real** ou **máxima velocidade**, uma RTX 5090 seria mais apropriada. Mas para desenvolvimento e deployment de pipelines inteligentes que aproveitam a capacidade massiva de memória, o DGX Spark é excelente.

**Recomendação:** Começar com **LTX-2 (NVFP8) via ComfyUI** como prova de conceito, seguindo o playbook oficial da NVIDIA.

---

## Fontes Consultadas

### Documentação Oficial NVIDIA
- [DGX Spark Product Page](https://www.nvidia.com/en-us/products/workstations/dgx-spark/)
- [New Software and Model Optimizations Supercharge NVIDIA DGX Spark](https://developer.nvidia.com/blog/new-software-and-model-optimizations-supercharge-nvidia-dgx-spark/)
- [How NVIDIA DGX Spark's Performance Enables Intensive AI Tasks](https://developer.nvidia.com/blog/how-nvidia-dgx-sparks-performance-enables-intensive-ai-tasks/)
- [DGX Spark Playbooks GitHub](https://github.com/NVIDIA/dgx-spark-playbooks)
- [NVFP4 Quantization](https://build.nvidia.com/spark/nvfp4-quantization)
- [Scaling NVFP4 Inference for FLUX.2](https://developer.nvidia.com/blog/scaling-nvfp4-inference-for-flux-2-on-nvidia-blackwell-data-center-gpus/)
- [TensorRT FP4 Image Generation](https://developer.nvidia.com/blog/nvidia-tensorrt-unlocks-fp4-image-generation-for-nvidia-blackwell-geforce-rtx-50-series-gpus/)
- [RTX AI Garage - CES 2026 Video Generation](https://blogs.nvidia.com/blog/rtx-ai-garage-ces-2026-open-models-video-generation/)
- [DGX Spark User Guide (PDF)](https://docs.nvidia.com/dgx/dgx-spark/dgx-spark.pdf)

### Reviews e Benchmarks
- [ProxPC Performance Tests](https://www.proxpc.com/blogs/nvidia-dgx-spark-gb10-performance-test-vs-5090-llm-image-and-video-generation)
- [ServeTheHome Review](https://www.servethehome.com/nvidia-dgx-spark-review-the-gb10-machine-is-so-freaking-cool/2/)
- [Tom's Hardware Review](https://www.tomshardware.com/pc-components/gpus/nvidia-dgx-spark-review)
- [LMSYS In-Depth Review](https://lmsys.org/blog/2025-10-13-nvidia-dgx-spark/)
- [IntuitionLabs Review](https://intuitionlabs.ai/articles/nvidia-dgx-spark-review)

### Modelos de Vídeo
- [LTX-2 Model Page](https://ltx.io/model/ltx-2)
- [Wan 2.2 Optimization - Baseten](https://www.baseten.co/blog/wan-2-2-video-generation-in-less-than-60-seconds/)
- [Wan2GP GitHub](https://github.com/deepbeepmeep/Wan2GP)
- [MAGI-1 arXiv Paper](https://arxiv.org/abs/2505.13211)
- [MAGI-1 GitHub](https://github.com/SandAI-org/MAGI-1)
- [Waver GitHub](https://github.com/FoundationVision/Waver)

### Community e Tutoriais
- [ComfyUI on DGX Spark Blog](https://blog.comfy.org/p/comfyui-on-nvidia-dgx-spark)
- [DGX Spark Setup Guide - natolambert](https://github.com/natolambert/dgx-spark-setup)
- [DGX Spark ML Guide - martimramos](https://github.com/martimramos/dgx-spark-ml-guide)
- [PyTorch Forums - DGX Spark Support](https://discuss.pytorch.org/t/nvidia-dgx-spark-support/223677)
- [NVIDIA Developer Forums - DGX Spark](https://forums.developer.nvidia.com/c/dgx-spark-gb10/)

### Arquitetura e Tecnologia
- [HPCwire - Unified GPU/CPU Memory](https://www.hpcwire.com/2025/01/09/nvidias-little-desktop-ai-box-with-big-unified-gpu-cpu-memory/)
- [VideoCardz - GB10 Details](https://videocardz.com/newz/nvidia-details-gb10-blackwell-superchip-successful-collaboration-between-nvidia-and-mediatek)
- [SatGeo NVFP4 Guide](https://satgeo.blog/2026/01/22/dgx-spark-quantization-guide-nvfp4-blackwell/)

### Frameworks
- [TensorRT Model Optimizer GitHub](https://github.com/NVIDIA/Model-Optimizer)
- [TransformerEngine GitHub](https://github.com/NVIDIA/TransformerEngine)
- [vLLM Issue #31128](https://github.com/vllm-project/vllm/issues/31128)

---

**Documento gerado em:** 16 de Fevereiro de 2026
**Última atualização das fontes:** Fevereiro 2026
**Próxima revisão recomendada:** Março 2026 (novos drivers e modelos)
