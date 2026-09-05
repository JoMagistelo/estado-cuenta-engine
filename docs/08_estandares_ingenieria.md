# Estándares de ingeniería de software

## Estado Cuenta Engine — SABG / DGEC

**Fecha de corte:** 5 de septiembre de 2026

## 1. Principios

Los cambios al sistema deben priorizar:

1. corrección funcional y regresión controlada;
2. legibilidad y mantenibilidad;
3. mínimo privilegio y minimización de datos;
4. dependencias explícitas y trazables;
5. cambios acotados, revisables y reversibles;
6. evidencia automatizable para liberaciones.

## 2. Dependencias

`pyproject.toml` es la fuente canónica de metadatos y dependencias Python.

Reglas:

- declarar únicamente dependencias directas necesarias;
- separar runtime, interfaces opcionales y herramientas de desarrollo/empaquetado;
- no utilizar un `pip freeze` de una estación personal como contrato del producto;
- justificar finalidad, licencia, mantenimiento y superficie de riesgo de nuevas dependencias;
- revisar vulnerabilidades antes de una liberación;
- conservar el conjunto exacto de versiones resueltas como evidencia de la versión;
- gestionar por separado los binarios incluidos en `vendor/`.

## 3. Comentarios y docstrings

Los comentarios deben explicar información que el código no expresa por sí solo:

- contratos e invariantes;
- razones de seguridad o privacidad;
- decisiones algorítmicas no obvias;
- compatibilidad requerida;
- limitaciones deliberadas relevantes para mantenimiento.

No deben utilizarse para narrar el historial del archivo. La documentación de cambios se conserva en el sistema institucional de gestión de versiones/liberaciones.

## 4. Tipado y contratos

- usar anotaciones de tipos en APIs internas compartidas;
- mantener compatibilidad con la versión mínima de Python soportada;
- conservar contratos de ausencia/valor definidos por los modelos existentes;
- no cambiar modelos transversales para resolver de forma aislada un layout bancario;
- considerar cualquier cambio de esquema exportado como cambio de contrato;
- mantener compatibilidad hacia atrás cuando el proceso consumidor lo requiera.

## 5. Manejo de errores

- utilizar excepciones específicas cuando sea posible;
- no ocultar fallas de infraestructura que impidan diagnosticar un incidente;
- separar mensajes operativos de detalles técnicos internos;
- evitar que excepciones expongan rutas sensibles, secretos o información financiera;
- mantener el procesamiento por lote tolerante a fallas individuales cuando el contrato funcional lo permita.

## 6. Observabilidad y privacidad

Los logs técnicos no deben contener, salvo necesidad institucional expresamente autorizada:

- contenido completo de PDFs;
- texto OCR completo;
- nombres completos;
- RFC/CURP;
- cuentas o CLABE completas;
- saldos o conceptos detallados;
- claves de rastreo completas;
- secretos o tokens.

Preferir identificadores técnicos, versión, parser, método Digital/OCR, duración y códigos de resultado/error.

## 7. Lógica financiera y extracción

Los parsers, reglas de layout, matching SPEI, validadores y exportadores son comportamiento funcional crítico.

Cualquier modificación debe:

- identificar claramente el alcance;
- conservar casos previamente correctos;
- añadir regresión específica;
- evitar cambios cosméticos masivos mezclados con lógica funcional;
- documentar cambios de contrato cuando existan;
- validarse con corpus autorizado cuando el riesgo lo justifique.

## 8. Componentes de terceros

El contenido de `vendor/` se gestiona como cadena de suministro y no como código fuente propio.

Para cada componente distribuido deben identificarse:

- nombre y versión;
- procedencia;
- licencia;
- hash de integridad;
- vulnerabilidades conocidas;
- procedimiento de actualización o sustitución.

## 9. Calidad automatizada

La versión debe superar como mínimo:

```text
python -m compileall -q app src tests
ruff check .
pytest -m "not integration"
python -m build
```

Adicionalmente, para la distribución Windows se valida el build PyInstaller y se genera evidencia de integridad del ejecutable.

La automatización de seguridad mantiene inventario de dependencias y auditoría de vulnerabilidades Python.

## 10. Revisión de cambios

Cada cambio debe indicar:

- propósito;
- componentes afectados;
- riesgo funcional;
- evidencia de pruebas;
- cambios de dependencias;
- implicaciones de seguridad/datos personales;
- compatibilidad y reversión cuando corresponda.

Los cambios de parsers/readers críticos deben mantenerse separados de refactors puramente estructurales siempre que sea posible.

## 11. Criterio de finalización

Un cambio se considera técnicamente completo cuando:

- está versionado y revisado;
- las pruebas aplicables están en verde;
- no contiene secretos ni datos reales;
- las dependencias están declaradas correctamente;
- el artefacto aplicable puede construirse;
- la documentación técnica está actualizada;
- existe una estrategia de reversión cuando el riesgo lo requiere.
