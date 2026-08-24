#requires -Version 7.0
<#
.SYNOPSIS
    Compress the reading list's PDFs IN PLACE with Ghostscript. Resumable,
    parallel, never loses data.

.DESCRIPTION
    The PowerShell twin of the --compressPDF pipeline stage
    (src/modules/compress_pdf.py). Same behaviour, same temp-file suffix, same
    ledger, so the two can be used interchangeably and even alternately:

        python src/main.py --compressPDF     # inside the conda env
        .\compress_pdfs.ps1                  # plain PowerShell, no env needed

    Each PDF is replaced by its compressed version only when that version is
    verified AND strictly smaller; otherwise the original is left exactly as it
    was and the log says why.

    Why in place rather than an output folder: file_info.id is an md5 of the
    file's ABSOLUTE PATH (create_unique_id in src/lib/updateDB.hpp) and
    modules/catalog.py joins through hash_id == the file's stem on disk.
    Compressed copies in a second folder would re-key file_token, tags_full,
    comparison and item_matrix and orphan the lot. Replacing each file at its own
    path keeps every key valid. The stem is never changed for the same reason.

    Run order:  --renameFile  ->  this script  ->  --pdfToText  ->  ...

.NOTES
    Verification here is header + %%EOF trailer. The Python stage additionally
    compares page counts with PyMuPDF, which catches a readable-but-truncated
    output that the trailer check would accept -- prefer it for a first pass over
    an unfamiliar library.

.EXAMPLE
    .\compress_pdfs.ps1                             # compress READING_LIST_PATH
    .\compress_pdfs.ps1 -WhatIf                     # dry run: list what would be done
    .\compress_pdfs.ps1 -Preset screen
    .\compress_pdfs.ps1 -Jobs 8                     # override the background-friendly default
    .\compress_pdfs.ps1 -Source "D:\BOOKS" -Force   # re-compress (lossy: each pass degrades images)
#>
param(
    [string]$Source,
    [ValidateSet('screen','ebook','printer','prepress')][string]$Preset = 'ebook',
    [int]$Jobs = 0,
    [string]$LogPath,
    [Alias('DryRun')][switch]$WhatIf,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

# --- Config (kept identical to src/modules/compress_pdf.py) ------------------
$TmpSuffix       = '.gstmp'   # deliberately not *.pdf -- other stages glob for that
$MinOutputBytes  = 1024       # anything smaller than this is not a real PDF
$GsTimeoutMs     = 1800 * 1000
$DefaultJobs     = 3          # this runs for hours in the background; leave the box usable
$LogFields       = @('timestamp','file','status','in_bytes','out_bytes','pct_saved','preset','pages')

# --- Helpers -----------------------------------------------------------------

function Get-ConfigValue {
    <# Environment first, then the repo's .env -- the same order python-dotenv gives. #>
    param([string]$Key)

    $value = [Environment]::GetEnvironmentVariable($Key)
    if ($value) { return $value }

    $envFile = Join-Path $PSScriptRoot '.env'
    if (Test-Path -LiteralPath $envFile) {
        foreach ($line in Get-Content -LiteralPath $envFile) {
            $text = $line.Trim()
            if (-not $text -or $text.StartsWith('#')) { continue }
            $split = $text.IndexOf('=')
            if ($split -lt 1) { continue }
            if ($text.Substring(0, $split).Trim() -eq $Key) {
                return $text.Substring($split + 1).Trim().Trim('"', "'")
            }
        }
    }
    return $null
}

function Find-Ghostscript {
    <#
    GHOSTSCRIPT_PATH, then PATH, then the default Windows install location -- the
    installer does not add itself to PATH, so looking only at PATH fails on a
    perfectly working installation.
    #>
    $override = Get-ConfigValue 'GHOSTSCRIPT_PATH'
    if ($override) {
        if (Test-Path -LiteralPath $override -PathType Leaf) { return (Resolve-Path -LiteralPath $override).Path }
        throw "GHOSTSCRIPT_PATH points at a missing file: $override"
    }

    foreach ($name in 'gswin64c', 'gswin32c', 'gs') {
        $found = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) { return $found.Source }
    }

    $candidates = @()
    foreach ($root in $env:ProgramFiles, ${env:ProgramFiles(x86)}) {
        if (-not $root) { continue }
        $candidates += @(Get-Item -Path (Join-Path $root 'gs\gs*\bin\gswin*c.exe') -ErrorAction SilentlyContinue)
    }
    if ($candidates) { return ($candidates | Sort-Object FullName)[-1].FullName }   # highest version wins

    throw @"
Ghostscript not found.
  Windows: install from https://ghostscript.com/releases/gsdnld.html
  Linux  : apt install ghostscript
  Or set GHOSTSCRIPT_PATH=<full path to gswin64c.exe|gs> in your .env.
"@
}

