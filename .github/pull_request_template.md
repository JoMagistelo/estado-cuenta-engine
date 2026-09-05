## Objetivo

<!-- Describir el cambio y por qué es necesario. -->

## Impacto funcional

- [ ] No modifica resultados de extracción, matching, validación o exportación.
- [ ] Si modifica comportamiento funcional, incluye pruebas de regresión específicas y evidencia de validación.
- [ ] No modifica parsers de bancos no relacionados con el objetivo del cambio.

## Seguridad y datos personales

- [ ] No incluye estados de cuenta reales, datos personales, secretos, tokens, certificados privados ni logs sensibles.
- [ ] Las nuevas dependencias o binarios de terceros están justificados y documentados.
- [ ] El cambio no debilita controles de acceso, trazabilidad, integridad o manejo de temporales.

## Calidad

- [ ] `compileall` pasa.
- [ ] Ruff pasa.
- [ ] Pytest no-integración pasa.
- [ ] El build correspondiente pasa.
- [ ] Revisé el diff final y no hay cambios accidentales.

## Producción / TIC

- [ ] Identifiqué si el cambio requiere actualización de documentación, inventario de terceros, análisis de riesgos o evidencia de release.
- [ ] Si cambia arquitectura, despliegue, autenticación, tratamiento de datos o terceros, se señala expresamente para revisión de TIC/SABG.

## Evidencia adicional

<!-- Capturas, hashes, resultados de pruebas o referencias técnicas sin datos sensibles. -->
