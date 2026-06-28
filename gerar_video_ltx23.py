#!/usr/bin/env python3
"""
Gerador CLI de video LTX-2.3 (22B distilled) via ComfyUI ja rodando.
====================================================================
Submete um workflow ao ComfyUI em http://127.0.0.1:8188 e salva o MP4 em
ComfyUI/output/ com o prefixo passado em --output.

Suporta:
  - T2V (text-to-video)  -> default
  - I2V (image-to-video) -> quando --image-name e fornecido

Abordagem: parte do workflow de exemplo do custom node ComfyUI-LTXVideo
(`example_workflows/2.3/LTX-2.3_T2V_I2V_Single_Stage_Distilled_Full.json`,
formato UI), converte para o formato API com `ltx_workflow_util.ui_to_api`
(usando o object_info real do servidor para resolver nomes de modelo/COMBO),
poda o ramo de sampler que depende de nos NAO instalados (ClownSampler_Beta /
RES4LYF), sobrescreve por node-id os campos relevantes e faz POST /prompt.

Contrato de stdout (a interface web depende disto):
  imprime "Prompt ID: <id>" e "SUCESSO" quando a submissao da certo.

Uso (identico ao gerar_video_wan22_5b.py):
  gerar_video_ltx23.py "PROMPT" --width W --height H --frames F --fps 24 \
      --cfg C --seed S --output PREFIXO --negative "..." [--image-name NOME]
  (-1 em seed = aleatorio; --image-name presente = I2V)
"""

import argparse
import random
import sys
import uuid
from pathlib import Path

import ltx_workflow_util as lxu
import json

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
COMFYUI_URL = "http://127.0.0.1:8188"
ROOT = Path(__file__).parent
EXAMPLE_WF = (
    ROOT / "ComfyUI" / "custom_nodes" / "ComfyUI-LTXVideo"
    / "example_workflows" / "2.3"
    / "LTX-2.3_T2V_I2V_Single_Stage_Distilled_Full.json"
)
OUTPUT_DIR = ROOT / "ComfyUI" / "output"

# ---- node-ids / papeis do workflow de exemplo (single-stage distilled full) --
# (descobertos via /object_info + inspecao do grafo UI)
N_POS_PROMPT   = "2483"   # CLIPTextEncode (positivo)  -> inputs.text
N_NEG_PROMPT   = "2612"   # CLIPTextEncode (negativo)  -> inputs.text
N_LATENT       = "3059"   # EmptyLTXVLatentVideo        -> width / height (length vem do 4979)
N_FRAMES       = "4979"   # PrimitiveInt "number of frames" -> inputs.value
N_FPS          = "4978"   # PrimitiveFloat "fps"        -> inputs.value
N_SEED         = "4832"   # RandomNoise (ramo CFGGuider)-> inputs.noise_seed
N_BYPASS_I2V   = "4977"   # PrimitiveBoolean "bypass_i2v" (true=T2V, false=I2V)
N_LOADIMAGE    = "2004"   # LoadImage                   -> inputs.image
N_IMG_COND     = "3159"   # LTXVImgToVideoConditionOnly -> inputs.bypass / strength
N_CFG_GUIDER   = "4828"   # CFGGuider                   -> inputs.cfg
N_LORA         = "4922"   # LoraLoaderModelOnly (ramo CFGGuider) -> strength_model
N_SAVE_KEEP    = "4852"   # SaveVideo do ramo CFGGuider (o que mantemos)
N_SAVE_DROP    = "4823"   # SaveVideo do ramo ClownSampler (descartado)

# Preferencias de resolucao de COMBO (quando o nome do workflow != instalado)
COMBO_PREFER = {
    # o exemplo usa "comfy_gemma_3_12B_it.safetensors"; instalado e a pasta
    # gemma-3-12b-it-qat-q4_0-unquantized (shards). Preferir o shard 1 do gemma.
    ("LTXAVTextEncoderLoader", "text_encoder"): ["gemma", "model-00001"],
    ("LTXAVTextEncoderLoader", "ckpt_name"):    ["ltx-2.3", "distilled"],
    ("CheckpointLoaderSimple", "ckpt_name"):    ["ltx-2.3", "distilled"],
    ("LTXVAudioVAELoader", "ckpt_name"):        ["ltx-2.3", "distilled"],
    ("LoraLoaderModelOnly", "lora_name"):       ["distilled-lora", "ltx-2.3"],
}

# Prompt negativo padrao (igual ao do exemplo)
NEGATIVE_DEFAULT = "pc game, console game, video game, cartoon, childish, ugly, worst quality, low quality, blurry, distorted"


