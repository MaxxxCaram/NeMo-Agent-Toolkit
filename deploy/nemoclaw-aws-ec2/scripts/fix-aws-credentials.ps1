# Respalda y quita credentials/config rotos para que "aws configure" vuelva a funcionar.
# No escribe claves secretas: despues debes ejecutar aws configure o pegar keys nuevas.
param(
    [switch]$RunConfigure
)

$ErrorActionPreference = "Stop"
$awsDir = Join-Path $env:USERPROFILE ".aws"
New-Item -ItemType Directory -Force -Path $awsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$files = @("credentials", "config")

foreach ($name in $files) {
    $path = Join-Path $awsDir $name
    if (Test-Path -LiteralPath $path) {
        $bak = Join-Path $awsDir "${name}.broken-${stamp}.bak"
        Copy-Item -LiteralPath $path -Destination $bak -Force
        Remove-Item -LiteralPath $path -Force
        Write-Host "OK: respaldado y eliminado: $path -> $bak"
    }
    else {
        Write-Host "OK: no existia $path"
    }
}

Write-Host ""
Write-Host "Siguiente paso (elige uno):"
Write-Host "  1) Interactivo:  aws configure"
Write-Host "     - AWS Access Key ID y Secret Access Key (crea keys NUEVAS en IAM si las filtraste)"
Write-Host "     - Default region: la misma que en terraform.tfvars (ej. us-east-1)"
Write-Host "     - Default output: json"
Write-Host ""
Write-Host "  2) Probar:        aws sts get-caller-identity"
Write-Host ""

if ($RunConfigure) {
    $aws = Get-Command aws -ErrorAction SilentlyContinue
    if (-not $aws) {
        Write-Error "AWS CLI no encontrado en PATH."
    }
    & aws configure
    Write-Host ""
    & aws sts get-caller-identity
}
