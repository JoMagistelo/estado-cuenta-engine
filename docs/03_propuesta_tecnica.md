# Especificación técnica para integración institucional

## Estado Cuenta Engine — SABG / DGEC

**Fecha de corte:** 5 de septiembre de 2026

## 1. Resumen ejecutivo

Estado Cuenta Engine es un motor modular para lectura, clasificación, extracción, normalización, validación y exportación de información contenida en estados de cuenta bancarios.

La solución soporta PDFs digitales y documentos que requieren OCR local con Tesseract, incorpora parsers especializados por institución y genera una salida estructurada para consumo operativo o integración con otros componentes institucionales.

La versión está preparada para entrega técnica a TIC con:

- dependencias declaradas en `pyproject.toml`;
- pruebas automatizadas;
- validación de Python 3.12 y 3.13;
- build Windows mediante PyInstaller;
- auditoría de vulnerabilidades de dependencias;
- hashes de integridad;
- documentación de despliegue Windows Server/IIS;
- lineamientos de seguridad y protección de datos.

## 2. Arquitectura funcional

| Etapa | Componente | Función |
|---|---|---|
| 1 | `ReaderManager` | lectura inicial y selección de camino Digital/OCR |
| 2 | `document_type_detector` | clasificación del documento |
| 3 | `bank_detector` | identificación de institución |
| 4 | `statement_processor` | resolución del parser correspondiente |
| 5 | `parsers/*` | extracción especializada |
| 6 | `models/*` | representación de dominio |
| 7 | `validators/*` | validaciones de consistencia |
| 8 | `mappers/*` / `exporters/*` | transformación y salida |

El diseño mantiene separadas la lectura, detección, lógica bancaria, validación y presentación para facilitar mantenimiento y pruebas de regresión.

## 3. Modos de procesamiento

### Digital

Utiliza texto y palabras con coordenadas extraídas directamente del PDF.

### OCR

Cuando el documento no contiene texto utilizable, el pipeline utiliza Tesseract de forma local y produce una representación espacial compatible con los parsers especializados.

Los documentos no se envían a servicios externos como parte del procesamiento normal.

## 4. Interfaces

### Flet

Interfaz de escritorio disponible y empaquetable mediante PyInstaller para Windows.

### Streamlit

Interfaz web disponible para despliegue interno. En el escenario institucional previsto se publica detrás de IIS/reverse proxy y no se expone directamente a la red de usuarios.

### Integración con SIEC

El motor está desacoplado de la identidad institucional. Si SIEC requiere integración programática, se recomienda incorporar una capa API dedicada sobre el mismo motor en lugar de utilizar Streamlit como contrato entre sistemas.

La API podrá agregar autenticación, autorización, límites de archivo, trazabilidad y versionado sin modificar los parsers.

## 5. Seguridad y privacidad

El sistema procesa información financiera y datos personales. Los principios técnicos son:

- procesamiento local dentro de infraestructura autorizada;
- mínimo privilegio;
- secretos fuera del código;
- TLS en la capa de publicación;
- minimización de logs;
- separación de temporales y salidas;
- control de acceso institucional;
- trazabilidad de versiones y artefactos;
- gestión de vulnerabilidades y terceros.

El detalle se encuentra en [`04_seguridad_datos_personales.md`](04_seguridad_datos_personales.md) y [`11_gestion_vulnerabilidades_incidentes.md`](11_gestion_vulnerabilidades_incidentes.md).

## 6. Cadena de suministro de software

`pyproject.toml` es la fuente canónica de dependencias Python.

La automatización de calidad genera:

- inventario de paquetes instalados;
- auditoría de vulnerabilidades conocidas;
- build del paquete;
- build del ejecutable Windows;
- hash SHA-256 del ejecutable;
- hash SHA-256 del runtime Tesseract versionado.

Tesseract se trata como componente de terceros sujeto a versión, procedencia, licencia, integridad y revisión de vulnerabilidades.

## 7. Despliegue institucional

La arquitectura recomendada para la interfaz web es:

```text
Usuario institucional
        │
        ▼
HTTPS
        │
        ▼
IIS / reverse proxy institucional
        │
        ▼
Streamlit en interfaz local
        │
        ▼
Estado Cuenta Engine
```

IIS/TIC administra publicación, TLS, DNS, red y controles de plataforma. La aplicación administra exclusivamente su lógica funcional.

La guía completa se encuentra en [`06_despliegue_produccion_windows.md`](06_despliegue_produccion_windows.md).

## 8. Requisitos de integración institucional

La puesta en servicio requiere que TIC defina o confirme:

- Windows Server soportado;
- IIS/reverse proxy;
- DNS y certificado TLS;
- cuenta de servicio;
- ACL y rutas de trabajo;
- firewall/segmentación;
- mecanismo de identidad y autorización;
- monitoreo y logs;
- respaldo y recuperación;
- gestión de parches;
- procedimiento de incidentes;
- operación y soporte.

Las áreas competentes deberán completar los instrumentos de protección de datos, clasificación, archivo y gestión de riesgos aplicables.

## 9. Calidad y regresión

Los parsers y reglas de extracción se consideran comportamiento crítico. Cualquier modificación funcional debe:

- identificar el banco/layout afectado;
- incluir pruebas específicas;
- preservar casos previamente correctos;
- validarse con corpus autorizado cuando corresponda;
- separar cambios funcionales de refactors cosméticos extensos.

## 10. Entregables técnicos

La entrega técnica del producto se compone de:

- código fuente de la versión;
- `pyproject.toml`;
- documentación técnica;
- suite de pruebas;
- configuración de build;
- ejecutable Windows cuando corresponda;
- inventario de dependencias;
- auditoría de vulnerabilidades;
- hashes de integridad;
- notas de versión;
- guía de despliegue y rollback.

## 11. Referencias internas

- [`02_arquitectura.md`](02_arquitectura.md)
- [`04_seguridad_datos_personales.md`](04_seguridad_datos_personales.md)
- [`05_normativa_tic_apf.md`](05_normativa_tic_apf.md)
- [`06_despliegue_produccion_windows.md`](06_despliegue_produccion_windows.md)
- [`09_verificacion_tecnica_version.md`](09_verificacion_tecnica_version.md)
- [`10_matriz_evidencias_tic.md`](10_matriz_evidencias_tic.md)
- [`12_checklist_liberacion_produccion.md`](12_checklist_liberacion_produccion.md)
