# Estado Cuenta Engine

Motor modular de extracción, normalización, validación y exportación de información contenida en estados de cuenta bancarios en PDF.

> **Contexto institucional previsto:** Secretaría Anticorrupción y Buen Gobierno (SABG), Dirección General de Evaluación de Confianza (DGEC). El sistema se encuentra **en desarrollo** y su documentación se mantiene como expediente técnico vivo. Su paso a producción queda sujeto a revisión y autorización de las áreas competentes de TIC, ciberseguridad, protección de datos personales, jurídica y archivo de la SABG.

## 1. Propósito

Estado Cuenta Engine automatiza parte del tratamiento documental requerido para estructurar información financiera proveniente de estados de cuenta. Su función es técnica: convertir documentos PDF en datos estructurados para apoyar procesos institucionales autorizados.

El motor **no emite por sí mismo determinaciones de confianza, resoluciones administrativas ni decisiones sobre personas servidoras públicas**. Las salidas deben ser revisadas dentro del proceso institucional que corresponda.

## 2. Estado actual

La versión actual del repositorio soporta:

- lectura de PDF digital con texto y palabras espaciales;
- clasificación automática entre procesamiento **Digital** y **OCR**;
- OCR local mediante **Tesseract** cuando el documento no contiene texto utilizable;
- detección de institución/emisor;
- parsers especializados para BBVA, Banamex, Banorte, HSBC, Scotiabank, Mifel, Mercado Pago y CETES;
- parser OCR especializado para Banorte y mecanismo extensible para parsers/normalizadores OCR;
- procesamiento secuencial y procesamiento concurrente/incremental por lotes;
- modelo de dominio unificado (`EstadoCuenta`);
- validación de movimientos contra el resumen financiero;
- exportación a Excel;
- interfaces actuales en Streamlit y Flet;
- build Windows mediante PyInstaller;
- imagen OCI opcional para Streamlit, sin sustituir el ejecutable actual.

## 3. Flujo técnico actual

```text
PDF
 │
 ▼
ReaderManager
 │
 ├─► lectura de texto
 │     │
 │     └─► detección Digital / OCR
 │
 ├─► Digital: palabras espaciales
 │
 └─► OCR: TesseractPDFReader
       │
       ▼
Detección de institución
       │
       ▼
Parser especializado
       │
       ▼
Modelo EstadoCuenta
       │
       ▼
Validaciones
       │
       ▼
Mapeo / exportación
```

Para OCR, `statement_processor` puede seleccionar un parser especializado `<banco>_ocr`; si no existe, puede aplicar un normalizador de coordenadas y reutilizar el parser base.

## 4. Estructura principal

```text
app/                    Interfaces actuales (Streamlit / Flet)
assets/                 Recursos visuales
src/
  catalog/              Firmas y catálogos técnicos
  detectors/            Detección de banco y tipo documental
  engine/               Orquestación del pipeline
  exporters/            Exportación de resultados
  extractors/           Extractores transversales
  mappers/              Conversión a tablas/salidas
  models/               Modelos de dominio y resultados
  parsers/              Parsers especializados por institución/emisor
  readers/              Lectura digital, palabras espaciales y OCR
  utils/                 Utilidades reutilizables
  validators/            Validaciones de consistencia
tests/                  Pruebas automatizadas y utilidades de prueba
vendor/tesseract/       Runtime/modelos Tesseract actualmente versionados
docs/                   Documentación técnica, normativa y de despliegue
Dockerfile              Contenedor OCI opcional de Streamlit
pyproject.toml          Metadatos, dependencias y configuración de calidad
```

## 5. Política de dependencias y cadena de suministro

`pyproject.toml` es la **fuente canónica** del proyecto. Las dependencias se mantienen por responsabilidad:

- runtime del motor en `[project.dependencies]`;
- interfaces opcionales en `[project.optional-dependencies]`;
- herramientas de desarrollo y empaquetado en `[dependency-groups]`.