def build_api_workflow(prompt, negative, width, height, frames, fps, cfg,
                       seed, output_prefix, image_name=None,
                       lora_strength=None, img_strength=0.7):
    """Carrega o exemplo UI, converte p/ API e sobrescreve por node-id."""
    ui = json.load(open(EXAMPLE_WF))
    oi = lxu.fetch_object_info(COMFYUI_URL)

    # Dropar o ramo de sampler ClownSampler_Beta (RES4LYF nao instalado).
    # ui_to_api ja descarta nos sem schema; aqui garantimos a poda do SaveVideo
    # desse ramo para nao deixar saida orfã.
    api = lxu.ui_to_api(ui, oi, combo_prefer=COMBO_PREFER)

    # Manter apenas o subgrafo do SaveVideo que queremos (ramo CFGGuider).
    if N_SAVE_KEEP in api:
        api = lxu.prune_unreachable(api, [N_SAVE_KEEP])
    else:
        raise RuntimeError(
            f"SaveVideo esperado (id {N_SAVE_KEEP}) sumiu apos conversao. "
            f"Nos presentes: {sorted(api.keys())}"
        )

    def setin(nid, key, value):
        if nid in api:
            api[nid]["inputs"][key] = value

    # Prompts
    setin(N_POS_PROMPT, "text", prompt)
    setin(N_NEG_PROMPT, "text", negative)

    # Resolucao (width/height ficam no EmptyLTXVLatentVideo; length vem do 4979)
    setin(N_LATENT, "width", int(width))
    setin(N_LATENT, "height", int(height))
    setin(N_LATENT, "length", int(frames))   # caso nao esteja wired, garante valor
    setin(N_FRAMES, "value", int(frames))

    # FPS
    setin(N_FPS, "value", float(fps))

    # Seed
    setin(N_SEED, "noise_seed", int(seed))

    # CFG (guider). Modelo distilled normalmente usa cfg baixo (~1).
    setin(N_CFG_GUIDER, "cfg", float(cfg))

    # LoRA strength (opcional)
    if lora_strength is not None:
        setin(N_LORA, "strength_model", float(lora_strength))

    # T2V vs I2V
    if image_name:
        setin(N_BYPASS_I2V, "value", False)      # nao bypassar -> usa imagem
        setin(N_IMG_COND, "bypass", False)
        setin(N_IMG_COND, "strength", float(img_strength))
        setin(N_LOADIMAGE, "image", image_name)
    else:
        setin(N_BYPASS_I2V, "value", True)       # bypass -> T2V puro
        setin(N_IMG_COND, "bypass", True)

    # Prefixo de saida
    setin(N_SAVE_KEEP, "filename_prefix", output_prefix)

    return api


