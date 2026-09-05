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
        └─ OCR local Tesseract
```

Principios:

- IIS es el único componente expuesto a la red institucional;
- Streamlit escucha únicamente en interfaz local cuando IIS y la aplicación residen en el mismo servidor;
- el puerto interno de Streamlit no debe publicarse directamente a usuarios;
- TLS se administra en IIS con certificado institucional;
- los documentos permanecen dentro de infraestructura autorizada;
- el motor no requiere servicios externos para procesar estados de cuenta;
- Tesseract opera localmente.

Si TIC utiliza un reverse proxy institucional distinto de IIS, deberá conservar los mismos principios de aislamiento, TLS, control de acceso y trazabilidad.

## 3. Componentes

### IIS

Responsable de:

- publicación HTTPS;
- certificado TLS institucional;
- nombre DNS;
- reglas de red y exposición;
- reverse proxy hacia el proceso Streamlit;
- cabeceras y controles definidos por TIC;
- soporte de WebSocket requerido por la interfaz Streamlit;
- logging de infraestructura conforme a política institucional.

La implementación concreta del reverse proxy —por ejemplo mediante módulos autorizados por TIC— debe ajustarse al baseline institucional de IIS.

### Streamlit

Responsable de:

- interfaz web de carga y consulta;
- gestión de sesión de la aplicación;
- invocación del pipeline;
- presentación y descarga de resultados.

En servidor debe ejecutarse en modo headless, sin abrir navegador, sin modo de desarrollo y limitado a la interfaz/puerto internos definidos por TIC.

### Estado Cuenta Engine

Responsable de:

- clasificación Digital/OCR;
- lectura de documento;
- detección de institución;
- parsing especializado;
- normalización y validación;
- exportación de resultados.

El motor no administra identidad institucional, certificados, DNS ni políticas de red.

### Tesseract

Se utiliza exclusivamente como OCR local. El runtime distribuido con la versión Windows debe quedar sujeto a inventario, versión, licencia, hash de integridad y revisión de vulnerabilidades dentro del expediente de liberación.

## 4. Requisitos del servidor

Configuración base esperada:

- Windows Server soportado por la infraestructura institucional;
- IIS con HTTPS habilitado;
- Python 3.12 o 3.13 para la vía Streamlit;
- almacenamiento local o institucional autorizado;
- runtime Tesseract aprobado;
- cuenta de servicio de mínimo privilegio;
- sincronización de tiempo institucional;
- antimalware/EDR y controles de plataforma definidos por TIC;
- capacidad suficiente de CPU, memoria y espacio temporal para OCR.

La versión exacta de Windows Server y los componentes IIS deben ser definidos por TIC conforme a su plataforma soportada.

## 5. Cuenta de servicio

La aplicación debe ejecutarse con una identidad de servicio institucional, no con una cuenta personal ni con privilegios administrativos salvo excepción formalmente justificada.

Permisos mínimos:

- lectura/ejecución sobre código y runtime;
- lectura/escritura sobre directorios temporales autorizados;
- escritura sobre salidas autorizadas cuando corresponda;
- escritura sobre logs técnicos si éstos se almacenan localmente.

La cuenta no debe tener acceso a recursos que no sean necesarios para el proceso.

## 6. Estructura de directorios

Ejemplo de separación operativa:

```text
C:\Apps\EstadoCuentaEngine\
    app\
    src\
    .venv\
    pyproject.toml

D:\EstadoCuentaEngine\Work\
D:\EstadoCuentaEngine\Output\
D:\EstadoCuentaEngine\Logs\
```

Las rutas son referenciales. TIC puede utilizar volúmenes, shares o ubicaciones equivalentes siempre que se apliquen ACL, respaldo y retención de acuerdo con la clasificación de información.

No deben utilizarse perfiles personales, escritorios de usuario ni carpetas públicas como almacenamiento operativo.

## 7. Instalación de la aplicación web

Procedimiento técnico de referencia:

```powershell
py -3.12 -m venv C:\Apps\EstadoCuentaEngine\.venv
C:\Apps\EstadoCuentaEngine\.venv\Scripts\python.exe -m pip install --upgrade pip
C:\Apps\EstadoCuentaEngine\.venv\Scripts\python.exe -m pip install -e "C:\Apps\EstadoCuentaEngine[streamlit]"
```

El entorno productivo debe instalarse desde la versión aprobada y no desde una estación personal.

Cuando la política institucional requiera instalación sin acceso a Internet, las dependencias deberán entregarse mediante repositorio interno, caché o paquete offline aprobado por TIC.

## 8. Ejecución de Streamlit

Comando de referencia cuando IIS y Streamlit se encuentran en el mismo servidor:

```powershell
C:\Apps\EstadoCuentaEngine\.venv\Scripts\python.exe -m streamlit run `
  C:\Apps\EstadoCuentaEngine\app\main_streamlit.py `
  --server.address=127.0.0.1 `
  --server.port=8501 `
  --server.headless=true `
  --browser.gatherUsageStats=false
```

La forma definitiva de registrar el proceso como servicio de Windows debe utilizar el mecanismo aprobado por TIC. La aplicación debe reiniciarse de forma controlada tras reinicio del servidor y registrar fallas de arranque.

## 9. Configuración IIS

La publicación institucional debe contemplar:

