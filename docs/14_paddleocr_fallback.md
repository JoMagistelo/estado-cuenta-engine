# Revisión OCR dual: Tesseract y PaddleOCR

## Estado Cuenta Engine — SABG / DGEC

**Fecha de corte:** 5 de septiembre de 2026

## 1. Objetivo

Estado Cuenta Engine mantiene **Tesseract como motor OCR primario** e incorpora PaddleOCR como segundo motor local de recuperación y comparación para documentos escaneados cuya extracción primaria requiere revisión.

La integración está diseñada para:

- conservar el comportamiento actual cuando Tesseract obtiene un resultado suficiente;
- generar un segundo candidato sólo ante señales objetivas de extracción no confiable;
- ejecutar ambos candidatos con el mismo parser bancario y los mismos validadores;
- permitir comparar Tesseract y PaddleOCR en las interfaces Flet y Streamlit;
- permitir que el usuario autorizado seleccione qué candidato desea revisar y exportar;
- conservar una recomendación automática conservadora como apoyo, sin sustituir la revisión humana;
- operar de forma local, sin enviar documentos a servicios OCR externos.

El alcance lingüístico de esta versión es **documentación bancaria en español utilizada en México**.

## 2. Flujo funcional

```text
PDF escaneado
    │
    ▼
Tesseract
    │
    ▼
Parser bancario existente
    │
    ▼
Validadores existentes
    │
    ├── resultado suficiente ─────────────► conservar Tesseract
    │
    └── requiere revisión
            │
            ▼
      PaddleOCR local
            │
            ▼
      mismo parser bancario
            │
            ▼
      mismos validadores
            │
            ▼
     conservar ambos candidatos
            │
            ├── recomendación automática
            │
            └── selección del usuario
                    │
                    ▼
          vista y exportación Excel
```

Los documentos **digitales no participan en esta comparación** y conservan el flujo histórico.

## 3. Condiciones que activan el segundo OCR

PaddleOCR sólo se intenta cuando el fallback está habilitado para el banco y Tesseract presenta al menos una señal objetiva de revisión. La versión actual considera:

- ausencia de movimientos extraídos;
- una o más validaciones financieras fallidas (`correcto=False` / tache en interfaz);
- ausencia de una validación principal de depósitos/abonos o retiros/cargos;
- ausencia total de validaciones disponibles.

El guion de una validación se interpreta dentro del contexto del resultado. No se utiliza una puntuación de confianza OCR aislada para decidir qué información financiera conservar.

## 4. Comparación y selección

Cuando PaddleOCR logra producir un segundo candidato, ambos resultados permanecen disponibles **en memoria durante la sesión de procesamiento**.

Las interfaces muestran para cada motor, como mínimo:

- cantidad de movimientos;
- cantidad de validaciones disponibles;
- cantidad de validaciones fallidas;
- motor recomendado;
- motor actualmente seleccionado.

El usuario autorizado puede alternar entre **Tesseract** y **PaddleOCR**. Al cambiar la selección se actualizan:

- datos de la cuenta;
- resumen financiero;
- movimientos;
- validaciones;
- resultado que se utilizará para la exportación a Excel.

No se duplican automáticamente los PDF ni se escriben copias del texto OCR alterno al disco para implementar esta comparación.

## 5. Recomendación automática

La recomendación automática sirve como punto de partida, no como sustituto de la revisión funcional.

La política es conservadora:

- si Tesseract no obtiene movimientos y PaddleOCR sí, se recomienda PaddleOCR;
- si PaddleOCR pierde movimientos que Tesseract sí obtuvo, se mantiene Tesseract;
- PaddleOCR no se recomienda si pierde validadores que Tesseract sí pudo calcular;
- con cobertura comparable, se favorece el candidato con menos validaciones fallidas;
- ante empate o evidencia insuficiente se mantiene Tesseract.

La selección manual del usuario puede diferir de la recomendación automática.

## 6. Seguridad y privacidad

La integración está diseñada para ejecución **local dentro de infraestructura autorizada**.

Controles implementados:

- no utiliza una API OCR alojada;
- no envía PDF, texto extraído o información financiera a servicios externos;
- no descarga modelos durante el procesamiento;
- resuelve únicamente modelos locales: variables explícitas, raíz administrada, ProgramData/LocalAppData o caché oficial local de PaddleX;
- deshabilita la comprobación automática de proveedores de modelos mediante `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=1`;
- el fallback está deshabilitado por defecto;
- la telemetría técnica utiliza estados y conteos, no importes ni contenido bancario;
- los candidatos alternos se conservan en memoria para revisión y no se persisten automáticamente como archivos independientes.

## 7. Componentes controlados

La línea técnica utiliza:

