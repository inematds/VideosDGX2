# Análise de Risco: Integração SkyReels V3
**Data:** 2026-02-22
**Sistema atual:** ComfyUI + LTX-2 + Wan 2.2 (5B e 14B) + Interface Web v4.2

---

## 1. Resumo de Riscos

| Nível de Risco | Categoria | Mitigação |
|----------------|-----------|-----------|
| 🟢 **BAIXO** | Instalação isolada (venv separado) | ✅ Zero impacto |
| 🟡 **MÉDIO** | Conflito de dependências (PyTorch) | ✅ Testável antes |
| 🟡 **MÉDIO** | Consumo de disco (modelos grandes) | ✅ 1.7 TB livre |
| 🟢 **BAIXO** | VRAM compartilhada (modelos simultâneos) | ✅ 128 GB suficiente |
| 🔴 **ALTO** | Integração profunda no ComfyUI | ❌ NÃO FAZER ainda |
| 🟢 **BAIXO** | Wrapper CLI standalone | ✅ Isolamento total |

**Conclusão:** Risco **BAIXO a MÉDIO** se feito corretamente (ambiente isolado, sem tocar no ComfyUI).

---

## 2. Riscos Técnicos Detalhados

### 2.1 Conflito de Dependências Python

#### Risco
- SkyReels V3 pode exigir versões específicas de PyTorch/CUDA diferentes do ComfyUI
- Sistema atual: **PyTorch 2.10.0+cu130** em `comfyui-env`
- SkyReels requer: **CUDA 12.8+** (temos 13.0 ✅) mas versão PyTorch não especificada

#### Probabilidade
🟡 **Média** — Repos novos frequentemente têm dependências rígidas

#### Impacto no Sistema Atual
- **Se instalar no mesmo venv (`comfyui-env`):** 🔴 ALTO — pode quebrar ComfyUI, Wan 2.2, LTX-2
- **Se instalar em venv separado:** 🟢 ZERO — isolamento completo

#### Mitigação
```bash
# ✅ CORRETO: venv isolado
cd /home/nmaldaner/projetos/VideosDGX
python3 -m venv skyreels-env
source skyreels-env/bin/activate
cd SkyReels-V3
pip install -r requirements.txt

# ❌ ERRADO: instalar no comfyui-env
source comfyui-env/bin/activate  # NÃO FAZER ISSO
pip install -r SkyReels-V3/requirements.txt  # RISCO ALTO
```

**Status:** ✅ **Mitigável** — venv separado elimina risco.

---

### 2.2 Consumo de Disco

#### Risco
Modelos SkyReels V3 são grandes:
- R2V 14B: ~28 GB (estimativa)
- V2V 14B: ~28 GB (pode compartilhar pesos com R2V?)
- Talking 19B: ~38 GB
- **Total estimado:** 60-94 GB

#### Estado Atual do Disco
```
/dev/nvme0n1p2  3.7T  1.8T  1.7T  52% /
Modelos atuais: 222 GB
```

#### Impacto
- **Pior caso:** 94 GB → disco ficaria em 1.89 TB / 3.7 TB (51% → 52%)
- **Ainda sobraria:** 1.6 TB

#### Probabilidade
🟢 **Baixa** — Muito espaço livre

#### Mitigação
- Baixar modelos sob demanda (não todos de uma vez)
- Remover duplicatas atuais (ex: `umt5_xxl_fp16.safetensors` 11 GB)
- Monitorar com `df -h` antes de cada download

**Status:** ✅ **Sem risco real** — temos 7.6× mais espaço que o necessário.

---

### 2.3 Conflito de VRAM (Modelos Simultâneos)

#### Risco
Se rodar SkyReels e Wan 2.2 14B ao mesmo tempo:
- Wan 2.2 14B MoE: ~90 GB VRAM
- SkyReels 14B: ~24 GB VRAM
- **Total:** 114 GB > 122 GB disponível (sobra 8 GB — apertado)

#### Probabilidade
🟡 **Média** — Se usuário submeter jobs de ambos os modelos simultaneamente

#### Impacto
- ComfyUI pode crashar por OOM
- Jobs podem falhar silenciosamente
- GPU pode ficar travada (requer reboot)

