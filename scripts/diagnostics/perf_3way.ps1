# Temporary PixelScope three-version performance regression harness.
# Keep the PUBLIC checkout/worktrees separate from INTERNAL sources and Python.
# Internal repository path is supplied at runtime, never stored in public Git.
[CmdletBinding()]
param(
    [ValidateSet("Setup", "Run", "Status")]
    [string]$Action = "Status",
    [ValidateSet("V1", "V2", "V3")]
    [string]$Stage = "V3",
    [string]$PublicRepo = "E:\git\pixelscope_debug\pixelscope",
    [string]$InternalRepo = "",
    [string]$InternalPython = "",
    [string]$CompareRoot = "",
    [double]$TraceThresholdMs = 5,
    [switch]$NoProbe
)

$ErrorActionPreference = "Stop"
$versions = [ordered]@{
    V1 = @{ sha = "36f672b6f63943c292ff2ef788f3a1b4ff899031"; title = "Before additive Quick Compare" }
    V2 = @{ sha = "00b7dd77f320adee7a9d681902bb19d86480ea4c"; title = "After additive Quick Compare" }
    V3 = @{ sha = "21c3158c18b01f4f50b322f8e908ec05a85a36a0"; title = "After PR 187" }
}
$PublicRepo = (Resolve-Path -LiteralPath $PublicRepo).Path
if (-not $CompareRoot) {
    $CompareRoot = Join-Path (Split-Path -Parent $PublicRepo) "perf_three_way"
}
$treeRoot = Join-Path $CompareRoot "worktrees"
$logRoot = Join-Path $CompareRoot "logs"
$probe = Join-Path $PSScriptRoot "perf_3way_probe.py"

function Invoke-GitChecked([string[]]$GitArgs) {
    & git -C $PublicRepo @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "git command failed: $($GitArgs -join ' ')" }
}
function Resolve-InternalPython {
    if ($InternalPython) {
        $candidate = $InternalPython
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            throw "Internal Python not found: $candidate"
        }
        return (Resolve-Path -LiteralPath $candidate).Path
    }
    $candidates = @()
    if ($InternalRepo) {
        if (-not (Test-Path -LiteralPath $InternalRepo -PathType Container)) {
            throw "InternalRepo does not exist: $InternalRepo"
        }
        $internalCheckoutRoot = (Resolve-Path -LiteralPath $InternalRepo).Path
        $candidates += (Join-Path $internalCheckoutRoot ".venv\Scripts\python.exe")
        $candidates += (Join-Path $internalCheckoutRoot "venv\Scripts\python.exe")
        $candidates += (Join-Path (Split-Path -Parent $internalCheckoutRoot) ".venv\Scripts\python.exe")
        $candidates += (Join-Path (Split-Path -Parent $internalCheckoutRoot) "venv\Scripts\python.exe")
    }
    if ($env:VIRTUAL_ENV) {
        $candidates += (Join-Path $env:VIRTUAL_ENV "Scripts\python.exe")
    }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw "No internal Python found. Supply -InternalRepo or the exact -InternalPython path. Searched: $($candidates -join '; ')"
}

# Verify we are operating on the public checkout, never on an internal Git repo.
$origin = (& git -C $PublicRepo remote get-url origin 2>$null)
if ($LASTEXITCODE -ne 0 -or ($origin -notmatch 'delphykmc[/\\]pixelscope(\.git)?$')) {
    throw "PublicRepo origin mismatch: $origin. Refusing to create diagnostic worktrees."
}

if ($Action -eq "Status") {
    Write-Host "PUBLIC REPOSITORY (source only): $PublicRepo"
    Write-Host "COMPARE ROOT: $CompareRoot"
    foreach ($key in $versions.Keys) {
        $path = Join-Path $treeRoot $key
        $exists = Test-Path -LiteralPath $path -PathType Container
        Write-Host "$key / $($versions[$key].sha.Substring(0, 7)) / present=$exists / $path"
    }
    Write-Host "Run -Action Setup once, then -Action Run -Stage V1, V2, V3."
    return
}

