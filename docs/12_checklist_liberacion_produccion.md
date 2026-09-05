# Checklist de liberación a producción

## Estado Cuenta Engine — SABG / DGEC

Este documento sirve como expediente mínimo de una versión candidata. No sustituye los formatos oficiales que establezcan TIC, ciberseguridad, protección de datos, archivos o las áreas competentes.

## 1. Identificación de la liberación

- [ ] versión/tag definido;
- [ ] commit exacto registrado;
- [ ] PR de liberación aprobado;
- [ ] responsable funcional identificado;
- [ ] responsable técnico identificado;
- [ ] fecha/ventana de liberación autorizada.

## 2. Calidad y equivalencia funcional

- [ ] CI obligatorio en verde;
- [ ] Python soportado validado;
- [ ] `compileall` en verde;
- [ ] Ruff en verde;
- [ ] suite Pytest sintética en verde;
- [ ] build Python en verde;
- [ ] smoke de interfaces en verde;
- [ ] PyInstaller Windows en verde;
- [ ] UAT ejecutada con corpus autorizado;
- [ ] resultados esperados de extracción comparados;
- [ ] cambios en parsers identificados explícitamente;
- [ ] no existen cambios accidentales fuera del alcance.

## 3. Seguridad de software y cadena de suministro

- [ ] auditoría de dependencias sin vulnerabilidades conocidas bloqueantes;
- [ ] inventario exacto de dependencias guardado como evidencia;
- [ ] dependencias nuevas justificadas y revisadas;
- [ ] componentes en `vendor/` inventariados;
- [ ] versión/procedencia/licencia de Tesseract verificadas;
- [ ] vulnerabilidades conocidas de terceros evaluadas;
- [ ] hash SHA-256 del EXE registrado;
- [ ] mecanismo institucional de distribución definido;
- [ ] firma de código aplicada si TIC la requiere.

## 4. Protección de datos personales

- [ ] clasificación institucional de la información definida;
- [ ] finalidades y usuarios autorizados identificados;
- [ ] minimización de datos revisada;
- [ ] Documento de Seguridad aplicable actualizado;
- [ ] análisis de riesgos y brecha actualizado;
- [ ] procedencia de Evaluación de Impacto determinada;
- [ ] aviso de privacidad/instrumentos aplicables revisados;
- [ ] retención y eliminación definidas conforme a archivo y protección de datos;
- [ ] pruebas y evidencias no exponen información real en Git/CI.

## 5. Arquitectura e infraestructura

- [ ] arquitectura productiva aprobada por TIC;
- [ ] integración con SIEC/API definida y documentada;
- [ ] autenticación institucional configurada;
- [ ] autorización/RBAC y mínimo privilegio configurados;
- [ ] identidad de servicio definida cuando corresponda;
- [ ] TLS/certificados institucionales configurados;
- [ ] hardening de Windows Server aplicado;
- [ ] firewall/red/segmentación revisados;
- [ ] secretos fuera del código y con rotación definida;
- [ ] antimalware/EDR y controles de plataforma conforme a TIC.

## 6. Operación

- [ ] monitoreo y alertamiento configurados;
- [ ] logs minimizados y sin PII innecesaria;
- [ ] retención/acceso a logs definidos;
- [ ] procedimiento de incidentes activo;
- [ ] responsables y escalamiento institucional confirmados;
- [ ] respaldos configurados;
- [ ] restauración probada;
- [ ] RPO/RTO definidos si aplica;
- [ ] rollback técnico probado/documentado;
- [ ] capacidad/recursos del servidor validados.

## 7. Aprobaciones

- [ ] validación funcional DGEC;
- [ ] aprobación TIC/infraestructura;
- [ ] revisión de ciberseguridad;
- [ ] revisión de protección de datos cuando aplique;
- [ ] revisión jurídica/archivo cuando aplique;
- [ ] excepciones de riesgo formalmente aceptadas, con vigencia y responsable.

## 8. Evidencia mínima que debe conservarse

- commit/tag;
- URL del PR;
- resultados de CI;
- reporte de vulnerabilidades;
- inventario de dependencias;
- hash del ejecutable;
- evidencia UAT;
- acta/ticket/autorización de cambio;
- aprobaciones aplicables;
- plan de rollback.

## 9. Criterio de liberación

La liberación es **NO-GO** mientras exista un punto obligatorio pendiente que TIC o el responsable institucional haya clasificado como bloqueante.

El hecho de que el repositorio compile, pase pruebas y genere el EXE demuestra calidad técnica del artefacto; no sustituye los controles de infraestructura, identidad, operación y protección de datos requeridos para producción.