#### Mitigação Automática
A interface web v4.2 já processa **jobs sequencialmente** via `queue_worker`:
```python
def queue_worker():
    while True:
        job_id = job_queue.get()   # Um job por vez
        run_job(job_id, req)       # Bloqueia até terminar
        job_queue.task_done()
```

**Cenário:**
1. Job Wan 2.2 14B entra → carrega 90 GB VRAM
2. Job SkyReels entra na fila (`queued`)
3. Wan termina → libera 90 GB
4. SkyReels inicia → carrega 24 GB

✅ **Sem conflito** — fila serializa execução.

#### Risco Residual
Se usuário rodar **manualmente via CLI** enquanto interface está processando:
```bash
# Interface gerando Wan 2.2 14B (90 GB)
# Usuário roda no terminal ao mesmo tempo:
python3 SkyReels-V3/generate_video.py ...  # +24 GB = 114 GB → OOM
```

#### Mitigação Final
- **Documentar:** Não rodar SkyReels CLI durante jobs da interface
- **Ou:** Adicionar SkyReels à interface (uso gerenciado pela fila)

**Status:** 🟡 **Risco médio mitigável** — fila resolve se integrado; documentar se standalone.

---

### 2.4 Interferência com ComfyUI

#### Risco
SkyReels pode:
- Modificar arquivos do sistema ComfyUI
- Instalar custom nodes conflitantes
- Alterar configurações globais

#### Probabilidade
🟢 **Muito baixa** — SkyReels é standalone, não interage com ComfyUI

#### Estrutura de Diretórios Proposta
```
/home/nmaldaner/projetos/VideosDGX/
├── ComfyUI/                    # Intocado
│   ├── models/                 # Modelos atuais
│   └── custom_nodes/           # LTX, Wan
├── comfyui-env/                # Venv atual (intocado)
├── SkyReels-V3/                # Novo (separado)
│   ├── skyreels_v3/            # Código fonte
│   └── generate_video.py       # CLI
└── skyreels-env/               # Novo venv (isolado)
```

**Zero overlap.** SkyReels baixa modelos para cache do Hugging Face (`~/.cache/huggingface/`).

#### Impacto
🟢 **Nenhum** — se mantido separado.

**Status:** ✅ **Sem risco** — diretórios independentes.

---

### 2.5 Estabilidade de Código Novo

#### Risco
SkyReels V3 lançado há **3 semanas** (29/01/2026):
- Bugs não descobertos
- API pode mudar (breaking changes)
- Documentação incompleta
- Dependências podem ter versões hard-coded que conflitam

#### Probabilidade
🟡 **Média a alta** — Repos novos são instáveis

#### Impacto no Sistema Atual
- **Se standalone:** 🟢 Zero — crashes só afetam o SkyReels
- **Se integrado à interface web:** 🟡 Médio — pode travar a fila de jobs

#### Mitigação
1. **Fase de testes isolados** (1-2 semanas)
   - Rodar apenas via CLI standalone
   - Não integrar à interface ainda
   - Monitorar issues no GitHub

2. **Wrapper defensivo** (se integrar)
   ```python
   def run_skyreels_job(job_id, req):
       try:
           subprocess.run([...], timeout=600)
       except Exception as e:
           jobs[job_id]["status"] = "error"
           jobs[job_id]["error"] = f"SkyReels crash: {e}"
           # Sistema continua funcionando
   ```

3. **Fallback automático**
   - Se SkyReels falhar 3× seguidas → desabilitar temporariamente
   - Log de erros para debug

**Status:** 🟡 **Risco mitigável** — testes + wrapper defensivo.

---

## 3. Riscos Operacionais

### 3.1 Complexidade de Manutenção

#### Risco
Sistema atual: 3 modelos (LTX-2, Wan 5B, Wan 14B) + ComfyUI
Com SkyReels: +3 task types (R2V, V2V, Talking) + nova stack

**Aumento de complexidade:**
- +1 venv para gerenciar
- +1 repositório para atualizar
- +3 modelos diferentes (total 6 modelos)
- +1 API para aprender

#### Impacto
🟡 **Médio** — Mais pontos de falha, mais tempo de debug

#### Mitigação
- Documentar tudo em `doc/SKYREELS_SETUP.md`
- Scripts de inicialização padronizados
- Testes automatizados antes de updates

