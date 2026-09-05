# Especificación técnica para integración institucional

## Estado Cuenta Engine — SABG / DGEC

**Fecha de corte:** 5 de septiembre de 2026

## 1. Resumen ejecutivo

Estado Cuenta Engine es un motor modular para lectura, clasificación, extracción, normalización, validación y exportación de información contenida en estados de cuenta bancarios.

La solución soporta PDFs digitales y documentos que requieren OCR local. Tesseract es el motor OCR primario; PaddleOCR está disponible como fallback local opcional y controlado cuando el resultado de Tesseract presenta fallas explícitas de validación financiera. Los parsers especializados por institución permanecen independientes del motor de lectura.

La versión está preparada para entrega técnica a TIC con:

- dependencias declaradas en `pyproject.toml`;
- pruebas automatizadas;
- validación de Python 3.12 y 3.13;
- build Windows mediante PyInstaller;
- auditoría de vulnerabilidades de dependencias;
- inventario de runtimes opcionales;
- hashes de integridad;
- documentación de despliegue Windows Server/IIS;
- lineamientos de seguridad y protección de datos.

## 2. Arquitectura funcional

| Etapa | Componente | Función |
|---|---|---|
| 1 | `ReaderManager` | lectura inicial y selección de camino Digital/OCR |
| 2 | `document_type_detector` | clasificación del documento |
| 3 | `bank_detector` | identificación de institución |
| 4 | `statement_processor` | resolución del parser y política de fallback OCR |
| 5 | `parsers/*` | extracción especializada |
| 6 | `models/*` | representación de dominio |
| 7 | `validators/*` | validaciones de consistencia |
| 8 | `mappers/*` / `exporters/*` | transformación y salida |

El diseño mantiene separadas la lectura, detección, lógica bancaria, validación y presentación para facilitar mantenimiento y pruebas de regresión.

## 3. Modos de procesamiento

### Digital

Utiliza texto y palabras con coordenadas extraídas directamente del PDF.

### OCR primario

Cuando el documento no contiene texto utilizable, el pipeline utiliza Tesseract de forma local y produce una representación espacial compatible con los parsers especializados.

### Fallback OCR controlado

Cuando Tesseract produce una o más validaciones financieras y al menos una falla, el sistema puede intentar PaddleOCR si el fallback está habilitado y existen modelos locales autorizados.

PaddleOCR procesa nuevamente el documento, pero el resultado pasa por el mismo parser bancario y el mismo validador. Sólo sustituye a Tesseract si reduce estrictamente el número de validaciones fallidas sin reducir el número de validaciones disponibles.

El fallback está deshabilitado por defecto. Si PaddleOCR no está disponible, falla o no mejora el resultado, se conserva Tesseract.

Los documentos no se envían a servicios externos como parte del procesamiento normal. Los modelos PaddleOCR se cargan desde rutas locales y la aplicación no los descarga durante el procesamiento.

Ver [`14_paddleocr_fallback.md`](14_paddleocr_fallback.md).

## 4. Interfaces

### Flet

Interfaz de escritorio disponible y empaquetable mediante PyInstaller para Windows. El artefacto PyInstaller actual conserva Tesseract y no incorpora PaddleOCR ni sus modelos.

### Streamlit

Interfaz web disponible para despliegue interno. En el escenario institucional previsto se publica detrás de IIS/reverse proxy y no se expone directamente a la red de usuarios. El runtime Python de esta vía puede instalar el extra opcional PaddleOCR cuando TIC lo autorice.

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
- gestión de vulnerabilidades y terceros;
- modelos OCR de terceros bajo inventario, integridad y aprobación institucional;
- ausencia de descarga de modelos PaddleOCR durante solicitudes productivas.

El detalle se encuentra en [`04_seguridad_datos_personales.md`](04_seguridad_datos_personales.md), [`11_gestion_vulnerabilidades_incidentes.md`](11_gestion_vulnerabilidades_incidentes.md) y [`14_paddleocr_fallback.md`](14_paddleocr_fallback.md).

## 6. Cadena de suministro de software

`pyproject.toml` es la fuente canónica de dependencias Python.

La automatización de calidad genera o valida:

- inventario de paquetes instalados;
- auditoría de vulnerabilidades conocidas;
- instalación/import del runtime PaddleOCR/PaddlePaddle opcional en Windows;
- build del paquete;
- build del ejecutable Windows;
- hash SHA-256 del ejecutable;
- hash SHA-256 del runtime Tesseract versionado.

Tesseract, PaddleOCR, PaddlePaddle y los modelos OCR se tratan como componentes de terceros sujetos a versión, procedencia, licencia, integridad y revisión de vulnerabilidades según su naturaleza.

Los modelos PaddleOCR no se versionan dentro del código fuente. Si se habilita el fallback, su paquete institucional debe registrar nombre, fuente, licencia y SHA-256.

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
        │
        ├─ Digital
        └─ OCR
            ├─ Tesseract primario
            └─ PaddleOCR fallback local
```

IIS/TIC administra publicación, TLS, DNS, red y controles de plataforma. La aplicación administra su lógica funcional. Cuando PaddleOCR se habilite, TIC administra además instalación del runtime/modelos, ACL, inventario y capacidad del servidor.

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
- operación y soporte;
- cuando aplique, ubicación, ACL, inventario y procedimiento de actualización de los modelos PaddleOCR.

Las áreas competentes deberán completar los instrumentos de protección de datos, clasificación, archivo y gestión de riesgos aplicables.

## 9. Calidad y regresión

Los parsers y reglas de extracción se consideran comportamiento crítico. Cualquier modificación funcional debe:

- identificar el banco/layout afectado;
- incluir pruebas específicas;
- preservar casos previamente correctos;
- validarse con corpus autorizado cuando corresponda;
- separar cambios funcionales de refactors cosméticos extensos.

El fallback PaddleOCR añade además pruebas de política para garantizar que:

- permanece deshabilitado por defecto;
- no se activa cuando Tesseract valida correctamente;
- no sustituye Tesseract con menor cobertura de validación;
- conserva Tesseract ante error del segundo motor.

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
- cuando aplique, expediente de modelos PaddleOCR autorizados;
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
- [`14_paddleocr_fallback.md`](14_paddleocr_fallback.md)
