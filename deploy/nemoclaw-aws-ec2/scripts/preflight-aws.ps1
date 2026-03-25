# Verifies AWS CLI and credentials before terraform apply.
param(
    [string]$Profile = ""
)

$ErrorActionPreference = "Stop"

$aws = Get-Command aws -ErrorAction SilentlyContinue
if (-not $aws) {
    $candidates = @(
        "$env:ProgramFiles\Amazon\AWSCLIV2\aws.exe",
        "${env:ProgramFiles(x86)}\Amazon\AWSCLIV2\aws.exe"
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) {
            $aws = @{ Source = $p }
            break
        }
    }
}

if (-not $aws) {
    Write-Error "AWS CLI not found. Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
}

$exe = if ($aws.Source) { $aws.Source } else { $aws.Path }
Write-Host "Using: $exe"

$profileArgs = @()
$activeProfile = $Profile
if (-not $activeProfile -and $env:AWS_PROFILE) {
    $activeProfile = $env:AWS_PROFILE
}
if ($activeProfile) {
    $profileArgs = @("--profile", $activeProfile)
    Write-Host "Profile: $activeProfile"
}

$keyId = & $exe configure get aws_access_key_id @profileArgs 2>$null
if ($keyId) {
    $keyId = $keyId.Trim()
}
if (-not $keyId -or $keyId -eq "None") {
    Write-Host "No aws_access_key_id in this profile. Run: aws configure"
    exit 1
}
if ($keyId -notmatch '^(AKIA|ASIA)[A-Z0-9]{16}$') {
    Write-Host "Invalid Access Key ID format: expected 20 chars starting with AKIA or ASIA (from IAM), not a username or password."
    Write-Host "Current value looks wrong. Create keys: IAM console -> Users -> Security credentials -> Create access key."
    exit 1
}

$secret = & $exe configure get aws_secret_access_key @profileArgs 2>$null
if ($secret) {
    $secret = $secret.Trim()
}
if (-not $secret -or $secret -eq "None" -or $secret.Length -lt 30) {
    Write-Host "Secret access key missing or too short. AWS secrets are ~40 characters; paste the full value from IAM (Show) when you create the key."
    exit 1
}

& $exe sts get-caller-identity @profileArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Fix: create IAM access keys in the AWS console, then run:"
    Write-Host "  aws configure"
    Write-Host "Or set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (and AWS_SESSION_TOKEN if temporary) in this shell."
    exit 1
}

Write-Host "OK - credentials valid for Terraform."
