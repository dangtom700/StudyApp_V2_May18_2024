<#
.SYNOPSIS
    Compress PDFs with Ghostscript. Resumable, parallel, never loses data.

.EXAMPLE
    .\compress_pdfs.ps1 -Source articles -Preset ebook
    .\compress_pdfs.ps1 -Source books -Preset ebook -Jobs 8
    .\compress_pdfs.ps1 -Source articles -WhatIf        # dry run: list what would be done
#>
param(
    [Parameter(Mandatory)][string]$Source,
    [string]$Destination,
    [ValidateSet('screen','ebook','printer','prepress')][string]$Preset = 'ebook',
    [int]$Jobs = [Math]::Max(1, [Environment]::ProcessorCount - 2),
    [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'

$gs = (Get-Command gswin64c.exe -ErrorAction SilentlyContinue).Source
if (-not $gs) { throw "gswin64c.exe not found on PATH." }

$Source = (Resolve-Path $Source).Path
if (-not $Destination) { $Destination = Join-Path $Source 'compressed' }
if (-not (Test-Path $Destination)) { New-Item -ItemType Directory $Destination | Out-Null }
$Destination = (Resolve-Path $Destination).Path
$logPath = Join-Path $Destination '_compress_log.csv'

# Resume: skip anything already present in the destination.
$done = @{}
Get-ChildItem $Destination -Filter *.pdf -File -ErrorAction SilentlyContinue |
    ForEach-Object { $done[$_.Name] = $true }

$todo = Get-ChildItem $Source -Filter *.pdf -File | Where-Object { -not $done[$_.Name] }

$totalIn = ($todo | Measure-Object Length -Sum).Sum
Write-Host ("Source      : {0}" -f $Source)
Write-Host ("Destination : {0}" -f $Destination)
Write-Host ("Preset      : /{0}   Parallel jobs: {1}" -f $Preset, $Jobs)
Write-Host ("To process  : {0} files, {1:N1} GB  ({2} already done, skipped)" -f `
    $todo.Count, ($totalIn/1GB), $done.Count)

$free = (Get-PSDrive ($Destination[0])).Free
Write-Host ("Free space  : {0:N1} GB" -f ($free/1GB))
if ($free -lt $totalIn) {
    Write-Warning ("Free space ({0:N1} GB) is less than the input set ({1:N1} GB). Files that fail to compress are copied through at full size, so this could fill the disk." -f ($free/1GB), ($totalIn/1GB))
}

if ($WhatIf) { Write-Host "`n-WhatIf: nothing written."; return }
if ($todo.Count -eq 0) { Write-Host "`nNothing to do."; return }

$sw = [Diagnostics.Stopwatch]::StartNew()
$counter = [System.Collections.Concurrent.ConcurrentQueue[string]]::new()
$total = $todo.Count

$results = $todo | ForEach-Object -ThrottleLimit $Jobs -Parallel {
    $gs      = $using:gs
    $preset  = $using:Preset
    $destDir = $using:Destination
    $queue   = $using:counter
    $total   = $using:total

    $src  = $_.FullName
    $out  = Join-Path $destDir $_.Name
    # Write to a temp name first so an interrupted run never leaves a truncated
    # PDF that the resume check would mistake for a finished one.
    $tmp  = Join-Path $destDir ("~" + $_.Name)

    $status = 'ok'
    try {
        # PowerShell does NOT expand $var inside an unquoted native-command
        # token after "=" or "/": -dPDFSETTINGS=/$preset reaches Ghostscript as
        # the literal text "$preset", and -sOutputFile=$out writes to a file
        # named "$out". Both fail quietly-ish. So pre-compose every argument
        # that embeds a variable into its own single variable, and pass the
        # output path as a separate argument to -o.
        $psetArg = "-dPDFSETTINGS=/$preset"
        & $gs -sDEVICE=pdfwrite -dNOPAUSE -dBATCH -dQUIET `
              $psetArg -dAutoRotatePages=/None `
              -o $tmp $src 2>$null

        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $tmp)) {
            $status = 'gs-failed'
        } else {
            $inLen  = $_.Length
            $outLen = (Get-Item $tmp).Length
            # Cheap integrity check: a real PDF starts with %PDF.
            $head = [System.IO.File]::ReadAllBytes($tmp)[0..3] -join ','
            $isPdf = $head -eq '37,80,68,70'

            if (-not $isPdf -or $outLen -lt 1024) {
                Remove-Item $tmp -Force
                Copy-Item $src $out -Force
                $status = 'bad-output'
            } elseif ($outLen -ge $inLen) {
                # Ghostscript made it bigger: keep the original.
                Remove-Item $tmp -Force
                Copy-Item $src $out -Force
                $status = 'kept-original'
            } else {
                Move-Item $tmp $out -Force
            }
        }
    } catch {
        $status = 'error'
        if (Test-Path $tmp) { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
    }

    if ($status -in 'gs-failed','error') {
        Copy-Item $src $out -Force -ErrorAction SilentlyContinue
    }

    $outLen = if (Test-Path $out) { (Get-Item $out).Length } else { 0 }
    $queue.Enqueue('x')
    Write-Host ("[{0}/{1}] {2,-13} {3,7:N1} -> {4,7:N1} MB  {5}" -f `
        $queue.Count, $total, $status, ($_.Length/1MB), ($outLen/1MB), $_.Name)

    [pscustomobject]@{
        timestamp = (Get-Date).ToString('s')
        file      = $_.Name
        status    = $status
        in_bytes  = $_.Length
        out_bytes = $outLen
        pct_saved = if ($_.Length) { [math]::Round(100*(1 - $outLen/$_.Length), 1) } else { 0 }
    }
}

$results | Export-Csv $logPath -Append -NoTypeInformation -Encoding utf8

$sw.Stop()
$inSum  = ($results | Measure-Object in_bytes  -Sum).Sum
$outSum = ($results | Measure-Object out_bytes -Sum).Sum
Write-Host ("`n{0} files in {1:hh\:mm\:ss}" -f $results.Count, $sw.Elapsed)
Write-Host ("{0:N1} GB -> {1:N1} GB   ({2:N1}% saved)" -f `
    ($inSum/1GB), ($outSum/1GB), (100*(1 - $outSum/[double]$inSum)))
$results | Group-Object status | ForEach-Object { Write-Host ("  {0,-14} {1}" -f $_.Name, $_.Count) }
Write-Host ("Log: {0}" -f $logPath)
