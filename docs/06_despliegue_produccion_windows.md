# Guía de despliegue institucional en Windows Server e IIS

## Estado Cuenta Engine — SABG / DGEC

**Fecha de corte:** 5 de septiembre de 2026

## 1. Objetivo

Definir la arquitectura técnica recomendada para desplegar Estado Cuenta Engine en infraestructura institucional Windows Server, utilizando IIS como punto de publicación HTTPS y manteniendo el proceso de aplicación aislado de la exposición directa a red.

Esta guía describe responsabilidades y requisitos técnicos. Los valores definitivos de DNS, certificados, cuentas, rutas, políticas de seguridad y operación serán los que establezca TIC.

## 2. Arquitectura recomendada

```text
Usuario institucional
        │
        ▼
HTTPS / certificado institucional
        │
        ▼
IIS
(reverse proxy / terminación TLS)
        │
        ▼
127.0.0.1:8501
Streamlit
        │
        ▼
Estado Cuenta Engine
        │
        ├─ Lectura PDF digital
        └─ OCR local
            ├─ Tesseract (primario)
            └─ PaddleOCR (fallback opcional)
```

Principios:

- IIS es el único componente expuesto a la red institucional;
- Streamlit escucha únicamente en interfaz local cuando IIS y la aplicación residen en el mismo servidor;
- el puerto interno de Streamlit no debe publicarse directamente a usuarios;
- TLS se administra en IIS con certificado institucional;
- los documentos permanecen dentro de infraestructura autorizada;
- el motor no utiliza servicios OCR alojados para procesar estados de cuenta;
- Tesseract opera localmente como OCR primario;
- PaddleOCR, cuando sea autorizado, opera localmente y sólo como fallback controlado;
- los modelos PaddleOCR deben existir previamente en almacenamiento institucional autorizado y no se descargan durante el procesamiento.

Si TIC utiliza un reverse proxy institucional distinto de IIS, deberá conservar los mismos principios de aislamiento, TLS, control de acceso y trazabilidad.

## 3. Componentes

### IIS

Responsable de publicación HTTPS, certificado TLS, DNS, exposición de red, reverse proxy hacia Streamlit, WebSocket y controles de plataforma definidos por TIC.

### Streamlit

Responsable de la interfaz web y la invocación del pipeline. En servidor debe ejecutarse en modo headless, limitado a la interfaz/puerto interno definido por TIC.

### Estado Cuenta Engine

Responsable de clasificación Digital/OCR, lectura, detección de institución, parsing especializado, normalización, validación y exportación.

El motor no administra identidad institucional, certificados, DNS ni políticas de red.

### Tesseract

OCR local primario. El runtime distribuido con la versión Windows queda sujeto a inventario, versión, licencia, hash de integridad y revisión de vulnerabilidades.

### PaddleOCR / PaddlePaddle

Runtime OCR opcional para recuperación de casos donde Tesseract falla validación financiera. Se instala únicamente cuando TIC autorice el fallback.

La aplicación exige modelos locales configurados expresamente y deshabilita la comprobación de proveedores de modelos. Los modelos deben formar parte del inventario institucional de terceros con procedencia, licencia e integridad verificadas.

La política completa se encuentra en [`14_paddleocr_fallback.md`](14_paddleocr_fallback.md).

## 4. Requisitos del servidor

Configuración base esperada:

- Windows Server soportado por la infraestructura institucional;
- IIS con HTTPS habilitado;
- Python 3.12 o 3.13 para la vía Streamlit;
- almacenamiento local o institucional autorizado;
- runtime Tesseract aprobado;
- cuando aplique, PaddleOCR/PaddlePaddle y modelos aprobados;
- cuenta de servicio de mínimo privilegio;
- sincronización de tiempo institucional;
- antimalware/EDR y controles de plataforma definidos por TIC;
- capacidad suficiente de CPU, memoria y espacio temporal para OCR.

PaddlePaddle incrementa de forma relevante el tamaño del runtime y el consumo potencial de memoria; el dimensionamiento debe validarse en UAT antes de habilitar el fallback en producción.

## 5. Cuenta de servicio y ACL

La aplicación debe ejecutarse con una identidad de servicio institucional, sin privilegios administrativos salvo excepción formalmente justificada.

Permisos mínimos:

