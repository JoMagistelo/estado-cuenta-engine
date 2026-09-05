# Estado Cuenta Engine

Motor institucional para lectura, extracción, normalización, validación y exportación de información contenida en estados de cuenta bancarios en PDF.

**Contexto funcional:** Secretaría Anticorrupción y Buen Gobierno (SABG), Dirección General de Evaluación de Confianza (DGEC).

La versión actual se encuentra preparada para **entrega técnica y evaluación de despliegue institucional**. La instalación productiva se realiza bajo los controles de infraestructura, identidad, seguridad y operación definidos por TIC.

## 1. Alcance

Estado Cuenta Engine procesa estados de cuenta bancarios y convierte su contenido en información estructurada para apoyar procesos institucionales autorizados.

El sistema:

- procesa PDF digital y documentos que requieren OCR;
- utiliza Tesseract de forma local como OCR primario;
- dispone de PaddleOCR como fallback local opcional cuando Tesseract presenta fallas explícitas de validación financiera;
- identifica institución/emisor;
- aplica parsers especializados por banco/layout;
- normaliza datos de cuenta, resumen y movimientos;
- valida consistencia financiera cuando existen datos suficientes;
- exporta resultados a Excel;
- dispone de interfaces Flet y Streamlit;
- puede integrarse posteriormente con SIEC mediante una capa API dedicada sin modificar el motor bancario.

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
 ├─► Digital: palabras espaciales
 │
 └─► OCR: TesseractPDFReader
              │
              ▼
        Parser especializado
              │
              ▼
       Validación financiera
              │
      ┌───────┴────────┐
      │                │
   correcta          falla
      │                │
      │        PaddleOCR opcional
      │                │
      │        mismo parser/validator
      │                │
      └───────┬────────┘
              ▼
       Modelo EstadoCuenta
              │
              ▼
        Mapeo / exportación
```

Tesseract continúa siendo el OCR primario. PaddleOCR está deshabilitado por defecto y sólo se ejecuta cuando una validación financiera obtenida a partir de Tesseract falla y el fallback ha sido habilitado expresamente. PaddleOCR sólo sustituye el resultado primario cuando reduce las validaciones fallidas sin reducir su cobertura.

La lógica bancaria se mantiene separada de lectura, detección, validación, exportación e interfaces para facilitar pruebas y mantenimiento.

## 3. Estructura del proyecto

```text
app/                    Interfaces Flet y Streamlit
assets/                 Recursos visuales
src/
  catalog/              Firmas y catálogos técnicos
  detectors/            Detección de banco y tipo documental
  engine/               Orquestación del pipeline y política de fallback
  exporters/            Exportación de resultados
  extractors/           Extractores transversales
  mappers/              Conversión a tablas/salidas
  models/               Modelos de dominio y resultados
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
py -3.12 -m venv .venv
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

Instalar PaddleOCR cuando TIC autorice el fallback en el runtime institucional:

```powershell
python -m pip install -e ".[streamlit,paddleocr]"
```

PaddleOCR requiere modelos locales previamente aprobados y configurados. Estado Cuenta Engine no descarga modelos automáticamente durante el procesamiento. Consulte [`docs/14_paddleocr_fallback.md`](docs/14_paddleocr_fallback.md).

Instalar herramientas de calidad:

```powershell
python -m pip install --group dev
```

`pyproject.toml` es la fuente canónica de dependencias. No se utiliza un `requirements.txt` generado desde un entorno personal como contrato del producto.

## 6. Ejecución

### Streamlit

```powershell
streamlit run app/main_streamlit.py
```

### Flet

```powershell
python app/main_flet.py
```

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

Las pruebas con documentos reales son opt-in y deben ejecutarse únicamente en entornos autorizados. Los parsers se consideran lógica crítica y cualquier cambio funcional requiere regresión específica.

## 8. Protección de datos personales

Los estados de cuenta contienen información financiera y datos personales. Reglas técnicas del proyecto:

- no versionar estados de cuenta reales ni derivados con información identificable;
- no registrar contenido financiero completo en logs;
- no almacenar contraseñas, tokens, llaves privadas o certificados en código;
- no enviar documentos o resultados a servicios externos sin autorización institucional;
- mantener temporales y salidas bajo control de acceso y retención definidos;
- utilizar datos sintéticos o corpus autorizado para pruebas;
- operar PaddleOCR mediante inferencia local con modelos previamente instalados cuando el fallback esté habilitado.

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
- cuando PaddleOCR esté habilitado: versiones de PaddleOCR/PaddlePaddle y procedencia/licencia/hash de los modelos locales;
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
- [`14_paddleocr_fallback.md`](docs/14_paddleocr_fallback.md): instalación, seguridad, UAT y operación del fallback PaddleOCR.

## 12. Responsabilidades de entrega

**Aplicación:** código fuente, dependencias, pruebas, documentación, build y evidencia de integridad.

**TIC:** infraestructura, IIS, DNS, TLS, identidad, red, hardening, monitoreo, respaldos, parches, aprobación/instalación de runtimes y modelos de terceros, y operación.

**DGEC:** validación funcional y aceptación de resultados.

**Áreas competentes:** protección de datos personales, gestión de riesgos, archivo y demás controles institucionales aplicables.
