# Portabilidad, contenedores y despliegue institucional

## Estado Cuenta Engine — SABG / DGEC

**Fecha de corte:** 5 de septiembre de 2026

## 1. Objetivo

Mantener el motor desacoplado de una plataforma concreta de control de versiones, integración continua o despliegue. El código debe poder migrarse a la infraestructura institucional aprobada por TIC conservando sus pruebas, artefactos, controles y evidencia técnica.

La portabilidad no significa que cualquier plataforma sea válida para producción. La selección final de repositorio, CI/CD, registro de artefactos, servidor, contenedores, red y mecanismos de identidad corresponde a TIC/SABG.

## 2. Controles portables

Los siguientes controles deben existir independientemente de la herramienta elegida:

- control de versiones;
- revisión y aprobación de cambios;
- protección de la rama o línea base productiva;
- compilación automatizada;
- pruebas unitarias y de regresión;
- análisis estático;
- auditoría de dependencias;
- inventario de software;
- construcción reproducible de artefactos;
- hashes de integridad;
- almacenamiento seguro de secretos;
- trazabilidad de liberaciones;
- rollback y recuperación.

## 3. Vías de empaquetado

### 3.1 Ejecutable Windows

El build con PyInstaller sigue siendo la vía compatible con la aplicación actual de escritorio y con escenarios Windows.

Ventajas:

- continuidad con la aplicación actual;
- artefacto único para distribución controlada;
- validación automática del build;
- hash SHA-256 del ejecutable;
- posibilidad de firma de código si TIC la requiere.

### 3.2 Imagen OCI para Streamlit

El proyecto incluye un `Dockerfile` opcional para construir una imagen OCI de la interfaz Streamlit. No sustituye el EXE ni cambia la lógica del motor.

La imagen está diseñada con estos principios:

- Python 3.12 soportado por el proyecto;
- Tesseract instalado desde paquetes del sistema de la imagen;
- instalación desde `pyproject.toml`;
- ejecución con usuario no privilegiado;
- contexto de build minimizado mediante `.dockerignore`;
- `HEALTHCHECK` sobre el endpoint de salud de Streamlit;
- sin datos reales, secretos ni archivos operativos dentro de la imagen.

## 4. Uso esperado de contenedores

Una imagen OCI puede ser útil cuando TIC requiera:

- despliegues reproducibles;
- aislamiento del runtime;
- separación entre aplicación e infraestructura;
- versionado y promoción de artefactos;
- ejecución en una plataforma de contenedores;
- escalamiento horizontal;
- integración con un reverse proxy o gateway institucional.

No debe asumirse que Docker Desktop o un servicio público de contenedores sea válido para producción. TIC debe determinar el motor de contenedores, registro de imágenes, plataforma de orquestación y política de operación autorizados.

## 5. Seguridad del contenedor

Antes de producción, TIC deberá validar como mínimo:

- imagen base aprobada y actualizada;
- escaneo de vulnerabilidades de la imagen;
- ejecución sin privilegios;
- filesystem de sólo lectura cuando sea compatible;
- límites de CPU/memoria;
- directorios temporales controlados;
- secretos montados en runtime, nunca incluidos en la imagen;
- TLS terminado en componente institucional autorizado;
- red y exposición de puertos restringidas;
- logging y monitoreo institucional;
- política de actualización y rollback de imágenes.

## 6. Integración futura con SIEC

La interfaz actual de Streamlit no debe confundirse con una API de integración. Si SIEC necesita consumo programático, la arquitectura recomendada es separar el motor de extracción de la capa de exposición mediante una API dedicada.

Esa API deberá definir, con TIC:

- autenticación institucional;
- autorización por roles o scopes;
- identidad de servicio;
- límites de tamaño y tipo de archivo;
- timeouts y concurrencia;
- trazabilidad de solicitudes;
- manejo seguro de errores;
- versionado del contrato;
- cifrado en tránsito;
- política de retención de documentos y resultados.

El motor existente puede mantenerse detrás de esa capa sin reescribir los parsers.

## 7. Migración de repositorio y línea base

Cuando el proyecto se traslade a una plataforma institucional, la línea base técnica debería conservar al menos:

- código fuente aprobado;
- versión/tag institucional;
- `pyproject.toml`;
- pruebas automatizadas;
- documentación técnica y de seguridad;
- scripts/configuración de build que sigan siendo aplicables;
- inventario de dependencias del release;
- hashes de artefactos;
- evidencia de UAT y aprobaciones en el sistema institucional correspondiente.

La historia de desarrollo y los mecanismos de conservación de evidencia deben seguir la política institucional aplicable; el repositorio de aplicación no debe usarse como sustituto de los sistemas oficiales de gestión de cambios o expedientes.

## 8. Criterio de decisión para TIC

El proyecto queda preparado para que TIC pueda elegir entre:

- ejecución de escritorio/Windows mediante EXE;
- servicio Streamlit contenido;
- futura API dedicada sobre el mismo motor;
- combinación de estas opciones según el proceso institucional.

La decisión final debe basarse en arquitectura, identidad, operación, seguridad, volumen, continuidad y mantenimiento, no en preferencia de una herramienta específica.