- lectura/ejecución sobre código y runtimes;
- lectura sobre directorios de modelos OCR;
- lectura/escritura sobre directorios temporales autorizados;
- escritura sobre salidas autorizadas cuando corresponda;
- escritura sobre logs técnicos si éstos se almacenan localmente.

Los directorios de modelos PaddleOCR deben ser de sólo lectura para la cuenta de servicio salvo necesidad técnica expresamente aprobada.

## 6. Estructura de directorios

Ejemplo de separación operativa:

```text
C:\Apps\EstadoCuentaEngine\
    app\
    src\
    .venv\
    pyproject.toml

C:\ProgramData\EstadoCuentaEngine\PaddleOCR\
    PP-OCRv5_mobile_det\
    latin_PP-OCRv5_mobile_rec\

D:\EstadoCuentaEngine\Work\
D:\EstadoCuentaEngine\Output\
D:\EstadoCuentaEngine\Logs\
```

Las rutas son referenciales. TIC puede utilizar ubicaciones equivalentes siempre que se apliquen ACL, inventario, respaldo y retención conforme a la clasificación de información.

Los modelos no deben almacenarse dentro del repositorio de código ni en perfiles personales.

## 7. Instalación de la aplicación web

Runtime base con Streamlit y Tesseract:

```powershell
py -3.12 -m venv C:\Apps\EstadoCuentaEngine\.venv
C:\Apps\EstadoCuentaEngine\.venv\Scripts\python.exe -m pip install --upgrade pip
C:\Apps\EstadoCuentaEngine\.venv\Scripts\python.exe -m pip install -e "C:\Apps\EstadoCuentaEngine[streamlit]"
```

Si PaddleOCR fue aprobado:

```powershell
C:\Apps\EstadoCuentaEngine\.venv\Scripts\python.exe -m pip install -e `
  "C:\Apps\EstadoCuentaEngine[streamlit,paddleocr]"
```

Cuando la política institucional requiera instalación sin Internet, las dependencias y modelos deberán entregarse mediante repositorio interno, caché o paquete offline aprobado por TIC.

## 8. Configuración del fallback PaddleOCR

Ejemplo para habilitación controlada inicial en HSBC:

```powershell
$env:PADDLEOCR_FALLBACK_ENABLED = "1"
$env:PADDLEOCR_FALLBACK_BANKS = "hsbc"
$env:PADDLEOCR_TEXT_DETECTION_MODEL_DIR = `
  "C:\ProgramData\EstadoCuentaEngine\PaddleOCR\PP-OCRv5_mobile_det"
$env:PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR = `
  "C:\ProgramData\EstadoCuentaEngine\PaddleOCR\latin_PP-OCRv5_mobile_rec"
$env:PADDLEOCR_DEVICE = "cpu"
$env:PADDLEOCR_LANG = "es"
```

El fallback permanece deshabilitado si `PADDLEOCR_FALLBACK_ENABLED` no está activo. La configuración productiva debe incorporarse al mecanismo institucional de variables/configuración del servicio y no a archivos con secretos dentro del código.

No se requiere salida a Internet para inferencia una vez instalados el runtime y los modelos locales autorizados.

## 9. Ejecución de Streamlit

```powershell
C:\Apps\EstadoCuentaEngine\.venv\Scripts\python.exe -m streamlit run `
  C:\Apps\EstadoCuentaEngine\app\main_streamlit.py `
  --server.address=127.0.0.1 `
  --server.port=8501 `
  --server.headless=true `
  --browser.gatherUsageStats=false
```

La forma definitiva de registrar el proceso como servicio de Windows debe utilizar el mecanismo aprobado por TIC.

## 10. Configuración IIS

La publicación institucional debe contemplar:

- sitio HTTPS con certificado institucional;
- binding al DNS autorizado;
- reverse proxy hacia `http://127.0.0.1:8501` o destino interno equivalente;
- soporte de WebSocket;
- bloqueo del acceso directo al puerto interno;
- límites de tamaño de solicitud acordes al PDF máximo autorizado;
- timeouts compatibles con procesamiento OCR;
- logs y rotación conforme a política TIC;
- redirección o bloqueo de HTTP plano según estándar institucional.

## 11. Integración con SIEC

Si SIEC será el punto de acceso de los usuarios, TIC deberá definir el mecanismo de identidad e integración aprobado.

