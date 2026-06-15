# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a project focused on running video LLMs (Large Language Models) on the DGX Spark 2026 hardware platform. The DGX Spark features 128GB unified memory (CPU+GPU) and ~1 PFLOP FP4 performance (Blackwell GB10).

### Target Models

The project focuses on these video generation models:
- **LTX-2**: Full video + audio generation
- **Wan 2.1 (14B)**: Versatile video generation
- **MAGI-1**: Autoregressive model for long-form video with temporal context
- **Waver 1.0**: Lightweight model for batch generation

## Current Status

This repository is in early stages and currently contains only documentation (`doc/videsodgx.txt`). No code implementation exists yet.

## Key Considerations for Development

### Hardware Context
- 128GB unified memory allows running larger models without CPU offloading
- FP4/FP8 quantization capabilities via Blackwell architecture
- Focus on models that benefit from high memory bandwidth and unified memory

### Quantization Strategy
- LTX-2: FP4 (NVFP4) for full version with audio
- Wan 2.1: FP8 for maximum context without compression
- MAGI-1: FP4 (NVFP4) for longer video sequences
- Waver 1.0: FP8 for balanced quality and performance

### Language
Primary documentation is in Portuguese (pt-BR).
