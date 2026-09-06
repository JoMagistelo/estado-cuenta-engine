param(
    [string]$Python = "python",
    [string]$Version = "2.4.1",
    [switch]$SkipTests,
    [switch]$IncludePaddleModels,
    [switch]$AllowPaddleModelDownload
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

# PaddleOCR 3.x depende de configuraciones dinámicas de PaddleX que pueden estar
# presentes en site-packages y faltar sólo dentro del ejecutable congelado. El
# self-test se ejecuta en el EXE real y evita entregar un binario que importe
# PaddleOCR pero falle después con "The pipeline (OCR) does not exist".
$PaddleRuntimeAvailable = & $Python -c "import importlib.util; print('1' if importlib.util.find_spec('paddleocr') and importlib.util.find_spec('paddlex') else '0')"
if ($PaddleRuntimeAvailable.Trim() -eq "1") {
    $Smoke = Start-Process `
        -FilePath $Exe `
        -ArgumentList "--self-test-paddlex-pipeline" `
        -Wait `
        -PassThru
    if ($Smoke.ExitCode -ne 0) {
        throw "El EXE no pudo cargar la pipeline OCR de PaddleX (ExitCode=$($Smoke.ExitCode))."
    }
}
else {
    Write-Warning "PaddleOCR/PaddleX no están instalados en este entorno; el EXE se construirá sin ese runtime."
}

& $Python scripts\verify_windows_release.py `
    $Exe `
    --output-dir (Join-Path $ProjectRoot "dist") `
    --version $Version
if ($LASTEXITCODE -ne 0) {
    throw "El ejecutable no superó la verificación previa a entrega."
}

if ($IncludePaddleModels) {
    if ($PaddleRuntimeAvailable.Trim() -ne "1") {
        throw "-IncludePaddleModels requiere instalar primero .[paddleocr] en el entorno de build."
    }

    $ModelDestination = Join-Path $ProjectRoot "dist\models\paddleocr"
    $BootstrapArgs = @(
        "scripts\preparar_modelos_paddleocr.py",
        "--destino", $ModelDestination,
        "--fuente", "bos",
        "--probar-inferencia"
    )
    if (-not $AllowPaddleModelDownload) {
        $BootstrapArgs += "--sin-descargas"
    }

    & $Python @BootstrapArgs
    if ($LASTEXITCODE -ne 0) {
        throw "No fue posible preparar/verificar los modelos PaddleOCR para la entrega."
    }

    Copy-Item `
        "scripts\instalar_modelos_paddleocr.ps1" `
        "dist\instalar_modelos_paddleocr.ps1" `
        -Force
}

$PaddleNote = if ($IncludePaddleModels) {
@"
- models\paddleocr\ (detección + reconocimiento + manifiesto)
- instalar_modelos_paddleocr.ps1

PaddleOCR: ejecutar instalar_modelos_paddleocr.ps1 durante el despliegue para copiar
los modelos a %PROGRAMDATA%\EstadoCuentaEngine\PaddleOCR. El runtime no descarga modelos.
"@
}
else {
@"
PaddleOCR: esta compilación no incluye pesos. TIC debe desplegar los modelos autorizados
en %PROGRAMDATA%\EstadoCuentaEngine\PaddleOCR o configurar PADDLEOCR_MODEL_ROOT.
"@
}

@"
Extractor de Movimientos Financieros - entrega para TIC

Contenido de esta carpeta:
- Extractor_de_Movimientos_Financieros.exe
- Extractor_de_Movimientos_Financieros.sha256.txt
- release-manifest.json
$PaddleNote
Antes de distribuir:
1. validar el SHA-256;
2. aplicar firma de código institucional si TIC la requiere;
3. probar el EXE en el Windows objetivo con una cuenta sin privilegios administrativos;
4. confirmar lectura Digital, OCR Tesseract, fallback PaddleOCR, selección dual, exportación y cierre controlado;
5. conservar el manifiesto de modelos PaddleOCR como evidencia cuando se incluya ese bundle.
"@ | Out-File -Encoding utf8 "dist\LEEME_TIC.txt"

Write-Host "Build verificado en: $ProjectRoot\dist"