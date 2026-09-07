# Despliegue offline

Estado Cuenta Engine mantiene dos perfiles de entrega separados, ambos sin descargas ni dependencias de Internet durante la operación.

## 1. Escritorio portable

Objetivo: entregar a una persona usuaria un único archivo `Extractor_de_Movimientos_Financieros.exe` que pueda copiarse a otra computadora Windows y ejecutarse con doble clic, sin instalar Python, Tesseract, PaddleOCR ni modelos.

El perfil portable incorpora dentro del `one-file`:

- runtime Python congelado;
- interfaz Flet;
- engine y parsers;
- Tesseract y `tessdata`;
- PaddlePaddle, PaddleOCR y PaddleX;
- modelos `PP-OCRv5_mobile_det` y `latin_PP-OCRv5_mobile_rec`;
- recursos institucionales.

Los modelos se preparan y validan antes de invocar PyInstaller. Durante la ejecución, el launcher fuerza el uso del modelo embebido y deshabilita comprobaciones/descargas de fuentes externas. El build ejecuta además una inferencia sintética dentro del EXE usando exclusivamente el bundle embebido.

Build recomendado:

```powershell
.\scripts\build_windows_release.ps1 -PortableOffline
```

Si los modelos todavía no existen en ninguna fuente local autorizada del equipo de build, su adquisición debe realizarse explícitamente durante la preparación de la entrega:

```powershell
.\scripts\build_windows_release.ps1 -PortableOffline -AllowPaddleModelDownload
```

La descarga, cuando se autoriza, ocurre sólo en el equipo de construcción. El ejecutable resultante no descarga modelos durante el procesamiento.

## 2. Despliegue TIC / Streamlit

Objetivo: ejecutar el mismo motor en infraestructura institucional. Streamlit y el EXE son superficies de despliegue diferentes y no se mezclan en un único artefacto.

Para Streamlit, TIC debe desplegar los dos modelos en una ubicación local controlada, por ejemplo:

```text
%PROGRAMDATA%\EstadoCuentaEngine\PaddleOCR\
  PP-OCRv5_mobile_det\
  latin_PP-OCRv5_mobile_rec\
```

También puede definirse `PADDLEOCR_MODEL_ROOT` a una ruta local administrada. El reader no descarga modelos durante el procesamiento.

El launcher recomendado para el servicio es:

```powershell
.\scripts\run_streamlit_offline.ps1
```

O, si TIC conserva los modelos en otra ruta local:

```powershell
.\scripts\run_streamlit_offline.ps1 -ModelRoot "D:\Modelos\EstadoCuentaEngine\PaddleOCR"
```

Ese launcher fuerza modo offline para PaddleX y dependencias que conozcan repositorios de modelos. La configuración `.streamlit/config.toml` deshabilita además `browser.gatherUsageStats` para evitar telemetría de uso.

Streamlit seguirá usando HTTP/WebSocket dentro de la red institucional porque es una aplicación web; la restricción offline significa que el motor no requiere ni debe iniciar conexiones hacia Internet para modelos, telemetría o procesamiento bancario.

## Criterio operativo

Una entrega portable se considera válida sólo si:

1. el EXE carga PaddleX dentro del binario congelado;
2. el EXE encuentra los dos modelos embebidos sin usar `ProgramData`, `LocalAppData`, cachés o variables externas;
3. el EXE ejecuta una inferencia PaddleOCR real y termina con código 0;
4. Tesseract funciona desde el bundle incluido;
5. el procesamiento normal no necesita conexión a Internet.

Para UAT final, copiar únicamente el EXE a una computadora Windows de prueba sin Python/PaddleOCR instalados y validar Digital, Tesseract, fallback PaddleOCR, comparación OCR y exportación Excel.
