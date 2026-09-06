# Preparación reproducible de modelos PaddleOCR

## Estado Cuenta Engine — SABG / DGEC

### Propósito

El runtime Python de PaddleOCR y los pesos de sus modelos son componentes distintos. Instalar `paddlepaddle` y `paddleocr` no instala necesariamente en una ubicación operativa los dos modelos que usa Estado Cuenta Engine:

- `PP-OCRv5_mobile_det`;
- `latin_PP-OCRv5_mobile_rec`.

Cuando esos directorios no existen, el fallback puede activarse correctamente después de una validación fallida de Tesseract, pero PaddleOCR termina antes de producir candidato con `PaddleOCRConfigurationError`. En ese caso Flet no puede mostrar la comparación de dos resultados porque sólo existe el candidato Tesseract.

Esta guía separa deliberadamente dos momentos:

1. **preparación/adquisición de modelos**, actividad explícita de instalación o UAT;
2. **procesamiento de estados de cuenta**, que continúa sin descargar modelos ni enviar documentos a servicios externos.

## Preparación local para desarrollo/UAT

Con el entorno virtual activo y el extra PaddleOCR instalado:

```powershell
python scripts\preparar_modelos_paddleocr.py --probar-inferencia
```

El comando:

1. reutiliza los modelos si ya están disponibles localmente;
2. si falta alguno, permite a PaddleX adquirir el modelo oficial únicamente durante este paso explícito;
3. instala ambos modelos por defecto en:

```text
%LOCALAPPDATA%\EstadoCuentaEngine\PaddleOCR\
```

4. genera `paddleocr-models-manifest.json` con hash SHA-256 del árbol de cada modelo, cantidad de archivos, tamaño y versiones del runtime;
5. configura temporalmente el reader contra esa raíz;
6. inicializa PaddleOCR y ejecuta `predict()` sobre una imagen sintética sin datos bancarios cuando se usa `--probar-inferencia`.

El éxito debe incluir:

```text
OK Inferencia PaddleOCR real: el engine local ejecutó predict().
PaddleOCR preparado correctamente.
```

### Entornos sin Internet

Si los modelos ya fueron entregados en una carpeta local autorizada:

```powershell
python scripts\preparar_modelos_paddleocr.py `
  --origen-local "D:\BundleAutorizado\PaddleOCR" `
  --sin-descargas `
  --probar-inferencia
```

También puede indicarse otro destino administrado:

```powershell
python scripts\preparar_modelos_paddleocr.py `
  --destino "C:\ProgramData\EstadoCuentaEngine\PaddleOCR" `
  --origen-local "D:\BundleAutorizado\PaddleOCR" `
  --sin-descargas `
  --probar-inferencia
```

## UAT real Tesseract vs PaddleOCR

El proyecto incluye un comando que primero verifica/prepara PaddleOCR y después fuerza los dos motores sobre el mismo PDF:

```powershell
.\scripts\uat_ocr_dual.ps1 -Pdf "C:\ruta\estado.pdf"
```

Para exigir operación totalmente offline durante la UAT:

```powershell
.\scripts\uat_ocr_dual.ps1 -Pdf "C:\ruta\estado.pdf" -NoDownload
```

El diagnóstico final debe mostrar dos candidatos y concluir con una evidencia equivalente a:

```text
Tesseract: ... movimientos / ... validaciones / ... fallidas
PaddleOCR: ... movimientos / ... validaciones / ... fallidas
PaddleOCR inference: OK · reader=paddleocr · tokens espaciales=...
```

La combinación `reader=paddleocr` más `tokens espaciales > 0` demuestra que el segundo documento fue generado por el reader PaddleOCR y no por una etiqueta de interfaz.

## Comportamiento esperado en Flet

La comparación manual no se muestra sólo porque la política haya **intentado** PaddleOCR. Se muestra cuando existen dos candidatos válidos en `OCRReview`.

Caso esperado:

```text
Tesseract
   │
   ├─ validación suficiente ──► un solo candidato
   │
   └─ señal de revisión
          │
          ▼
      PaddleOCR
          │
          ├─ error ───────────► Tesseract → PaddleOCR ⚠
          │                    no existe candidato Paddle para mostrar
          │
          └─ candidato ───────► Tesseract → PaddleOCR ✓
                               Comparación OCR visible
```

Con `✓`, Flet conserva los controles existentes por archivo:

- **Ver resultado** para Tesseract;
- **Ver resultado** para PaddleOCR;
- **Elegir para Excel** para cada candidato.

La vista actual y la elección confirmada para exportación son estados distintos. Cuando existen dos candidatos, la exportación continúa requiriendo una elección explícita.

## Instalación institucional/offline para TIC

El workflow manual `TICS desktop release` puede preparar un bundle que incluye:

```text
models\paddleocr\
    PP-OCRv5_mobile_det\
    latin_PP-OCRv5_mobile_rec\
    paddleocr-models-manifest.json
instalar_modelos_paddleocr.ps1
```

En el equipo de destino, el instalador copia los pesos a:

```text
C:\ProgramData\EstadoCuentaEngine\PaddleOCR\
```

Comando de referencia:

```powershell
powershell -ExecutionPolicy Bypass -File .\instalar_modelos_paddleocr.ps1
```

Para una instalación por usuario durante UAT:

```powershell
powershell -ExecutionPolicy Bypass -File .\instalar_modelos_paddleocr.ps1 -CurrentUser
```

El reader ya reconoce tanto `ProgramData` como `LocalAppData`; no es necesario mantener variables de entorno efímeras una vez que los modelos se encuentran en esas ubicaciones.

## Política de red

`preparar_modelos_paddleocr.py` es un **bootstrap explícito**, no forma parte del procesamiento ordinario de un PDF. Sólo este comando o el workflow de preparación puede adquirir modelos cuando se permite.

Durante el procesamiento de estados de cuenta:

- el reader exige modelos locales;
- `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=1` permanece activo antes de construir PaddleOCR;
- no se habilita descarga automática;
- no se envían estados de cuenta, OCR ni información financiera a un servicio externo.

Para una entrega estrictamente offline se debe generar el bundle en un ambiente de build autorizado, conservar su manifiesto/hash y desplegarlo con `instalar_modelos_paddleocr.ps1`.

## Evidencia automática en CI

`Production readiness` contiene un job específico de PaddleOCR que, en Windows/Python 3.12:

1. instala el runtime declarado por el proyecto;
2. prepara los dos modelos oficiales en un directorio temporal de build;
3. ejecuta una inferencia real sintética mediante el mismo `PaddleOCRPDFReader` utilizado por la aplicación;
4. conserva el manifiesto de modelos como evidencia.

Esto complementa las pruebas unitarias de routing/fallback. Una prueba de importación demuestra que el paquete existe; la prueba de inferencia demuestra que el engine, los modelos y `predict()` son compatibles.

## Criterio de aceptación antes de merge/release

- [ ] suite Python 3.12/3.13 en verde;
- [ ] job `PaddleOCR models + real inference` en verde;
- [ ] PyInstaller Windows en verde;
- [ ] UAT local con un PDF autorizado muestra `reader=paddleocr` y tokens espaciales;
- [ ] un caso con fallback produce `Tesseract → PaddleOCR ✓`;
- [ ] Flet muestra ambos botones **Ver resultado**;
- [ ] se puede confirmar Tesseract o PaddleOCR con **Elegir para Excel**;
- [ ] Excel respeta el candidato confirmado;
- [ ] procesamiento ordinario no realiza descargas de modelos.
