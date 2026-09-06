param(
    [Parameter(Mandatory = $true)]
    [string]$Pdf,
    [string]$Python = "python",
    [switch]$NoDownload
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if (-not (Test-Path $Pdf -PathType Leaf)) {
    throw "No existe el PDF indicado: $Pdf"
}

$PrepareArgs = @(
    "scripts\preparar_modelos_paddleocr.py",
    "--probar-inferencia",
    "--fuente", "bos"
)
if ($NoDownload) {
    $PrepareArgs += "--sin-descargas"
}

Write-Host "== 1/2 Preparación/verificación PaddleOCR =="
& $Python @PrepareArgs
if ($LASTEXITCODE -ne 0) {
    throw "PaddleOCR no quedó listo; no se ejecutará la comparación."
}

Write-Host "== 2/2 Comparación real Tesseract vs PaddleOCR =="
& $Python scripts\diagnostico_paddleocr.py $Pdf --comparar-motores
if ($LASTEXITCODE -ne 0) {
    throw "La comparación OCR dual no terminó correctamente."
}

Write-Host "UAT OCR dual completada."
