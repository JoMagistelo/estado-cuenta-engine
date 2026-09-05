# Gestión de vulnerabilidades e incidentes

## Estado Cuenta Engine — SABG / DGEC

## 1. Objetivo

Definir el tratamiento técnico mínimo de vulnerabilidades e incidentes relacionados con la aplicación, alineado al procedimiento institucional que determine TIC/SABG.

## 2. Detección de vulnerabilidades

Las fuentes mínimas de revisión son:

- auditoría automatizada de dependencias Python;
- avisos de seguridad de proveedores oficiales;
- revisión de componentes de terceros incluidos en `vendor/`;
- hallazgos de pruebas de seguridad;
- revisión de código;
- observaciones de TIC o del equipo de operación.

## 3. Registro y clasificación

Para cada hallazgo registrar:

- componente y versión;
- identificador CVE u otra referencia cuando exista;
- exposición real dentro de la arquitectura;
- severidad;
- posibilidad de explotación;
- impacto en confidencialidad, integridad y disponibilidad;
- impacto potencial en datos personales;
- decisión de tratamiento;
- responsable y fecha objetivo.

Las opciones de tratamiento pueden incluir corrección, mitigación, aceptación temporal formal o sustitución/retiro del componente.

## 4. Remediación

1. registrar un cambio trazable;
2. aplicar actualización o mitigación;
3. ejecutar la automatización de calidad completa;
4. verificar regresión cuando el componente intervenga en extracción u OCR;
5. actualizar inventario y evidencia de la versión;
6. documentar el cierre del hallazgo.

## 5. Componentes de terceros

Para cada componente distribuido con la aplicación deben identificarse:

- nombre y versión;
- fabricante/proyecto de origen;
- mecanismo de adquisición autorizado;
- licencia;
- hash criptográfico;
- fecha de incorporación;
- responsable de revisión;
- procedimiento de actualización;
- vulnerabilidades conocidas relevantes.

El runtime Tesseract debe formar parte de este inventario en cada liberación.

## 6. Criterios de escalamiento de incidentes

Un evento debe escalarse al procedimiento institucional cuando pueda involucrar:

- acceso no autorizado;
- pérdida, copia o exposición de estados de cuenta o resultados;
- compromiso de credenciales, certificados o secretos;
- alteración no autorizada del software o artefactos;
- malware o ejecución no esperada;
- indisponibilidad significativa;
- manipulación de resultados;
- vulneración potencial de datos personales.

## 7. Secuencia técnica de respuesta

### Identificar

Registrar fecha/hora, versión, entorno, componente afectado y síntoma sin copiar datos personales innecesarios.

### Contener

Aplicar las medidas autorizadas por TIC: aislamiento, suspensión de una versión, bloqueo de acceso o revocación de credenciales, según el caso.

No eliminar evidencia necesaria para investigación.

### Preservar evidencia

Conservar de forma controlada:

- hashes;
- logs autorizados;
- versión/referencia del código;
- artefactos relevantes;
- resultados de pruebas y auditorías;
- línea temporal de acciones.

### Erradicar y recuperar

Aplicar la corrección, reconstruir desde fuente confiable, validar integridad, ejecutar pruebas y restaurar el servicio conforme al procedimiento institucional.

### Cerrar

Documentar:

- causa raíz;
- alcance;
- corrección;
- acciones preventivas;
- responsables;
- evidencia de validación.

Cuando existan datos personales afectados, aplicar además el procedimiento institucional correspondiente a vulneraciones.

## 8. Logs y privacidad

Los logs no deben convertirse en una copia secundaria de los estados de cuenta.

Evitar registrar:

- contenido completo del PDF;
- nombres completos;
- cuentas, CLABE, RFC/CURP o referencias completas;
- conceptos de movimientos;
- archivos exportados;
- secretos o tokens.

Preferir identificadores técnicos, código de error, versión, método Digital/OCR, parser y duración.

## 9. Operación institucional

TIC deberá definir:

- canal de reporte;
- responsables y escalamiento;
- severidades institucionales;
- tiempos de atención;
- herramientas de monitoreo;
- retención de evidencia;
- coordinación con protección de datos y áreas jurídicas cuando corresponda.

Los datos de contacto internos y procedimientos operativos sensibles deben mantenerse en los medios institucionales destinados para ese fin.