No se versiona un `requirements.txt` obtenido mediante `pip freeze`. Las versiones exactas de una liberación deben resolverse de forma controlada y conservarse como evidencia del release, junto con el inventario de terceros, revisión de vulnerabilidades y, cuando corresponda, SBOM.

La automatización de calidad audita vulnerabilidades conocidas de las dependencias instaladas, genera un inventario del entorno resuelto y registra hashes de integridad de artefactos relevantes. Las actualizaciones de dependencias requieren revisión humana y los mismos gates de calidad que cualquier otro cambio.

## 6. Protección de datos personales

Los estados de cuenta contienen datos personales y financieros y pueden revelar información adicional sobre terceras personas o, por el concepto de una operación, información de carácter sensible. Por ello deben tratarse con **minimización, finalidad, necesidad de conocer, control de acceso y trazabilidad**.

Reglas obligatorias para desarrollo y pruebas:

- **No versionar estados de cuenta reales**, capturas identificables, OCR/JSON derivados, archivos Excel resultantes ni bases de datos con información real.
- **No incluir datos personales en logs, excepciones, tickets o revisiones de cambio.**
- Usar únicamente fixtures sintéticos o previamente anonimizados conforme al procedimiento institucional autorizado.
- No enviar documentos, texto extraído o resultados a servicios externos, IA, nubes o APIs de terceros sin autorización institucional y análisis previo de transferencia/encargo, seguridad y privacidad.
- No versionar contraseñas, tokens, llaves privadas, certificados ni archivos `.env`.
- Los artefactos temporales y salidas deben almacenarse sólo durante el tiempo autorizado y eliminarse conforme a las políticas de conservación y disposición aplicables.

La guía detallada está en [`docs/04_seguridad_datos_personales.md`](docs/04_seguridad_datos_personales.md) y el procedimiento de reporte técnico en [`SECURITY.md`](SECURITY.md).

## 7. Marco normativo y de ciberseguridad

El proyecto se documenta tomando como referencia, entre otros instrumentos vigentes, la normativa TIC de la APF, la Política General de Ciberseguridad para la APF, la Ley General de Protección de Datos Personales en Posesión de Sujetos Obligados y el marco organizacional vigente de la SABG y de la DGEC.

La matriz normativa, su aplicabilidad y los entregables requeridos están en [`docs/05_normativa_tic_apf.md`](docs/05_normativa_tic_apf.md). La separación entre controles demostrables por el repositorio y controles institucionales se mantiene en [`docs/10_matriz_evidencias_tic.md`](docs/10_matriz_evidencias_tic.md).

> Esta documentación facilita la revisión técnica y de cumplimiento, pero **no sustituye** dictámenes, autorizaciones, evaluación de impacto, Documento de Seguridad, análisis de riesgos, Plan Institucional de Ciberseguridad ni demás instrumentos que determinen las áreas competentes.

## 8. Despliegue y portabilidad

La aplicación conserva la vía Windows existente y añade una vía OCI opcional para Streamlit. Esto permite que TIC evalúe el esquema de despliegue sin obligar a reescribir el motor bancario.

Antes de producción deberán definirse y aprobarse, como mínimo:

- topología de red y segmentación;
- cuenta o identidad de servicio y principio de mínimo privilegio;
- autenticación, autorización por roles y, cuando corresponda, MFA;
- cifrado en tránsito mediante HTTPS y certificado institucional autorizado;
- cifrado y controles de acceso para información en reposo;
- gestión de secretos y certificados fuera del código fuente;
- bitácoras de auditoría sin exposición de datos personales;
- respaldo, restauración, continuidad y recuperación;
- análisis de vulnerabilidades, dependencias e imágenes cuando aplique;
- monitoreo y procedimiento de respuesta a incidentes;
- política de conservación y eliminación de entradas, temporales y salidas.

La interfaz de Streamlit existe hoy como aplicación. **No debe tratarse como una API de integración.** Si SIEC requiere consumo programático, deberá evaluarse una capa API dedicada que encapsule el motor y permita controles de autenticación, autorización, trazabilidad, límites, versionado y manejo seguro de archivos.

