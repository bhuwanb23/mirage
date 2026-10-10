$ErrorActionPreference = 'Stop'
$work = 'D:\projects\website\mirage\brag-output\work'
$fontDir = Join-Path $work 'fonts'
New-Item -ItemType Directory -Force -Path $fontDir | Out-Null

# Fetch Geist + Geist Mono from Google Fonts (woff2 latin)
$ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
function Get-GoogleCss($family) {
    $url = "https://fonts.googleapis.com/css2?family=$($family):wght@400;500;600;700&display=swap"
    (Invoke-WebRequest -Uri $url -Headers @{ 'User-Agent' = $ua } -UseBasicParsing).Content
}
$css = (Get-GoogleCss 'Geist') + "`n" + (Get-GoogleCss 'Geist+Mono')
# extract latin-only blocks: find each @font-face with unicode-range starting with U+0000
$faces = [regex]::Matches($css, '@font-face\s*\{([^}]+)\}')
$downloaded = @{}
foreach ($f in $faces) {
    $body = $f.Groups[1].Value
    if ($body -notmatch 'unicode-range:\s*U\+0000') { continue }  # latin subset only
    $fam = if ($body -match "font-family:\s*'([^']+)'") { $Matches[1] } else { continue }
    $weight = if ($body -match 'font-weight:\s*(\d+)') { $Matches[1] } else { '400' }
    $url = if ($body -match 'url\(([^)]+)\)') { $Matches[1] } else { continue }
    $name = ($fam -replace ' ', '') + '-' + $weight + '.woff2'
    $outPath = Join-Path $fontDir $name
    if (-not $downloaded.ContainsKey($name)) {
        Invoke-WebRequest -Uri $url -OutFile $outPath -UseBasicParsing
        $downloaded[$name] = (Get-Item $outPath).Length
        Write-Output "saved $name $($downloaded[$name]) bytes"
    }
}
Get-ChildItem $fontDir | Select-Object Name, Length
