# Wan 2.2 14B MoE — Limites de Frames e Duração

## Resumo

O Wan 2.2 T2V A14B foi treinado para gerar vídeos de **5 segundos a 16 FPS = 81 frames**.
Ultrapassar 81 frames produz artefatos documentados pela comunidade.
No DGX Spark (128GB), o limite **não é VRAM** — é a distribuição de treinamento do modelo.

---

## Limites por Resolução

| Resolução | Dimensões | Frames Máx. | Duração | FPS |
|-----------|-----------|-------------|---------|-----|
| 480P | 832x480 ou 480x832 | **81** | 5.06s | 16 |
| 720P | 1280x720 ou 720x1280 | **81** | 5.06s | 16 |
| 1080P | 1920x1080 | ❌ Não suportado | — | — |

> **Nota:** O modelo 5B (TI2V-5B) usa 24fps e suporta 121 frames (5s).
> O 14B MoE usa **16fps** — configurar como 24fps deixa o vídeo acelerado.

---

## Regra dos Frames Válidos: `4n+1`

Os valores válidos para `frame_num` são da série:
```
1, 5, 9, 13, 17, 21, 25, 33, 41, 49, 57, 65, 81, 97, 121...
```
Valores fora desta série podem causar artefatos ou erros de geração.

**Recomendado para 14B MoE:** `81 frames` (máximo nativo de treinamento)

---

## O Que Acontece ao Exceder 81 Frames

Comportamento documentado pela comunidade (GitHub ComfyUI Issue #9106):

- **Frames iniciais "queimados"** (burnt) — artefatos visuais nos primeiros frames
- **Vídeo acelerado** — parece em speedup quando exportado em 16fps
- **Qualidade degradada** — texturas borradas e jitter de movimento
- **Artifacts gerais** — distorções, aberrações cromáticas, flashes

> Mais VRAM **não resolve** esses problemas — é uma limitação arquitetural do treinamento.

---

## Diferença 14B MoE vs 5B

| Aspecto | T2V-A14B (14B MoE) | TI2V-5B (5B) |
|---------|-------------------|--------------|
| FPS nativo | **16 fps** | 24 fps |
| Frames para 5s | **81** | 121 |
| Resolução 720P | 1280x720 | 1280x704 |
| I2V nativo | ❌ Não | ✅ Sim |

---

## Para Vídeos Mais Longos que 5s

A abordagem correta **não é aumentar frame_num além de 81**.
A solução é **encadeamento de clips via I2V (Image-to-Video)**:

1. Gerar clip 1 (T2V, 81 frames)
2. Usar o último frame como input do clip 2 (I2V)
3. Repetir quantas vezes necessário
4. Concatenar clips em pós-produção

Requer o modelo **Wan2.2-I2V-A14B** para o passo de I2V.

---

## Configuração Correta no Workflow ComfyUI

```json
"61": {
  "class_type": "EmptyHunyuanLatentVideo",
  "inputs": {
    "width": 1280,
    "height": 720,
    "length": 81,
    "batch_size": 1
  }
}
```

**Output VHS_VideoCombine:**
```json
"9": {
  "inputs": {
    "frame_rate": 16,
    "filename_prefix": "wan22_14b_video"
  }
}
```

---

## Fontes

- [Wan-AI/Wan2.2-T2V-A14B — HuggingFace](https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B)
- [Wan2.2-T2V-A14B-Diffusers: 16fps or 24fps? (discussão oficial)](https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B-Diffusers/discussions/6)
- [GitHub Wan-Video/Wan2.2](https://github.com/Wan-Video/Wan2.2)
- [ComfyUI Issue #9106: Burnt Initial Frames at 121 Frames](https://github.com/comfyanonymous/ComfyUI/issues/9106)
- Wan: Open and Advanced Large-Scale Video Generative Models (arXiv:2503.20314)
