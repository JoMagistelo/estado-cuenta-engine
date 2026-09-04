# Instalación y entorno de desarrollo

> Documento de desarrollo. **No autoriza el uso de información real ni constituye guía de despliegue productivo.**

## 1. Requisitos

Entorno de referencia actual:

- Windows 10/11 para desarrollo;
- Windows Server como plataforma objetivo de producción, pendiente de definición final por TIC;
- Python 3.12+;
- Git;
- PowerShell;
- entorno virtual de Python aislado.

El repositorio incluye actualmente un runtime de Tesseract bajo `vendor/tesseract/`. Antes de producción TIC deberá revisar la procedencia, versión, licenciamiento, integridad y mecanismo de actualización de los binarios y modelos incluidos.

## 2. Preparación del entorno

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Ejecución actual

### Streamlit

```powershell
streamlit run app/main_streamlit.py
```

### Flet

```powershell
python app/main_flet.py
```

La existencia de estas dos interfaces no implica que ambas formen parte de la arquitectura productiva definitiva.

## 4. Datos de prueba

Para desarrollo y pruebas:

- no utilizar estados de cuenta reales salvo en un entorno institucional expresamente autorizado;
- no almacenar PDFs reales, OCR, JSON derivados, Excel de salida ni capturas identificables dentro del repositorio;
- preferir fixtures sintéticos o información previamente anonimizada/disociada;
- evitar nombres, RFC, CURP, CLABE, cuentas, tarjetas, domicilios, conceptos de movimientos y demás datos identificables en archivos de prueba, issues, commits o pull requests;
- no enviar documentos o datos extraídos a servicios externos sin autorización institucional.

## 5. Variables, secretos y certificados

Nunca deben versionarse:

- contraseñas;
- tokens;
- llaves privadas;
- secretos de aplicación;
- certificados con llave privada;
- archivos `.env` con credenciales;
- cadenas de conexión reales.

En producción, secretos y certificados deberán ser administrados por el mecanismo institucional que determine TIC.

## 6. Dependencias

Antes de cada liberación candidata a producción se recomienda generar evidencia de:

- inventario de dependencias Python;
- versiones fijadas y reproducibles;
- revisión de vulnerabilidades conocidas;
- licencias de dependencias y componentes de terceros;
- hash o mecanismo de integridad de artefactos distribuibles;
- pruebas automatizadas ejecutadas sobre la versión candidata.

## 7. Restricción de red

El procesamiento digital y OCR está diseñado para ejecutarse localmente. Cualquier incorporación futura de APIs externas, almacenamiento en nube, telemetría o servicios de inteligencia artificial deberá pasar previamente por revisión de arquitectura, seguridad, privacidad y, cuando corresponda, contratación institucional.

## 8. Producción

La instalación productiva se documenta por separado en [`06_despliegue_produccion_windows.md`](06_despliegue_produccion_windows.md). No debe exponerse directamente el servidor de desarrollo ni publicarse Streamlit en Internet sin la arquitectura y controles aprobados por TIC.
