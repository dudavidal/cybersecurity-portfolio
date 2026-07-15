#!/usr/bin/env bash
# =============================================================================
# demo.sh — Roteiro de demonstração do Lotus Garden 🪷 com Docker
#
# Uso: bash demo.sh
# Requer: Docker e Docker Compose instalados e rodando.
# =============================================================================

set -e

VERDE="\033[0;32m"
AMARELO="\033[1;33m"
VERMELHO="\033[0;31m"
RESET="\033[0m"

info()  { echo -e "${VERDE}[INFO]${RESET}  $*"; }
aviso() { echo -e "${AMARELO}[AVISO]${RESET} $*"; }
erro()  { echo -e "${VERMELHO}[ERRO]${RESET}  $*"; }

pausar() {
    echo ""
    read -rp "$(echo -e "${AMARELO}>>> Pressione ENTER para continuar...${RESET}")"
    echo ""
}

# -----------------------------------------------------------------------------
# 0) Preparação
# -----------------------------------------------------------------------------
info "Criando pastas de volume no host (se não existirem)..."
mkdir -p volumes/peer1 volumes/peer2 volumes/peer3

info "Construindo imagem e subindo os 3 peers..."
docker compose up --build -d

info "Aguardando 8s para os peers se descobrirem via UDP broadcast..."
sleep 8

echo ""
info "=== CENÁRIO 1: Arquivo novo propagado de peer1 para peer2 e peer3 ==="
info "Criando arquivo 'ola_mundo.txt' na pasta do peer1..."
echo "Olá do Peer Alpha! $(date)" > volumes/peer1/ola_mundo.txt

info "Aguardando propagação (POLL_INTERVAL=3s + transferência)..."
sleep 6

info "Conteúdo das pastas após propagação:"
echo "  peer1: $(ls volumes/peer1/)"
echo "  peer2: $(ls volumes/peer2/ 2>/dev/null || echo '(vazio)')"
echo "  peer3: $(ls volumes/peer3/ 2>/dev/null || echo '(vazio)')"

pausar

# -----------------------------------------------------------------------------
echo ""
info "=== CENÁRIO 2: Modificação de arquivo ==="
info "Editando 'ola_mundo.txt' no peer1..."
echo "Arquivo MODIFICADO pelo Peer Alpha em $(date)" > volumes/peer1/ola_mundo.txt

info "Aguardando propagação da nova versão..."
sleep 6

info "Conteúdo do arquivo no peer2 (deve estar atualizado):"
cat volumes/peer2/ola_mundo.txt 2>/dev/null || aviso "Arquivo ainda não chegou — aguarde mais alguns segundos."

pausar

# -----------------------------------------------------------------------------
echo ""
info "=== CENÁRIO 3: Remoção de arquivo ==="
info "Removendo 'ola_mundo.txt' da pasta do peer1..."
rm -f volumes/peer1/ola_mundo.txt

info "Aguardando propagação do file_delete..."
sleep 6

info "Verificando se o arquivo foi removido nos outros peers:"
echo "  peer2: $(ls volumes/peer2/ 2>/dev/null || echo '(vazio)')"
echo "  peer3: $(ls volumes/peer3/ 2>/dev/null || echo '(vazio)')"

pausar

# -----------------------------------------------------------------------------
echo ""
info "=== CENÁRIO 4: Tolerância a falhas — derrubando peer2 ==="
info "Parando container peer2..."
docker stop peer2

info "Criando 'arquivo_novo.txt' enquanto peer2 está offline..."
echo "Criado com peer2 offline em $(date)" > volumes/peer1/arquivo_novo.txt

info "Aguardando propagação para peer3..."
sleep 6

info "Reiniciando peer2..."
docker start peer2

info "Aguardando peer2 ser redescoberto e fazer handshake de sync..."
sleep 12

info "Verificando pasta do peer2 (deve ter recebido o arquivo via sync inicial):"
ls volumes/peer2/

pausar

# -----------------------------------------------------------------------------
echo ""
info "=== CENÁRIO 5: Arquivo adicionado via interface web (peer3) ==="
info "Fazendo upload de arquivo via HTTP para peer3 (porta 8002)..."
echo "Upload via API web em $(date)" > /tmp/upload_teste.txt
curl -s -X POST http://localhost:8002/action/upload \
     -F "file=@/tmp/upload_teste.txt" | python3 -m json.tool || \
     aviso "curl falhou — verifique se a porta 8002 está acessível."

info "Aguardando propagação..."
sleep 6

info "Conteúdo das pastas:"
echo "  peer1: $(ls volumes/peer1/)"
echo "  peer2: $(ls volumes/peer2/)"
echo "  peer3: $(ls volumes/peer3/)"

pausar

# -----------------------------------------------------------------------------
echo ""
info "=== Demonstração concluída ==="
info "Interfaces Lotus Garden disponíveis:"
echo "  Lotus Garden - Peer Alpha (peer1): http://localhost:8000"
echo "  Lotus Garden - Peer Beta  (peer2): http://localhost:8001"
echo "  Lotus Garden - Peer Gamma (peer3): http://localhost:8002"
echo ""
aviso "Para encerrar todos os containers: docker compose down"
aviso "Para ver logs em tempo real:        docker compose logs -f"