---

### 3.2 Curva de Aprendizado

#### Risco
SkyReels tem API diferente:
- Flags CLI específicas (`--task_type`, `--ref_imgs`, etc.)
- Parâmetros com nomes diferentes (vs. Wan/LTX)
- Comportamentos não documentados

#### Impacto
- Tempo para dominar: 4-8 horas
- Possibilidade de uso incorreto → vídeos ruins → frustração

#### Mitigação
- Criar `gerar_video_skyreels_r2v.py` wrapper simplificado
- Documentar parâmetros testados e validados
- Presets na interface web (igual Wan/LTX)

---

## 4. Riscos de Dados e Segurança

### 4.1 Download de Modelos de Fonte Externa

#### Risco
Modelos baixados do Hugging Face automaticamente:
- Possível malware em pesos (improvável, mas possível)
- Modelos corrompidos
- Download incompleto → crashes

#### Probabilidade
🟢 **Muito baixa** — Hugging Face é plataforma confiável, SkyworkAI é empresa legítima

#### Mitigação
- Verificar checksums se disponíveis
- Baixar manualmente primeiro (teste) antes de automático
- Monitorar logs de download

**Status:** ✅ **Risco desprezível**

---

### 4.2 Privacidade de Vídeos Gerados

#### Risco
SkyReels pode:
- Enviar telemetria para servidores externos?
- Fazer upload de vídeos/prompts?
- Coletar métricas de uso?

#### Análise
Código é **open-source** — possível auditar antes de rodar.

#### Mitigação
- Revisar `generate_video.py` para chamadas de rede
- Rodar com firewall bloqueando saída (exceto Hugging Face)
- Verificar issues no GitHub sobre privacidade

**Status:** 🟢 **Risco baixo** — código auditável.

---

## 5. Plano de Mitigação Completo

### Fase 1: Setup Seguro (Dia 1)
```bash
# ✅ Ambiente isolado
cd /home/nmaldaner/projetos/VideosDGX
python3 -m venv skyreels-env
source skyreels-env/bin/activate

# ✅ Clone em diretório separado
git clone https://github.com/SkyworkAI/SkyReels-V3
cd SkyReels-V3

# ✅ Revisar requirements.txt ANTES de instalar
cat requirements.txt
# Verificar conflitos com PyTorch 2.10

# ✅ Instalar dependências
pip install -r requirements.txt

# ✅ Verificar espaço em disco
df -h /home/nmaldaner/projetos/VideosDGX
```

### Fase 2: Teste Isolado (Dia 1-2)
```bash
# ✅ Rodar teste mínimo (baixa apenas 1 modelo)
python3 generate_video.py \
  --task_type reference_to_video \
  --ref_imgs "test1.jpg,test2.jpg" \
  --prompt "A simple test" \
  --duration 5

# ✅ Monitorar VRAM
watch -n 1 nvidia-smi

# ✅ Verificar output
ls -lh outputs/
```

### Fase 3: Validação (Dia 3-7)
- [ ] Testar 3 task_types (R2V, V2V, Talking)
- [ ] Medir VRAM real vs. estimado
- [ ] Avaliar qualidade visual
- [ ] Verificar tempo de geração
- [ ] Procurar crashes/bugs

### Fase 4: Decisão (Dia 7)
**SE testes positivos E sem crashes:**
- [ ] Criar wrapper CLI simples
- [ ] Adicionar à interface web v4.2 (experimental)
- [ ] Documentar limitações

**SE testes negativos OU muitos crashes:**
- [ ] Arquivar em `projetos/VideosDGX/archived/SkyReels-V3/`
- [ ] Esperar próxima versão (2-3 meses)
- [ ] Manter apenas modelos atuais

---

## 6. Checklist de Segurança

Antes de integrar SkyReels ao sistema:

### Pré-requisitos
- [ ] ✅ Venv separado criado
- [ ] ✅ Diretório separado do ComfyUI
- [ ] ✅ Espaço em disco verificado (>100 GB livre)
- [ ] ✅ Backup dos jobs atuais (`/tmp/dgx_jobs_v4_2.json`)

### Durante Testes
- [ ] ⚠️ ComfyUI continua rodando?
- [ ] ⚠️ Interface web v4.2 responde?
- [ ] ⚠️ VRAM não ultrapassa 120 GB?
- [ ] ⚠️ Disco não ultrapassa 70% uso?

