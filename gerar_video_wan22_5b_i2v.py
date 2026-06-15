#!/usr/bin/env python3
"""
Wan 2.2 5B Ti2V (Image-to-Video) via ComfyUI
Uso: python3 gerar_video_wan22_5b_i2v.py "prompt" --image imagem.png [opções]
"""
import argparse, json, requests, sys, uuid
from pathlib import Path

COMFYUI_URL = "http://127.0.0.1:8188"
OUTPUT_DIR  = Path(__file__).resolve().parent / "ComfyUI" / "output"


def upload_image(image_path: str) -> str:
    p = Path(image_path)
    with open(p, "rb") as f:
        files = {"image": (p.name, f, "image/png")}
        r = requests.post(f"{COMFYUI_URL}/upload/image", files=files, timeout=30)
    r.raise_for_status()
    return r.json()["name"]


def criar_workflow(prompt, image_name, negative="", width=720, height=480,
                   frames=33, fps=24, cfg=6.0, seed=42, prefix="wan22_5b_i2v"):
    import random
    if seed == -1:
        seed = random.randint(0, 2**32 - 1)

    return {
        "1":  {"inputs": {"text": prompt,   "clip": ["11", 0]}, "class_type": "CLIPTextEncode"},
        "6":  {"inputs": {"text": negative, "clip": ["11", 0]}, "class_type": "CLIPTextEncode"},
        "10": {"inputs": {"unet_name": "wan2.2_ti2v_5B_fp16.safetensors", "weight_dtype": "default"}, "class_type": "UNETLoader"},
        "11": {"inputs": {"clip_name": "umt5_xxl_fp16.safetensors", "type": "wan"}, "class_type": "CLIPLoader"},
        "12": {"inputs": {"vae_name": "wan2.2_vae.safetensors"}, "class_type": "VAELoader"},
        "14": {"inputs": {"model": ["10", 0], "shift": 8.0}, "class_type": "ModelSamplingSD3"},
        "20": {"inputs": {"image": image_name, "upload": "image"}, "class_type": "LoadImage"},
        # WanImageToVideo substitui EmptyHunyuanLatentVideo e condiciona pela imagem inicial
        "5":  {"inputs": {
                   "positive": ["1", 0], "negative": ["6", 0],
                   "vae": ["12", 0],
                   "width": width, "height": height, "length": frames, "batch_size": 1,
                   "start_image": ["20", 0]
               }, "class_type": "WanImageToVideo"},
        # KSampler usa positive/negative atualizados pelo WanImageToVideo
        "3":  {"inputs": {
                   "seed": seed, "steps": 20, "cfg": cfg,
                   "sampler_name": "euler", "scheduler": "normal", "denoise": 1,
                   "model": ["14", 0],
                   "positive":     ["5", 0],
                   "negative":     ["5", 1],
                   "latent_image": ["5", 2]
               }, "class_type": "KSampler"},
        "8":  {"inputs": {"samples": ["3", 0], "vae": ["12", 0]}, "class_type": "VAEDecode"},
        "9":  {"inputs": {
                   "frame_rate": fps, "loop_count": 0,
                   "filename_prefix": prefix, "format": "video/h264-mp4",
                   "pingpong": False, "save_output": True,
                   "images": ["8", 0]
               }, "class_type": "VHS_VideoCombine"},
    }, seed


def submeter(workflow):
    r = requests.post(f"{COMFYUI_URL}/prompt",
                      json={"prompt": workflow, "client_id": str(uuid.uuid4())},
                      timeout=30)
    r.raise_for_status()
    return r.json()["prompt_id"]


def main():
    p = argparse.ArgumentParser(description="Wan 2.2 5B I2V")
    p.add_argument("prompt")
    p.add_argument("--image",      default="",  help="Caminho local da imagem (faz upload)")
    p.add_argument("--image-name", default="",  dest="image_name", help="Nome do arquivo já no ComfyUI (sem upload)")
    p.add_argument("--negative", default="")
    p.add_argument("--width",    type=int,   default=720)
    p.add_argument("--height",   type=int,   default=480)
    p.add_argument("--frames",   type=int,   default=33)
    p.add_argument("--fps",      type=int,   default=24)
    p.add_argument("--cfg",      type=float, default=6.0)
    p.add_argument("--seed",     type=int,   default=-1)
    p.add_argument("--output",   default="wan22_5b_i2v")
    args = p.parse_args()

    if args.image_name:
        image_name = args.image_name
        print(f"📎 Imagem já no ComfyUI: {image_name}")
    else:
        print("📤 Fazendo upload da imagem...")
        image_name = upload_image(args.image)
        print(f"   Imagem: {image_name}")

    workflow, seed = criar_workflow(
        args.prompt, image_name, args.negative,
        args.width, args.height, args.frames,
        args.fps, args.cfg, args.seed, args.output
    )

    print(f"🎬 Wan 2.2 5B I2V | {args.width}x{args.height} | {args.frames}f | seed={seed}")
    print(f"   Prompt: {args.prompt}")

    prompt_id = submeter(workflow)
    print(f"✅ SUCESSO! Geração iniciada!")
    print(f"   Prompt ID: {prompt_id}")
    print(f"📂 Output: {OUTPUT_DIR}/{args.output}_*.mp4")


if __name__ == "__main__":
    main()
