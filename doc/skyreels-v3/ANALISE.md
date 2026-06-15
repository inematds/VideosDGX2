# Análise Técnica: SkyReels V3
**Data:** 2026-02-22
**Repositório:** https://github.com/SkyworkAI/SkyReels-V3

---

## 1. Visão Geral

**SkyReels V3** é um framework de geração multimodal de vídeo desenvolvido pela SkyworkAI, lançado em 29/01/2026. Baseado em arquitetura de **Diffusion Transformer** com aprendizado multimodal in-context.

### Diferenciais

- **Três modos nativos unificados** em um único framework
- **Multi-reference consistency** — mantém identidade visual através de 1-4 imagens de referência
- **Transições cinematográficas** com 5 tipos de cortes profissionais
- **Talking avatars** com sincronização labial multi-idioma

---

## 2. Capacidades Principais

### 2.1 Reference-to-Video (R2V)
- **Input:** 1-4 imagens de referência + prompt de texto
- **Output:** Vídeo coerente mantendo identidade dos sujeitos/objetos
- **Modelo:** 14B parâmetros @ 720P
- **Duração:** 5-30 segundos
- **Use case:** Consistência de personagem em múltiplas cenas

**Vantagem vs modelos atuais:** Nenhum dos nossos modelos (LTX-2, Wan 2.2) tem suporte nativo a multi-reference. Todos são T2V ou I2V com 1 imagem apenas.

### 2.2 Video Extension (V2V)
- **Input:** Vídeo existente + prompt
- **Output:** Extensão do vídeo (5-30s adicionais)
- **Modelo:** 14B @ 720P
- **Modos:**
  - **Single-shot continuation:** Estende continuamente
  - **Shot-switching:** 5 tipos de transição (Cut-In, Cut-Out, Reverse Shot, Multi-Angle, Cut-Away)

**Vantagem vs modelos atuais:** Nossos modelos não fazem V2V nativo — seria necessário usar I2V no último frame.

### 2.3 Talking Avatar
- **Input:** 1 imagem de retrato + áudio (até 200s)
- **Output:** Avatar falando com sincronização labial
- **Modelo:** 19B @ 720P
- **Idiomas:** Múltiplos (não especificado quais)

**Vantagem vs modelos atuais:** LTX-2 gera áudio, mas não sincroniza labial com input de áudio externo.

---

## 3. Especificações Técnicas

| Aspecto | Valor |
|---------|-------|
| **Arquitetura** | Diffusion Transformer com multimodal in-context learning |
| **Variantes** | R2V: 14B · V2V: 14B · Talking: 19B |
| **Resolução** | 720P nativo (540P/480P para low-VRAM) |
| **FPS** | 24 fps fixo |
| **Aspect ratios** | 1:1, 3:4, 4:3, 16:9, 9:16 |
| **Quantização** | FP8 weight-only via `--low_vram` |
| **VRAM mínima** | 24 GB (12-16 GB com otimizações) |
| **Python** | 3.12+ |
| **CUDA** | 12.8+ |

---

## 4. Instalação e Uso

### 4.1 Instalação

```bash
git clone https://github.com/SkyworkAI/SkyReels-V3
cd SkyReels-V3
pip install -r requirements.txt
```

Modelos baixados automaticamente do Hugging Face ou ModelScope.

### 4.2 Exemplos de Uso

**Reference-to-Video:**
```bash
python3 generate_video.py \
  --task_type reference_to_video \
  --ref_imgs "img1.png,img2.png,img3.png" \
  --prompt "A warrior walking through a forest" \
  --duration 10 \
  --offload
```

**Video Extension (multi-GPU com xDiT):**
```bash
torchrun --nproc_per_node=4 generate_video.py \
  --task_type single_shot_extension \
  --input_video input.mp4 \
  --prompt "Continue the action sequence" \
  --duration 15 \
  --use_usp
```

**Talking Avatar:**
```bash
python3 generate_video.py \
  --task_type talking_avatar \
  --input_image portrait.jpg \
  --input_audio speech.mp3 \
  --prompt "Professional presenter"
```

---

## 5. Performance e Benchmarks

### Reference-to-Video (vs. competidores)

| Modelo | Reference Consistency | Visual Quality |
|--------|----------------------|----------------|
| **SkyReels V3** | **0.6698** | **0.8119** |
| Outros (não especificados) | — | — |

### Talking Avatar

| Métrica | Score |
|---------|-------|
| Audio-Visual Sync | 8.18/10 |
| Visual Quality | 4.60/5 |
| Character Consistency | 0.80 |

---

## 6. Comparação com Setup Atual (DGX Spark)

### Modelos Atuais vs SkyReels V3