- PaddleOCR `>=3.7,<3.8`;
- PaddlePaddle `3.2.0` fijado para el runtime CPU;
- modelo de detección `PP-OCRv5_mobile_det`;
- modelo de reconocimiento `latin_PP-OCRv5_mobile_rec`;
- `PADDLEOCR_LANG=es` como único idioma admitido por la aplicación;
- inferencia CPU como configuración inicial;
- oneDNN/MKL-DNN deshabilitado por defecto para priorizar estabilidad en Windows/CPU; puede habilitarse de forma explícita después de UAT;
- límite del lado mayor de detección para evitar procesamiento innecesario de páginas completas a alta resolución.

La versión 3.2.0 del runtime se fija deliberadamente para mantener una combinación reproducible con PaddleOCR 3.7 en Windows y Python 3.12/3.13. No debe actualizarse de forma independiente sin repetir pruebas funcionales y de rendimiento.

PaddleOCR no proporciona un modelo independiente `es-MX`; el modelo latino oficial incluye español y reconocimiento numérico. La aplicación restringe el contrato funcional al español utilizado en documentación bancaria mexicana.

## 8. Instalación

PaddleOCR es una dependencia opcional. Para el runtime Python institucional:

```powershell
python -m pip install -e ".[streamlit,paddleocr]"
```

Para desarrollo local con Flet y PaddleOCR:

```powershell
python -m pip install -e ".[desktop,paddleocr]"
```

La instalación del extra fija PaddlePaddle 3.2.0. Si el ambiente ya contiene otra versión, el instalador debe reconciliarla con la versión declarada por el proyecto antes de ejecutar UAT.

La automatización de calidad valida el runtime PaddleOCR/PaddlePaddle en Windows con Python 3.12 y Python 3.13.

## 9. Gestión institucional de modelos

Los modelos deben administrarse como componentes de terceros controlados. Antes de habilitarlos en producción debe registrarse, como mínimo:

- nombre exacto del modelo;
- versión o referencia de origen;
- fuente oficial de adquisición;
- licencia aplicable;
- fecha de adquisición;
- hash SHA-256;
- responsable de incorporación;
- ubicación autorizada;
- permisos/ACL;
- revisión de vulnerabilidades o avisos aplicables.

Ubicación operativa de referencia:

```text
C:\ProgramData\EstadoCuentaEngine\PaddleOCR\
    PP-OCRv5_mobile_det\
    latin_PP-OCRv5_mobile_rec\
```

La ubicación definitiva y las ACL corresponden a TIC.

## 10. Configuración

```powershell
$env:PADDLEOCR_FALLBACK_ENABLED = "1"
$env:PADDLEOCR_FALLBACK_BANKS = "hsbc"

$env:PADDLEOCR_TEXT_DETECTION_MODEL_DIR = `
  "C:\ProgramData\EstadoCuentaEngine\PaddleOCR\PP-OCRv5_mobile_det"

$env:PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR = `
  "C:\ProgramData\EstadoCuentaEngine\PaddleOCR\latin_PP-OCRv5_mobile_rec"

$env:PADDLEOCR_DEVICE = "cpu"
$env:PADDLEOCR_LANG = "es"
$env:PADDLEOCR_DPI = "300"
$env:PADDLEOCR_TEXT_DET_LIMIT_SIDE_LEN = "1600"
$env:PADDLEOCR_ENABLE_MKLDNN = "1"
$env:PADDLEOCR_CPU_THREADS = "10"
```

Desde la versión 2.4 las dos variables de directorio siguen teniendo prioridad, pero dejan de depender de la sesión actual de PowerShell cuando los modelos ya están instalados en una ubicación local reconocida. El reader busca, en este orden:

1. `PADDLEOCR_TEXT_DETECTION_MODEL_DIR` / `PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR`;
2. `PADDLEOCR_MODEL_ROOT\<modelo>`;
3. `%PROGRAMDATA%\EstadoCuentaEngine\PaddleOCR\<modelo>`;
4. `%LOCALAPPDATA%\EstadoCuentaEngine\PaddleOCR\<modelo>`;
5. `~\.paddlex\official_models\<modelo>`.

En todos los casos se pasa un directorio local explícito al runtime; esta resolución **no habilita descargas**. Si una variable individual está configurada con una ruta inválida, se rechaza en lugar de ocultar el error usando otra ubicación.

`PADDLEOCR_LANG` debe permanecer en `es`. Cualquier otro valor es rechazado por el reader.

`PADDLEOCR_ENABLE_MKLDNN=0` es la configuración estable predeterminada. `PADDLEOCR_ENABLE_MKLDNN=1` queda como opt-in de rendimiento y debe probarse con el runtime aprobado antes de adoptarse.

`PADDLEOCR_CPU_THREADS` se acota internamente entre 1 y 32. `PADDLEOCR_TEXT_DET_LIMIT_SIDE_LEN` se acota entre 960 y 2400.