function Format-CsvValue {
    <# Invariant formatting: on a comma-decimal locale "34,2" would split the row. #>
    param($Value)

    $text = if ($Value -is [double] -or $Value -is [single] -or $Value -is [decimal]) {
        [string]::Format([cultureinfo]::InvariantCulture, '{0}', $Value)
    } else {
        [string]$Value
    }
    if ($text -match '[",\r\n]') { return '"' + $text.Replace('"', '""') + '"' }
    return $text
}

function Import-Ledger {
    <#
    {filename = out_bytes} from the compression log, last entry wins. A missing or
    unreadable log is not fatal -- the worst case is a second compression pass,
    which the size check below still guards against.
    #>
    param([string]$Path)

    $done = @{}
    if (-not (Test-Path -LiteralPath $Path)) { return $done }
    try {
        foreach ($row in Import-Csv -LiteralPath $Path) {
            $bytes = 0
            if ([int64]::TryParse($row.out_bytes, [ref]$bytes)) { $done[$row.file] = $bytes }
        }
    } catch {
        Write-Warning "Could not read $Path : $($_.Exception.Message) -- treating every file as new."
        return @{}
    }
    return $done
}

# --- Setup -------------------------------------------------------------------

if (-not $Source)  { $Source  = (Get-ConfigValue 'READING_LIST_PATH') ?? 'D:\READING LIST' }
if (-not $LogPath) { $LogPath = Join-Path $PSScriptRoot 'data\compression_log.csv' }
# Ghostscript is CPU-bound and pegs a core per job. Three is the background
# default; -Jobs is the deliberate override for when the machine is idle.
if ($Jobs -le 0)   { $Jobs    = [Math]::Max(1, [Math]::Min($DefaultJobs, [Environment]::ProcessorCount - 1)) }

if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
    Write-Host "[ERROR] Reading list folder not found: $Source"
    Write-Host "  Set READING_LIST_PATH in your .env file, or pass -Source."
    exit 1
}
$Source = (Resolve-Path -LiteralPath $Source).Path
$gs = Find-Ghostscript

# Temps from a run that was killed mid-write. Harmless to the rest of the
# pipeline (nothing globs *.gstmp), but they waste disk until swept.
$stale = @(Get-ChildItem -LiteralPath $Source -Filter "*$TmpSuffix" -File -ErrorAction SilentlyContinue)
if ($stale.Count -and $WhatIf) {
    Write-Host "[INFO] $($stale.Count) leftover $TmpSuffix file(s) would be removed."
} elseif ($stale.Count) {
    $swept = 0
    foreach ($file in $stale) {
        try { Remove-Item -LiteralPath $file.FullName -Force; $swept++ } catch {}
    }
    Write-Host "[INFO] Removed $swept leftover $TmpSuffix file(s) from an interrupted run."
}

# An earlier version of this script wrote compressed copies into <Source>\compressed\
# instead of replacing in place. Nothing reads that folder any more and the *.pdf
# scan below is non-recursive, so it is inert -- but it looks like live output and
# it grows, so say what it is rather than let it be mistaken for this run's work.
$legacyDir = Join-Path $Source 'compressed'
if (Test-Path -LiteralPath $legacyDir -PathType Container) {
    $legacySize = (Get-ChildItem -LiteralPath $legacyDir -File -Recurse -ErrorAction SilentlyContinue |
                   Measure-Object Length -Sum).Sum
    Write-Warning ("Leftover folder from the old copy-to-a-folder version: {0} ({1:N1} GB). This script writes in place and never reads or updates it -- delete it when you are ready." -f $legacyDir, ($legacySize/1GB))
}

$pdfs   = Get-ChildItem -LiteralPath $Source -Filter *.pdf -File | Sort-Object Name
$ledger = if ($Force) { @{} } else { Import-Ledger $LogPath }

