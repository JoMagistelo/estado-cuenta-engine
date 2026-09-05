# Política de seguridad

## Alcance

Estado Cuenta Engine procesa documentos financieros que pueden contener datos personales, patrimoniales y otra información reservada o sensible. La seguridad del repositorio forma parte de la defensa del sistema, pero no sustituye los controles institucionales de la SABG, su infraestructura, identidad, redes, monitoreo, respaldos ni gestión de incidentes.

## Reporte de vulnerabilidades

No publicar vulnerabilidades explotables, credenciales, tokens, rutas internas, configuraciones institucionales, estados de cuenta reales ni datos personales en tickets, revisiones de cambio, discusiones, commits o repositorios no autorizados.

Cuando se identifique una vulnerabilidad o posible exposición:

1. suspender la difusión de detalles técnicos innecesarios;
2. conservar evidencia mínima y autorizada del hallazgo;
3. notificar por el canal institucional definido por TIC/SABG;
4. clasificar severidad, alcance, activos y datos potencialmente afectados;
5. corregir mediante un cambio trazable y revisado;
6. validar la corrección y documentar la evidencia de cierre;
7. evaluar si corresponde activar el procedimiento institucional de incidente o vulneración de datos personales.

El repositorio no define ni publica direcciones internas, teléfonos, correos privados ni mecanismos sensibles de escalamiento. TIC deberá establecer el canal operativo autorizado antes de producción.

## Datos prohibidos en el repositorio

No deben versionarse:

- estados de cuenta reales;
- PDFs, hojas de cálculo o exportaciones que contengan información real;
- nombres, RFC, CURP, CLABE, cuentas, referencias o conceptos asociados a personas reales;
- credenciales, secretos, certificados privados, llaves o tokens;
- volcados de base de datos o logs con información personal;
- configuraciones productivas con direcciones, rutas, usuarios o secretos institucionales.

Las pruebas con documentos reales deben ejecutarse únicamente en entornos autorizados y usando los mecanismos opt-in definidos por el proyecto.

## Dependencias y terceros

Toda nueva dependencia debe justificar su necesidad, origen, licencia, mantenimiento y efecto en la superficie de ataque. Cualquier actualización automática o manual de dependencias requiere revisión humana y debe pasar los mismos gates de calidad y seguridad que cualquier otro cambio.

Los binarios de terceros incluidos en `vendor/` requieren inventario, versión, procedencia, licencia, integridad criptográfica y proceso de actualización antes de una liberación productiva.

## Severidad orientativa

- **Crítica:** ejecución remota, compromiso de credenciales, exposición masiva de datos, bypass de autenticación/autorización o alteración no detectada de resultados financieros.
- **Alta:** acceso indebido relevante, lectura/escritura no autorizada, dependencia explotable en el flujo productivo o pérdida de integridad de artefactos.
- **Media:** debilidad explotable con condiciones adicionales o impacto limitado.
- **Baja:** defensa en profundidad, endurecimiento o mejora sin explotación práctica inmediata.

La clasificación definitiva corresponde al proceso institucional de gestión de riesgos y vulnerabilidades.

## Cambios de seguridad

Las correcciones de seguridad no deben mezclarse innecesariamente con cambios de parsers o reglas de negocio. Cuando una corrección pueda modificar resultados de extracción, debe incluir pruebas de regresión específicas y evidencia de validación con corpus autorizado.

## Producción

La aprobación técnica de un cambio no equivale por sí misma a autorización de producción. La puesta en servicio requiere los controles y aprobaciones institucionales aplicables, incluyendo arquitectura, identidad, infraestructura, TLS, monitoreo, respaldo, continuidad, gestión de incidentes, protección de datos personales y liberación controlada.
