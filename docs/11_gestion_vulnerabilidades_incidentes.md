# Gestión de vulnerabilidades e incidentes

## 1. Objetivo

Definir una guía técnica mínima para que los hallazgos de seguridad relacionados con Estado Cuenta Engine sean identificados, contenidos, corregidos y documentados de forma trazable, sin sustituir el procedimiento institucional de TIC/SABG.

## 2. Vulnerabilidades de software

### Detección

Las fuentes mínimas son:

- auditoría automatizada de dependencias Python en CI;
- alertas y PR de Dependabot;
- revisión de terceros incluidos en `vendor/`;
- hallazgos de pruebas, revisión de código o TIC;
- avisos de seguridad de los proveedores oficiales.

### Triage

Registrar como mínimo:

- componente y versión;
- identificador CVE/GHSA u otra referencia cuando exista;
- exposición real en la arquitectura;
- severidad técnica;
- posibilidad de explotación;
- impacto potencial en confidencialidad, integridad y disponibilidad;
- impacto potencial en datos personales;
- decisión: corregir, mitigar, aceptar temporalmente o retirar componente.

Toda aceptación de riesgo debe tener responsable, justificación y fecha de revisión; no debe resolverse únicamente con un comentario informal en código.

### Remediación

1. crear cambio trazable;
2. actualizar la dependencia o aplicar mitigación;
3. ejecutar CI completo;
4. validar que no cambien resultados funcionales cuando el componente esté en el flujo de extracción;
5. actualizar inventario/evidencia de release;
6. cerrar el hallazgo con evidencia.

## 3. Binarios y componentes de terceros

Para cada componente distribuido con la aplicación debe existir, antes de producción:

- nombre y versión;
- fabricante/proyecto de origen;
- URL o mecanismo de adquisición autorizado;
- licencia;
- hash criptográfico del paquete/binario aprobado;
- fecha de incorporación;
- responsable de revisión;
- procedimiento de actualización;
- revisión de vulnerabilidades conocidas.

El runtime Tesseract incluido actualmente en `vendor/` debe completar esta evidencia antes de considerarse aprobado para una liberación institucional.

## 4. Incidentes

Un evento debe escalarse al procedimiento institucional cuando pueda involucrar, entre otros:

- acceso no autorizado;
- pérdida, copia o exposición de estados de cuenta o resultados;
- credenciales o secretos comprometidos;
- alteración no autorizada del software o sus artefactos;
- malware o ejecución de código no esperado;
- indisponibilidad significativa;
- resultados financieros alterados por manipulación;
- vulneración potencial de datos personales.

## 5. Secuencia técnica mínima

### Identificar

Registrar fecha/hora, componente afectado, versión, entorno y síntoma sin copiar datos personales innecesarios.

### Contener

Aislar el componente, suspender una liberación, revocar credenciales o bloquear acceso conforme al procedimiento y facultades institucionales. No borrar evidencia necesaria para investigación.

### Preservar evidencia

Conservar de forma controlada:

- hashes;
- logs autorizados;
- commit/tag;
- artefactos relevantes;
- resultados de CI;
- línea temporal de acciones.

### Erradicar y recuperar

Aplicar corrección, reconstruir desde fuente confiable, validar integridad, ejecutar pruebas y restaurar servicio de acuerdo con TIC.

### Cerrar

Documentar causa raíz, alcance, corrección, acciones preventivas y responsables. Si hubo datos personales, seguir además el procedimiento legal e institucional aplicable a vulneraciones.

## 6. Logs y privacidad

Los logs no deben transformarse en una copia secundaria de los estados de cuenta. Evitar registrar:

- contenido completo del PDF;
- nombres completos cuando no sean necesarios;
- cuentas, CLABE, RFC o referencias completas;
- conceptos de movimientos;
- archivos exportados;
- secretos o tokens.

Preferir identificadores técnicos, códigos de error, conteos, nombre lógico del parser, versión y correlación no reversible cuando sea suficiente.

La retención, acceso y destrucción de logs debe ser definida por TIC/SABG.

## 7. Responsabilidades

El repositorio aporta controles técnicos y evidencia. La designación de responsables de incidente, ciberseguridad, protección de datos, infraestructura y comunicación corresponde a la estructura institucional aplicable.

No deben publicarse en este repositorio datos de contacto internos sensibles; el canal operativo se documentará en el medio institucional autorizado.