if ($Action -eq "Setup") {
    New-Item -ItemType Directory -Force -Path $treeRoot, $logRoot | Out-Null
    foreach ($key in $versions.Keys) {
        $entry = $versions[$key]
        $path = Join-Path $treeRoot $key
        if (Test-Path -LiteralPath $path) {
            $actual = (& git -C $path rev-parse HEAD 2>$null)
            if ($LASTEXITCODE -ne 0 -or $actual.Trim() -ne $entry.sha) {
                throw "$key exists but has a different revision or is not a Git worktree: $path"
            }
            Write-Host "$key already pinned at $($entry.sha.Substring(0,7))"
            continue
        }

        & git -C $PublicRepo cat-file -e "$($entry.sha)^{commit}" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Fetching public objects needed for $key..."
            Invoke-GitChecked @("fetch", "--no-tags", "origin", "main")
            & git -C $PublicRepo cat-file -e "$($entry.sha)^{commit}" 2>$null
            if ($LASTEXITCODE -ne 0) {
                Invoke-GitChecked @("fetch", "--no-tags", "origin", $entry.sha)
            }
        }
        Invoke-GitChecked @("worktree", "add", "--detach", $path, $entry.sha)
        Write-Host "$key ready: $path ($($entry.sha.Substring(0,7)))"
    }
    Write-Host "Setup complete. No checkout or branch switch performed in either original repository."
    return
}

$python = Resolve-InternalPython
$tree = Join-Path $treeRoot $Stage
if (-not (Test-Path -LiteralPath $tree -PathType Container)) {
    throw "Stage $Stage does not exist; first run -Action Setup"
}
$actualSha = (& git -C $tree rev-parse HEAD)
if ($LASTEXITCODE -ne 0 -or $actualSha.Trim() -ne $versions[$Stage].sha) {
    throw "Stage $Stage HEAD differs from the pinned reference"
}
if ($env:QT_QPA_PLATFORM -eq "offscreen") {
    throw "QT_QPA_PLATFORM=offscreen prevents a visual test. Remove it in this PowerShell session."
}
if ($TraceThresholdMs -lt 0) { throw "TraceThresholdMs must be nonnegative" }
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$log = Join-Path $logRoot ("$Stage-$stamp.log")
$settingsDir = Join-Path $CompareRoot ("settings\" + $Stage)
New-Item -ItemType Directory -Force -Path $settingsDir | Out-Null

$vars = @(
    "PYTHONPATH", "PYTHONNOUSERSITE", "PYTHONUNBUFFERED",
    "PIXELSCOPE_LOAD_TRACE", "PIXELSCOPE_ANALYSIS_TRACE",
    "PIXELSCOPE_DIAG_SRC", "PIXELSCOPE_DIAG_STAGE",
    "PIXELSCOPE_DIAG_SETTINGS", "PIXELSCOPE_DIAG_MIN_MS",
    "PIXELSCOPE_DIAG_NO_PROBE"
)
$saved = @{}
foreach ($var in $vars) {
    $saved[$var] = [Environment]::GetEnvironmentVariable($var, "Process")
}
try {
    # One interpreter from the INTERNAL environment; every pixelscope import
    # is forced to the pinned PUBLIC worktree (never its editable installation).
    $env:PYTHONPATH = Join-Path $tree "src"
    $env:PYTHONNOUSERSITE = "1"
    $env:PYTHONUNBUFFERED = "1"
    $env:PIXELSCOPE_LOAD_TRACE = "1"
    $env:PIXELSCOPE_ANALYSIS_TRACE = "1"
    $env:PIXELSCOPE_DIAG_SRC = $env:PYTHONPATH
    $env:PIXELSCOPE_DIAG_STAGE = $Stage
    $env:PIXELSCOPE_DIAG_SETTINGS = $settingsDir
    $env:PIXELSCOPE_DIAG_MIN_MS = [string]$TraceThresholdMs
    $env:PIXELSCOPE_DIAG_NO_PROBE = if ($NoProbe) { "1" } else { "0" }

    Write-Host "STAGE: $Stage / $($versions[$Stage].sha.Substring(0,7))"
    Write-Host "PUBLIC SOURCE: $env:PIXELSCOPE_DIAG_SRC"
    Write-Host "INTERNAL PYTHON: $python"
    Write-Host "ISOLATED QSettings: $settingsDir"
    Write-Host "OUTPUT LOG: $log"
    Write-Host "Complete manual scenarios and close PixelScope to see the per-method summary."
    Push-Location $tree
    try {
        & $python $probe 2>&1 | Tee-Object -FilePath $log
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($exitCode -ne 0) { throw "Stage $Stage exited with code $exitCode. Check $log" }
} finally {
    foreach ($var in $vars) {
        [Environment]::SetEnvironmentVariable($var, $saved[$var], "Process")
    }
}
