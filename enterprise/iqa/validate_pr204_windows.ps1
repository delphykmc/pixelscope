# PixelScope PR #204 owner-local Windows regression validation.
# Source under test: PR #204 at 0b19620e27e7709a5b81515bc345994d47f12a39.
# This QA-only commit adds this script to the PR head; it is NOT a Handoff release.
#
# From a Windows checkout of qa/enterprise-iqa-pr204-windows-20261021:
#   & .\enterprise\iqa\validate_pr204_windows.ps1 -PythonPath "E:\venvs\pixelscope\Scripts\python.exe"
# Or provide -RepoPath pointing to the checkout. Python must include pytest-qt.

param(
    [string]$PythonPath = 'python',
    [string]$RepoPath = (Get-Location).Path
)

$ErrorActionPreference = 'Stop'
$expectedCodeCommit = '0b19620e27e7709a5b81515bc345994d47f12a39'
$scriptPath = 'enterprise/iqa/validate_pr204_windows.ps1'
$originalLocation = (Get-Location).Path
$originalPythonPath = $env:PYTHONPATH
$originalQtPlatform = $env:QT_QPA_PLATFORM
$transcriptStarted = $false
$logs = Join-Path ([System.IO.Path]::GetTempPath()) ('pixelscope_pr204_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))

# Resolve a relative executable path BEFORE changing directories.
if (Test-Path -LiteralPath $PythonPath -PathType Leaf) {
    $PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
}
$RepoPath = (Resolve-Path -LiteralPath $RepoPath).Path

try {
    New-Item -ItemType Directory -Force -Path $logs | Out-Null
    Start-Transcript -Path (Join-Path $logs 'test-transcript.txt') -Force | Out-Null
    $transcriptStarted = $true
    Set-Location -LiteralPath $RepoPath

    $actualHead = (& git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot determine checked-out Git HEAD.' }

    if ($actualHead -ne $expectedCodeCommit) {
        $parentHead = (& git rev-parse 'HEAD^').Trim()
        if ($LASTEXITCODE -ne 0 -or $parentHead -ne $expectedCodeCommit) {
            throw "Unexpected code baseline: HEAD=$actualHead. Expected PR #204 commit or its direct QA-script child."
        }
        $changed = @(& git diff --name-only $expectedCodeCommit HEAD)
        if ($LASTEXITCODE -ne 0 -or $changed.Count -ne 1 -or $changed[0] -ne $scriptPath) {
            throw 'QA branch must differ from PR #204 only by this validation script.'
        }
    }

    $trackedChanges = @(& git status --porcelain --untracked-files=no)
    if ($LASTEXITCODE -ne 0 -or $trackedChanges.Count -ne 0) {
        throw 'Tracked files have local modifications. Use a clean QA worktree.'
    }

    Write-Host "Code baseline: $expectedCodeCommit"
    Write-Host "Checked-out HEAD: $actualHead"
    Write-Host "Repo: $RepoPath"
    Write-Host "Python: $PythonPath"

    $env:PYTHONPATH = Join-Path $RepoPath 'src'
    Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    Write-Host 'Using native Windows Qt platform (not offscreen).'

    & $PythonPath -c 'import sys, PySide6; print(sys.version); print("PySide6", PySide6.__version__)'
    if ($LASTEXITCODE -ne 0) { throw 'Python/PySide6 preflight failed.' }
    & $PythonPath -m pytest --version
    if ($LASTEXITCODE -ne 0) { throw 'pytest preflight failed.' }

    $pure = @(
        'tests/enterprise/iqa/test_quality_presentation.py',
        'tests/enterprise/iqa/test_analysis_insights.py',
        'tests/enterprise/iqa/test_analysis_model.py'
    )
    Write-Host '=== Pure-model / quality policy regression ==='
    $baseArgs = @('-m', 'pytest', '-q', '--durations=5', '-W', 'error::DeprecationWarning')
    & $PythonPath @baseArgs @pure
    if ($LASTEXITCODE -ne 0) { throw 'Pure-model / quality-policy regression failed.' }

    # Fresh Python process per native-Qt module: Qt GC and teardown are known risks.
    $nativeModules = @(
        'test_post_integration_feedback_203.py',
        'test_quality_presentation_window.py',
        'test_analysis_integration_req1_req2_req3_req4.py',
        'test_analysis_file_menu_request7.py'
    )
    foreach ($module in $nativeModules) {
        Write-Host "=== Native Qt regression: $module ==="
        & $PythonPath @baseArgs "tests/enterprise/iqa/$module"
        if ($LASTEXITCODE -ne 0) { throw "Native Qt regression failed: $module" }
    }

    Write-Host 'FOCUSED AUTOMATED VALIDATION PASS.'
    Write-Host 'Not covered: physical monitor/mixed DPI acceptance or PRIVATE .pxiqa writer atomicity.'
} catch {
    Write-Host "VALIDATION FAILED: $_"
    throw
} finally {
    if ($transcriptStarted) { Stop-Transcript | Out-Null }
    if ($null -eq $originalPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $originalPythonPath
    }
    if ($null -eq $originalQtPlatform) {
        Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    } else {
        $env:QT_QPA_PLATFORM = $originalQtPlatform
    }
    Set-Location -LiteralPath $originalLocation
    Write-Host "Validation transcript: $(Join-Path $logs 'test-transcript.txt')"
}
