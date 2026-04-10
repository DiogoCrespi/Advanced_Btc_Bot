# Script de Deploy Remoto - BTC Bot
# Ajustado para as pastas atuais e mapeamento de chaves

$pscp = 'C:\Program Files\PuTTY\pscp.exe'
$plink = 'C:\Program Files\PuTTY\plink.exe'
$hostkey = 'SHA256:cgSnasY3sX/GYZeGqh3trJs6gyafnvQCHdBB0URD+h0'
$user = 'diogo@100.86.220.116'
$pass = '1597'
$local_path = 'C:\Nestjs\Btc_bot'
$remote_path = '/home/diogo/Btc_bot'

Write-Host "🚀 Iniciando deploy para $user..." -ForegroundColor Cyan

# 1. Copiar arquivos raiz (Python, Configs, Docker)
Write-Host "📦 Copiando arquivos raiz..."
& $pscp -pw $pass -hostkey $hostkey "$local_path\*.py" "$local_path\*.yml" "$local_path\Dockerfile" "$local_path\requirements.txt" "$local_path\.dockerignore" "$user`:$remote_path/"

# 2. Copiar pastas de lógica e MiroFish
Write-Host "📁 Copiando pastas logic e MiroFish..."
& $pscp -pw $pass -hostkey $hostkey -r "$local_path\logic" "$user`:$remote_path/"
& $pscp -pw $pass -hostkey $hostkey -r "$local_path\data" "$user`:$remote_path/"
& $pscp -pw $pass -hostkey $hostkey -r "$local_path\MiroFish" "$user`:$remote_path/"

# 3. Preparar estado e Executar Build/Up no servidor
Write-Host "🛠️  Resetando saldo e executando Docker Compose..."
$remote_cmd = "mkdir -p Btc_bot/results && echo '1000.00' > Btc_bot/results/balance_state.txt && cd $remote_path && docker compose build btc-master-bot && docker compose up --force-recreate -d"
& $plink -batch -pw $pass -hostkey $hostkey $user $remote_cmd

Write-Host "✅ Deploy concluído com sucesso!" -ForegroundColor Green
Write-Host "💡 Dica: Para ver os logs, use o comando de monitoramento: plink -batch -hostkey $hostkey -t -ssh $user -pw $pass `"cd Btc_bot && docker compose logs --tail=50 -f btc-master-bot`""
