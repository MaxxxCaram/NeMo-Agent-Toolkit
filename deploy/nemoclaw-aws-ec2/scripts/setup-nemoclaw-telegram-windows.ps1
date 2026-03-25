# Installs the real NemoClaw CLI from GitHub (NOT the empty "nemoclaw" package on npmjs.org),
# ensures npm global bin is on your user PATH, saves TELEGRAM_BOT_TOKEN, and prints next steps.
# Requires: Node.js 22+ (https://nodejs.org), Docker Desktop for "nemoclaw onboard" on Windows.
# Run in PowerShell:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force; .\setup-nemoclaw-telegram-windows.ps1
#
# If you see EPERM / ENOENT during npm install: close Cursor/terminals, run this script with
#   -RelocateGlobalPrefix  (uses %LOCALAPPDATA%\nemoclaw-npm-global instead of AppData\Roaming\npm)

[CmdletBinding()]
param(
    # Use a dedicated global prefix under your profile (fewer locks vs AppData\Roaming; helps OneDrive/AV).
    [switch]$RelocateGlobalPrefix,
    # Only install CLI; do not open BotFather or prompt for token.
    [switch]$SkipTelegram
    ,
    # Retry install when Windows locks/delete operations fail (EPERM/ENOTEMPTY are common).
    [int]$MaxRetries = 4,
    # If running as Administrator, temporarily disable Defender real-time scan
    # and add exclusions for the npm prefix/cache to prevent EPERM during npm deletes.
    [switch]$TryDisableDefender
)

$ErrorActionPreference = "Stop"