- sitio HTTPS con certificado emitido/aprobado institucionalmente;
- binding al nombre DNS autorizado;
- reverse proxy hacia `http://127.0.0.1:8501` o destino interno equivalente;
- soporte de WebSocket;
- bloqueo del acceso directo al puerto interno desde otras redes;
- límites de tamaño de solicitud acordes al tamaño máximo de PDF autorizado;
- timeouts compatibles con procesamiento OCR;
- logs y rotación conforme a política TIC;
- redirección o bloqueo de HTTP plano según estándar institucional.

No deben incluirse llaves privadas, contraseñas o secretos dentro del repositorio o del código.

## 10. Integración con SIEC

La arquitectura prevista debe separar autenticación institucional del motor de extracción.

Si SIEC será el punto de acceso de los usuarios, TIC deberá definir el mecanismo de integración: identidad federada, encabezados confiables, token institucional, API o esquema equivalente aprobado.

Streamlit es una interfaz web; no debe utilizarse como contrato de integración entre sistemas. Si SIEC requiere invocación programática, deberá incorporarse una capa API explícita sobre el motor.

Una API institucional deberá definir al menos:

- autenticación y autorización;
- identidad de servicio;
- límites de archivo;
- timeouts y concurrencia;
- códigos de respuesta;
- trazabilidad de solicitudes;
- manejo seguro de errores;
- versionado del contrato;
- política de retención de entrada y salida.

Los parsers y el motor pueden reutilizarse sin cambios detrás de dicha capa.

## 11. Protección de documentos

Los estados de cuenta contienen información financiera y datos personales. En producción:

- limitar acceso mediante ACL y roles institucionales;
- evitar persistencia innecesaria de PDFs;
- controlar directorios temporales;
- no registrar contenido del documento en logs;
- no almacenar secretos o PII en nombres de archivo cuando pueda evitarse;
- aplicar las reglas institucionales de conservación y archivo;
- analizar archivos de entrada con los controles antimalware definidos por TIC cuando corresponda.

## 12. Logs y monitoreo

Los logs técnicos deben priorizar información operativa:

- fecha/hora;
- identificador de proceso;
- versión desplegada;
- método Digital/OCR;
- institución detectada cuando sea necesario;
- duración;
- código de resultado/error.

Evitar:

- texto completo extraído;
- nombres de personas;
- RFC, CURP, cuentas o CLABE completas;
- conceptos de movimientos;
- contenido del PDF.

La retención, centralización, SIEM y acceso a logs serán definidos por TIC.

## 13. Recursos y OCR

Tesseract puede consumir CPU y memoria de forma intensiva. Antes de dimensionar producción se recomienda medir con el corpus autorizado:

- páginas por documento;
- tiempo medio y percentiles de procesamiento;
- memoria máxima;
- CPU máxima;
- espacio temporal;
- concurrencia esperada;
- comportamiento ante PDFs grandes o dañados.

Los límites operativos deben quedar configurados para evitar agotamiento de recursos.

## 14. Seguridad de red

El servidor debe aplicar:

- acceso de usuarios únicamente por HTTPS;
- puerto interno de Streamlit no expuesto externamente;
- administración del servidor limitada a redes/roles autorizados;
- reglas de firewall mínimas;
- salidas a Internet restringidas conforme a política institucional;
- DNS y certificados administrados por TIC.

El procesamiento bancario no requiere enviar documentos a servicios externos.

## 15. Respaldo y recuperación

Debe existir procedimiento para:

- respaldar configuración necesaria;
- conservar artefactos de liberación aprobados;
- restaurar la aplicación;
- restaurar certificados/configuración conforme al procedimiento institucional;
- volver a la versión previa;
- validar funcionamiento después de restauración.

No se recomienda respaldar indiscriminadamente archivos temporales ni duplicados de estados de cuenta.

## 16. Actualizaciones y vulnerabilidades

Cada liberación debe incluir:

- inventario de dependencias Python;
- resultado de auditoría de vulnerabilidades;
- revisión del runtime Tesseract;
- hash SHA-256 del artefacto distribuido;
- resultado de pruebas automatizadas;
- validación funcional correspondiente.

Los parches de Windows Server, IIS, Python y demás componentes de plataforma corresponden al proceso institucional de gestión de vulnerabilidades y cambios.

## 17. Liberación

Secuencia recomendada:

```text
Versión candidata
      │
      ▼
CI / pruebas automatizadas
      │
      ▼
Auditoría de dependencias
      │
      ▼
Build + hash de integridad
      │
      ▼
UAT funcional
      │
      ▼
Revisión TIC / seguridad
      │
      ▼
Despliegue controlado
      │
      ▼
Smoke test
      │
      ▼
Monitoreo
```

## 18. Verificación posterior al despliegue

Comprobar al menos:

- sitio HTTPS disponible con certificado válido;
- acceso HTTP no autorizado bloqueado o redirigido conforme a política;
- puerto interno de Streamlit no accesible desde red de usuarios;
- carga de PDF autorizada;
- procesamiento Digital correcto;
- procesamiento OCR correcto;
- exportación correcta;
- logs sin datos personales innecesarios;
- reinicio controlado del servicio;
- rollback disponible.

## 19. Responsabilidades

**Equipo de aplicación:** código, dependencias declaradas, pruebas, documentación técnica, artefacto y evidencia de integridad.

**TIC / infraestructura:** Windows Server, IIS, DNS, TLS, red, cuenta de servicio, hardening, monitoreo, respaldos, gestión de parches y operación.

**Área funcional:** validación de resultados y aceptación funcional.

**Áreas competentes de seguridad/protección de datos:** controles, riesgos, Documento de Seguridad, incidentes y demás instrumentos aplicables.
