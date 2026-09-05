# Matriz de evidencias TIC y ciberseguridad

## Estado Cuenta Engine — SABG / DGEC

**Fecha de corte:** 5 de septiembre de 2026

Esta matriz separa tres cosas que no deben confundirse:

1. controles que el repositorio puede demostrar por sí mismo;
2. controles que requieren infraestructura o configuración institucional;
3. aprobaciones y documentos cuya titularidad corresponde a TIC, seguridad, protección de datos, jurídica, archivos u otras áreas competentes.

Un control marcado como implementado en el repositorio no equivale a certificación ni autorización de producción.

## 1. Criterio de estado

- **Implementado:** existe evidencia técnica verificable en el repositorio/CI.
- **Parcial:** existe una parte, pero falta evidencia institucional o cobertura completa.
- **Institucional:** no corresponde resolverlo exclusivamente desde el código.
- **Pendiente:** falta definir o ejecutar antes de producción.

## 2. Matriz

| Dominio | Estado | Evidencia actual | Pendiente / responsable |
|---|---|---|---|
| Control de cambios | Parcial | historial Git, CI y checklist de cambios | configurar en la plataforma institucional la protección de la línea base, revisiones y checks obligatorios |
| Equivalencia funcional | Implementado/Parcial | suite sintética, compileall, Ruff, build | UAT con corpus autorizado y resultados esperados |
| Gestión de dependencias Python | Implementado | `pyproject.toml`, rangos controlados y auditoría CI | conservar inventario exacto por release y proceso de actualización aprobado |
| Vulnerabilidades de dependencias | Implementado | `pip-audit` en CI | proceso institucional de excepción/remediación |
| Build reproducible controlado | Parcial | build Windows/PyInstaller en CI, hash SHA-256 del EXE | firma de código y canal oficial de distribución si TIC lo requiere |
| Contenedor OCI opcional | Implementado/Parcial | `Dockerfile`, `.dockerignore`, build y health check en CI | escaneo de imagen, registro institucional, hardening y plataforma aprobada por TIC |
| Terceros/binarios `vendor/` | Parcial | inclusión explícita y evidencia de hash | procedencia, versión, licencia, CVE, aprobación y ciclo de actualización de Tesseract |
| Datos personales en repositorio | Implementado a nivel repo | `.gitignore`, pruebas opt-in, `SECURITY.md` y reglas de cambio | supervisión y procedimiento institucional |
| Clasificación de información | Institucional | documentación de sensibilidad del sistema | clasificación formal SABG y reglas de manejo |
| Documento de Seguridad | Institucional/Pendiente | insumos técnicos documentados | responsable de protección de datos/SABG |
| Análisis de riesgos y brecha | Parcial | riesgos técnicos identificados en docs | análisis institucional aprobado y plan de tratamiento |
| Evaluación de impacto en protección de datos | Institucional/Pendiente | se documenta necesidad de determinar procedencia | área competente de protección de datos |
| Identidad y autenticación | Institucional/Pendiente | arquitectura prevista de integración con SIEC | definir SSO/API, MFA, identidad de servicio, expiración y revocación |
| Autorización/RBAC | Institucional/Pendiente | separación conceptual de motor e identidad | matriz de roles y mínimo privilegio |
| Secretos y certificados | Parcial | prohibición de versionado y `.gitignore` | almacén institucional de secretos/certificados y rotación |
| TLS y comunicaciones | Institucional/Pendiente | requisito documentado | terminación TLS, certificados y hardening de servidor/red |
| Logs y monitoreo | Parcial | criterios de no registrar PII documentados | plataforma institucional, retención, alertas y acceso |
| Gestión de incidentes | Parcial | `SECURITY.md` y guía de incidentes | canal, responsables, CSIRT/TIC, tiempos y formatos institucionales |
| Vulneraciones de datos personales | Institucional/Pendiente | criterio de escalamiento documentado | bitácora y procedimiento legal/institucional |
| Respaldo/recuperación | Institucional/Pendiente | requisito identificado | RPO/RTO, respaldo, restauración y pruebas |
| Continuidad operativa | Institucional/Pendiente | requisito identificado | integración al BCP/DR institucional |
| Gestión de parches | Parcial | auditoría automatizada e inventario de paquetes | Windows Server, Tesseract, imagen base y demás componentes de infraestructura |
| Integridad de artefactos | Implementado/Parcial | hash SHA-256 generado en CI | custodia, firma/certificado y registro de release institucional |
| Inventario de software | Implementado/Parcial | inventario de paquetes generado en CI | integrar con CMDB/SBOM/inventario institucional si aplica |
| Segregación desarrollo/producción | Institucional | CI evita depender de archivos locales | entornos y permisos definidos por TIC |
| Retención y archivo | Institucional/Pendiente | distinción entre temporales y documentos de archivo | catálogo de disposición, expediente y reglas SABG |
| Capacitación | Institucional/Pendiente | documentación técnica disponible | programa institucional de capacitación y evidencia |