def main():
    parser = argparse.ArgumentParser(
        description="Gera videos com LTX-2.3 (22B distilled) via ComfyUI (T2V / I2V)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # T2V 512x512, ~2s
  ./gerar_video_ltx23.py "a calm ocean wave at sunset" --width 512 --height 512 \\
      --frames 49 --fps 24 --cfg 3 --seed 1 --output ltx23_test

  # T2V HD
  ./gerar_video_ltx23.py "a cinematic drone shot over mountains" \\
      --width 1280 --height 704 --frames 97 --output ltx23_hd

  # I2V (imagem deve estar em ComfyUI/input/)
  ./gerar_video_ltx23.py "the cat slowly turns its head" \\
      --image-name minha_foto.png --frames 97 --output ltx23_i2v

LTX-2.3 22B distilled:
  - frames: usar 8k+1 (ex.: 49, 57, 81, 97, 121). Default 97 (~4s @24fps).
  - cfg: o modelo distilled usa CFGGuider; valores baixos (1-4) sao normais.
  - gera audio nativo junto do video (mp4 com trilha).
  - --image-name: nome de um arquivo ja presente em ComfyUI/input/.
        """,
    )
    parser.add_argument("prompt", help="Descricao do video a gerar")
    parser.add_argument("--negative", default=NEGATIVE_DEFAULT, help="Prompt negativo")
    parser.add_argument("--width",  type=int, default=1280, help="Largura (padrao: 1280)")
    parser.add_argument("--height", type=int, default=704,  help="Altura (padrao: 704)")
    parser.add_argument("--frames", type=int, default=97,   help="Frames (padrao: 97 ~4s; usar 8k+1)")
    parser.add_argument("--fps",    type=int, default=24,   help="FPS output (padrao: 24)")
    parser.add_argument("--cfg",    type=float, default=3.0, help="CFG (CFGGuider) (padrao: 3.0)")
    parser.add_argument("--seed",   type=int, default=-1,   help="Seed (-1 = aleatorio)")
    parser.add_argument("--output", default="ltx23_video",  help="Prefixo do arquivo de saida")
    parser.add_argument("--image-name", dest="image_name", default=None,
                        help="Nome do arquivo em ComfyUI/input/ para I2V (ativa I2V)")
    parser.add_argument("--lora-strength", dest="lora_strength", type=float, default=None,
                        help="Forca da LoRA distilled (padrao: a do workflow, 0.5)")
    parser.add_argument("--img-strength", dest="img_strength", type=float, default=0.7,
                        help="Forca de condicionamento da imagem em I2V (padrao: 0.7)")
    parser.add_argument("--wait", action="store_true",
                        help="Aguardar a geracao terminar (polling /history) e reportar o mp4")
    parser.add_argument("--timeout", type=int, default=1800,
                        help="Timeout do --wait em segundos (padrao: 1800)")

    args = parser.parse_args()

    seed = args.seed if args.seed != -1 else random.randint(0, 2**32 - 1)

    mode = "I2V" if args.image_name else "T2V"
    duration = args.frames / args.fps

    print("🎬 Gerando workflow LTX-2.3 (22B distilled)...")
    print(f"   Modo: {mode}")
    print(f"   Prompt: {args.prompt}")
    if args.image_name:
        print(f"   Imagem (input/): {args.image_name}")
    print(f"   Resolucao: {args.width}x{args.height}")
    print(f"   Frames: {args.frames} @ {args.fps}fps = {duration:.1f}s")
    print(f"   CFG: {args.cfg}")
    print(f"   Seed: {seed}")
    print(f"   Output: {args.output}_*.mp4")
    print()

    try:
        api = build_api_workflow(
            prompt=args.prompt,
            negative=args.negative,
            width=args.width,
            height=args.height,
            frames=args.frames,
            fps=args.fps,
            cfg=args.cfg,
            seed=seed,
            output_prefix=args.output,
            image_name=args.image_name,
            lora_strength=args.lora_strength,
            img_strength=args.img_strength,
        )
    except Exception as e:
        print(f"❌ ERRO ao montar workflow: {e}")
        sys.exit(1)

    print("🚀 Submetendo para ComfyUI...")
    client_id = str(uuid.uuid4())
    prompt_id, resp = lxu.submit_prompt(COMFYUI_URL, api, client_id=client_id)

    if not prompt_id:
        print("❌ ERRO: Falha ao submeter workflow")
        err = resp.get("error") if isinstance(resp, dict) else resp
        print(json.dumps(err, indent=2, ensure_ascii=False)[:3000])
        print()
        print("Verificar:")
        print(f"  1. ComfyUI rodando? {COMFYUI_URL}/system_stats")
        print(f"  2. Modelos no lugar (checkpoints/loras/text_encoders).")
        sys.exit(1)

    # ---- contrato de stdout esperado pela interface web ----
    print("✅ SUCESSO! Geracao iniciada!")
    print(f"   Prompt ID: {prompt_id}")
    print()
    estimated = int(args.frames * 4)
    print(f"⏳ Tempo estimado: ~{estimated//60}min {estimated%60}s")
    print(f"📂 Output: {OUTPUT_DIR}/{args.output}_*.mp4")
    print(f"   {COMFYUI_URL}")

    if args.wait:
        print()
        print("⏳ Aguardando conclusao (polling /history)...")

        def tick(elapsed, status_str, messages):
            print(f"   ... {elapsed}s (status={status_str})", flush=True)

        result = lxu.wait_for_completion(
            COMFYUI_URL, prompt_id, poll_every=5, max_wait=args.timeout, on_tick=tick
        )
        print()
        if result["status"] == "completed":
            mp4s = [f for f in result["files"] if f.endswith(".mp4")]
            print(f"✅ CONCLUIDO. Arquivos: {result['files']}")
            if mp4s:
                print(f"   MP4: {OUTPUT_DIR}/{mp4s[0]}")
        elif result["status"] == "timeout":
            print(f"⏱️  TIMEOUT apos {args.timeout}s. Pode ainda estar rodando.")
            sys.exit(2)
        else:
            print("❌ ERRO na execucao:")
            for m in result["messages"]:
                print("   ", m)
            sys.exit(1)


if __name__ == "__main__":
    main()
