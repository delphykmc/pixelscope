# Executable only through the isolated Sandbox LogonCommand.
[CmdletBinding()]
param([Parameter(Mandatory)][ValidateSet('B1','B4','C1','D1','D2','D3','D4','D5','D6','D7','D8','D9')][string]$Case)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function File-Sha256([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','') }
    finally { $sha.Dispose(); $stream.Dispose() }
}
$inputRoot = 'C:\PixelScopeInput'
$outputRoot = 'C:\PixelScopeOutput'
# Fail closed BEFORE logs, installers, UI actions or shutdown on any other machine.
$machine = Get-CimInstance Win32_ComputerSystem
if ($env:USERNAME -ne 'WDAGUtilityAccount' -or $machine.Model -ne 'Virtual Machine' -or
    $machine.Manufacturer -ne 'Microsoft Corporation' -or $PSScriptRoot -ne $inputRoot -or
    -not (Test-Path "$inputRoot\config.json") -or -not (Test-Path $outputRoot)) {
    throw 'Guest isolation identity not established; no actions performed.'
}
$cfg = Get-Content "$inputRoot\config.json" -Raw | ConvertFrom-Json
$result = [ordered]@{ Case=$Case; Verdict='BLOCKED'; ExitCode=$null; Reason='Not completed'; Head=$cfg.Head;
    RunId=$cfg.RunId; DownstreamSha256=$cfg.DownstreamSha256; OS=[Environment]::OSVersion.VersionString;
    Before=$null; After=$null; UiActions=@(); Fault=$null; CoreStillRunning=$null }
$coreRoot = Join-Path $env:LOCALAPPDATA 'Programs\PixelScope'
$downRoot = Join-Path $env:LOCALAPPDATA 'Programs\PixelScopeTestEdition'
$coreKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6FA0AB08-AB41-4F77-93E8-16CE6FF53E5C}_is1'
$downKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{A6C3E629-46AC-4061-841B-46F61ECD0AB3}_is1'
function Registry([string]$Key, [Microsoft.Win32.RegistryView]$View = [Microsoft.Win32.RegistryView]::Registry64) {
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser,$View)
    try {
        $k = $base.OpenSubKey($Key)
        if ($null -eq $k) { return $null }
        try { return @{ DisplayName=$k.GetValue('DisplayName'); DisplayVersion=$k.GetValue('DisplayVersion');
            InstallLocation=$k.GetValue('InstallLocation'); UninstallString=$k.GetValue('UninstallString') } }
        finally { $k.Dispose() }
    } finally { $base.Dispose() }
}
function Exe([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $f = Get-Item -LiteralPath $Path
    return @{ Sha256=(File-Sha256 $Path); FileVersion=$f.VersionInfo.FileVersion; ProductVersion=$f.VersionInfo.ProductVersion }
}
function Snapshot {
    return @{ CoreExe=(Exe "$coreRoot\PixelScope.exe"); DownstreamExe=(Exe "$downRoot\PixelScopeTestEdition.exe");
        CoreRegistry=(Registry $coreKey); CoreRegistry32=(Registry $coreKey Registry32); DownstreamRegistry=(Registry $downKey) }
}
function User-State {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Software\PixelScope\PixelScope')
    try { $marker = if ($key) { $key.GetValue('sandbox_validation_marker') } else { $null } }
    finally { if ($key) { $key.Dispose() } }
    return @{ RegistryMarker=$marker; FileHash=(File-Sha256 "$env:APPDATA\PixelScope\sandbox-validation.txt") }
}
function Downstream-Valid([string]$Version = '0.1.0.1') {
    $a = Snapshot
    if (-not $a.DownstreamExe -or -not $a.DownstreamRegistry -or
        $a.DownstreamExe.FileVersion -ne $Version -or
        $a.DownstreamRegistry.DisplayVersion -ne $Version -or
        $a.DownstreamRegistry.InstallLocation.TrimEnd('\') -ne $downRoot) { return $false }
    $code = Run-Setup "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" (
        '-NoProfile -ExecutionPolicy Bypass -File C:\PixelScopeInput\verify_downstream_payload.ps1' +
        ' -InstallRoot "' + $downRoot + '" -ExpectedProduct "PixelScope Test Edition" -ExpectedVersion ' + $Version + ' -ExpectedExeName PixelScopeTestEdition.exe')
    return $code -eq 0
}
function Retry-Conversion {
    $result.RetryExitCode = Run-Setup "$inputRoot\downstream-setup.exe" '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /ALLOWCORECONVERSION=1 /LOG="C:\PixelScopeOutput\retry-install.log"'
    $result.AfterRetry = Snapshot
    $result.RetryPayloadValid = Downstream-Valid
    return $result.RetryExitCode -eq 0 -and -not $result.AfterRetry.CoreExe -and
        -not $result.AfterRetry.CoreRegistry -and -not (Test-Path "$coreRoot\unins000.exe") -and
        $result.RetryPayloadValid -and
        (Get-Content "$outputRoot\retry-install.log" -Raw).Contains('Verified Core-to-downstream conversion completed')
}
function Run-Setup([string]$Path,[string]$Arguments) {
    $p = Start-Process -FilePath $Path -ArgumentList $Arguments -PassThru
    if (-not $p.WaitForExit($cfg.TimeoutSeconds * 1000)) { throw 'Installer timeout; no PASS.' }
    $p.Refresh()
    return $p.ExitCode
}
function Installer-Windows([int]$RootPid) {
    $ids = @($RootPid)
    $processes = @(Get-CimInstance Win32_Process)
    for ($i=0; $i -lt 5; $i++) {
        $ids += @($processes | Where-Object { $_.ParentProcessId -in $ids } | ForEach-Object { [int]$_.ProcessId })
        $ids = @($ids | Select-Object -Unique)
    }
    return @([System.Windows.Automation.AutomationElement]::RootElement.FindAll(
        [System.Windows.Automation.TreeScope]::Children,[System.Windows.Automation.Condition]::TrueCondition) |
        Where-Object { $_.Current.ProcessId -in $ids })
}
function Invoke-Button($Element) {
    $handle = $Element.Current.NativeWindowHandle
    if ($handle -eq 0) { throw 'Recognized button has no native handle; no blind input performed.' }
    $result.UiActions += $Element.Current.Name
    Write-Output "UI action: $($Element.Current.Name) (ID $($Element.Current.AutomationId))"
    # InvokePattern.Invoke may wait inside ssDone's modal warning. Post BM_CLICK
    # only to the exact process-scoped recognized button, allowing dialog handling.
    if (-not [SandboxUi]::PostMessage([IntPtr]$handle,0x00F5,[IntPtr]::Zero,[IntPtr]::Zero)) {
        throw 'Recognized button click could not be queued.'
    }
}
try {
    Start-Transcript -Path "$outputRoot\guest.log" | Out-Null
    Write-Output 'Phase: verify inputs and fresh state'
    foreach ($pair in @(@('core-setup.exe',$cfg.CoreSha256),@('downstream-setup.exe',$cfg.DownstreamSha256))) {
        if ((File-Sha256 "$inputRoot\$($pair[0])") -ne $pair[1]) { throw 'Guest installer SHA-256 mismatch.' }
    }
    if ($Case -eq 'D7' -and (File-Sha256 "$inputRoot\upgrade-setup.exe") -ne $cfg.UpgradeSha256) { throw 'Guest upgrade installer SHA-256 mismatch.' }
    $fresh = Snapshot
    if ($fresh.CoreRegistry -or $fresh.CoreExe -or $fresh.DownstreamRegistry -or $fresh.DownstreamExe) { throw 'Guest is not a fresh installation state.' }
    New-Item -ItemType Directory -Path "$env:APPDATA\PixelScope" -Force | Out-Null
    [IO.File]::WriteAllText("$env:APPDATA\PixelScope\sandbox-validation.txt",$cfg.RunId)
    $stateKey = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Software\PixelScope\PixelScope')
    try { $stateKey.SetValue('sandbox_validation_marker',$cfg.RunId) } finally { $stateKey.Dispose() }
    $result.UserStateBefore = User-State
    $result.CoreInstallExit = if ($Case -notin @('D3','D7')) { Run-Setup "$inputRoot\core-setup.exe" '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /LOG="C:\PixelScopeOutput\core-install.log"' } else { $null }
    Write-Output "Phase: Core installer returned $($result.CoreInstallExit)"
    $result.Before = Snapshot
    if ($Case -notin @('D3','D7') -and ($result.CoreInstallExit -ne 0 -or -not $result.Before.CoreExe -or -not $result.Before.CoreRegistry)) { throw 'Core fixture installation failed.' }
    $args = '/NORESTART /SP- /LOG="C:\PixelScopeOutput\downstream-install.log"'
    if ($Case -in @('D1','D6')) {
        $lockedFile = if ($Case -eq 'D1') { 'unins000.exe' } else { 'unins000.dat' }
        $result.LockedCoreFile = $lockedFile
        $lock = [IO.File]::Open("$coreRoot\$lockedFile",[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::None)
        try {
            $result.ExitCode = Run-Setup "$inputRoot\downstream-setup.exe" ($args + ' /VERYSILENT /SUPPRESSMSGBOXES /ALLOWCORECONVERSION=1')
        } finally { $lock.Dispose() }
    } elseif ($Case -eq 'D4') {
        $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($coreKey,$true)
        $originalLocation = $key.GetValue('InstallLocation')
        try {
            $key.SetValue('InstallLocation',"$env:LOCALAPPDATA\Programs\UnverifiedCore")
            $result.ExitCode = Run-Setup "$inputRoot\downstream-setup.exe" ($args + ' /VERYSILENT /SUPPRESSMSGBOXES /ALLOWCORECONVERSION=1')
            $result.InvalidRegistrationSnapshot = Snapshot
        } finally { $key.SetValue('InstallLocation',$originalLocation); $key.Dispose() }
    } elseif ($Case -eq 'D7') {
        $result.ExitCode = Run-Setup "$inputRoot\downstream-setup.exe" ($args + ' /VERYSILENT /SUPPRESSMSGBOXES')
        $result.Revision1 = Snapshot
        $result.Revision1Valid = Downstream-Valid
        $result.UpgradeExitCode = Run-Setup "$inputRoot\upgrade-setup.exe" '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /LOG="C:\PixelScopeOutput\upgrade-install.log"'
        $result.Revision2 = Snapshot
        $result.Revision2Valid = Downstream-Valid '0.1.0.2'
    } elseif ($Case -eq 'D3') {
        $result.ExitCode = Run-Setup "$inputRoot\downstream-setup.exe" ($args + ' /VERYSILENT /SUPPRESSMSGBOXES')
        $result.FreshInstall = Snapshot
        $result.FreshPayloadValid = Downstream-Valid
        $result.ReinstallExitCode = Run-Setup "$inputRoot\downstream-setup.exe" '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /LOG="C:\PixelScopeOutput\reinstall.log"'
        $result.ReinstallPayloadValid = Downstream-Valid
        $app = Start-Process "$downRoot\PixelScopeTestEdition.exe" -PassThru
        $windowDeadline = (Get-Date).AddSeconds(45)
        while (-not $app.HasExited -and $app.MainWindowHandle -eq 0 -and (Get-Date) -lt $windowDeadline) {
            Start-Sleep -Milliseconds 250; $app.Refresh()
        }
        $result.GuiWindowTitle = $app.MainWindowTitle
        $result.GuiWindowObserved = -not $app.HasExited -and $app.MainWindowHandle -ne 0 -and $app.MainWindowTitle -like '*PixelScope*'
        $result.GuiCloseRequested = $app.CloseMainWindow()
        $result.GuiClosed = $app.WaitForExit(30000)
        if ($result.GuiClosed) { $result.GuiExitCode = $app.ExitCode }
    } elseif ($Case -eq 'B4') {
        Write-Output 'Phase: launch actual installed Core'
        $core = Start-Process "$coreRoot\PixelScope.exe" -PassThru
        Start-Sleep -Seconds 3
        $core.Refresh()
        if ($core.HasExited) { throw 'Actual Core exited before the running-process test.' }
        Write-Output 'Phase: attempt silent consented conversion while Core runs'
        $result.ExitCode = Run-Setup "$inputRoot\downstream-setup.exe" ($args + ' /VERYSILENT /SUPPRESSMSGBOXES /ALLOWCORECONVERSION=1')
        $core.Refresh()
        $result.CoreStillRunning = -not $core.HasExited
    } else {
        Write-Output 'Phase: inspect interactive installer UI'
        Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class SandboxUi {
    [DllImport("user32.dll", SetLastError=true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool PostMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
}
'@
        $setup = Start-Process "$inputRoot\downstream-setup.exe" -ArgumentList $args -PassThru
        $deadline = (Get-Date).AddSeconds($cfg.TimeoutSeconds)
        $consent = $false
        $finish = $false
        while ((Get-Date) -lt $deadline) {
            $setup.Refresh()
            if ($setup.HasExited) { break }
            foreach ($window in (Installer-Windows $setup.Id)) {
                $all = @($window.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition))
                $names = @($all | ForEach-Object { $_.Current.Name })
                $result.LastUi = @($all | ForEach-Object { @{ Name=$_.Current.Name; Id=$_.Current.AutomationId; Type=$_.Current.ControlType.ProgrammaticName } })
                $result.LastUi | ConvertTo-Json -Depth 4 | Set-Content "$outputRoot\last-ui.json" -Encoding UTF8
                $buttons = @($all | Where-Object { $_.Current.ControlType -eq [System.Windows.Automation.ControlType]::Button -and $_.Current.IsEnabled })
                if (($names -join ' ') -like '*Convert the existing PUBLIC PixelScope Core installation*') {
                    $label = if ($Case -eq 'B1') { 'No' } else { 'Yes' }
                    # Win32 IDNO=7 / IDYES=6 survive localized Windows button labels.
                    $buttonId = if ($Case -eq 'B1') { '7' } else { '6' }
                    $button = @($buttons | Where-Object { $_.Current.AutomationId -eq $buttonId -or $_.Current.Name.Replace('&','') -eq $label })
                    if ($button.Count -ne 1) { throw 'Conversion consent button is ambiguous.' }
                    $result.ConsentDialogObserved = $true
                    Invoke-Button $button[0]
                    $consent = $true
                    break
                }
                if ($Case -in @('C1','D2','D5','D8','D9') -and $consent) {
                    $done = @($buttons | Where-Object { $_.Current.Name.Replace('&','') -eq 'Finish' })
                    if ($done.Count -eq 1 -and -not $finish) {
                        $log = Get-Content "$outputRoot\downstream-install.log" -Raw
                        if ($log -notmatch 'Installation process succeeded' -or $log -match 'Verified Core-to-downstream|PARTIAL CONVERSION') {
                            throw 'Finish checkpoint is not before conversion verification.'
                        }
                        if ($Case -eq 'D2') {
                            # Interrupt this observed installer tree only, in this guarded guest.
                            $ids = @($setup.Id)
                            $allProcesses = @(Get-CimInstance Win32_Process)
                            for ($depth=0; $depth -lt 5; $depth++) {
                                $ids += @($allProcesses | Where-Object { $_.ParentProcessId -in $ids } | ForEach-Object { [int]$_.ProcessId })
                                $ids = @($ids | Select-Object -Unique)
                            }
                            $result.Interruption = 'Installed Finish page before ssDone verification; not mid-copy interruption'
                            foreach ($targetPid in ($ids | Sort-Object -Descending)) {
                                $owned = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
                                if ($owned) { $owned.Kill() }
                            }
                            $finish = $true
                            break
                        }
                        $manifest = Get-Content "$downRoot\release-manifest.json" -Raw | ConvertFrom-Json
                        $entry = @($manifest.files | Where-Object { $_.path -eq '_bz2.pyd' })
                        if ($entry.Count -ne 1) { throw 'Known manifest-owned dependency not found.' }
                        $victimName = switch ($Case) { 'D8' { 'release-manifest.json' }; 'D9' { 'PixelScopeTestEdition.exe' }; default { '_bz2.pyd' } }
                        $victim = Join-Path $downRoot $victimName
                        if ((Get-Item $victim).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Unsafe fault target.' }
                        $originalSize = (Get-Item $victim).Length
                        $originalHash = (File-Sha256 $victim)
                        if ($Case -notin @('D8','D9') -and $originalHash -ne $entry[0].sha256) { throw 'Fault target was not intact.' }
                        if ($Case -eq 'D9') {
                            $exeEntry = @($manifest.files | Where-Object { $_.path -eq $victimName })
                            if ($exeEntry.Count -ne 1 -or $exeEntry[0].sha256 -ne $originalHash) { throw 'Original EXE does not match the installed manifest.' }
                        }
                        if ($Case -eq 'D9') { $faultBackupBytes = [IO.File]::ReadAllBytes($victim) }
                        if ($Case -eq 'D5') { Remove-Item -LiteralPath $victim } else { [IO.File]::WriteAllBytes($victim,[byte[]]@(0,1,2,3)) }
                        $result.Fault = @{ Path=$victimName; BeforeSha256=$originalHash; AfterSha256=$(if (Test-Path $victim) { File-Sha256 $victim } else { $null });
                            Checkpoint='Finish page after install success and before ssDone'; OriginalExpectedSize=$originalSize }
                        $finish = $true
                        Invoke-Button $done[0]
                        break
                    }
                    if ($finish -and ($names -join ' ') -like '*PixelScope conversion is incomplete*') {
                        # Inno's task dialog exposes its sole OK button as ID 2
                        # on this Windows build; Win32 MessageBox uses ID 1.
                        $ok = @($buttons | Where-Object { $_.Current.AutomationId -in @('1','2') -or $_.Current.Name -eq 'OK' })
                        if ($ok.Count -eq 1) { Invoke-Button $ok[0] }
                        break
                    }
                    $next = @($buttons | Where-Object { $_.Current.Name.Replace('&','') -in @('Next','Next >','Install') })
                    if ($next.Count -eq 1 -and -not $finish) { Invoke-Button $next[0]; break }
                }
            }
            Start-Sleep -Milliseconds 350
        }
        if (-not $setup.WaitForExit(1000)) { throw 'Recognized interactive flow did not complete; inspect guest UI.' }
        $setup.Refresh()
        $result.ExitCode = $setup.ExitCode
        if (-not $consent -or ($Case -in @('C1','D2','D5','D8','D9') -and -not $finish)) { throw 'Required UI checkpoint was not observed.' }
    }
    $result.After = Snapshot
    $a = $result.After
    $result.AfterFirstAttempt = $a
    $coreSame = $a.CoreExe -and $a.CoreRegistry -and
        (($a.CoreExe | ConvertTo-Json -Compress) -eq ($result.Before.CoreExe | ConvertTo-Json -Compress)) -and
        (($a.CoreRegistry | ConvertTo-Json -Compress) -eq ($result.Before.CoreRegistry | ConvertTo-Json -Compress))
    $log = Get-Content "$outputRoot\downstream-install.log" -Raw
    $pass = $false
    if ($Case -eq 'B1') { $pass = $result.ExitCode -ne 0 -and $coreSame -and -not $a.DownstreamExe -and -not $a.DownstreamRegistry -and $log.Contains('Core conversion not authorized') }
    if ($Case -eq 'B4') { $pass = $result.ExitCode -ne 0 -and $coreSame -and $result.CoreStillRunning -and -not $a.DownstreamExe -and -not $a.DownstreamRegistry -and $log.Contains('Core process check refused') }
    if ($Case -eq 'C1') { $pass = $result.ExitCode -eq 77 -and $coreSame -and $a.DownstreamExe -and $a.DownstreamRegistry -and $result.Fault -and
        $a.DownstreamExe.FileVersion -eq '0.1.0.1' -and $a.DownstreamRegistry.DisplayVersion -eq '0.1.0.1' -and
        $log.Contains('full payload manifest verification failed') -and $log.Contains('PARTIAL CONVERSION') -and -not $log.Contains('Verified Core-to-downstream conversion completed') }
    if ($Case -eq 'D1') { $pass = $result.ExitCode -eq 77 -and $coreSame -and (Downstream-Valid) -and
        $log.Contains('Core uninstaller could not be started') -and $log.Contains('PARTIAL CONVERSION') }
    if ($Case -eq 'D6') { $pass = $result.ExitCode -eq 77 -and $coreSame -and (Downstream-Valid) -and
        $log.Contains('Core uninstall returned error') -and $log.Contains('PARTIAL CONVERSION') }
    if ($Case -eq 'D2') { $pass = $coreSame -and (Downstream-Valid) -and $result.Interruption -and
        -not $log.Contains('Verified Core-to-downstream conversion completed') }
    if ($Case -eq 'D4') { $pass = $result.ExitCode -ne 0 -and $coreSame -and -not $a.DownstreamExe -and -not $a.DownstreamRegistry -and
        $log.Contains('Core install location is not the supported PUBLIC layout') }
    if ($Case -eq 'D5') { $pass = $result.ExitCode -eq 77 -and $coreSame -and $result.Fault -and $a.DownstreamRegistry -and
        $log.Contains('full payload manifest verification failed') -and $log.Contains('PARTIAL CONVERSION') }
    if ($Case -in @('D8','D9')) { $pass = $result.ExitCode -eq 77 -and $coreSame -and $result.Fault -and $a.DownstreamRegistry -and
        $log.Contains('downstream manifest or executable SHA-256 mismatch') -and $log.Contains('PARTIAL CONVERSION') }
    if ($Case -eq 'D9' -and $pass) {
        # Unknown EXE version is intentionally not silently repairable. Preserve
        # that refusal, then restore the exact guest backup before normal retry.
        $result.CorruptExeSilentRetryExit = Run-Setup "$inputRoot\downstream-setup.exe" '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /ALLOWCORECONVERSION=1 /LOG="C:\PixelScopeOutput\unknown-version-retry.log"'
        $pass = $result.CorruptExeSilentRetryExit -ne 0 -and (Snapshot).CoreRegistry
        [IO.File]::WriteAllBytes("$downRoot\PixelScopeTestEdition.exe",$faultBackupBytes)
        $result.RepairRestoredOriginalExe = (File-Sha256 "$downRoot\PixelScopeTestEdition.exe") -eq $result.Fault.BeforeSha256
        $pass = $pass -and $result.RepairRestoredOriginalExe
    }
    if ($Case -in @('D1','D2','D4','D5','D6','D8','D9')) {
        $result.InitialContractPass = [bool]$pass
        if ($pass) { $pass = Retry-Conversion }
    }
    if ($Case -eq 'D3') { $pass = $result.ExitCode -eq 0 -and $result.ReinstallExitCode -eq 0 -and
        $result.FreshPayloadValid -and $result.ReinstallPayloadValid -and $result.GuiWindowObserved -and
        $result.GuiCloseRequested -and $result.GuiClosed -and $result.GuiExitCode -eq 0 -and -not $a.CoreRegistry -and -not $a.CoreExe }
    if ($Case -eq 'D7') { $pass = $result.ExitCode -eq 0 -and $result.UpgradeExitCode -eq 0 -and
        $result.Revision1Valid -and $result.Revision2Valid -and -not $a.CoreExe -and -not $a.CoreRegistry -and
        $result.Revision1.DownstreamRegistry.UninstallString -eq $result.Revision2.DownstreamRegistry.UninstallString -and
        -not (Get-Content "$outputRoot\upgrade-install.log" -Raw).Contains('Reinstall this version') }
    $result.UserStateAfter = User-State
    $result.UserStatePreserved = ($result.UserStateBefore | ConvertTo-Json -Compress) -eq ($result.UserStateAfter | ConvertTo-Json -Compress)
    $pass = $pass -and $result.UserStatePreserved
    $result.Verdict = if ($pass) { 'PASS' } else { 'FAIL' }
    $result.Reason = if ($pass) { 'Exit, files, registry and expected installer log corroborate the contract.' } else { 'Observed state does not satisfy the contract; inspect raw evidence.' }
} catch {
    $result.Reason = $_.Exception.Message
} finally {
    try { $result.After = Snapshot } catch { $result.SnapshotError = $_.Exception.Message }
    try { Stop-Transcript | Out-Null } catch { }
    $result | ConvertTo-Json -Depth 12 | Set-Content "$outputRoot\result.tmp" -Encoding UTF8
    Move-Item -LiteralPath "$outputRoot\result.tmp" -Destination "$outputRoot\result.json"
    # This shutdown can only be reached after the isolation guard succeeded.
    & "$env:WINDIR\System32\shutdown.exe" /s /t 5
}
