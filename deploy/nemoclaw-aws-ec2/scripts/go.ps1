# One-shot: preflight -> terraform init -> plan (optional apply).
param(
    [switch]$Apply,
    [string]$Profile = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

if (-not $Profile -and (Test-Path "$root\terraform.tfvars")) {
    $line = Get-Content "$root\terraform.tfvars" -ErrorAction SilentlyContinue |
    Where-Object { $_ -match '^\s*aws_profile\s*=' } |
    Select-Object -First 1
    if ($line -match '=\s*"([^"]*)"') {
        $parsed = $Matches[1].Trim()
        if ($parsed) {
            $Profile = $parsed
        }
    }
}

if ($Profile) {
    $env:AWS_PROFILE = $Profile
    Write-Host "Using AWS_PROFILE=$Profile"
}

$hostExe = (Get-Process -Id $PID).Path
$preflightArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "$PSScriptRoot\preflight-aws.ps1")
if ($Profile) {
    $preflightArgs += @("-Profile", $Profile)
}
$preflightProc = Start-Process -FilePath $hostExe -ArgumentList $preflightArgs -Wait -PassThru -NoNewWindow
if ($preflightProc.ExitCode -ne 0) {
    exit $preflightProc.ExitCode
}

terraform init -upgrade
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($Apply) {
    terraform apply -auto-approve
} else {
    terraform plan -out=tfplan
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "Plan saved to tfplan. To apply: terraform apply tfplan"
        Write-Host "Or re-run: .\scripts\go.ps1 -Apply"
    }
}
