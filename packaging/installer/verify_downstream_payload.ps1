# PUBLIC, provider-neutral offline payload integrity gate for Issue #176.
# Included in the shared Inno installer ONLY when Core conversion is opted in.
# Do not execute binaries or uninstall anything here. Failure must preserve Core.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InstallRoot,
    [Parameter(Mandatory=$true)][string]$ExpectedProduct,
    [Parameter(Mandatory=$true)][string]$ExpectedVersion,
    [Parameter(Mandatory=$true)][string]$ExpectedExeName
)

$ErrorActionPreference = 'Stop'
try {
    $root = [IO.Path]::GetFullPath($InstallRoot).TrimEnd('\')
    $prefix = $root + '\'
    $manifestPath = Join-Path $root 'release-manifest.json'
    $manifestItem = Get-Item -LiteralPath $manifestPath -Force -ErrorAction Stop
    if (($manifestItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Manifest is a reparse point'
    }

    $m = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 |
        ConvertFrom-Json -ErrorAction Stop
    if ($null -eq $m -or $m.schema_version -ne 1 -or
        $m.product -cne $ExpectedProduct -or
        $m.version -cne $ExpectedVersion -or
        $m.payload_root -ne (Split-Path -Leaf $root) -or
        $m.target -ne 'windows-x64') {
        throw 'Manifest metadata does not match the selected downstream release'
    }
    $entries = @($m.files)
    if ($entries.Count -eq 0) { throw 'Manifest is empty' }

    $seen = New-Object 'System.Collections.Generic.HashSet[string]' (
        [StringComparer]::OrdinalIgnoreCase
    )
    $foundExe = $false
    foreach ($e in $entries) {
        if ($null -eq $e -or $e.path -isnot [string] -or
            $e.path -notmatch '^[A-Za-z0-9_ .()/+-]+$' -or
            $e.path.Contains('\') -or $e.path.StartsWith('/') -or
            $e.path.EndsWith('/') -or $e.path.Contains('//') -or
            $e.path.Contains(':') -or
            @($e.path.Split('/')).Where({ $_ -eq '.' -or $_ -eq '..' }).Count -ne 0) {
            throw "Unsafe manifest file path: $($e.path)"
        }
        if (-not $seen.Add($e.path)) { throw "Duplicate payload entry: $($e.path)" }
        $candidate = [IO.Path]::GetFullPath((Join-Path $root ($e.path -replace '/', '\')))
        if (-not $candidate.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Payload escaped install root: $($e.path)"
        }
        $parts = $e.path.Split('/')
        $cursor = $root
        foreach ($part in $parts) {
            $cursor = Join-Path $cursor $part
            $item = Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Reparse point in payload: $($e.path)"
            }
        }
        $file = Get-Item -LiteralPath $candidate -Force -ErrorAction Stop
        if ($file.PSIsContainer) { throw "Payload entry is directory: $($e.path)" }
        if ($e.size -isnot [long] -and $e.size -isnot [int] -and
            $e.size -isnot [decimal]) {
            throw "Invalid manifest size: $($e.path)"
        }
        if ($file.Length -ne [long]$e.size -or
            $e.sha256 -isnot [string] -or $e.sha256 -notmatch '^[0-9a-fA-F]{64}$') {
            throw "Payload size or hash metadata mismatch: $($e.path)"
        }
        $digest = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash
        if ($digest -ine $e.sha256) { throw "Payload hash mismatch: $($e.path)" }
        if ($e.path -ieq $ExpectedExeName) { $foundExe = $true }
    }
    if (-not $foundExe) { throw 'Executable missing from manifest inventory' }
    exit 0
}
catch {
    [Console]::Error.WriteLine("PixelScope downstream integrity failure: $($_.Exception.Message)")
    exit 21
}
