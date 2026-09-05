# Especificación técnica para integración institucional

## Estado Cuenta Engine — SABG / DGEC

**Fecha de corte:** 5 de septiembre de 2026

## 1. Resumen ejecutivo

Estado Cuenta Engine es un motor modular para lectura, clasificación, extracción, normalización, validación y exportación de información contenida en estados de cuenta bancarios.

La solución soporta PDFs digitales y documentos que requieren OCR local. Tesseract permanece como motor OCR primario. PaddleOCR se incorpora como segundo motor local opcional para generar un candidato alterno cuando el resultado de Tesseract requiere revisión objetiva. Los parsers especializados por institución permanecen independientes del motor de lectura.

Cuando ambos candidatos están disponibles, la aplicación conserva Tesseract y PaddleOCR en memoria, genera una recomendación automática conservadora y permite que el usuario autorizado seleccione en Flet o Streamlit cuál resultado desea revisar y utilizar para la exportación.

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
| 4 | `statement_processor` | resolución del parser y política de revisión OCR |
| 5 | `parsers/*` | extracción especializada |
| 6 | `models/*` | representación de dominio y candidatos OCR |
| 7 | `validators/*` | validaciones de consistencia |
| 8 | `mappers/*` / `exporters/*` | transformación y salida |

El diseño mantiene separadas la lectura, detección, lógica bancaria, validación, selección OCR y presentación para facilitar mantenimiento y pruebas de regresión.

## 3. Modos de procesamiento

### Digital

Utiliza texto y palabras con coordenadas extraídas directamente del PDF. Los documentos digitales no participan en la comparación Tesseract/PaddleOCR.

### OCR primario

Cuando el documento no contiene texto utilizable, el pipeline utiliza Tesseract de forma local y produce una representación espacial compatible con los parsers especializados.

### Segundo OCR controlado

Si el resultado de Tesseract presenta una señal objetiva de revisión y el segundo OCR está habilitado para el banco, el sistema intenta PaddleOCR con modelos locales autorizados.

Las señales actuales incluyen:

- ausencia de movimientos;
- una o más validaciones fallidas;
- ausencia de validaciones principales de depósitos/abonos o retiros/cargos;
- ausencia total de validaciones disponibles.

PaddleOCR reprocesa el mismo documento y su salida pasa por el mismo parser bancario y los mismos validadores.

### Revisión dual

Si PaddleOCR produce un candidato válido, se conservan ambos resultados:

- Tesseract;
- PaddleOCR.

El sistema recomienda inicialmente uno de ellos mediante una política conservadora basada en cobertura de validación, validaciones fallidas y disponibilidad de movimientos. La recomendación no elimina el candidato alterno.

Flet y Streamlit permiten cambiar el motor seleccionado. El candidato seleccionado alimenta:

- datos de cuenta;
- resumen financiero;
- movimientos;
- validaciones;
- exportación Excel.

La comparación se mantiene en memoria durante la sesión y no requiere persistir automáticamente copias alternas del texto OCR.

El segundo OCR está deshabilitado por defecto. Si PaddleOCR no está instalado, los modelos no están configurados o la inferencia falla, el flujo conserva el resultado Tesseract disponible.

Los documentos no se envían a servicios externos. Los modelos PaddleOCR se cargan desde rutas locales y la aplicación no los descarga durante el procesamiento.

Ver [`14_paddleocr_fallback.md`](14_paddleocr_fallback.md).

## 4. Interfaces

### Flet

Interfaz de escritorio para Windows. Cuando un documento OCR dispone de dos candidatos, muestra una comparación Tesseract/PaddleOCR con cantidad de movimientos, validaciones y taches, además del selector del candidato que se visualizará y exportará.

El artefacto PyInstaller actual conserva Tesseract y no incorpora PaddlePaddle ni modelos PaddleOCR dentro del ejecutable.

### Streamlit

Interfaz web disponible para despliegue interno. En el escenario institucional previsto se publica detrás de IIS/reverse proxy. Cuando existen dos candidatos OCR, permite alternarlos y conserva la selección para la exportación.

El runtime Python de esta vía puede instalar el extra opcional PaddleOCR cuando TIC lo autorice.

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
- modelos OCR bajo inventario, integridad y aprobación institucional;
- ausencia de descarga de modelos PaddleOCR durante solicitudes productivas;
- comparación de candidatos OCR en memoria, sin persistencia automática de copias alternas.

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

Los modelos PaddleOCR no se versionan dentro del código fuente. Su paquete institucional debe registrar nombre, fuente, licencia y SHA-256.

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
            └─ PaddleOCR local cuando se requiere revisión
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

La revisión dual PaddleOCR añade pruebas para garantizar que:

- permanece deshabilitada por defecto;
- no se ejecuta cuando Tesseract obtiene las validaciones principales correctas;
- se activa ante taches, ausencia de validadores principales o ausencia de movimientos;
- conserva ambos candidatos cuando PaddleOCR logra procesar el documento;
- no recomienda PaddleOCR cuando pierde cobertura de validación relevante;
- permite cambiar el candidato seleccionado sin modificar parsers;
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
