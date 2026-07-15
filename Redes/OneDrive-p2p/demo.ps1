# =============================================================================
# demo.ps1 — Roteiro de demonstração do Lotus Garden 🪷 (PowerShell)
#
# Uso: .\demo.ps1
# Requer: Python 3.8+ instalado e acessível via PATH
# =============================================================================

$ErrorActionPreference = "Stop"

function Info  { Write-Host "[INFO]" -ForegroundColor Green -NoNewline; Write-Host "  $args" }
function Aviso { Write-Host "[AVISO]" -ForegroundColor Yellow -NoNewline; Write-Host " $args" }
function Erro  { Write-Host "[ERRO]" -ForegroundColor Red -NoNewline; Write-Host "  $args" }

function Pausar {
    Write-Host ""
    $null = Read-Host ">>> Pressione ENTER para continuar..."
    Write-Host ""
}

# ---------------------------------------------------------------------------
# 0) Limpa execuções anteriores e prepara pastas
# ---------------------------------------------------------------------------
Info "Limpando pastas de sincronização..."
@("sync_A", "sync_B", "sync_C") | ForEach-Object {
    $p = Join-Path -Path $PSScriptRoot -ChildPath $_
    if (Test-Path $p) { Remove-Item -Path "$p\*" -Force -ErrorAction SilentlyContinue }
}

# ---------------------------------------------------------------------------
# 1) Sobe os 3 peers em janelas separadas
# ---------------------------------------------------------------------------
Info "Iniciando 3 peers em janelas separadas..."
$peer1 = Start-Process powershell -ArgumentList "-NoExit -NoProfile -Command cd '$PSScriptRoot'; python main.py 6000 sync_A" -WindowStyle Normal -PassThru
$peer2 = Start-Process powershell -ArgumentList "-NoExit -NoProfile -Command cd '$PSScriptRoot'; python main.py 6001 sync_B" -WindowStyle Normal -PassThru
$peer3 = Start-Process powershell -ArgumentList "-NoExit -NoProfile -Command cd '$PSScriptRoot'; python main.py 6002 sync_C" -WindowStyle Normal -PassThru

Info "Aguardando 10s para os peers se descobrirem..."
Start-Sleep 10

Write-Host ""
Info "=== CENÁRIO 1: Arquivo novo propagado do peer1 para peer2 e peer3 ==="
Info "Criando arquivo 'ola_mundo.txt' no sync_A..."
"Ola do Peer Alpha! $(Get-Date)" | Out-File -FilePath "$PSScriptRoot\sync_A\ola_mundo.txt" -Encoding utf8
Info "Aguardando propagação (polling 3s + transferência)..."
Start-Sleep 8
Info "Verificando pastas:"
Write-Host "  sync_A: $(Get-ChildItem "$PSScriptRoot\sync_A" | ForEach-Object Name)"
Write-Host "  sync_B: $(Get-ChildItem "$PSScriptRoot\sync_B" | ForEach-Object Name)"
Write-Host "  sync_C: $(Get-ChildItem "$PSScriptRoot\sync_C" | ForEach-Object Name)"

Pausar

# ---------------------------------------------------------------------------
Write-Host ""
Info "=== CENÁRIO 2: Modificação de arquivo ==="
Info "Editando 'ola_mundo.txt' no peer1..."
"Arquivo MODIFICADO pelo Peer Alpha em $(Get-Date)" | Out-File -FilePath "$PSScriptRoot\sync_A\ola_mundo.txt" -Encoding utf8
Info "Aguardando propagação..."
Start-Sleep 8
Info "Conteúdo no peer2:"
Get-Content "$PSScriptRoot\sync_B\ola_mundo.txt" -ErrorAction SilentlyContinue | Write-Host

Pausar

# ---------------------------------------------------------------------------
Write-Host ""
Info "=== CENÁRIO 3: Remoção de arquivo ==="
Info "Removendo 'ola_mundo.txt' do peer1..."
Remove-Item -Path "$PSScriptRoot\sync_A\ola_mundo.txt" -Force
Info "Aguardando propagação do file_delete..."
Start-Sleep 8
Info "Verificando peer2 e peer3:"
Write-Host "  sync_B: $(Get-ChildItem "$PSScriptRoot\sync_B" | ForEach-Object Name)"
Write-Host "  sync_C: $(Get-ChildItem "$PSScriptRoot\sync_C" | ForEach-Object Name)"

Pausar

# ---------------------------------------------------------------------------
Write-Host ""
Info "=== Interfaces web disponíveis ==="
Write-Host "  Lotus Garden - Peer Alpha (porta 6000): http://localhost:8000"
Write-Host "  Lotus Garden - Peer Beta  (porta 6001): http://localhost:8001"
Write-Host "  Lotus Garden - Peer Gamma (porta 6002): http://localhost:8002"
Write-Host ""

$resposta = Read-Host "Deseja encerrar os peers? (S/N)"
if ($resposta -eq "S" -or $resposta -eq "s") {
    Info "Encerrando processos..."
    $peer1 | Stop-Process -Force -ErrorAction SilentlyContinue
    $peer2 | Stop-Process -Force -ErrorAction SilentlyContinue
    $peer3 | Stop-Process -Force -ErrorAction SilentlyContinue
    Info "Processos encerrados."
}
