# Clone full NVIDIA/NemoClaw repo and overlay autonomy Dockerfile + sandbox policy, then print docker build command.
# Run from PowerShell (Docker Desktop running):
#   cd G:\NeMo-Agent-Toolkit\deploy\nemoclaw-aws-ec2\scripts
#   .\bootstrap-nemoclaw-docker-context.ps1
#
# Optional: -Dest "D:\work\NemoClaw-build"
param(
    [string] $Dest = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DeployRoot = Split-Path -Parent $ScriptDir

if (-not $Dest) {
    $Dest = Join-Path $DeployRoot "NemoClaw-build"
}

$RepoUrl = "https://github.com/NVIDIA/NemoClaw.git"

if (-not (Test-Path (Join-Path $Dest ".git"))) {
    New-Item -ItemType Directory -Force -Path (Split-Path $Dest -Parent) | Out-Null
    if (Test-Path $Dest) {
        Remove-Item -Recurse -Force $Dest
    }
    Write-Host "Cloning $RepoUrl -> $Dest"
    git clone --depth 1 $RepoUrl $Dest
} else {
    Write-Host "Repo exists, pull latest: $Dest"
    Push-Location $Dest
    try {
        git pull --ff-only
    } finally {
        Pop-Location
    }
}

$OurDockerfile = Join-Path $DeployRoot "NemoClaw\Dockerfile"
$OurPolicy = Join-Path $DeployRoot "nemoclaw-blueprint\policies\openclaw-sandbox.yaml"

if (-not (Test-Path $OurDockerfile)) { throw "Missing autonomy Dockerfile: $OurDockerfile" }
if (-not (Test-Path $OurPolicy)) { throw "Missing policy: $OurPolicy" }

Copy-Item -Force $OurDockerfile (Join-Path $Dest "Dockerfile")
New-Item -ItemType Directory -Force -Path (Join-Path $Dest "nemoclaw-blueprint\policies") | Out-Null
Copy-Item -Force $OurPolicy (Join-Path $Dest "nemoclaw-blueprint\policies\openclaw-sandbox.yaml")

Write-Host ""
Write-Host "OK. Build from repo root:"
Write-Host "  cd `"$Dest`""
Write-Host "  docker build -f Dockerfile -t nemoclaw-sandbox:local ."
