# Instalación y entorno técnico

## Estado Cuenta Engine — SABG / DGEC

## 1. Requisitos

Entorno soportado para desarrollo y validación:

- Windows 10/11;
- Windows Server para despliegue institucional;
- Python 3.12 o 3.13;
- Git;
- PowerShell;
- entorno virtual de Python aislado.

La versión mínima de Python responde a la sintaxis utilizada por la interfaz Flet y se valida automáticamente en Python 3.12 y 3.13.

## 2. Dependencias

`pyproject.toml` es la fuente canónica de metadatos y dependencias Python.

Clasificación:

- `[project.dependencies]`: runtime del motor;
- `[project.optional-dependencies].streamlit`: interfaz web;
- `[project.optional-dependencies].desktop`: interfaz Flet;
- `[dependency-groups].dev`: calidad, pruebas y auditoría;
- `[dependency-groups].packaging`: empaquetado Windows.

Las versiones exactas utilizadas por una liberación deben conservarse como evidencia del artefacto construido.

## 3. Preparación del entorno

Crear entorno virtual:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Motor + Streamlit:

```powershell
python -m pip install -e ".[streamlit]"
```

Motor + Flet:

```powershell
python -m pip install -e ".[desktop]"
```

Herramientas de calidad:

```powershell
python -m pip install --group dev
```

Herramientas de empaquetado:

```powershell
python -m pip install --group packaging
```

## 4. Ejecución

Streamlit:

```powershell
streamlit run app/main_streamlit.py
```

Flet:

```powershell
python app/main_flet.py
```

La configuración productiva de Streamlit se describe en [`06_despliegue_produccion_windows.md`](06_despliegue_produccion_windows.md).

## 5. Calidad

Comprobaciones locales equivalentes a los gates principales:

```powershell
python -m compileall -q app src tests
ruff check .
pytest -m "not integration"
python -m build
```

Auditoría de dependencias:

```powershell
pip-audit
```

## 6. Pruebas de integración

Las pruebas con PDFs reales son opt-in y deben ejecutarse únicamente con documentos autorizados fuera del repositorio.

Un archivo:

```powershell
$env:ESTADO_CUENTA_TEST_PDF = "C:\ruta\autorizada\estado.pdf"
pytest -m integration
```

Un lote:

```powershell
$env:ESTADO_CUENTA_TEST_PDFS = "C:\ruta\uno.pdf;C:\ruta\dos.pdf"
pytest -m integration
```

## 7. Datos de prueba

- utilizar fixtures sintéticos para pruebas automatizadas;
- utilizar corpus real únicamente en entorno institucional autorizado;
- no incorporar PDFs reales, OCR, JSON, Excel, capturas o logs identificables al repositorio;
- no utilizar nombres, RFC, CURP, CLABE, cuentas, tarjetas, domicilios o referencias reales en fixtures;
- no trasladar documentos o resultados a servicios externos sin autorización institucional.

## 8. Secretos y certificados

No deben versionarse:

- contraseñas;
- tokens;
- llaves privadas;
- certificados con llave privada;
- archivos `.env` con credenciales;
- cadenas de conexión reales.

En producción, secretos y certificados se administran mediante el mecanismo definido por TIC.

## 9. Tesseract

El runtime Tesseract incluido bajo `vendor/tesseract/` forma parte de la distribución Windows y debe identificarse por versión, procedencia, licencia, hash y vulnerabilidades dentro del expediente de liberación.

## 10. Construcción del ejecutable

Instalar dependencias de escritorio y empaquetado:

```powershell
python -m pip install -e ".[desktop]"
python -m pip install --group packaging
```

Construir:

```powershell
pyinstaller --clean --noconfirm EstadoCuentaEngine.spec
```

Artefacto esperado:

```text
dist/Extractor_de_Movimientos_Financieros.exe
```

## 11. Producción

La instalación productiva se realiza conforme a [`06_despliegue_produccion_windows.md`](06_despliegue_produccion_windows.md). El proceso de liberación debe conservar evidencia de pruebas, dependencias, vulnerabilidades e integridad del artefacto.
