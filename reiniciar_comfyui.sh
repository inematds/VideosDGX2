#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "🔄 Reiniciando ComfyUI..."
echo ""

# Parar ComfyUI
echo "1️⃣ Parando ComfyUI..."
pkill -f "python main.py.*8188" && echo "   ✅ ComfyUI parado" || echo "   ⚠️  ComfyUI já estava parado"

sleep 2

# Limpar cache GPU se possível
echo ""
echo "2️⃣ Limpando cache..."
python3 -c "import torch; torch.cuda.empty_cache(); print('   ✅ Cache CUDA limpo')" 2>/dev/null || echo "   ⚠️  Não foi possível limpar cache"

sleep 1

# Reiniciar ComfyUI
echo ""
echo "3️⃣ Reiniciando ComfyUI..."
cd "$SCRIPT_DIR/ComfyUI"
source ../comfyui-env/bin/activate
nohup python main.py --listen 0.0.0.0 --port 8188 --highvram > ../comfyui_server.log 2>&1 &
COMFYUI_PID=$!

sleep 3

# Verificar se está rodando
if ps -p $COMFYUI_PID > /dev/null; then
    echo "   ✅ ComfyUI reiniciado com sucesso!"
    echo "   PID: $COMFYUI_PID"
    echo ""
    echo "🌐 Acesse: http://localhost:8188"
    echo ""
    echo "📝 Log: tail -f $SCRIPT_DIR/comfyui_server.log"
else
    echo "   ❌ Erro ao iniciar ComfyUI"
    echo "   Veja o log: tail -50 $SCRIPT_DIR/comfyui_server.log"
fi

echo ""
echo "============================================================"
