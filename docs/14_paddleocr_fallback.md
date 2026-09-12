# Revisión OCR dual: Tesseract y PaddleOCR — documento histórico

> **Estado documental:** histórico / no vigente para la ejecución productiva actual.  
> Este documento conserva la decisión, configuración y evidencia técnica de la etapa en la que Estado Cuenta Engine evaluó fallback OCR automático. La política productiva vigente se define en [`17_politica_ocr_produccion.md`](17_politica_ocr_produccion.md). Las secciones que describen activación automática del segundo motor, recomendación automática o selección dual no deben interpretarse como comportamiento vigente del producto.

## Estado Cuenta Engine — SABG / DGEC

**Fecha de corte histórica:** 5 de septiembre de 2026

## 1. Objetivo histórico

Estado Cuenta Engine mantuvo **Tesseract como motor OCR primario** e incorporó PaddleOCR como segundo motor local de recuperación y comparación para documentos escaneados cuya extracción primaria requería revisión.

La integración fue diseñada para:

- conservar el comportamiento cuando Tesseract obtenía un resultado suficiente;
- generar un segundo candidato sólo ante señales objetivas de extracción no confiable;
- ejecutar ambos candidatos con el mismo parser bancario y los mismos validadores;
- permitir comparar Tesseract y PaddleOCR en las interfaces Flet y Streamlit;
- permitir que el usuario autorizado seleccionara qué candidato revisar y exportar;
- conservar una recomendación automática conservadora como apoyo;
- operar de forma local, sin enviar documentos a servicios OCR externos.

El alcance lingüístico de esa etapa fue **documentación bancaria en español utilizada en México**.

## 2. Flujo funcional histórico

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

Los documentos **digitales no participaban en esta comparación** y conservaban el flujo histórico.

## 3. Condiciones históricas de activación del segundo OCR

Durante esta etapa, PaddleOCR sólo se intentaba cuando el fallback estaba habilitado para el banco y Tesseract presentaba al menos una señal objetiva de revisión. Se consideraban:

- ausencia de movimientos extraídos;
- una o más validaciones financieras fallidas (`correcto=False` / tache en interfaz);
- ausencia de una validación principal de depósitos/abonos o retiros/cargos;
- ausencia total de validaciones disponibles.

Estas condiciones **ya no activan un motor secundario en el procesamiento productivo vigente**.

## 4. Comparación y selección históricas

Cuando PaddleOCR lograba producir un segundo candidato, ambos resultados permanecían disponibles **en memoria durante la sesión de procesamiento**.

Las interfaces mostraban para cada motor, como mínimo:

- cantidad de movimientos;
- cantidad de validaciones disponibles;
- cantidad de validaciones fallidas;
- motor recomendado;
- motor actualmente seleccionado.

El usuario autorizado podía alternar entre **Tesseract** y **PaddleOCR**. Al cambiar la selección se actualizaban:

- datos de la cuenta;
- resumen financiero;
- movimientos;
- validaciones;
- resultado utilizado para la exportación a Excel.

No se duplicaban automáticamente los PDF ni se escribían copias del texto OCR alterno al disco para implementar esta comparación.

## 5. Recomendación automática histórica

La recomendación automática se utilizaba como punto de partida, no como sustituto de la revisión funcional.

La política histórica era conservadora:

- si Tesseract no obtenía movimientos y PaddleOCR sí, se recomendaba PaddleOCR;
- si PaddleOCR perdía movimientos que Tesseract sí obtuvo, se mantenía Tesseract;
- PaddleOCR no se recomendaba si perdía validadores que Tesseract sí pudo calcular;
- con cobertura comparable, se favorecía el candidato con menos validaciones fallidas;
- ante empate o evidencia insuficiente se mantenía Tesseract.

Esta recomendación automática no forma parte del procesamiento estándar definido por la política vigente.

## 6. Seguridad y privacidad

La integración fue diseñada para ejecución **local dentro de infraestructura autorizada**.

Controles relevantes que continúan siendo aplicables a los motores locales:

- no utilizar una API OCR alojada;
- no enviar PDF, texto extraído o información financiera a servicios externos;
- no descargar modelos durante el procesamiento;
- resolver únicamente modelos locales: variables explícitas, raíz administrada, ProgramData/LocalAppData o caché oficial local de PaddleX;
- deshabilitar la comprobación automática de proveedores de modelos mediante `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=1`;
- mantener telemetría técnica basada en estados y conteos, no importes ni contenido bancario.

## 7. Componentes controlados

La línea técnica documentada utiliza:

- PaddleOCR `>=3.7,<3.8`;
- PaddlePaddle `3.2.0` fijado para el runtime CPU;
- modelo de detección `PP-OCRv5_mobile_det`;
- modelo de reconocimiento `latin_PP-OCRv5_mobile_rec`;
- `PADDLEOCR_LANG=es` como único idioma admitido por la aplicación;
- inferencia CPU como configuración inicial;
- límite del lado mayor de detección para evitar procesamiento innecesario de páginas completas a alta resolución.

La versión 3.2.0 del runtime se fijó deliberadamente para mantener una combinación reproducible con PaddleOCR 3.7 en Windows y Python 3.12/3.13. No debe actualizarse de forma independiente sin repetir pruebas funcionales y de rendimiento.

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

## 10. Configuración técnica de modelos

Las variables de modelo documentadas continúan siendo válidas para resolver componentes locales:

```powershell
$env:PADDLEOCR_TEXT_DETECTION_MODEL_DIR = `
  "C:\ProgramData\EstadoCuentaEngine\PaddleOCR\PP-OCRv5_mobile_det"

