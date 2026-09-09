param(
    [string]$Python = "python",
    [string]$Version = "3.0",
    [switch]$SkipTests,
    [switch]$PortableOffline,
    [switch]$IncludePaddleModels,
    [switch]$AllowPaddleModelDownload
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

Write-Host "== Extractor de Movimientos Financieros: build Windows TIC =="

if ($PortableOffline -and $IncludePaddleModels) {
    throw "Usa -PortableOffline para un EXE único o -IncludePaddleModels para un bundle TIC con modelos externos; no ambos a la vez."
}

if (-not $SkipTests) {
    & $Python -m pytest -m "not integration" -q
    if ($LASTEXITCODE -ne 0) {
        throw "La suite de regresión falló. No se generará un artefacto de liberación."
    }
}

foreach ($folder in @("build", "dist", ".packaging")) {
    if (Test-Path $folder) {
        Remove-Item $folder -Recurse -Force
    }
}

$PaddleRuntimeAvailable = & $Python -c "import importlib.util; print('1' if importlib.util.find_spec('paddleocr') and importlib.util.find_spec('paddlex') else '0')"
$PaddleRuntimeAvailable = $PaddleRuntimeAvailable.Trim()
$PortableModelRoot = $null
$PortableFletRoot = $null
$FletClientArchive = $null

if ($PortableOffline) {
    if ($PaddleRuntimeAvailable -ne "1") {
        throw "-PortableOffline requiere instalar primero .[desktop,paddleocr] en el entorno de build."
    }

    # El perfil portable prepara y valida los modelos ANTES de PyInstaller para
    # que el spec pueda incorporarlos físicamente dentro del one-file. El
    # staging vive fuera de build/, porque build/ es el workpath temporal de
    # PyInstaller y puede limpiarse/recrearse durante la construcción.
    $PortableModelRoot = Join-Path $ProjectRoot ".packaging\portable-paddleocr"
    $BootstrapArgs = @(
        "scripts\preparar_modelos_paddleocr.py",
        "--destino", $PortableModelRoot,
        "--fuente", "bos",
        "--probar-inferencia"
    )
    if (-not $AllowPaddleModelDownload) {
        $BootstrapArgs += "--sin-descargas"
    }

    Write-Host "Preparando modelos PaddleOCR para el EXE portable..."
    & $Python @BootstrapArgs
    if ($LASTEXITCODE -ne 0) {
        throw "No fue posible preparar/verificar los modelos PaddleOCR para el EXE portable."
    }

    # Flet 0.86.x puede resolver el visor de escritorio desde su caché o, si no
    # está disponible, descargarlo desde GitHub Releases en el primer arranque.
    # Un portable institucional no debe depender de ese fallback. Se prepara el
    # cliente exacto de la versión instalada durante el BUILD y luego el spec lo
    # incorpora en flet_desktop/app, que es la ubicación que Flet consulta antes
    # de intentar cualquier acceso de red en runtime.
    $PortableFletRoot = Join-Path $ProjectRoot ".packaging\portable-flet-client"
    Write-Host "Preparando cliente Flet Desktop para el EXE portable..."
    & $Python "scripts\preparar_cliente_flet.py" --destino $PortableFletRoot
    if ($LASTEXITCODE -ne 0) {
        throw "No fue posible preparar/verificar el cliente Flet para el EXE portable."
    }

    $FletClientArchive = Join-Path $PortableFletRoot "flet-windows.zip"
    if (-not (Test-Path $FletClientArchive)) {
        throw "No se generó el cliente Flet esperado: $FletClientArchive"
    }
}

$PreviousBundleRoot = $env:PADDLEOCR_BUNDLE_ROOT
$PreviousFletBundle = $env:FLET_DESKTOP_BUNDLE_ARCHIVE
try {
    if ($PortableOffline) {
        $env:PADDLEOCR_BUNDLE_ROOT = $PortableModelRoot
        $env:FLET_DESKTOP_BUNDLE_ARCHIVE = $FletClientArchive
    }
    else {
        Remove-Item Env:PADDLEOCR_BUNDLE_ROOT -ErrorAction SilentlyContinue
        Remove-Item Env:FLET_DESKTOP_BUNDLE_ARCHIVE -ErrorAction SilentlyContinue
    }

    & $Python -m PyInstaller --clean --noconfirm EstadoCuentaEngine.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller no pudo construir el ejecutable."
    }
}
finally {
    if ($null -eq $PreviousBundleRoot) {
        Remove-Item Env:PADDLEOCR_BUNDLE_ROOT -ErrorAction SilentlyContinue
    }
    else {
        $env:PADDLEOCR_BUNDLE_ROOT = $PreviousBundleRoot
    }

    if ($null -eq $PreviousFletBundle) {
        Remove-Item Env:FLET_DESKTOP_BUNDLE_ARCHIVE -ErrorAction SilentlyContinue
    }
    else {
        $env:FLET_DESKTOP_BUNDLE_ARCHIVE = $PreviousFletBundle
    }
}

$Exe = Join-Path $ProjectRoot "dist\Extractor_de_Movimientos_Financieros.exe"
if (-not (Test-Path $Exe)) {
    throw "No se generó el ejecutable esperado: $Exe"
}