function Ensure-Dir([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Add-UserPathSegment([string]$Segment) {
    if (-not $Segment) { return }
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*${Segment}*") {
        $newPath = if ($userPath) { "$userPath;$Segment" } else { $Segment }
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        $env:Path = "$env:Path;$Segment"
        Write-Host "Added to user PATH: $Segment (open a new terminal for it to apply everywhere)."
    }
}

function Set-NpmGlobalPrefix {
    param([string]$PrefixRoot)
    $prefixRoot = $PrefixRoot.TrimEnd('\', '/')
    Ensure-Dir $prefixRoot
    # On Windows, npm shims may live in multiple locations depending on npm/node version.
    & npm config set prefix $prefixRoot | Out-Null
    Add-UserPathSegment $prefixRoot
    Add-UserPathSegment (Join-Path $prefixRoot "bin")
    Add-UserPathSegment (Join-Path $prefixRoot "node_modules\\.bin")
}

function Remove-TreeRobocopy {
    param([string]$Target)
    if (-not (Test-Path -LiteralPath $Target)) { return }
    $empty = Join-Path $env:TEMP ("npm-empty-" + [Guid]::NewGuid().ToString("N"))
    try {
        Ensure-Dir $empty
        & robocopy $empty $Target /MIR /R:0 /W:0 /NFL /NDL /NJH /NJS /NP | Out-Null
        Remove-Item -LiteralPath $Target -Recurse -Force -ErrorAction SilentlyContinue
    }
    finally {
        Remove-Item -LiteralPath $empty -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Clear-NpmGlobalPrefixTree {
    param([string]$GlobalModulesRoot)

    Write-Host "Clearing npm global prefix tree..."
    $nodeModules = Join-Path $GlobalModulesRoot "node_modules"
    if (Test-Path -LiteralPath $nodeModules) {
        try {
            Remove-Item -LiteralPath $nodeModules -Recurse -Force -ErrorAction Stop
        }
        catch {
            Write-Warning "Normal delete failed ($($_.Exception.Message)); trying robocopy mirror trick..."
            Remove-TreeRobocopy -Target $nodeModules
        }
    }

    # Leftover shims/entries can break smoke tests.
    foreach ($shim in @("nemoclaw.cmd", "nemoclaw.ps1", "nemoclaw")) {
        $p = Join-Path $GlobalModulesRoot $shim
        if (Test-Path -LiteralPath $p) {
            Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Ensure-GitLongPaths {
    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) { return }
    try {
        & git config --global core.longpaths true 2>$null
    }
    catch {
        # ignore
    }
}

function Test-IsAdministrator {
    $p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Maybe-ConfigureDefenderForNpm {
    param(
        [string]$NpmPrefixRoot,
        [string]$NpmCachePath
    )
    if (-not $TryDisableDefender) { return }
    if (-not (Test-IsAdministrator)) {
        Write-Warning "TryDisableDefender requires Administrator. Running without Defender changes."
        return
    }
    if (-not (Get-Command Add-MpPreference -ErrorAction SilentlyContinue)) { return }

    foreach ($ex in @($NpmPrefixRoot, $NpmCachePath)) {
        if (-not $ex) { continue }
        try {
            Add-MpPreference -ExclusionPath $ex -ErrorAction SilentlyContinue | Out-Null
            Write-Host "Defender exclusion added (best-effort): $ex"
        }
        catch {
            # ignore best-effort
        }
    }
}

function Invoke-WithDefenderRealtimeDisabled {
    param([scriptblock]$Body)

    if (-not $TryDisableDefender) {
        & $Body
        return
    }
    if (-not (Test-IsAdministrator)) {
        Write-Warning "TryDisableDefender requires Administrator. Running without Defender changes."
        & $Body
        return
    }
    if (-not (Get-Command Set-MpPreference -ErrorAction SilentlyContinue)) {
        & $Body
        return
    }

    $wasDisabled = $false
    try {
        $pref = Get-MpPreference -ErrorAction Stop
        $wasDisabled = [bool]$pref.DisableRealtimeMonitoring
    }
    catch {
        $wasDisabled = $false
    }

    try {
        if (-not $wasDisabled) {
            Set-MpPreference -DisableRealtimeMonitoring $true | Out-Null
            Write-Host "Defender real-time monitoring DISABLED (temporary)."
        }
    }
    catch {
        Write-Warning "Could not disable Defender real-time monitoring (continuing)."
    }

    try {
        & $Body
    }
    finally {
        try {
            if (-not $wasDisabled) {
                Set-MpPreference -DisableRealtimeMonitoring $false | Out-Null
                Write-Host "Defender real-time monitoring RESTORED."
            }
        }
        catch {
            # ignore restore errors
        }
    }
}

Write-Host "Checking Node.js..."
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    Write-Host "Node.js not found. Install LTS from https://nodejs.org then re-run this script."
    exit 1
}
& node --version

# Resolve global root: either relocated prefix or default AppData npm folder.
$defaultNpmRoot = Join-Path $env:APPDATA "npm"
if ($RelocateGlobalPrefix) {
    $relocated = Join-Path $env:LOCALAPPDATA "nemoclaw-npm-global"
    Write-Host "Using relocated npm global prefix: $relocated"
    Set-NpmGlobalPrefix -PrefixRoot $relocated
    $globalModulesRoot = $relocated
}
else {
    Ensure-Dir $defaultNpmRoot
    Add-UserPathSegment $defaultNpmRoot
    $globalModulesRoot = $defaultNpmRoot
}

Ensure-GitLongPaths

Invoke-WithDefenderRealtimeDisabled -Body {
    $npmCachePath = (& npm config get cache 2>$null).Trim()
    Maybe-ConfigureDefenderForNpm -NpmPrefixRoot $globalModulesRoot -NpmCachePath $npmCachePath

    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        Write-Host ""
        Write-Host "NemoClaw install attempt $attempt of $MaxRetries..."

        Clear-NpmGlobalPrefixTree -GlobalModulesRoot $globalModulesRoot

        Write-Host "npm cache clean --force..."
        & npm cache clean --force | Out-Null

        Write-Host "Installing NemoClaw CLI from github:NVIDIA/NemoClaw..."
        & npm install -g --no-audit --no-fund "github:NVIDIA/NemoClaw"
        if ($LASTEXITCODE -eq 0) {
            break
        }

        if ($attempt -eq $MaxRetries) {
            Write-Host ""
            Write-Host "Install failed after retries."
            exit $LASTEXITCODE
        }

        Start-Sleep -Seconds 3
    }
}

$nemoclawCmd = $null
$cmd = Get-Command nemoclaw -ErrorAction SilentlyContinue
if ($cmd) {
    $nemoclawCmd = $cmd.Source
}
if (-not $nemoclawCmd) {
    $candidates = @(
        (Join-Path $globalModulesRoot "nemoclaw.cmd"),
        (Join-Path $globalModulesRoot "bin\\nemoclaw.cmd"),
        (Join-Path $globalModulesRoot "node_modules\\.bin\\nemoclaw.cmd")
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) { $nemoclawCmd = $c; break }
    }
}
if (-not $nemoclawCmd) { $nemoclawCmd = "nemoclaw" }

Write-Host ""
Write-Host "Smoke test: nemoclaw --help"
& $nemoclawCmd --help
if ($LASTEXITCODE -ne 0) {
    Write-Warning "nemoclaw --help returned non-zero; check PATH in a NEW terminal."
}

if ($SkipTelegram) {
    Write-Host "SkipTelegram: done."
    exit 0
}

Write-Host ""
Write-Host "Opening BotFather in browser. In Telegram: /newbot and copy the bot token."
Start-Process "https://t.me/BotFather"

$secure = Read-Host "Paste TELEGRAM_BOT_TOKEN here (input hidden)" -AsSecureString
if ($secure.Length -eq 0) {
    Write-Host "No token entered. Set later: [Environment]::SetEnvironmentVariable('TELEGRAM_BOT_TOKEN','YOUR_TOKEN','User')"
    exit 0
}
$BSTR = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($BSTR)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR) | Out-Null
}

[Environment]::SetEnvironmentVariable("TELEGRAM_BOT_TOKEN", $plain, "User")
$plain = $null
$secure.Dispose()

Write-Host ""
Write-Host "Token saved to your Windows user environment (TELEGRAM_BOT_TOKEN)."
Write-Host "Open a NEW PowerShell window, then run:"
Write-Host ""
Write-Host "  1) nemoclaw onboard          # first time only; needs Docker Desktop running"
Write-Host "  2) nemoclaw my-assistant policy-add   # choose telegram preset (adjust name if your sandbox differs)"
Write-Host "  3) nemoclaw start"
Write-Host "  4) nemoclaw status"
Write-Host ""
Write-Host "Docs: https://docs.nvidia.com/nemoclaw/latest/deployment/set-up-telegram-bridge.html"