$env:PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR = `
  "C:\ProgramData\EstadoCuentaEngine\PaddleOCR\latin_PP-OCRv5_mobile_rec"

$env:PADDLEOCR_DEVICE = "cpu"
$env:PADDLEOCR_LANG = "es"
$env:PADDLEOCR_DPI = "300"
$env:PADDLEOCR_TEXT_DET_LIMIT_SIDE_LEN = "1600"
$env:PADDLEOCR_ENABLE_MKLDNN = "0"
$env:PADDLEOCR_CPU_THREADS = "10"
```

Las antiguas variables `PADDLEOCR_FALLBACK_ENABLED` y `PADDLEOCR_FALLBACK_BANKS` pertenecen a la política histórica y **no gobiernan la selección productiva vigente**. El motor activo se define mediante la configuración de la aplicación o `OCR_PRIMARY_ENGINE`.

Las dos variables de directorio siguen teniendo prioridad, pero dejan de depender de la sesión actual de PowerShell cuando los modelos ya están instalados en una ubicación local reconocida. El reader busca, en este orden:

1. `PADDLEOCR_TEXT_DETECTION_MODEL_DIR` / `PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR`;
2. `PADDLEOCR_MODEL_ROOT\<modelo>`;
3. `%PROGRAMDATA%\EstadoCuentaEngine\PaddleOCR\<modelo>`;
4. `%LOCALAPPDATA%\EstadoCuentaEngine\PaddleOCR\<modelo>`;
5. `~\.paddlex\official_models\<modelo>`.

En todos los casos se pasa un directorio local explícito al runtime; esta resolución **no habilita descargas**. Si una variable individual está configurada con una ruta inválida, se rechaza en lugar de ocultar el error usando otra ubicación.

`PADDLEOCR_LANG` debe permanecer en `es`. Cualquier otro valor es rechazado por el reader.

`PADDLEOCR_CPU_THREADS` se acota internamente entre 1 y 32. `PADDLEOCR_TEXT_DET_LIMIT_SIDE_LEN` se acota entre 960 y 2400.

## 11. Selección y rollback vigente

Para utilizar Tesseract como motor OCR del procesamiento estándar:

```powershell
$env:OCR_PRIMARY_ENGINE = "tesseract"
```

Para utilizar PaddleOCR:

```powershell
$env:OCR_PRIMARY_ENGINE = "paddleocr"
```

La interfaz Flet permite realizar la misma selección antes de iniciar el lote. El motor alternativo no se ejecuta de forma automática.

## 12. Diagnóstico técnico seguro

El proyecto incluye:

```powershell
python scripts\diagnostico_paddleocr.py "C:\ruta\estado.pdf"
```

El diagnóstico se considera una herramienta técnica separada de la política productiva del lote. Puede utilizarse para evaluar motores concretos en un entorno autorizado.

También puede evaluarse un candidato concreto:

```powershell
python scripts\diagnostico_paddleocr.py "C:\ruta\estado.pdf" --motor tesseract
python scripts\diagnostico_paddleocr.py "C:\ruta\estado.pdf" --motor paddleocr
```

El diagnóstico no debe imprimir nombres, cuentas, CLABE, conceptos, texto OCR ni importes financieros.

## 13. Recursos y operación

PaddlePaddle incorpora un runtime de inferencia mayor que Tesseract. Antes de producción deben medirse con corpus autorizado:

- memoria residente;
- CPU por página;
- tiempo por motor seleccionado;
- espacio de los modelos;
- concurrencia segura;
- comportamiento ante lotes con varios documentos OCR.

La política vigente evita duplicar automáticamente el costo de OCR ejecutando un segundo motor por resultado fallido.

## 14. Ejecutable de escritorio

La incorporación de PaddleOCR/PaddlePaddle y sus modelos al artefacto portable debe verificarse en cada liberación autorizada. Deben controlarse tamaño, licencias, hashes, runtime, disponibilidad local de modelos y pruebas funcionales del artefacto resultante.

## 15. UAT recomendada para la política vigente

Antes de utilizar PaddleOCR como motor productivo:

1. instalar el extra PaddleOCR en ambiente controlado;
2. confirmar `paddle.__version__ == "3.2.0"`;
3. registrar e instalar modelos aprobados;
4. validar que no existan descargas durante procesamiento;
5. seleccionar PaddleOCR de forma explícita;
6. procesar corpus autorizado representativo;
7. validar datos de cuenta, resumen, movimientos y conciliaciones;
8. repetir el mismo corpus con Tesseract cuando se requiera comparación técnica;
9. validar nombres, conceptos, acentos, `Ñ`, números, fechas, referencias e importes de documentación mexicana;
10. medir CPU, memoria y tiempos;
11. comprobar cambio explícito de motor por configuración;
12. documentar aceptación funcional y técnica.

## 16. Criterios de aceptación TIC vigentes

- [ ] PaddleOCR/PaddlePaddle inventariados como componentes de terceros;
- [ ] versiones aprobadas y auditadas;
- [ ] modelos identificados con procedencia, licencia y hash;
- [ ] modelos instalados en ubicación protegida;
- [ ] ejecución local sin transferencia de documentos a servicios externos;
- [ ] sin descarga de modelos durante procesamiento;
- [ ] idioma restringido a español;
- [ ] selección del motor OCR verificada;
- [ ] ausencia de fallback automático verificada;
- [ ] uso de recursos aceptado;
- [ ] cambio explícito de motor probado;
- [ ] logs y diagnósticos sin información financiera o personal innecesaria.

## 17. Responsabilidades

**Equipo de aplicación:** readers OCR, selección de motor, pruebas, dependencias y documentación técnica.

**TIC:** aprobación e instalación del runtime/modelos, ubicación, ACL, inventario, vulnerabilidades, configuración de servicio, recursos y operación.

**DGEC / área funcional:** UAT con corpus autorizado, comparación controlada de resultados y aceptación funcional de los criterios de uso.
