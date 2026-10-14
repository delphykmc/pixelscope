# Host-only orchestrator. Never invokes a PixelScope installer on the host.
[CmdletBinding()]
param(
    [string]$CoreInstaller = "$PSScriptRoot\..\release\PixelScope-0.1.0-windows-x64-setup.exe",
    [string]$DownstreamInstaller = "$PSScriptRoot\..\release\PixelScopeTestEdition-0.1.0.1-windows-x64-setup.exe",
    [string]$Descriptor = "$PSScriptRoot\..\issue176-vm.json",
    [string]$UpgradeInstaller,
    [string]$ExpectedUpgradeSha256,
    [string]$ExpectedDownstreamSha256 = '30441EC0BAB8952C19D83BAA65BB3E38C3333C6918E0233FA188BA25B00D6D56',
    [string]$ExpectedHead = 'dce97be97b70973b7400ecd7b6706e8b74f6ee4f',
    [string]$OutputParent = 'C:\Users\Public\Documents\ESTsoft\CreatorTemp\PixelScopeSandbox',
    [ValidateSet('B1','B4','C1','D1','D2','D3','D4','D5','D6','D7','D8','D9')][string[]]$Cases = @('B1','B4','C1'),
    [ValidateRange(60,1800)][int]$TimeoutSeconds = 420,
    [switch]$PrepareOnly
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function File-Sha256([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','') }
    finally { $sha.Dispose(); $stream.Dispose() }
}
function Assert-NoReparse([string]$Path) {
    $item = Get-Item -LiteralPath $Path
    while ($null -ne $item) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse paths are forbidden.' }
        $item = $item.Parent
    }
}
$repo = (Resolve-Path "$PSScriptRoot\..").Path
$head = (& git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Implementation HEAD mismatch.' }
if ($head -ne $ExpectedHead) {
    try { & git -C $repo merge-base --is-ancestor $ExpectedHead HEAD 2>$null }
    catch { throw 'Implementation HEAD mismatch.' }
    if ($LASTEXITCODE -ne 0) { throw 'Implementation HEAD mismatch.' }
}
# Harness/docs-only descendant commits may retain the reviewed installer fixture.
# Refuse any changed production input, including uncommitted tracked changes.
$productionChanges = @(& git -C $repo diff --name-only $ExpectedHead -- src packaging requirements scripts)
if ($LASTEXITCODE -ne 0 -or @($productionChanges | Where-Object { $_ -notin @('scripts/sandbox-runner.ps1','scripts/sandbox-guest.ps1') }).Count -gt 0) {
    throw 'Implementation HEAD mismatch: production inputs changed.'
}
if ($ExpectedDownstreamSha256 -notmatch '^[0-9a-fA-F]{64}$') { throw 'Invalid SHA-256.' }
$parent = [IO.Path]::GetFullPath($OutputParent).TrimEnd('\')
if ($parent -eq $repo -or $parent.StartsWith($repo + '\', [StringComparison]::OrdinalIgnoreCase) -or
    $repo.StartsWith($parent + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Output must be outside the repository and its ancestors.' }
foreach ($path in @($CoreInstaller,$DownstreamInstaller,$Descriptor)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Input file missing.' }
    # Check file and containing directory separately (FileInfo has no Parent).
    if ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse input.' }
    Assert-NoReparse (Split-Path (Resolve-Path -LiteralPath $path).Path)
}
$downHash = (File-Sha256 $DownstreamInstaller)
if ($downHash -ne $ExpectedDownstreamSha256) { throw 'Downstream installer hash mismatch.' }
if ('D7' -in $Cases) {
    if (-not $UpgradeInstaller -or $ExpectedUpgradeSha256 -notmatch '^[0-9a-fA-F]{64}$') { throw 'D7 requires a separately reviewed revision 2 installer and SHA-256.' }
    if ((File-Sha256 $UpgradeInstaller) -ne $ExpectedUpgradeSha256) { throw 'Upgrade installer hash mismatch.' }
    if ((Get-Item -LiteralPath $UpgradeInstaller).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse upgrade input.' }
    Assert-NoReparse (Split-Path (Resolve-Path -LiteralPath $UpgradeInstaller).Path)
}
$target = Get-Content -LiteralPath $Descriptor -Raw | ConvertFrom-Json
if ($target.app_dir -ne 'PixelScopeTestEdition' -or $target.executable -ne 'PixelScopeTestEdition.exe' -or
    $target.installer_app_id -ne '{A6C3E629-46AC-4061-841B-46F61ECD0AB3}' -or $target.release_revision -ne 1) {
    throw 'This acceptance fixture requires the reviewed disposable descriptor.'
}
if (-not $PrepareOnly -and (Get-Process -Name 'WindowsSandbox*' -ErrorAction SilentlyContinue)) { throw 'Close the existing Sandbox before starting fresh cases.' }
$existingParent = $parent
while (-not (Test-Path -LiteralPath $existingParent)) {
    $existingParent = Split-Path $existingParent -Parent
    if (-not $existingParent) { throw 'Output parent has no accessible existing ancestor.' }
}
Assert-NoReparse $existingParent
if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }
Assert-NoReparse $parent
$run = Join-Path $parent ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N'))
$inputDir = New-Item -ItemType Directory -Path (Join-Path $run 'input')
Copy-Item -LiteralPath $CoreInstaller -Destination "$inputDir\core-setup.exe"
Copy-Item -LiteralPath $DownstreamInstaller -Destination "$inputDir\downstream-setup.exe"
Copy-Item -LiteralPath "$PSScriptRoot\sandbox-guest.ps1" -Destination "$inputDir\sandbox-guest.ps1"
Copy-Item -LiteralPath "$repo\packaging\installer\verify_downstream_payload.ps1" -Destination "$inputDir\verify_downstream_payload.ps1"
if ('D7' -in $Cases) { Copy-Item -LiteralPath $UpgradeInstaller -Destination "$inputDir\upgrade-setup.exe" }
$config = @{ Head=$ExpectedHead; HarnessHead=$head; DownstreamSha256=$downHash; CoreSha256=(File-Sha256 $CoreInstaller);
    Descriptor=$target; TimeoutSeconds=$TimeoutSeconds; RunId=(Split-Path $run -Leaf); UpgradeSha256=$ExpectedUpgradeSha256 }
$config | ConvertTo-Json -Depth 8 | Set-Content "$inputDir\config.json" -Encoding UTF8
$summary = @()
foreach ($case in $Cases) {
    $out = New-Item -ItemType Directory -Path (Join-Path $run $case)
    $inXml = [Security.SecurityElement]::Escape($inputDir.FullName)
    $outXml = [Security.SecurityElement]::Escape($out.FullName)
    $wsb = Join-Path $run "$case.wsb"
    @"
<Configuration>
  <Networking>Disable</Networking><ClipboardRedirection>Disable</ClipboardRedirection>
  <AudioInput>Disable</AudioInput><VideoInput>Disable</VideoInput><PrinterRedirection>Disable</PrinterRedirection>
  <MappedFolders>
    <MappedFolder><HostFolder>$inXml</HostFolder><SandboxFolder>C:\PixelScopeInput</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
    <MappedFolder><HostFolder>$outXml</HostFolder><SandboxFolder>C:\PixelScopeOutput</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder>
  </MappedFolders>
  <LogonCommand><Command>powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\PixelScopeInput\sandbox-guest.ps1 -Case $case</Command></LogonCommand>
</Configuration>
"@ | Set-Content -LiteralPath $wsb -Encoding UTF8
    if ($PrepareOnly) { continue }
    if (Get-Process -Name 'WindowsSandbox*' -ErrorAction SilentlyContinue) { throw 'Sandbox still active; fresh-instance guarantee unavailable.' }
    # Only WindowsSandbox.exe is launched on the HOST. Its guest owns installation.
    $launcher = Start-Process -FilePath "$env:WINDIR\System32\WindowsSandbox.exe" -ArgumentList ('"' + $wsb + '"') -PassThru
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds + 120)
    while (-not (Test-Path "$out\result.json") -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 2 }
    if (Test-Path "$out\result.json") {
        $result = Get-Content "$out\result.json" -Raw | ConvertFrom-Json
        $summary += $result
        Write-Host "$case : $($result.Verdict) exit=$($result.ExitCode) $($result.Reason)"
    } else {
        $summary += [pscustomobject]@{ Case=$case; Verdict='BLOCKED'; ExitCode=$null; Reason='No guest result before host timeout; inspect Sandbox startup.' }
    }
    $summary | ConvertTo-Json -Depth 12 | Set-Content "$run\summary.json" -Encoding UTF8
    # Never kill an unrelated/pre-existing session. Guest requests shutdown itself.
    $closeDeadline = (Get-Date).AddSeconds(60)
    while ((Get-Process -Name 'WindowsSandbox*' -ErrorAction SilentlyContinue) -and (Get-Date) -lt $closeDeadline) { Start-Sleep -Seconds 2 }
    if (Get-Process -Name 'WindowsSandbox*' -ErrorAction SilentlyContinue) { Write-Warning 'Sandbox did not close. Remaining cases not started.'; break }
}
Write-Host "Evidence: $run"
if (-not $PrepareOnly) {
    $lines = @('# PixelScope Sandbox acceptance', '', "Implementation HEAD: ``$ExpectedHead``", '', "Harness checkout HEAD: ``$head``", '',
        "Downstream installer SHA-256: ``$downHash``", '',
        '| Case | Verdict | ExitCode | Evidence |', '| --- | --- | --- | --- |')
    foreach ($case in $Cases) {
        $entry = @($summary | Where-Object Case -eq $case)
        if ($entry.Count -eq 1) {
            $lines += "| $case | $($entry[0].Verdict) | $($entry[0].ExitCode) | $case/result.json and installer logs |"
        } else { $lines += "| $case | NOT RUN | | Fresh Sandbox unavailable |" }
    }
    $lines += @('', 'Raw JSON and installer logs are authoritative. BLOCKED and NOT RUN are not PASS.',
        'Check each case snapshot and log for the exact fault/checkpoint and retry scope.',
        'No host installer execution, release rebuild, manifest change, publication or merge was performed.')
    $lines | Set-Content "$run\report.md" -Encoding UTF8
}
if (-not $PrepareOnly -and (@($summary | Where-Object Verdict -ne 'PASS').Count -gt 0 -or $summary.Count -ne $Cases.Count)) { exit 2 }