| Recurso | LTX-2 19B | Wan 2.2 14B | Wan 2.2 5B | **SkyReels V3** |
|---------|-----------|-------------|------------|-----------------|
| **T2V** | ✅ | ✅ | ✅ | ✅ (via R2V com 0 refs) |
| **I2V (1 img)** | ✅ | ❌ | ✅ | ✅ |
| **Multi-ref (2-4 imgs)** | ❌ | ❌ | ❌ | ✅ |
| **V2V Extension** | ❌ | ❌ | ❌ | ✅ |
| **Talking Avatar** | ❌ | ❌ | ❌ | ✅ |
| **Geração de áudio** | ✅ | ❌ | ❌ | ❌ |
| **Transições cinematográficas** | ❌ | ❌ | ❌ | ✅ |
| **VRAM estimada** | ~45 GB | ~90 GB | ~25 GB | ~24 GB (14B), ~30 GB (19B) |
| **Resolução máxima** | 1024×576 | 1280×720 | 1280×720 | 1280×720 |
| **Duração máxima** | ~5s | ~5s | ~5s | **30s** (extensível) |

### Vantagens do SkyReels V3

✅ **Multi-reference consistency** — personagem coerente em múltiplas cenas
✅ **V2V nativo** — estende vídeos existentes (nossos modelos não fazem isso)
✅ **Talking Avatar** — sincronização labial com áudio externo
✅ **Vídeos mais longos** — até 30s por extensão (iterável)
✅ **Transições cinematográficas** — 5 tipos de cortes profissionais
✅ **Aspect ratios flexíveis** — 5 formatos nativos

### Desvantagens vs Setup Atual

❌ **Sem geração de áudio** — LTX-2 consegue gerar áudio do zero
❌ **Menos maduro** — lançado há 3 semanas (29/01/2026) vs. modelos estabelecidos
❌ **Single framework** — não integrado ao ComfyUI (inferência standalone)
❌ **Documentação limitada** — repositório novo, menos exemplos da comunidade

---

## 7. Viabilidade no DGX Spark

### Hardware Compatibility

| Aspecto | DGX Spark | SkyReels V3 Req | Status |
|---------|-----------|-----------------|--------|
| GPU | GB10 (Blackwell) | CUDA 12.8+ | ✅ OK |
| VRAM | 128 GB unificado | 24 GB (low: 12-16 GB) | ✅ OK |
| Python | 3.12.3 | 3.12+ | ✅ OK |
| CUDA | 13.0 | 12.8+ | ✅ OK |

### Estimativa de VRAM por Modelo

| Modelo SkyReels | Params | VRAM Estimada | DGX Cabe? |
|-----------------|--------|---------------|-----------|
| R2V 14B @ 720P | 14B | ~24 GB | ✅ Sim |
| V2V 14B @ 720P | 14B | ~24 GB | ✅ Sim |
| Talking 19B @ 720P | 19B | ~30 GB | ✅ Sim |
| **Com FP8 (`--low_vram`)** | — | ~12-16 GB | ✅✅ Sobra muito |

**Conclusão:** Todos os modelos cabem confortavelmente na GB10.

---

## 8. Integração com ComfyUI

### Status Atual

❌ **Não há custom node oficial do SkyReels V3 para ComfyUI** (até 22/02/2026)

### Opções de Integração

**Opção 1: Wrapper CLI**
- Chamar `generate_video.py` via subprocess (igual fazemos com Wan/LTX)
- Criar workflows JSON que mapeiam para flags CLI
- **Prós:** Rápido de implementar
- **Contras:** Não aparece na UI do ComfyUI, menos flexível

**Opção 2: Custom Node Próprio**
- Criar `ComfyUI-SkyReels` que importa os módulos do repo
- Expor os 3 task_types como nodes separados
- **Prós:** Integração nativa no ComfyUI
- **Contras:** Requer engenharia reversa da API interna

**Opção 3: Standalone Interface**
- Manter SkyReels separado do ComfyUI
- Adicionar à interface web v4.2 como 4º modelo
- **Prós:** Isolamento, independência
- **Contras:** Não se beneficia do ecossistema ComfyUI

---

## 9. Casos de Uso Únicos

### Use Cases que Apenas o SkyReels Faz

1. **Storytelling com personagem consistente**
   - 4 imagens de referência (frente, lado, costas, close)
   - Gerar 10 cenas diferentes com mesmo personagem
   - Impossível com LTX-2/Wan (cada I2V gera um "novo" personagem)

2. **Extensão de vídeos existentes**
   - Vídeo de 5s → estender para 30s
   - Manter continuidade de movimento e cena
   - Nossos modelos: teria que usar último frame em I2V (perda de motion context)

3. **Talking heads para narração**
   - 1 foto + arquivo de áudio (podcast, narração, etc.)
   - Avatar sincronizado automaticamente
   - LTX-2 gera áudio, mas não aceita áudio externo como input

