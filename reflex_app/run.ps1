$env:PATH = "C:\Program Files\nodejs;$env:PATH"
$env:REACT_ROUTER_DEV_RESTARTED = "true"

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)=(.*)$') {
            Set-Item -Path "env:$($Matches[1].Trim())" -Value $Matches[2].Trim()
        }
    }
}

if (-not $env:VFCLOUD_URL) { $env:VFCLOUD_URL = Read-Host "URL do Web App (/exec)" }
if (-not $env:VFCLOUD_USUARIO) { $env:VFCLOUD_USUARIO = Read-Host "Usuario" }
if (-not $env:VFCLOUD_SENHA) { $env:VFCLOUD_SENHA = Read-Host "Senha" }

Write-Host "Iniciando Visualfil Reflex em http://localhost:3000" -ForegroundColor Cyan
python -m reflex run