# Size still matching what we logged means this is the file we produced; a
# different size means it was replaced on disk, so compress it again.
$todo    = @($pdfs | Where-Object { -not ($ledger.ContainsKey($_.Name) -and $_.Length -eq $ledger[$_.Name]) })
$skipped = $pdfs.Count - $todo.Count
$totalIn = ($todo | Measure-Object Length -Sum).Sum

Write-Host ("Ghostscript : {0}" -f $gs)
Write-Host ("Source      : {0}   (in place)" -f $Source)
Write-Host ("Preset      : /{0}   Parallel jobs: {1}" -f $Preset, $Jobs)
Write-Host ("Verify      : %PDF header + %%EOF trailer  (run --compressPDF for page-count verification)")
Write-Host ("To process  : {0} files, {1:N1} GB  ({2} already compressed, skipped)" -f $todo.Count, ($totalIn/1GB), $skipped)

# In place needs room for one temp file per job, not for the whole set.
try {
    $free    = [System.IO.DriveInfo]::new($Source).AvailableFreeSpace
    $largest = ($todo | Measure-Object Length -Maximum).Maximum
    Write-Host ("Free space  : {0:N1} GB" -f ($free/1GB))
    if ($largest -and $free -lt ($largest * $Jobs)) {
        Write-Warning ("Free space ({0:N1} GB) is tight for {1} parallel temp files of up to {2:N1} GB each." -f ($free/1GB), $Jobs, ($largest/1GB))
    }
} catch {}

Write-Host ("Log         : {0}" -f $LogPath)
Write-Host ''

if ($WhatIf) {
    foreach ($p in $todo) { Write-Host ("  [WOULD] {0,8:N1} MB  {1}" -f ($p.Length/1MB), $p.Name) }
    Write-Host "`n-WhatIf: nothing written."
    return
}
if ($todo.Count -eq 0) { Write-Host 'Nothing to do.'; return }

# --- Run ---------------------------------------------------------------------