if ($PortableOffline) {
    # Verificación estructural del ONE-FILE ya generado. No basta con comprobar
    # que el staging contenga el ZIP: el archivo debe estar físicamente dentro
    # del CArchive de PyInstaller en la ruta exacta que flet_desktop consulta.
    & $Python -c "from PyInstaller.archive.readers import CArchiveReader; import sys; names={name.replace('\\','/') for name in CArchiveReader(sys.argv[1]).toc}; expected='flet_desktop/app/flet-windows.zip'; print('Flet client embedded:', expected in names); raise SystemExit(0 if expected in names else 2)" $Exe
    if ($LASTEXITCODE -ne 0) {
        throw "El EXE portable no contiene flet_desktop/app/flet-windows.zip; Flet podría intentar descargar el visor al iniciar."
    }
}

# PaddleOCR 3.x depende de configuraciones dinámicas de PaddleX que pueden estar
# presentes en site-packages y faltar sólo dentro del ejecutable congelado. El
# self-test se ejecuta en el EXE real y evita entregar un binario que importe
# PaddleOCR pero falle después con "The pipeline (OCR) does not exist".
if ($PaddleRuntimeAvailable -eq "1") {
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
    Write-Warning "PaddleOCR/PaddleX no están instalados en este entorno; el EXE se construyó sin ese runtime."
}

if ($PortableOffline) {
    # Esta prueba no acepta ProgramData, LocalAppData, cachés ni variables de
    # modelo como sustituto: el propio launcher exige sys._MEIPASS/models/paddleocr
    # y ejecuta predict() usando esos pesos extraídos del one-file.
    $PortableSmoke = Start-Process `
        -FilePath $Exe `
        -ArgumentList "--self-test-portable-paddleocr-runtime" `
        -Wait `
        -PassThru
    if ($PortableSmoke.ExitCode -ne 0) {
        throw "El EXE portable no pudo ejecutar PaddleOCR con sus modelos embebidos (ExitCode=$($PortableSmoke.ExitCode))."
    }
}

& $Python scripts\verify_windows_release.py `
    $Exe `
    --output-dir (Join-Path $ProjectRoot "dist") `
    --version $Version
if ($LASTEXITCODE -ne 0) {
    throw "El ejecutable no superó la verificación previa a entrega."
}

if ($PortableOffline) {
    Copy-Item `
        (Join-Path $PortableModelRoot "paddleocr-models-manifest.json") `
        "dist\paddleocr-models-manifest.json" `
        -Force
}

if ($IncludePaddleModels) {
    if ($PaddleRuntimeAvailable -ne "1") {
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

    # La prueba anterior valida configuración y metadata. Ésta inicializa los
    # mismos modelos locales del bundle y ejecuta predict() dentro del EXE
    # congelado, que es donde históricamente aparecieron las regresiones.
    $PreviousPaddleModelRoot = $env:PADDLEOCR_MODEL_ROOT
    try {
        $env:PADDLEOCR_MODEL_ROOT = $ModelDestination
        $RuntimeSmoke = Start-Process `
            -FilePath $Exe `
            -ArgumentList "--self-test-paddleocr-runtime" `
            -Wait `
            -PassThru
        if ($RuntimeSmoke.ExitCode -ne 0) {
            throw "El EXE no pudo ejecutar inferencia PaddleOCR real (ExitCode=$($RuntimeSmoke.ExitCode))."
        }
    }
    finally {
        if ($null -eq $PreviousPaddleModelRoot) {
            Remove-Item Env:PADDLEOCR_MODEL_ROOT -ErrorAction SilentlyContinue
        }
        else {
            $env:PADDLEOCR_MODEL_ROOT = $PreviousPaddleModelRoot
        }
    }
}

$PaddleNote = if ($PortableOffline) {
@"
PaddleOCR portable: los dos modelos están embebidos dentro del EXE. La persona usuaria
sólo necesita Extractor_de_Movimientos_Financieros.exe; no debe instalar Python,
Tesseract, PaddleOCR, modelos ni ejecutar scripts. El runtime fuerza operación offline.

Cliente Flet portable: el visor de escritorio correspondiente a la versión de Flet usada
en el build también está embebido. El primer arranque no necesita descargar el cliente
Flet ni acceder a GitHub Releases; sólo puede crear la caché local de Flet a partir del
recurso incluido dentro del propio EXE.

paddleocr-models-manifest.json se conserva en dist únicamente como evidencia para TIC;
no es necesario copiarlo junto al EXE al equipo usuario.
"@
}
elseif ($IncludePaddleModels) {
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
5. para -PortableOffline, copiar sólo el EXE a una computadora limpia y confirmar que el visor Flet no intenta conectarse a Internet, el self-test Paddle embebido y una UAT real.

Streamlit se despliega como servicio separado: debe usar modelos locales autorizados y
la configuración del repositorio mantiene deshabilitada su telemetría de uso.
"@ | Out-File -Encoding utf8 "dist\LEEME_TIC.txt"

Write-Host "Build verificado en: $ProjectRoot\dist"