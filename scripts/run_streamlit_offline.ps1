param(
    [string]$Python = "python",
    [string]$ModelRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

# El servicio institucional no debe consultar repositorios externos de modelos
# ni enviar telemetría de Streamlit. La comunicación HTTP/WebSocket de
# Streamlit queda limitada al servicio que TIC publique dentro de su red.
$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = "1"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:HF_DATASETS_OFFLINE = "1"
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"

if ($ModelRoot.Trim()) {
    $ResolvedModelRoot = (Resolve-Path $ModelRoot).Path
    $env:PADDLEOCR_MODEL_ROOT = $ResolvedModelRoot
}

& $Python -m streamlit run app\main_streamlit.py
if ($LASTEXITCODE -ne 0) {
    throw "Streamlit terminó con código $LASTEXITCODE."
}
