# Estado Cuenta Engine

Motor institucional para lectura, extracción, normalización, validación y exportación de información contenida en estados de cuenta bancarios en PDF.

**Contexto funcional:** Secretaría Anticorrupción y Buen Gobierno (SABG), Dirección General de Evaluación de Confianza (DGEC).

La versión actual se encuentra preparada para **entrega técnica y evaluación de despliegue institucional**. La instalación productiva se realiza bajo los controles de infraestructura, identidad, seguridad y operación definidos por TIC.

## 1. Alcance

Estado Cuenta Engine procesa estados de cuenta bancarios y convierte su contenido en información estructurada para apoyar procesos institucionales autorizados.

El sistema:

- procesa PDF digital y documentos que requieren OCR;
- permite seleccionar Tesseract o PaddleOCR como motor OCR activo para un lote;
- ejecuta exclusivamente el motor OCR seleccionado durante el procesamiento estándar;
- no ejecuta automáticamente un segundo OCR por validaciones fallidas, ausencia de movimientos o error del motor seleccionado;
- identifica institución/emisor;
- aplica parsers especializados por banco/layout;
- normaliza datos de cuenta, resumen y movimientos;
- valida consistencia financiera cuando existen datos suficientes;
- exporta resultados a Excel;
- dispone de interfaces Flet y Streamlit;
- puede integrarse posteriormente con SIEC mediante una capa API dedicada sin modificar el motor bancario.

La infraestructura de comparación OCR se conserva como capacidad explícita para futuras acciones por archivo, pero no forma parte del flujo productivo automático.

El motor no emite resoluciones administrativas ni decisiones sobre personas; produce información estructurada para el proceso institucional correspondiente.

## 2. Arquitectura funcional

```text
PDF
 │
 ▼
ReaderManager
 │
 ├─► lectura de texto
 │     │
 │     └─► clasificación Digital / OCR
 │
 ├─► Digital: palabras espaciales ───────────────► parser / validación
 │
 └─► OCR: motor seleccionado
              │
       ┌──────┴──────┐
       │             │
   Tesseract      PaddleOCR
       │             │
       └──────┬──────┘
              │
              ▼
      Parser especializado
              │
              ▼
     Validadores existentes
              │
              ▼
        EstadoCuenta
              │
              ▼
        Mapeo / exportación
```

La configuración OCR es determinista: el motor seleccionado al iniciar el lote es el único motor que se ejecuta para cada documento escaneado de ese lote. Los PDFs digitales no participan en OCR.

Si el motor seleccionado falla al iniciar, el archivo se reporta con error; el sistema no cambia silenciosamente al motor alternativo. Si el parsing produce validaciones fallidas o no detecta movimientos, ese resultado se conserva sin iniciar un segundo OCR.

La capacidad de ejecutar un motor secundario se mantiene separada del flujo estándar y queda reservada para una futura acción explícita por archivo. La decisión productiva completa está documentada en [`docs/14_paddleocr_fallback.md`](docs/14_paddleocr_fallback.md).

La lógica bancaria se mantiene separada de lectura, detección, validación, exportación e interfaces para facilitar pruebas y mantenimiento.

## 3. Estructura del proyecto

```text
app/                    Interfaces Flet y Streamlit
assets/                 Recursos visuales
src/
  catalog/              Firmas y catálogos técnicos
  detectors/            Detección de banco y tipo documental
  engine/               Orquestación del pipeline y política OCR
  exporters/            Exportación de resultados
  extractors/           Extractores transversales
  mappers/              Conversión a tablas/salidas
  models/               Modelos de dominio, resultados y revisión OCR
  parsers/              Parsers especializados
  readers/              Lectura digital, Tesseract y PaddleOCR opcional
  utils/                 Utilidades
  validators/            Validaciones de consistencia
tests/                  Pruebas automatizadas
docs/                   Documentación técnica y de operación
vendor/tesseract/       Runtime Tesseract para distribución Windows
pyproject.toml          Metadatos y dependencias
EstadoCuentaEngine.spec Configuración de build PyInstaller
```

## 4. Requisitos

- Windows 10/11 para desarrollo o Windows Server para despliegue institucional;
- Python 3.12 o 3.13;
- Git para control de versiones durante desarrollo;
- entorno virtual aislado.

## 5. Instalación

Crear entorno:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Instalar motor + Streamlit:

```powershell
python -m pip install -e ".[streamlit]"
```

Instalar interfaz Flet:

```powershell
python -m pip install -e ".[desktop]"
```

Instalar PaddleOCR cuando vaya a utilizarse como motor OCR activo o para pruebas autorizadas de la ruta secundaria explícita:

```powershell
python -m pip install -e ".[streamlit,paddleocr]"
```

Para Flet:

```powershell
python -m pip install -e ".[desktop,paddleocr]"
```

PaddleOCR requiere modelos locales previamente aprobados y configurados. Estado Cuenta Engine no descarga modelos automáticamente durante el procesamiento. Consulte [`docs/14_paddleocr_fallback.md`](docs/14_paddleocr_fallback.md).