4. **Edição com transições cinematográficas**
   - 5 tipos de cortes (Cut-In, Reverse Shot, etc.)
   - Produção semi-automatizada de vídeos multi-cena
   - Modelos atuais: T2V/I2V isolado, sem transições

---

## 10. Roadmap de Teste

### Fase 1: Setup Básico (1-2h)
1. Clonar repositório em `/home/nmaldaner/projetos/VideosDGX/SkyReels-V3`
2. Criar venv separado (Python 3.12)
3. Instalar dependências (`requirements.txt`)
4. Baixar modelos automáticos (Hugging Face)

### Fase 2: Testes de Funcionalidade (2-3h)
1. **Reference-to-Video:** Gerar vídeo com 2-3 imagens de referência
2. **Video Extension:** Estender um vídeo gerado pelo Wan 2.2
3. **Talking Avatar:** Testar sincronização labial (PT-BR)
4. Medir VRAM real, tempo de geração, qualidade

### Fase 3: Integração (4-6h)
1. Criar wrapper CLI para interface web v4.2
2. Adicionar SkyReels como 4º modelo no selector
3. UI específica para multi-reference (upload de 1-4 imagens)
4. UI para V2V (upload de vídeo + extensão)
5. UI para Talking Avatar (foto + áudio)

### Fase 4: Comparação e Decisão (1-2h)
1. Comparar qualidade: SkyReels R2V vs. Wan 2.2 5B I2V
2. Benchmark de performance (tempo/frame)
3. Avaliar casos de uso únicos vs. complexidade de manutenção
4. Decisão: manter standalone ou integrar totalmente?

---

## 11. Riscos e Considerações

### Riscos Técnicos

⚠️ **Modelo muito novo** (3 semanas) — bugs, API instável
⚠️ **Sem ComfyUI native** — integração manual necessária
⚠️ **Dependências conflitantes?** — PyTorch 2.10 vs. requerimentos do SkyReels
⚠️ **Multi-GPU xDiT** — pode não funcionar bem em single GB10

### Considerações Operacionais

⚠️ **Curva de aprendizado** — novo framework, nova API
⚠️ **Manutenção** — updates do repo podem quebrar integração
⚠️ **Documentação limitada** — menos exemplos que Wan/LTX

### Mitigações

✅ Testar em ambiente isolado (venv separado)
✅ Começar com wrapper CLI simples (baixo risco)
✅ Avaliar qualidade antes de integração profunda
✅ Manter modelos atuais como fallback

---

## 12. Recomendação

### Curto Prazo (Esta Semana)

✅ **FAZER:** Testes exploratórios standalone
- Clonar repo, instalar, rodar 3 task_types
- Avaliar qualidade real vs. claims do paper
- Medir VRAM, tempo de geração

❌ **NÃO FAZER:** Integração completa ainda
- Esperar estabilização do código (mais 2-4 semanas)
- Ver se comunidade cria ComfyUI node

### Médio Prazo (Próximas 2-4 Semanas)

✅ **Se testes forem positivos:**
- Adicionar à interface web v4.2 como opção experimental
- Wrapper CLI básico para 3 task_types
- Documentar limitações e casos de uso únicos

### Longo Prazo (1-2 Meses)

✅ **Se modelo provar valor:**
- Custom node ComfyUI completo
- Workflows de exemplo para multi-reference
- Tutoriais de V2V e Talking Avatar

---

## 13. Conclusão

**SkyReels V3 oferece capacidades únicas** que complementam (não substituem) o setup atual:

| Capacidade | Melhor Escolha |
|-----------|----------------|
| T2V genérico | Wan 2.2 14B (qualidade) ou 5B (velocidade) |
| I2V (1 imagem) | Wan 2.2 5B ou LTX-2 |
| **Multi-reference (2-4 imgs)** | **SkyReels V3 R2V** |
| **V2V Extension** | **SkyReels V3 V2V** |
| **Talking Avatar** | **SkyReels V3 Talking** |
| Geração de áudio | LTX-2 |
| Vídeos longos (>30s) | SkyReels V3 (iterável) |

**Veredito:** Vale a pena testar. Se qualidade for boa, adicionar como **4º modelo especializado** para casos de uso que os outros não cobrem.

---

**Próximo passo sugerido:** Clonar repo e rodar teste rápido de R2V com 2-3 imagens de referência, medir VRAM e qualidade visual.

---

**Referências:**
- Repo: https://github.com/SkyworkAI/SkyReels-V3
- Paper: arXiv:2601.17323
- HuggingFace: https://huggingface.co/spaces/SkyworkAI/SkyReels-V3
- ModelScope: (mencionado no README)
