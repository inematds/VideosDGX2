#!/usr/bin/env python3
"""
Script CLI para gerar vídeos usando Wan 2.2 14B MoE via ComfyUI
Arquitetura: Dual-Sampler (High Noise Expert + Low Noise Expert)
Uso: ./gerar_video_wan22_14b.py "seu prompt aqui" [opções]
"""

import json
import uuid
import sys
import argparse
import requests
from pathlib import Path

COMFYUI_URL = "http://127.0.0.1:8188"
WORKFLOW_TEMPLATE = Path(__file__).parent / "workflow_wan22_14b_t2v.json"
OUTPUT_DIR = Path(__file__).parent / "ComfyUI" / "output"

# Prompt negativo oficial do Wan 2.2 (em chinês - recomendado pelo time)
NEGATIVE_DEFAULT = "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走"

def load_workflow_template():
    with open(WORKFLOW_TEMPLATE) as f:
        return json.load(f)

def create_workflow(prompt, negative=None, width=1280, height=704, frames=57,
                    fps=24, cfg=3.5, seed=-1, steps=20, split_step=10,
                    output_prefix="wan22_14b_video"):
    import random
    workflow = load_workflow_template()

    if negative is None:
        negative = NEGATIVE_DEFAULT

    if seed == -1:
        seed = random.randint(0, 2**32 - 1)

    # Prompts
    workflow["6"]["inputs"]["text"] = prompt
    workflow["7"]["inputs"]["text"] = negative

    # Dimensões
    workflow["61"]["inputs"]["width"] = width
    workflow["61"]["inputs"]["height"] = height
    workflow["61"]["inputs"]["length"] = frames

    # KSampler High Noise
    workflow["57"]["inputs"]["noise_seed"] = seed
    workflow["57"]["inputs"]["steps"] = steps
    workflow["57"]["inputs"]["cfg"] = cfg
    workflow["57"]["inputs"]["end_at_step"] = split_step

    # KSampler Low Noise
    workflow["58"]["inputs"]["steps"] = steps
    workflow["58"]["inputs"]["cfg"] = cfg
    workflow["58"]["inputs"]["start_at_step"] = split_step

    # Output
    workflow["9"]["inputs"]["filename_prefix"] = output_prefix
    workflow["9"]["inputs"]["frame_rate"] = fps

    return workflow, seed

def submit_workflow(workflow):
    try:
        payload = {"prompt": workflow, "client_id": str(uuid.uuid4())}
        response = requests.post(f"{COMFYUI_URL}/prompt", json=payload)
        if response.status_code == 200:
            return response.json().get("prompt_id")
        else:
            print(f"❌ Erro ao submeter: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"❌ Erro de conexão: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(
        description="Gera vídeos usando Wan 2.2 14B MoE (qualidade cinematográfica máxima)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # 720P, ~3.5s (padrão)
  ./gerar_video_wan22_14b.py "a cinematic shot of a waterfall"

  # 480P mais rápido
  ./gerar_video_wan22_14b.py "ocean waves" --width 832 --height 480 --frames 33

  # Mais steps para qualidade máxima
  ./gerar_video_wan22_14b.py "epic landscape" --steps 30 --split-step 15

  # Seed fixo para reproduzir
  ./gerar_video_wan22_14b.py "cyberpunk city" --seed 42

Wan 2.2 14B MoE - Arquitetura:
  - Expert 1 (High Noise): Steps 0 → split_step  (primeiras etapas)
  - Expert 2 (Low Noise):  Steps split_step → total (últimas etapas)
  - CFG padrão: 3.5 (mais baixo que Wan 2.1 e 5B)
  - Qualidade cinematográfica máxima da família Wan

Parâmetros recomendados:
  - 720P:  1280x704, 57 frames  (~3.5s @ 24fps) — ~6-8 min geração
  - 480P:  832x480,  33 frames  (~2s @ 24fps)   — ~3-4 min geração
  - 1080P: 1920x1080, 57 frames (heavy, ~128GB VRAM mínimo)
        """
    )

    parser.add_argument("prompt", help="Descrição do vídeo a gerar")
    parser.add_argument("--negative", default=None, help="Prompt negativo (padrão: oficial Wan em chinês)")
    parser.add_argument("--width",  type=int, default=1280, help="Largura (padrão: 1280)")
    parser.add_argument("--height", type=int, default=704,  help="Altura (padrão: 704)")
    parser.add_argument("--frames", type=int, default=57,   help="Frames (padrão: 57 = ~3.5s)")
    parser.add_argument("--fps",    type=int, default=24,   help="FPS output (padrão: 24)")
    parser.add_argument("--cfg",    type=float, default=3.5, help="CFG scale (padrão: 3.5)")
    parser.add_argument("--seed",   type=int, default=-1,   help="Seed (-1 = aleatório)")
    parser.add_argument("--steps",  type=int, default=20,   help="Steps totais (padrão: 20)")
    parser.add_argument("--split-step", type=int, default=10, dest="split_step",
                        help="Step de troca High→Low Noise (padrão: 10 = metade)")
    parser.add_argument("--output", default="wan22_14b_video", help="Prefixo do arquivo de saída")

    args = parser.parse_args()

    if args.split_step >= args.steps:
        print(f"⚠️  split-step ({args.split_step}) deve ser menor que steps ({args.steps})")
        sys.exit(1)

    workflow, actual_seed = create_workflow(
        prompt=args.prompt,
        negative=args.negative,
        width=args.width,
        height=args.height,
        frames=args.frames,
        fps=args.fps,
        cfg=args.cfg,
        seed=args.seed,
        steps=args.steps,
        split_step=args.split_step,
        output_prefix=args.output
    )

    duration = args.frames / args.fps

    print("🎬 Gerando workflow Wan 2.2 14B MoE...")
    print(f"   Modelo: Wan 2.2 T2V 14B MoE (High Noise + Low Noise)")
    print(f"   Prompt: {args.prompt}")
    print(f"   Resolução: {args.width}x{args.height}")
    print(f"   Frames: {args.frames} @ {args.fps}fps = {duration:.1f}s")
    print(f"   Steps: {args.steps} (split em step {args.split_step})")
    print(f"   CFG: {args.cfg}")
    print(f"   Seed: {actual_seed}")
    print()

    print("🚀 Submetendo para ComfyUI...")

    prompt_id = submit_workflow(workflow)

    if prompt_id:
        print("✅ SUCESSO! Geração iniciada!")
        print(f"   Prompt ID: {prompt_id}")
        print()
        estimated = int(args.frames * 5)
        print(f"⏳ Tempo estimado: ~{estimated//60}min {estimated%60}s (14B MoE é mais lento)")
        print()
        print(f"📂 Output: {OUTPUT_DIR}/{args.output}_*.mp4")
        print(f"📊 Monitor: tail -f {Path(__file__).parent}/comfyui_server.log")
        print(f"   {COMFYUI_URL}")
    else:
        print("❌ ERRO: Falha ao submeter workflow")
        print()
        print("Verificar:")
        print(f"  1. ComfyUI rodando? curl {COMFYUI_URL}/system_stats")
        print(f"  2. Modelos no lugar?")
        print(f"     - models/unet/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors")
        print(f"     - models/unet/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors")
        print(f"     - models/text_encoders/umt5_xxl_fp16.safetensors")
        print(f"     - models/vae/Wan2.1_VAE.pth")
        print(f"  3. Log: tail -50 {Path(__file__).parent}/comfyui_server.log")
        sys.exit(1)

if __name__ == "__main__":
    main()