$logDir = Split-Path $LogPath -Parent
if ($logDir -and -not (Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory $logDir -Force | Out-Null }
$isNewLog = -not (Test-Path -LiteralPath $LogPath) -or (Get-Item -LiteralPath $LogPath).Length -eq 0
$writer = [System.IO.StreamWriter]::new($LogPath, $true, [System.Text.UTF8Encoding]::new($false))
if ($isNewLog) { $writer.WriteLine($LogFields -join ',') }

$sw      = [Diagnostics.Stopwatch]::StartNew()
$total   = $todo.Count
$done    = 0
$results = @()

try {
    $results = $todo | ForEach-Object -ThrottleLimit $Jobs -Parallel {
        $gs        = $using:gs
        $preset    = $using:Preset
        $tmpSuffix = $using:TmpSuffix
        $minBytes  = $using:MinOutputBytes
        $timeoutMs = $using:GsTimeoutMs

        $src      = $_.FullName
        $tmp      = $src + $tmpSuffix
        $inBytes  = $_.Length
        $outBytes = $inBytes          # unchanged unless the replace actually happens
        $status   = 'error'

        try {
            # ArgumentList passes each argument to the process verbatim. Do not go
            # back to `& $gs -dPDFSETTINGS=/$preset ...`: PowerShell does not expand
            # $var inside an unquoted native-command token after "=" or "/", so
            # Ghostscript would receive the literal text "$preset".
            $psi = [System.Diagnostics.ProcessStartInfo]::new()
            $psi.FileName               = $gs
            $psi.UseShellExecute        = $false
            $psi.CreateNoWindow         = $true
            $psi.RedirectStandardOutput = $true
            $psi.RedirectStandardError  = $true
            foreach ($arg in @('-sDEVICE=pdfwrite', '-dNOPAUSE', '-dBATCH', '-dQUIET',
                               "-dPDFSETTINGS=/$preset", '-dAutoRotatePages=/None',
                               '-o', $tmp, $src)) {
                $psi.ArgumentList.Add($arg)
            }

            $proc = [System.Diagnostics.Process]::Start($psi)
            # Below normal so a multi-hour run stays in the background instead of
            # fighting the foreground for CPU. A process that already exited has
            # no priority left to set, hence the swallow.
            try { $proc.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal } catch {}

            # Drain both pipes asynchronously. A malformed PDF can emit enough
            # warnings to fill the stderr buffer, and a full buffer blocks gs
            # forever while we sit in WaitForExit.
            $null = $proc.StandardOutput.ReadToEndAsync()
            $null = $proc.StandardError.ReadToEndAsync()

            if (-not $proc.WaitForExit($timeoutMs)) {
                try { $proc.Kill($true) } catch {}
                $status = 'timeout'
            }
            elseif ($proc.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $tmp)) {
                $status = 'gs-failed'
            }
            else {
                $len   = (Get-Item -LiteralPath $tmp).Length
                $isPdf = $false
                $hasEof = $false
                if ($len -ge $minBytes) {
                    $stream = [System.IO.File]::OpenRead($tmp)
                    try {
                        $head = [byte[]]::new(4)
                        $null = $stream.Read($head, 0, 4)
                        $isPdf = ($head[0] -eq 0x25 -and $head[1] -eq 0x50 -and $head[2] -eq 0x44 -and $head[3] -eq 0x46)

                        # %%EOF in the last KB: the cheapest truncation check available
                        # without a PDF library. Ghostscript writes it last.
                        $tailLen = [Math]::Min(1024, $stream.Length)
                        $null = $stream.Seek(-$tailLen, [System.IO.SeekOrigin]::End)
                        $tail = [byte[]]::new($tailLen)
                        $null = $stream.Read($tail, 0, $tailLen)
                        $hasEof = [System.Text.Encoding]::ASCII.GetString($tail).Contains('%%EOF')
                    } finally { $stream.Dispose() }
                }

                if ($len -lt $minBytes -or -not $isPdf) {
                    $status = 'bad-output'
                }
                elseif (-not $hasEof) {
                    $status = 'verify-failed'
                }
                elseif ($len -ge $inBytes) {
                    # Already well compressed, or mostly vector/text. Keep the
                    # original: rewriting it would cost quality for no gain.
                    $status = 'kept-original'
                }
                else {
                    try {
                        # Atomic within a filesystem: the file is either the original
                        # or the compressed version, never a mix.
                        [System.IO.File]::Move($tmp, $src, $true)
                        $status   = 'compressed'
                        $outBytes = $len
                    } catch {
                        # Typically the PDF is open in a reader and Windows refuses.
                        $status = 'locked'
                    }
                }
            }
        } catch {
            $status = 'error'
        } finally {
            # Whatever happened, never leave a temp file behind for the next run.
            if (Test-Path -LiteralPath $tmp) {
                try { Remove-Item -LiteralPath $tmp -Force } catch {}
            }
        }

        [pscustomobject]@{
            timestamp = (Get-Date).ToString('s')
            file      = $_.Name
            status    = $status
            in_bytes  = $inBytes
            out_bytes = $outBytes
            pct_saved = if ($inBytes) { [math]::Round(100 * (1 - $outBytes / $inBytes), 1) } else { 0.0 }
            preset    = $preset
            pages     = ''
        }
    } | ForEach-Object {
        # Logged in the parent as each file finishes -- one writer, no contention,
        # and an interrupted run resumes from where it stopped instead of
        # re-compressing everything.
        $row = $_
        $writer.WriteLine((($LogFields | ForEach-Object { Format-CsvValue $row.$_ }) -join ','))
        $writer.Flush()

        $done++
        Write-Host ("  [{0,4}/{1}] {2,-17} {3,8:N1} -> {4,8:N1} MB  {5}" -f `
            $done, $total, $row.status, ($row.in_bytes/1MB), ($row.out_bytes/1MB), $row.file)
        $row
    }
} finally {
    $writer.Dispose()
}

# --- Summary -----------------------------------------------------------------

$sw.Stop()
$inSum  = ($results | Measure-Object in_bytes  -Sum).Sum
$outSum = ($results | Measure-Object out_bytes -Sum).Sum

Write-Host ''
Write-Host ("{0} files in {1:hh\:mm\:ss}" -f @($results).Count, $sw.Elapsed)
if ($inSum) {
    Write-Host ("{0:N1} GB -> {1:N1} GB   ({2:N1}% saved)" -f ($inSum/1GB), ($outSum/1GB), (100 * (1 - $outSum/[double]$inSum)))
}

$results | Group-Object status | Sort-Object Count -Descending |
    ForEach-Object { Write-Host ("  {0,-18} {1}" -f $_.Name, $_.Count) }

$compressed = @($results | Where-Object status -eq 'compressed').Count
$untouched  = @($results).Count - $compressed
if ($untouched) {
    Write-Host ''
    Write-Host "$untouched file(s) were left exactly as they were (not compressed, not damaged)."
}
Write-Host ("Log: {0}" -f $LogPath)
