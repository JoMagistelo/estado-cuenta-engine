param(
    [string]$Python = "python",
    [string]$Version = "2.3.0",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

Write-Host "== Extractor de Movimientos Financieros: build Windows TIC =="

if (-not $SkipTests) {
    & $Python -m pytest -m "not integration" -q
    if ($LASTEXITCODE -ne 0) {
        throw "La suite de regresión falló. No se generará un artefacto de liberación."
    }
}

foreach ($folder in @("build", "dist")) {
    if (Test-Path $folder) {
        Remove-Item $folder -Recurse -Force
    }
}

& $Python -m PyInstaller --clean --noconfirm EstadoCuentaEngine.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller no pudo construir el ejecutable."
}

$Exe = Join-Path $ProjectRoot "dist\Extractor_de_Movimientos_Financieros.exe"
if (-not (Test-Path $Exe)) {
    throw "No se generó el ejecutable esperado: $Exe"
}

& $Python scripts\verify_windows_release.py `
    $Exe `
    --output-dir (Join-Path $ProjectRoot "dist") `
    --version $Version
if ($LASTEXITCODE -ne 0) {
    throw "El ejecutable no superó la verificación previa a entrega."
}

@"
Extractor de Movimientos Financieros - entrega para TIC

Contenido de esta carpeta:
- Extractor_de_Movimientos_Financieros.exe
- Extractor_de_Movimientos_Financieros.sha256.txt
- release-manifest.json

Antes de distribuir:
1. validar el SHA-256;
2. aplicar firma de código institucional si TIC la requiere;
3. probar el EXE en el Windows objetivo con una cuenta sin privilegios administrativos;
4. confirmar lectura Digital, OCR Tesseract, exportación y cierre controlado;
5. habilitar PaddleOCR únicamente con runtime y modelos previamente autorizados.
"@ | Out-File -Encoding utf8 "dist\LEEME_TIC.txt"

Write-Host "Build verificado en: $ProjectRoot\dist"