## 3. Evidencia automática del repositorio

La automatización de calidad debe demostrar en cada cambio candidato:

- compilación de `app/`, `src/` y `tests/`;
- errores críticos de código mediante Ruff;
- pruebas unitarias y sintéticas;
- build del paquete Python;
- smoke de dependencias de interfaces;
- build real del ejecutable Windows;
- auditoría de vulnerabilidades conocidas en dependencias Python;
- inventario de paquetes resueltos;
- hash SHA-256 del ejecutable generado;
- build y health check del contenedor OCI opcional.

Estas evidencias permiten a TIC revisar un cambio sin depender del equipo personal del desarrollador.

## 4. Configuración administrativa del repositorio institucional

Los controles que viven fuera del código deben configurarse en la plataforma de desarrollo aprobada por TIC. Como mínimo, para una línea base productiva se recomienda:

- prohibición de cambios directos a la rama o línea base productiva para desarrolladores ordinarios;
- revisión/aprobación obligatoria antes de integrar cambios;
- checks automáticos de calidad obligatorios;
- actualización con la línea base antes de integrar cuando la política interna lo requiera;
- aprobación por persona distinta del autor cuando exista el equipo suficiente;
- restricción de reescritura no autorizada de la historia productiva;
- permisos mínimos para administrar CI/CD, secretos, entornos y reglas del repositorio.

La herramienta concreta utilizada para implementar estos controles debe ser la que autorice TIC; la documentación del motor no depende de un proveedor específico.

## 5. Evidencia que debe conservarse por liberación

Para una versión candidata a producción se recomienda integrar un expediente de liberación con:

- commit/tag o identificador institucional equivalente;
- registro de revisión/aprobación del cambio;
- resultado de CI;
- versión de Python;
- inventario exacto de dependencias;
- resultado de auditoría de vulnerabilidades;
- hash SHA-256 del ejecutable y, cuando aplique, digest de imagen;
- inventario y hash de terceros relevantes;
- resultado de UAT con corpus autorizado y sin exponer PII en el repositorio;
- autorización funcional;
- autorización TIC/seguridad correspondiente;
- rollback documentado.

## 6. No-go para producción

No liberar si ocurre cualquiera de los siguientes:

- CI obligatorio en rojo;
- vulnerabilidad conocida sin tratamiento/aceptación formal;
- cambio funcional de parser sin regresión/UAT suficiente;
- binario o dependencia de origen no trazable;
- uso de datos reales fuera de entorno autorizado;
- ausencia de controles institucionales de identidad/autorización para un servicio expuesto;
- ausencia de TLS cuando exista tránsito por red;
- falta de respaldo/rollback aplicable;
- falta de aprobación requerida por TIC o protección de datos.

## 7. Referencias normativas principales

- Política General de Ciberseguridad para la APF, DOF 17/12/2025: https://www.dof.gob.mx/nota_detalle.php?codigo=5776454&fecha=17/12/2025
- LGPDPPSO vigente, Cámara de Diputados: https://www.diputados.gob.mx/LeyesBiblio/pdf/LGPDPPSO.pdf
- Marco detallado del proyecto: [`05_normativa_tic_apf.md`](05_normativa_tic_apf.md)

La matriz deberá ajustarse cuando ATDT o TIC/SABG entreguen lineamientos, criterios o formatos institucionales más específicos.