La portabilidad y la opción de contenedores se documentan en [`docs/13_portabilidad_y_contenedores.md`](docs/13_portabilidad_y_contenedores.md).

## 9. Instalación de desarrollo

Requisitos generales:

- Windows 10/11 o Windows Server para el escenario actual;
- Python 3.12 o 3.13;
- Git;
- entorno virtual aislado.

El mínimo de Python 3.12 refleja el código actual de la interfaz Flet y se valida en CI; no se declara soporte para versiones que el código vigente no puede compilar.

Para Streamlit:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[streamlit]"
streamlit run app/main_streamlit.py
```

Para Flet:

```powershell
python -m pip install -e ".[desktop]"
python app/main_flet.py
```

Para herramientas de calidad y pruebas:

```powershell
python -m pip install --group dev
ruff check .
pytest -m "not integration"
```

Para validar el contenedor OCI opcional:

```powershell
docker build -t estado-cuenta-engine .
docker run --rm -p 8501:8501 estado-cuenta-engine
```

El motor no depende de Docker para funcionar. La imagen existe como alternativa de empaquetado y debe ejecutarse únicamente en infraestructura aprobada por TIC.

Las pruebas con PDFs reales son opt-in y deben usar archivos autorizados fuera del repositorio mediante `ESTADO_CUENTA_TEST_PDF` o `ESTADO_CUENTA_TEST_PDFS`.

## 10. Documentación

- [`00_setup.md`](docs/00_setup.md): instalación, dependencias y operación de desarrollo.
- [`01_vision.md`](docs/01_vision.md): objetivo, alcance y límites.
- [`02_arquitectura.md`](docs/02_arquitectura.md): arquitectura actual del motor.
- [`03_propuesta_tecnica.md`](docs/03_propuesta_tecnica.md): estado técnico y ruta hacia producción.
- [`04_seguridad_datos_personales.md`](docs/04_seguridad_datos_personales.md): privacidad y controles de seguridad.
- [`05_normativa_tic_apf.md`](docs/05_normativa_tic_apf.md): marco normativo aplicable a APF/SABG.
- [`06_despliegue_produccion_windows.md`](docs/06_despliegue_produccion_windows.md): línea base prevista para Windows Server/HTTPS.
- [`07_checklist_revision_tic.md`](docs/07_checklist_revision_tic.md): checklist de auditoría TIC, brechas y criterios de no-go.
- [`08_estandares_ingenieria.md`](docs/08_estandares_ingenieria.md): reglas de ingeniería, comentarios, dependencias y evidencia de liberación.
- [`09_auditoria_integral_produccion.md`](docs/09_auditoria_integral_produccion.md): auditoría completa del código, riesgos y gates de equivalencia funcional.
- [`10_matriz_evidencias_tic.md`](docs/10_matriz_evidencias_tic.md): controles demostrables por el repositorio y pendientes institucionales.
- [`11_gestion_vulnerabilidades_incidentes.md`](docs/11_gestion_vulnerabilidades_incidentes.md): triage, remediación, incidentes y terceros.
- [`12_checklist_liberacion_produccion.md`](docs/12_checklist_liberacion_produccion.md): expediente mínimo y criterios GO/NO-GO para una liberación.
- [`13_portabilidad_y_contenedores.md`](docs/13_portabilidad_y_contenedores.md): portabilidad, imagen OCI e integración futura.
- [`14_control_cambios.md`](docs/14_control_cambios.md): checklist portable de control de cambios.
- [`SECURITY.md`](SECURITY.md): reglas para reportar vulnerabilidades sin exponer datos sensibles.

## 11. Estado de cumplimiento

El repositorio **no debe considerarse certificado, acreditado ni autorizado para producción** por el hecho de documentar estos controles. La documentación distingue controles existentes, controles no verificados y requisitos pendientes, para que TIC pueda realizar una revisión basada en evidencia.

**Fecha de corte documental:** 5 de septiembre de 2026.
