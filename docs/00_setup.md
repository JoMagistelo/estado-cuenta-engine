# Instalación y entorno de desarrollo

> Documento de desarrollo. **No autoriza el uso de información real ni constituye guía de despliegue productivo.**

## 1. Requisitos

Entorno de referencia actual:

- Windows 10/11 para desarrollo;
- Windows Server como plataforma objetivo de producción, pendiente de definición final por TIC;
- Python 3.12 o 3.13;
- Git;
- PowerShell;
- entorno virtual de Python aislado.

El mínimo de Python 3.12 no es arbitrario: la interfaz Flet actual utiliza sintaxis válida desde Python 3.12. La CI valida explícitamente Python 3.12 y 3.13 para no declarar compatibilidad que el código actual no ofrece.

El repositorio incluye actualmente un runtime de Tesseract bajo `vendor/tesseract/`. Antes de producción TIC deberá revisar su procedencia, versión, licenciamiento, integridad, vulnerabilidades y mecanismo de actualización.

## 2. Fuente canónica de dependencias

`pyproject.toml` es la fuente única de metadatos y dependencias Python del proyecto. No se mantiene un `requirements.txt` generado mediante `pip freeze`, porque ese archivo mezcla dependencias directas y transitivas y puede capturar accidentalmente herramientas instaladas en una estación de desarrollo.

La clasificación utilizada es:

- `[project.dependencies]`: dependencias necesarias para el motor;
- `[project.optional-dependencies].streamlit`: interfaz Streamlit;
- `[project.optional-dependencies].desktop`: interfaz Flet;
- `[dependency-groups].dev`: herramientas de calidad, pruebas, auditoría y build;
- `[dependency-groups].packaging`: herramientas para generar el ejecutable.

Las versiones exactas de una liberación deben resolverse y conservarse como evidencia del proceso de release aprobado; no deben obtenerse copiando el estado de un entorno personal.

## 3. Preparación del entorno

### Motor + Streamlit

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[streamlit]"
```

### Motor + Flet

```powershell
python -m pip install -e ".[desktop]"
```

### Herramientas de desarrollo

Con una versión de `pip` compatible con dependency groups:

```powershell
python -m pip install --group dev
```

### Empaquetado

```powershell
python -m pip install --group packaging
```

## 4. Ejecución actual

### Streamlit

```powershell
streamlit run app/main_streamlit.py
```

### Flet

```powershell
python app/main_flet.py
```

La existencia de estas dos interfaces no implica que ambas formen parte de la arquitectura productiva definitiva.

## 5. Comprobaciones de calidad

La configuración de Ruff vive en `pyproject.toml` y cubre el repositorio completo salvo `vendor/`, concentrándose en errores críticos de sintaxis y nombres. La CI también compila `app/`, `src/` y `tests/`, ejecuta la suite sintética y construye el ejecutable Flet en Windows.

```powershell
ruff check .
pytest -m "not integration"
python -m build
pip-audit
```

Las pruebas que requieren PDFs reales son opt-in. Use archivos autorizados fuera del repositorio:

```powershell
$env:ESTADO_CUENTA_TEST_PDF = "C:\ruta\autorizada\estado.pdf"
pytest -m integration
```

Para un lote:

```powershell
$env:ESTADO_CUENTA_TEST_PDFS = "C:\ruta\uno.pdf;C:\ruta\dos.pdf"
pytest -m integration
```

Una liberación institucional deberá ejecutar las comprobaciones aplicables dentro de un proceso automatizado y conservar su evidencia.

## 6. Datos de prueba

Para desarrollo y pruebas:

- no utilizar estados de cuenta reales salvo en un entorno institucional expresamente autorizado;
- no almacenar PDFs reales, OCR, JSON derivados, Excel de salida ni capturas identificables dentro del repositorio;
- preferir fixtures sintéticos o información previamente anonimizada/disociada;
- evitar nombres, RFC, CURP, CLABE, cuentas, tarjetas, domicilios, conceptos de movimientos y demás datos identificables en archivos de prueba, issues, commits o pull requests;
- no enviar documentos o datos extraídos a servicios externos sin autorización institucional.

## 7. Variables, secretos y certificados

Nunca deben versionarse contraseñas, tokens, llaves privadas, secretos de aplicación, certificados con llave privada, archivos `.env` con credenciales ni cadenas de conexión reales.

En producción, secretos y certificados deberán administrarse mediante el mecanismo institucional que determine TIC.

## 8. Dependencias y liberaciones

Antes de cada liberación candidata a producción se debe generar evidencia de:

- dependencias directas declaradas y conjunto exacto resuelto para la liberación;
- revisión de vulnerabilidades conocidas;
- inventario/licencias de componentes de terceros;
- SBOM cuando el proceso institucional lo requiera;
- procedencia, versión e integridad del runtime Tesseract vendorizado;
- hash del artefacto distribuible;
- pruebas automatizadas ejecutadas contra el commit candidato.

## 9. Restricción de red

El procesamiento digital y OCR está diseñado para ejecutarse localmente. Cualquier incorporación futura de APIs externas, almacenamiento en nube, telemetría o servicios de inteligencia artificial deberá pasar previamente por revisión de arquitectura, seguridad, privacidad y, cuando corresponda, contratación institucional.

## 10. Producción

La instalación productiva se documenta por separado en [`06_despliegue_produccion_windows.md`](06_despliegue_produccion_windows.md). No debe exponerse directamente el servidor de desarrollo ni publicarse Streamlit en Internet sin la arquitectura y controles aprobados por TIC.