Streamlit es una interfaz web y no debe utilizarse como contrato de integración entre sistemas. Si SIEC requiere invocación programática, deberá incorporarse una capa API explícita sobre el motor con autenticación, autorización, límites, trazabilidad, códigos de respuesta y versionado.

Los parsers y la política OCR pueden reutilizarse detrás de dicha capa.

## 12. Protección de documentos

En producción:

- limitar acceso mediante ACL y roles institucionales;
- evitar persistencia innecesaria de PDFs;
- controlar directorios temporales;
- no registrar contenido del documento en logs;
- no almacenar secretos o PII en nombres de archivo cuando pueda evitarse;
- aplicar reglas institucionales de conservación y archivo;
- analizar entradas con controles antimalware definidos por TIC cuando corresponda.

El uso de PaddleOCR no cambia estas reglas: el mismo documento se reprocesa localmente dentro del flujo cuando la condición de fallback se cumple.

## 13. Logs y monitoreo

Registrar información operativa como fecha/hora, identificador de proceso, versión, método Digital/OCR, duración y código de resultado/error.

Para el fallback puede registrarse:

- intento PaddleOCR sí/no;
- motor seleccionado;
- cantidad de validaciones disponibles por motor;
- cantidad de validaciones fallidas por motor;
- tipo de error técnico del fallback.

No registrar texto OCR completo, importes de validación, nombres, RFC, cuentas, CLABE, conceptos de movimientos ni contenido del PDF.

## 14. Recursos y OCR

Antes de producción medir con corpus autorizado:

- páginas por documento;
- tiempo medio y percentiles;
- memoria máxima;
- CPU máxima;
- espacio temporal;
- concurrencia esperada;
- frecuencia real de activación del fallback;
- costo adicional de PaddleOCR cuando se activa;
- comportamiento ante lotes con múltiples fallas Tesseract.

PaddleOCR sólo se ejecuta cuando Tesseract presenta una falla de validación y el fallback está habilitado, evitando duplicar procesamiento OCR en documentos que validan correctamente.

## 15. Seguridad de red

El servidor debe aplicar acceso de usuarios únicamente por HTTPS, puerto Streamlit interno no expuesto, administración restringida, firewall mínimo y egress conforme a política institucional.

La operación normal de los motores OCR con modelos instalados localmente no requiere enviar documentos a Internet.

## 16. Respaldo, recuperación y rollback

Debe existir procedimiento para restaurar aplicación, configuración y artefactos aprobados.

Rollback específico PaddleOCR:

```powershell
$env:PADDLEOCR_FALLBACK_ENABLED = "0"
```

Después del reinicio controlado del servicio, Tesseract vuelve a ser el único motor OCR utilizado sin necesidad de revertir código o parsers.

## 17. Actualizaciones y vulnerabilidades

Cada liberación debe incluir:

- inventario de dependencias Python;
- auditoría de vulnerabilidades;
- revisión del runtime Tesseract;
- si PaddleOCR está habilitado, revisión de PaddleOCR/PaddlePaddle y modelos;
- hashes de artefactos/componentes requeridos;
- resultado de pruebas automatizadas;
- validación funcional correspondiente.

Las actualizaciones de runtime o modelos PaddleOCR requieren regresión antes de promoción, aun cuando no se modifique código del engine.

## 18. Verificación posterior al despliegue

Comprobar al menos:

- HTTPS y certificado;
- puerto interno no expuesto;
- carga de PDF;
- procesamiento Digital;
- OCR Tesseract;
- fallback PaddleOCR si fue habilitado;
- exportación;
- logs sin datos personales innecesarios;
- reinicio controlado;
- rollback disponible.

## 19. Responsabilidades

**Equipo de aplicación:** código, dependencias declaradas, pruebas, política de fallback, documentación técnica y evidencia de integridad.

**TIC / infraestructura:** Windows Server, IIS, DNS, TLS, red, cuenta de servicio, hardening, monitoreo, respaldos, gestión de parches, instalación/aprobación de PaddleOCR/PaddlePaddle/modelos y operación.

**Área funcional:** validación de resultados, UAT del fallback y aceptación funcional.

**Áreas competentes de seguridad/protección de datos:** controles, riesgos, Documento de Seguridad, incidentes y demás instrumentos aplicables.