### Pós-Integração
- [ ] 🔍 Monitorar logs por 48h
- [ ] 🔍 Verificar jobs não falharem mais que usual
- [ ] 🔍 Confirmar galeria mostra vídeos SkyReels
- [ ] 🔍 Testar cancelamento de jobs SkyReels

---

## 7. Rollback Plan

Se algo der errado:

### Rollback Rápido (5 minutos)
```bash
# 1. Matar processos SkyReels
pkill -f skyreels

# 2. Remover da interface web (se integrado)
# Editar web_interface_v4_2.py → comentar SkyReels

# 3. Reiniciar interface
kill $(lsof -t -i:7862)
source comfyui-env/bin/activate
nohup python3 web_interface_v4_2.py >> web_v4_2.log 2>&1 &

# Sistema volta ao estado anterior
```

### Rollback Completo (10 minutos)
```bash
# 1. Desativar venv
deactivate

# 2. Remover diretório
rm -rf /home/nmaldaner/projetos/VideosDGX/SkyReels-V3
rm -rf /home/nmaldaner/projetos/VideosDGX/skyreels-env

# 3. Liberar espaço dos modelos (se baixados)
rm -rf ~/.cache/huggingface/hub/models--SkyworkAI--*

# Sistema limpo, zero vestígios
```

---

## 8. Matriz de Decisão

| Cenário | Ação Recomendada |
|---------|------------------|
| ✅ Testes bem-sucedidos + qualidade boa | Integrar como modelo experimental |
| 🟡 Testes OK mas qualidade mediana | Manter standalone (sem integração) |
| 🟡 Bugs ocasionais mas recuperáveis | Wrapper defensivo + fallback |
| 🔴 Crashes frequentes | Arquivar, esperar versão estável |
| 🔴 Conflito de dependências grave | Não instalar (incompatível) |

---

## 9. Resumo Final

### Risco Geral: 🟡 **BAIXO-MÉDIO**

**Desde que:**
1. ✅ Instalação em venv separado
2. ✅ Diretório isolado do ComfyUI
3. ✅ Testes antes de integração
4. ✅ Wrapper defensivo se integrar
5. ✅ Monitoramento por 48h pós-deploy

### O Que PODE Quebrar

| Item | Probabilidade | Impacto | Recuperação |
|------|---------------|---------|-------------|
| ComfyUI parar de funcionar | 🟢 Muito baixa | 🔴 Alto | ✅ Fácil (venv separado) |
| Wan 2.2 / LTX-2 pararem | 🟢 Muito baixa | 🔴 Alto | ✅ Fácil (isolamento) |
| Interface web travar | 🟡 Média | 🟡 Médio | ✅ Fácil (restart) |
| Disco cheio | 🟢 Muito baixa | 🟡 Médio | ✅ Médio (remover modelos) |
| OOM crash | 🟡 Média | 🟡 Médio | ✅ Fácil (restart GPU) |

### O Que NÃO Pode Quebrar

✅ **ComfyUI** — totalmente isolado
✅ **Modelos atuais** — não são tocados
✅ **Jobs históricos** — arquivo separado
✅ **Vídeos gerados** — diretório de output compartilhado (só adiciona, não remove)

---

## 10. Recomendação Final

### ✅ SEGURO PROSSEGUIR **SE:**
1. Criar venv separado (`skyreels-env`)
2. NÃO instalar no `comfyui-env`
3. Testar standalone por 3-7 dias
4. Monitorar recursos (VRAM, disco)
5. Ter plano de rollback documentado

### ❌ NÃO PROSSEGUIR **SE:**
1. Usuário não tem tempo para testes (urgência)
2. Sistema atual está instável (resolver primeiro)
3. Espaço em disco <200 GB livre
4. Não há backup dos jobs atuais

---

**Conclusão:** O risco é **gerenciável e baixo** com as mitigações corretas. A arquitetura isolada (venv + diretório separado) garante que **mesmo no pior caso** (SkyReels quebrar completamente), o sistema atual **continua funcionando normalmente**.

**Próximo passo seguro:** Setup em ambiente isolado conforme Fase 1 do plano.
