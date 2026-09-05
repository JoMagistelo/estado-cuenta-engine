# Estándares de ingeniería de software

## Estado Cuenta Engine — línea base de producción

**Fecha de corte:** 5 de septiembre de 2026

Este documento define convenciones técnicas del repositorio. Complementa el marco normativo y de seguridad institucional; no lo sustituye.

## 1. Principios

Los cambios al motor deben priorizar:

1. corrección funcional y regresión controlada;
2. legibilidad y mantenibilidad;
3. mínimo privilegio y minimización de datos;
4. dependencias explícitas y trazables;
5. cambios pequeños, revisables y reversibles;
6. evidencia automatizable para liberaciones.

## 2. Dependencias

`pyproject.toml` es la fuente canónica de metadatos y dependencias Python.

Reglas:

- declarar sólo dependencias directas del producto;
- separar capacidades opcionales de la interfaz del runtime del motor;
- separar herramientas de desarrollo y empaquetado mediante dependency groups;
- no versionar salidas de `pip freeze` como contrato del proyecto;
- no introducir una dependencia nueva sin justificar finalidad, licencia, mantenimiento y superficie de riesgo;
- revisar vulnerabilidades y licencias antes de una liberación;
- conservar el conjunto exacto de versiones resueltas como evidencia del release mediante el mecanismo aprobado por TIC;
- documentar y verificar por separado los binarios vendorizados.

## 3. Comentarios y docstrings

Los comentarios de producción deben explicar información que el código no expresa por sí solo:

- contratos e invariantes;
- razones de seguridad o privacidad;
- decisiones algorítmicas no obvias;
- compatibilidad necesaria con consumidores externos;
- limitaciones deliberadas y sus consecuencias.

No deben utilizarse como historial de cambios. Evitar expresiones como “original”, “antes”, “se corrigió”, “temporal”, “parche” o “hack” cuando sólo narran cómo evolucionó el archivo. Ese historial corresponde a Git, issues, PR y ADR/documentación técnica.

Los `TODO` de producción deben tener alcance concreto y, cuando representen deuda relevante, referencia a un issue o entregable. No deben ocultar controles de seguridad obligatorios.

## 4. Tipado y contratos

- usar anotaciones de tipos en APIs internas compartidas;
- preferir sintaxis moderna compatible con la versión mínima de Python soportada;
- evitar mezclar representaciones de ausencia (`None`, cadena vacía, cero) sin un contrato explícito;
- no cambiar el significado de modelos transversales únicamente para resolver un layout bancario;
- cualquier cambio de esquema exportado debe considerarse cambio de contrato y revisarse por compatibilidad.

## 5. Manejo de errores y observabilidad

- fallar con excepciones específicas cuando sea posible;
- no ocultar excepciones de infraestructura sin conservar una señal diagnóstica útil;
- no registrar PDFs, texto OCR completo, nombres, RFC, cuentas, CLABE, saldos, conceptos ni claves completas;
- los errores expuestos a UI/API futura deberán separar mensaje para usuario de detalle técnico;
- la observabilidad productiva debe usar identificadores técnicos y códigos de error, no contenido financiero.

## 6. Datos financieros

Los modelos actuales utilizan `float` en distintos campos monetarios. Cambiar todo el dominio a aritmética decimal requiere una migración transversal y pruebas de regresión de parsers/exportadores; por tanto, no debe hacerse de manera aislada.

Mientras exista este contrato:

- las comparaciones deben usar tolerancias explícitas y documentadas;
- no se debe interpretar un valor numérico válido de `0.0` como ausencia por simple evaluación booleana;
- cualquier nueva lógica financiera debe distinguir de forma explícita entre dato ausente y cero cuando el modelo lo permita.

## 7. Terceros y `vendor/`

El contenido de `vendor/` no se considera código fuente propio para efectos de estilo o comentarios. Debe gestionarse como componente de cadena de suministro:

- nombre y versión;
- fuente/procedencia;
- licencia;
- hashes de integridad;
- vulnerabilidades conocidas;
- componentes incluidos realmente necesarios;
- procedimiento de actualización o retiro.

## 8. Calidad automatizada

La línea base inicial utiliza Ruff para errores de sintaxis/importación y Pytest para regresión. El alcance de linting se ampliará de manera gradual para evitar un cambio masivo mezclado con estabilización de parsers/readers.

Antes de mergear código de producción se espera, como mínimo:

```text
ruff check .
pytest
python -m build
```

La revisión de dependencias debe incorporarse al proceso de CI/release con una herramienta aprobada.

## 9. Pull requests

Un PR debe indicar:

- propósito;
- archivos/componentes afectados;
- riesgo funcional;
- evidencia de pruebas;
- cambios de dependencias;
- implicaciones de seguridad o datos personales;
- compatibilidad y plan de reversa cuando corresponda.

Los cambios que alteren parsers/readers críticos deben mantenerse separados de refactors puramente estructurales siempre que sea posible.

## 10. Criterios de finalización

Un cambio no se considera listo sólo porque “funciona localmente”. Debe quedar:

- versionado;
- documentado al nivel necesario;
- revisable;
- probado;
- sin secretos ni datos reales;
- con dependencias declaradas correctamente;
- compatible con la arquitectura aprobada o marcado explícitamente como decisión pendiente de TIC.
