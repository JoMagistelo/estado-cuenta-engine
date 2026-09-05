# Verificación técnica de la versión

## Estado Cuenta Engine — SABG / DGEC

**Fecha de corte:** 5 de septiembre de 2026

## 1. Objetivo

Documentar las comprobaciones técnicas aplicadas a la versión para demostrar consistencia del código, preservación de la lógica de extracción y capacidad de construcción del artefacto distribuible.

Esta verificación complementa, pero no sustituye, las validaciones funcionales y de infraestructura que correspondan al proceso institucional de liberación.

## 2. Alcance revisado

La revisión técnica abarca:

- interfaces Flet y Streamlit;
- pipeline de procesamiento;
- readers Digital/OCR;
- parsers y extractores bancarios;
- modelos y validadores;
- exportadores;
- pruebas automatizadas;
- empaquetado Python;
- build Windows con PyInstaller;
- dependencias y componentes de terceros.

## 3. Regla de preservación funcional

Se considera funcionalmente sensible cualquier cambio que pueda modificar:

- banco detectado;
- clasificación Digital/OCR;
- parser seleccionado;
- datos de cuenta;
- resumen financiero;
- fecha, concepto, referencia, cargo, abono o saldo de movimientos;
- clave de rastreo o matching SPEI;
- validaciones financieras;
- estructura y contenido de exportaciones.

Los trabajos de preparación técnica de esta versión no modifican deliberadamente esos contratos. Los parsers se tratan como lógica crítica y los cambios futuros sobre ellos deberán acompañarse de pruebas de regresión específicas.

## 4. Compatibilidad de Python

La aplicación utiliza Python 3.12 como versión mínima soportada por la interfaz actual. La automatización de calidad valida Python 3.12 y 3.13.

No se declara compatibilidad con versiones que el código vigente no puede compilar.

## 5. Dependencias

`pyproject.toml` es la fuente canónica de dependencias.

La clasificación utilizada separa:

- runtime del motor;
- interfaz Streamlit;
- interfaz Flet;
- herramientas de desarrollo/calidad;
- herramientas de empaquetado.

Las dependencias resueltas de cada liberación deben conservarse como evidencia del artefacto construido.

## 6. Pruebas automatizadas

La automatización de calidad ejecuta:

1. instalación del proyecto desde `pyproject.toml`;
2. compilación de `app/`, `src/` y `tests/`;
3. análisis estático de errores críticos con Ruff;
4. suite Pytest sintética/autocontenida;
5. build del paquete Python;
6. smoke test de dependencias Streamlit/Flet;
7. build real del ejecutable Windows mediante PyInstaller;
8. verificación de existencia del ejecutable esperado.

Las pruebas que requieren PDFs reales se mantienen fuera del flujo automático y se ejecutan únicamente con archivos autorizados mediante las variables de entorno documentadas.

## 7. Evidencia de seguridad de software

La versión incorpora comprobaciones de:

- inventario de paquetes instalados;
- auditoría de vulnerabilidades conocidas de dependencias Python;
- hash SHA-256 del runtime Tesseract versionado;
- hash SHA-256 del ejecutable construido.

Esta evidencia facilita la revisión de cadena de suministro y la identificación precisa del artefacto entregado.

## 8. Componentes de terceros

El runtime Tesseract incluido en la distribución Windows se considera componente de terceros y debe mantenerse bajo control de versión/procedencia/licencia/integridad/vulnerabilidades dentro del expediente de liberación.

Las actualizaciones de Tesseract o de cualquier dependencia del flujo OCR requieren validación de regresión cuando puedan alterar resultados de extracción.

## 9. Datos de prueba

No deben incorporarse estados de cuenta reales ni archivos derivados con información personal al repositorio.

Las pruebas de integración con documentos reales deben ejecutarse en entorno autorizado y sus resultados deben registrarse en el expediente institucional correspondiente, sin trasladar PII al código fuente.

## 10. Criterio de aceptación técnica

Una versión candidata se considera técnicamente aceptable para pasar a validación institucional cuando:

- la automatización de calidad está en verde;
- el artefacto Windows se construye correctamente;
- no existen vulnerabilidades bloqueantes sin tratamiento;
- el inventario de dependencias está identificado;
- el hash del artefacto está disponible;
- los cambios funcionales, cuando existan, cuentan con regresión suficiente;
- la UAT funcional correspondiente ha sido planificada o ejecutada según el tipo de liberación.

## 11. Validaciones institucionales complementarias

La puesta en servicio requiere adicionalmente los controles que correspondan a TIC y a las áreas competentes, entre ellos:

- Windows Server e IIS;
- DNS y TLS;
- cuenta de servicio;
- hardening;
- red/firewall;
- autenticación y autorización;
- monitoreo y logs;
- respaldo y recuperación;
- gestión de incidentes;
- protección de datos personales;
- retención y archivo;
- aceptación funcional.

La guía operativa se encuentra en [`06_despliegue_produccion_windows.md`](06_despliegue_produccion_windows.md) y la matriz de evidencias en [`10_matriz_evidencias_tic.md`](10_matriz_evidencias_tic.md).
