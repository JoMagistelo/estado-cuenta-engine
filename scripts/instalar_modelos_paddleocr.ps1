param(
    [string]$Source,
    [string]$Destination,
    [switch]$CurrentUser,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($Source)) {
    $Source = Join-Path $PSScriptRoot "models\paddleocr"
}

if ([string]::IsNullOrWhiteSpace($Destination)) {
    if ($CurrentUser) {
        if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
            throw "LOCALAPPDATA no está disponible para una instalación por usuario."
        }
        $Destination = Join-Path $env:LOCALAPPDATA "EstadoCuentaEngine\PaddleOCR"
    }
    else {
        if ([string]::IsNullOrWhiteSpace($env:PROGRAMDATA)) {
            throw "PROGRAMDATA no está disponible para una instalación institucional."
        }
        $Destination = Join-Path $env:PROGRAMDATA "EstadoCuentaEngine\PaddleOCR"
    }
}

$Source = [System.IO.Path]::GetFullPath($Source)
$Destination = [System.IO.Path]::GetFullPath($Destination)

$Models = @(
    "PP-OCRv5_mobile_det",
    "latin_PP-OCRv5_mobile_rec"
)

foreach ($Model in $Models) {
    $ModelSource = Join-Path $Source $Model
    if (-not (Test-Path $ModelSource -PathType Container)) {
        throw "No se encontró el modelo requerido en el bundle: $ModelSource"
    }
    $Files = Get-ChildItem $ModelSource -File -Recurse -ErrorAction Stop
    if (-not $Files) {
        throw "El modelo $Model no contiene archivos utilizables."
    }
}

New-Item -ItemType Directory -Force $Destination | Out-Null

foreach ($Model in $Models) {
    $ModelSource = Join-Path $Source $Model
    $ModelDestination = Join-Path $Destination $Model

    if ((Test-Path $ModelDestination) -and $Force) {
        Remove-Item $ModelDestination -Recurse -Force
    }

    if (-not (Test-Path $ModelDestination)) {
        Copy-Item $ModelSource $ModelDestination -Recurse -Force
    }
    else {
        Copy-Item (Join-Path $ModelSource "*") $ModelDestination -Recurse -Force
    }
}

$ManifestSource = Join-Path $Source "paddleocr-models-manifest.json"
if (Test-Path $ManifestSource -PathType Leaf) {
    Copy-Item $ManifestSource (Join-Path $Destination "paddleocr-models-manifest.json") -Force
}

Write-Host "Modelos PaddleOCR instalados en: $Destination"
Write-Host "Estado Cuenta Engine los resolverá automáticamente sin variables de entorno."