Para la primera UAT se recomienda habilitar el fallback únicamente para HSBC. La ampliación a otros bancos debe realizarse con corpus de prueba representativo.

## 11. Rollback

PaddleOCR queda deshabilitado por defecto. Para regresar al comportamiento exclusivo de Tesseract:

```powershell
$env:PADDLEOCR_FALLBACK_ENABLED = "0"
```

Después de reiniciar la aplicación o servicio, el flujo OCR vuelve a utilizar únicamente Tesseract sin modificar parsers.

## 12. Diagnóstico técnico seguro

El proyecto incluye:

```powershell
python scripts\diagnostico_paddleocr.py "C:\ruta\estado.pdf"
```

El diagnóstico muestra únicamente información técnica como:

- banco detectado;
- motores disponibles;
- movimientos por candidato;
- número de validaciones;
- número de validaciones fallidas;
- recomendación automática;
- tipo de error técnico si PaddleOCR no pudo ejecutarse.

También puede evaluarse un candidato concreto:

```powershell
python scripts\diagnostico_paddleocr.py "C:\ruta\estado.pdf" --motor tesseract
python scripts\diagnostico_paddleocr.py "C:\ruta\estado.pdf" --motor paddleocr
```

El diagnóstico no imprime nombres, cuentas, CLABE, conceptos, texto OCR ni importes financieros.

## 13. Recursos y operación

PaddlePaddle incorpora un runtime de inferencia mayor que Tesseract. Antes de producción deben medirse con corpus autorizado:

- memoria residente;
- CPU por página;
- tiempo adicional cuando se activa el segundo OCR;
- espacio de los modelos;
- concurrencia segura;
- comportamiento ante lotes con varios documentos OCR que requieren revisión.

El segundo OCR no se ejecuta para documentos digitales ni para resultados OCR que no presentan señales de revisión.

## 14. Ejecutable de escritorio

El ejecutable PyInstaller actual se mantiene sin integrar PaddlePaddle dentro del binario. La comparación PaddleOCR está destinada inicialmente al runtime Python utilizado para UAT y despliegue web/servicio.

Si TIC requiere incorporar PaddleOCR dentro del ejecutable de escritorio, debe tratarse como una liberación de empaquetado específica que incluya tamaño, modelos, licencias, hashes, runtime y pruebas del artefacto resultante.

## 15. UAT recomendada

Antes de habilitar PaddleOCR en producción:

1. instalar el extra PaddleOCR en ambiente controlado;
2. confirmar `paddle.__version__ == "3.2.0"`;
3. registrar e instalar modelos aprobados;
4. validar que no existan descargas durante procesamiento;
5. habilitar inicialmente HSBC;
6. procesar casos donde Tesseract obtiene resultados correctos y confirmar que PaddleOCR no se ejecuta innecesariamente;
7. procesar casos con taches de validación;
8. procesar casos donde Tesseract no obtiene movimientos o validaciones suficientes;
9. comparar Tesseract y PaddleOCR en Flet y Streamlit;
10. alternar manualmente el motor y verificar que toda la vista cambie de candidato;
11. exportar Excel con Tesseract seleccionado y con PaddleOCR seleccionado y comprobar que la exportación respete la selección;
12. validar nombres, conceptos, acentos, `Ñ`, números, fechas, referencias e importes de documentación mexicana;
13. medir CPU, memoria y tiempos;
14. comprobar rollback por configuración;
15. documentar aceptación funcional y técnica.

## 16. Criterios de aceptación TIC

- [ ] PaddleOCR/PaddlePaddle inventariados como componentes de terceros;
- [ ] versiones aprobadas y auditadas;
- [ ] modelos identificados con procedencia, licencia y hash;
- [ ] modelos instalados en ubicación protegida;
- [ ] ejecución local sin transferencia de documentos a servicios externos;
- [ ] sin descarga de modelos durante procesamiento;
- [ ] idioma restringido a español;
- [ ] fallback deshabilitado hasta completar UAT;
- [ ] condiciones de activación verificadas;
- [ ] comparación Tesseract/PaddleOCR verificada en Flet y Streamlit;
- [ ] selección manual y exportación del candidato elegido verificadas;
- [ ] recomendación automática validada como apoyo y no como decisión irreversible;
- [ ] uso de recursos aceptado;
- [ ] rollback probado;
- [ ] logs y diagnósticos sin información financiera o personal innecesaria.

## 17. Responsabilidades

**Equipo de aplicación:** reader, política de activación/recomendación, comparación en interfaz, pruebas, dependencias y documentación técnica.

**TIC:** aprobación e instalación del runtime/modelos, ubicación, ACL, inventario, vulnerabilidades, configuración de servicio, recursos y operación.

**DGEC / área funcional:** UAT con corpus autorizado, comparación de resultados y aceptación funcional de los criterios de uso.
