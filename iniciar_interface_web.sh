#!/bin/bash
# Interface Web v4.2 - Fila de Jobs + Cancelamento
# Modelos T2V: Wan 2.2 14B MoE, Wan 2.2 5B
# Modelos I2V: Wan 2.2 5B (WanImageToVideo)
# Novidades: múltiplos jobs em fila, cancelar job em andamento
# Acesso: http://localhost:7862

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ativar venv
source comfyui-env/bin/activate

# Verificar dependências
python3 -c "import fastapi, uvicorn, aiofiles" 2>/dev/null || {
    echo "Instalando dependências..."
    pip install fastapi uvicorn aiofiles python-multipart -q
}

python3 -c "import websocket" 2>/dev/null || {
    echo "Instalando websocket-client para progresso real..."
    pip install websocket-client -q
}

# Verificar se ComfyUI está rodando
if ! curl -s http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
    echo "⚠️  ComfyUI não está rodando. Iniciando..."
    nohup python3 ComfyUI/main.py --listen 0.0.0.0 --highvram > comfyui_server.log 2>&1 &
    sleep 5
    echo "✅ ComfyUI iniciado (porta 8188)"
fi

echo ""
echo "🎬 Interface Web v4.2 - Fila de Jobs + Cancelamento"
echo "   T2V:  Wan 2.2 14B MoE | Wan 2.2 5B"
echo "   I2V:  Wan 2.2 5B"
echo "   Fila: múltiplos jobs em sequência"
echo "   Cancel: cancelar job na fila ou em processamento"
echo "   Acesso: http://localhost:7862"
echo ""
echo "Pressione Ctrl+C para parar"
echo ""

python3 web_interface.py