Instalar herramientas de calidad:

```powershell
python -m pip install --group dev
```

`pyproject.toml` es la fuente canónica de dependencias. No se utiliza un `requirements.txt` generado desde un entorno personal como contrato del producto.

## 6. Ejecución

### Empaquetar y ejecutar la versión 5.0.0 en Windows

Después de fusionar el PR, desde PowerShell con el entorno virtual de build
ya preparado y activo, actualizar el repositorio:

```powershell
Set-Location C:\Proyectos\estado-cuenta-engine
git switch master
git pull --ff-only origin master
```

La corrección de conciliación de Nu también requiere [Pillow 13](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html), que corrige
los hallazgos de la auditoría de dependencias. Si el entorno todavía tiene
Pillow 12, sincronizar las dependencias una vez antes de empaquetar:

```powershell
python -m pip install -e ".[desktop,paddleocr]"
```

La instalación se repite cuando cambian las dependencias declaradas en
`pyproject.toml`. Para actualizaciones posteriores que sólo cambian código,
basta con actualizar el repositorio y ejecutar el build habitual:

```powershell
.\scripts\build_windows_release.ps1 -Version "5.0.0" -PortableOffline
Get-Content .\dist\release-manifest.json
.\dist\Extractor_de_Movimientos_Financieros.exe
```

El script ejecuta las pruebas, limpia `build`, `dist` y `.packaging`, y verifica
el ejecutable portable con sus modelos PaddleOCR y cliente Flet embebidos.
El manifiesto debe indicar `5.0.0`; las propiedades del EXE usan `5.0.0.0`.
La interfaz muestra `Versión 5.0.0` y el modal «Información y ayuda» incluye
Santander como «Digital · Escaneado (cuenta de cheques)».

### Streamlit

```powershell
streamlit run app/main_streamlit.py
```

### Flet

```powershell
python app/main_flet.py
```

### Generar words originales de los readers

Desde la raíz del proyecto, con el entorno virtual activo, cambiar sólo la
ruta de la carpeta:

```powershell
$Carpeta = 'C:\ruta\a\tus\pdfs'
python .\scripts\generar_words.py "$Carpeta"
```

Recorre los PDFs de esa carpeta y sus subcarpetas, incluidas extensiones `.PDF`.
Guarda los JSON en `output/` del proyecto, conservando las subcarpetas de origen
para evitar colisiones entre PDFs con el mismo nombre.

| Salida | Fuente exacta |
| --- | --- |
| `<nombre>__readwords.json` | Lista de `PDFWordReader.read(pdf, start_page=0)`, sólo si contiene words extraíbles. |
| `<nombre>__paddleocr_words.json` | `PaddleOCRPDFReader.read(pdf, start_page=0).spatial_words`, para PDFs digitales y escaneados. |

Serializa las listas directamente, conservando campos, valores, orden y
coordenadas. No ejecuta parsers, normalizadores ni `read_ocr_for_parser`, y no
genera ni vuelve a leer una capa de texto OCR. Los PDFs originales se leen sin
modificarlos. PaddleOCR usa el runtime y los modelos locales habituales.

Opcionalmente, `--modo digital` o `--modo paddleocr` ejecuta un solo reader;
`--salida 'C:\ruta\salida'` cambia el destino. Si ya existe un JSON, lo reemplaza
sólo después de terminar su escritura. Los errores de un reader no impiden
intentar el otro ni continuar con los demás PDFs; el proceso retorna código 1
si hubo errores y 2 si la ruta es inválida o no contiene PDFs.

## 7. Calidad y regresión

La automatización de calidad valida:

- Python 3.12 y 3.13;
- compilación de `app/`, `src/` y `tests/`;
- Ruff para errores críticos;
- suite Pytest sintética/autocontenida;
- build del paquete Python;
- dependencias de Flet/Streamlit;
- instalación e import del runtime opcional PaddleOCR/PaddlePaddle en Windows;
- build real del ejecutable Windows con PyInstaller;
- auditoría de vulnerabilidades Python, incluido el stack Paddle cuando forma parte del runtime evaluado;
- inventario de dependencias;
- hash SHA-256 del runtime Tesseract;
- hash SHA-256 del ejecutable construido.

La regresión OCR debe comprobar además que el procesamiento estándar ejecuta exclusivamente el motor seleccionado y que una falla de validación o arranque no inicia automáticamente el motor alternativo.

Las pruebas con documentos reales son opt-in y deben ejecutarse únicamente en entornos autorizados. Los parsers se consideran lógica crítica y cualquier cambio funcional requiere regresión específica.

## 8. Protección de datos personales

Los estados de cuenta contienen información financiera y datos personales. Reglas técnicas del proyecto:

- no versionar estados de cuenta reales ni derivados con información identificable;
- no registrar contenido financiero completo en logs;
- no almacenar contraseñas, tokens, llaves privadas o certificados en código;
- no enviar documentos o resultados a servicios externos sin autorización institucional;
- mantener temporales y salidas bajo control de acceso y retención definidos;
- utilizar datos sintéticos o corpus autorizado para pruebas;
- operar Tesseract y PaddleOCR mediante inferencia local;
- mantener los modelos PaddleOCR previamente instalados y sin descargas automáticas en runtime;
- no generar candidatos OCR secundarios salvo que una función explícita y autorizada los solicite.

Consultar [`docs/04_seguridad_datos_personales.md`](docs/04_seguridad_datos_personales.md), [`docs/14_paddleocr_fallback.md`](docs/14_paddleocr_fallback.md) y [`SECURITY.md`](SECURITY.md).

## 9. Despliegue institucional

Para la interfaz web, la arquitectura recomendada es:

```text
Usuario institucional
        │
        ▼
HTTPS / certificado institucional
        │
        ▼
IIS
(reverse proxy / TLS)
        │
        ▼
Streamlit en interfaz local
        │
        ▼
Estado Cuenta Engine
```

TIC administra Windows Server, IIS, DNS, TLS, red, cuenta de servicio, hardening, monitoreo, respaldo y operación. La aplicación mantiene su lógica funcional independiente de esos controles.

Streamlit no debe utilizarse como API entre sistemas. Si SIEC requiere integración programática, la solución recomendada es una API institucional dedicada sobre el mismo motor.

Guía completa: [`docs/06_despliegue_produccion_windows.md`](docs/06_despliegue_produccion_windows.md).

## 10. Cadena de suministro

Las dependencias Python se declaran por función en `pyproject.toml`.

Cada versión candidata debe identificar:

- dependencias resueltas;
- vulnerabilidades conocidas;
- componentes de terceros;
- versión/procedencia/licencia de Tesseract;
- cuando PaddleOCR forme parte de la instalación: versiones de PaddleOCR/PaddlePaddle y procedencia/licencia/hash de los modelos locales;
- hash del artefacto entregado.

El proceso técnico se documenta en [`docs/09_verificacion_tecnica_version.md`](docs/09_verificacion_tecnica_version.md), [`docs/11_gestion_vulnerabilidades_incidentes.md`](docs/11_gestion_vulnerabilidades_incidentes.md) y [`docs/14_paddleocr_fallback.md`](docs/14_paddleocr_fallback.md).

## 11. Documentación

- [`00_setup.md`](docs/00_setup.md): instalación y entorno técnico.
- [`01_vision.md`](docs/01_vision.md): alcance y propósito.
- [`02_arquitectura.md`](docs/02_arquitectura.md): arquitectura del motor.
- [`03_especificacion_tecnica.md`](docs/03_especificacion_tecnica.md): especificación para integración institucional.
- [`04_seguridad_datos_personales.md`](docs/04_seguridad_datos_personales.md): privacidad y manejo de información.
- [`05_normativa_tic_apf.md`](docs/05_normativa_tic_apf.md): marco normativo de referencia.
- [`06_despliegue_produccion_windows.md`](docs/06_despliegue_produccion_windows.md): despliegue Windows Server/IIS.
- [`07_checklist_revision_tic.md`](docs/07_checklist_revision_tic.md): puntos de revisión TIC.
- [`08_estandares_ingenieria.md`](docs/08_estandares_ingenieria.md): estándares de ingeniería.
- [`09_verificacion_tecnica_version.md`](docs/09_verificacion_tecnica_version.md): verificación de calidad de la versión.
- [`10_matriz_evidencias_tic.md`](docs/10_matriz_evidencias_tic.md): matriz de controles y evidencias.
- [`11_gestion_vulnerabilidades_incidentes.md`](docs/11_gestion_vulnerabilidades_incidentes.md): vulnerabilidades e incidentes.
- [`12_checklist_liberacion_produccion.md`](docs/12_checklist_liberacion_produccion.md): checklist de liberación.
- [`13_control_cambios.md`](docs/13_control_cambios.md): criterios de control de cambios.
- [`14_paddleocr_fallback.md`](docs/14_paddleocr_fallback.md): política OCR de producción, trazabilidad, capacidad secundaria explícita y ruta de evolución arquitectónica.
- [`15_parser_santander.md`](docs/15_parser_santander.md): cobertura, contrato, extensión de layouts y validación local de Santander.
- [`nu_conciliacion.md`](docs/nu_conciliacion.md): conciliación de Cajitas, rendimientos y comisiones de Nu conservando el detalle original.

## 12. Responsabilidades de entrega

**Aplicación:** código fuente, dependencias, pruebas, documentación, build y evidencia de integridad.

**TIC:** infraestructura, IIS, DNS, TLS, identidad, red, hardening, monitoreo, respaldos, parches, aprobación/instalación de runtimes y modelos de terceros, y operación.

**DGEC:** validación funcional y aceptación de resultados.

**Áreas competentes:** protección de datos personales, gestión de riesgos, archivo y demás controles institucionales aplicables.
