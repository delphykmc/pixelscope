# PixelScope PR #213: Windows Qt/COM lifecycle diagnostic.
# Non-invasive: no production edits, no GC disabling, no skipped tests.
# Run from this repository's root with .venv installed (Python 3.10).
# powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\diagnostics\pr213_native_lifecycle.ps1 -Mode Focused
# Valid modes: Focused, W02, Full, PassiveGC. Output goes to %TEMP%.
[CmdletBinding()]
param(
    [ValidateSet('Focused','W02','Full','PassiveGC')]
    [string]$Mode = 'Focused',
    [string]$Repo = '.',
    [string]$OutputBase = ''
)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Run in a Windows desktop session.' }

$rootResult = & git -C $Repo rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0 -or -not $rootResult) { throw "Not a Git checkout: $Repo" }
$root = [string]($rootResult | Select-Object -First 1)
$root = $root.Trim()
$sha = [string]((& git -C $root rev-parse HEAD) | Select-Object -First 1)
$sha = $sha.Trim()
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw ("Missing worktree-local Python: " + $python + ". Install requirements/runtime.txt, requirements/dev.txt, then pip install -e .")
}
if (-not $OutputBase) { $OutputBase = Join-Path $env:TEMP 'pixelscope-diagnostics' }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$output = Join-Path $OutputBase ("{0}-{1}-{2}" -f $Mode,$sha.Substring(0,8),$stamp)
$rootPrefix = [IO.Path]::GetFullPath($root).TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar
$output = [IO.Path]::GetFullPath($output)
if ($output.StartsWith($rootPrefix,[StringComparison]::OrdinalIgnoreCase)) {
    throw "Place diagnostics outside the Git worktree: $output"
}
New-Item -ItemType Directory -Force -Path $output | Out-Null
$baseTemp = Join-Path $output 'pytest-temp'
$log = Join-Path $output 'pytest-console.log'
$junit = Join-Path $output 'junit.xml'
$gcLog = Join-Path $output 'gc_passive.tsv'
$gcSummary = Join-Path $output 'gc_passive_summary.txt'
$gcFatal = Join-Path $output 'gc_passive_fatal.log'

# Force imported source to this worktree and remove inherited CI-only pytest flags.
$env:PYTHONPATH = Join-Path $root 'src'
$env:PYTHONFAULTHANDLER = '1'
$env:PYTHONUNBUFFERED = '1'
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue
Push-Location $root
try {
    # Windows PowerShell 5.1 can remove embedded double quotes from native
    # python -c arguments. Avoid nested quote characters altogether.
    # Also preserve Python stderr as diagnostic output without PowerShell
    # promoting NativeCommandError to a terminating script error.
    $ErrorActionPreference = 'Continue'
    $versions = (& $python -c 'import sys, PySide6, pyqtgraph, pixelscope; print(sys.version.split()[0], PySide6.__version__, pyqtgraph.__version__, pixelscope.__file__)' 2>&1 | Out-String).Trim()
    $preflightExit = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($preflightExit -ne 0) { throw "Python preflight failed (exit=$preflightExit): $versions" }
    $gitStatus = (& git status --short | Out-String).Trim()
    @(
        "timestamp=$(Get-Date -Format o)"
        "mode=$Mode"
        "head=$sha"
        "repo=$root"
        "output=$output"
        "git_status=$gitStatus"
        "$versions"
        "PYTHONPATH=$env:PYTHONPATH"
        "normal_automatic_gc=True"
        "QT_QPA_PLATFORM=unset"
        "PYTEST_ADDOPTS=unset"
    ) | Set-Content -Encoding UTF8 (Join-Path $output 'metadata.txt')

    $tests = @('-vv','--tb=short',"--basetemp=$baseTemp","--junitxml=$junit")
    switch ($Mode) {
        'Focused' {
            $tests += @(
                'tests/ui/test_background_work_lifecycle.py'
                'tests/ui/test_wp_c2_yuv_difference.py'
                'tests/ui/test_issue81_qt_lifecycle.py'
                'tests/ui/test_issue121_qt_gc_lifecycle.py'
                'tests/ui/test_clipboard_support.py'
                'tests/ui/test_p4e_analysis_productivity.py'
            )
        }
        'W02' {
            $tests += @(
                'tests/unit/test_review_analysis_bundle.py'
                'tests/unit/test_analysis_export.py'
                'tests/unit/test_analysis_export_metrics.py'
                'tests/ui/test_w02b_presented_analysis.py'
                'tests/ui/test_p4e_analysis_export.py'
                'tests/ui/test_wp_c1_yuv_semantics.py'
                'tests/ui/test_wp_c2_yuv_difference.py'
            )
        }
        'Full' { }
        'PassiveGC' { }
    }
    if ($Mode -eq 'PassiveGC') {
        $argv = @('-u','-X','faulthandler','-m','scripts.diagnose_gc_passive',
            '--gc-log',$gcLog,'--summary',$gcSummary,'--fatal-log',$gcFatal) + $tests
    } else {
        $argv = @('-u','-X','faulthandler','-m','pytest') + $tests
    }
    Write-Host "Mode=$Mode HEAD=$sha"
    Write-Host "Log directory: $output"
    Write-Host "Command: $python $($argv -join ' ')"
    # Windows PowerShell 5.1 may turn native stderr into ErrorRecords.
    $ErrorActionPreference = 'Continue'
    & $python @argv 2>&1 | Tee-Object -FilePath $log
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    "pytest_exit=$exitCode" | Set-Content -Encoding ASCII (Join-Path $output 'exitcode.txt')

    $paths = @($log)
    if (Test-Path -LiteralPath $gcFatal) { $paths += $gcFatal }
    $pattern = '0x8001010d|0x80010108|0xc0000005|0xc0000374|Windows fatal exception|OleFlushClipboard|OleSetClipboard|E_ACCESSDENIED'
    $matches = @(Select-String -Path $paths -Pattern $pattern -Context 12,22)
    $exceptionReport = Join-Path $output 'native-exception-context.txt'
    if ($matches.Count -gt 0) {
        $matches | Out-String -Width 260 | Set-Content -Encoding UTF8 $exceptionReport
        Write-Warning "Native/COM exception patterns found: $exceptionReport"
    } else {
        'No known native/COM exception pattern matched the selected logs.' |
            Set-Content -Encoding UTF8 $exceptionReport
    }
    Write-Host "Exit code: $exitCode"
    Write-Host "Share (after removing private paths): metadata.txt, exitcode.txt, junit.xml, pytest-console.log, native-exception-context.txt"
    if ($Mode -eq 'PassiveGC') {
        Write-Host "Additional: gc_passive.tsv, gc_passive_summary.txt, gc_passive_fatal.log"
    }
    exit $exitCode
} finally {
    Pop-Location
}
