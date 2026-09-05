# Auditoría integral de preparación a producción

## Estado Cuenta Engine

**Fecha de corte:** 5 de septiembre de 2026  
**Alcance:** repositorio completo, incluyendo `app/`, `src/parsers/`, `src/readers/` y `tests/`.

> Esta auditoría evalúa calidad de ingeniería y riesgo de regresión del repositorio. No sustituye las autorizaciones de TIC, seguridad, protección de datos, jurídica o archivo necesarias para un despliegue institucional.

## 1. Objetivo

Fortalecer el repositorio sin alterar la lógica de extracción ni los resultados actualmente soportados. Para esta pasada se adopta una regla conservadora:

- comentarios, documentación, packaging y pruebas pueden refactorizarse;
- cambios que modifiquen detección, parsing, validación financiera o enriquecimiento de movimientos no se incorporan sin una prueba de regresión específica;
- los parsers se consideran comportamiento crítico y se preservan funcionalmente;
- PaddleOCR queda fuera de esta línea base.

## 2. Auditoría del PR #13

El PR #13 introdujo una base útil de ingeniería, pero no debía aplicarse sin ajustes si el requisito es equivalencia estricta de resultados.

Se identificaron dos cambios funcionales que debían revertirse y una modificación de identidad de paquete que no era necesaria:

1. eliminación de una señal RFC heredada del catálogo de Nu;
2. cambio de semántica en la validación de saldo `0.0`;
3. cambio del nombre de distribución del paquete.

La restricción propuesta por #13 a Python `>=3.12,<3.14` sí resultó correcta después de auditar el repositorio completo: `app/main_flet.py` en el propio `master` utiliza sintaxis de f-strings disponible desde Python 3.12. La primera matriz CI confirmó que Python 3.10 no puede compilar la aplicación actual. Por tanto, la línea consolidada conserva Python 3.12–3.13 como contrato real, en vez de prometer compatibilidad no existente.

La rama de esta auditoría conserva las mejoras estructurales de #13 y restaura los contratos que sí podían alterar resultados.

## 3. Áreas revisadas

### `app/`

Se revisaron las interfaces Flet y Streamlit en aspectos de:

- imports y compilación;
- separación UI/pipeline;
- worker de procesamiento;
- manejo de archivos temporales;
- exportación;
- dependencias opcionales;
- empaquetado.

No se modificó su flujo funcional. La CI compila ambas aplicaciones e instala sus dependencias opcionales. Flet además se valida mediante un build real de PyInstaller en Windows.

Hallazgos que se conservan por compatibilidad y deben tratarse en cambios específicos posteriores:

- ambas apps agregan `src/` a `sys.path` para soportar ejecución directa desde el checkout;
- Streamlit ignora errores `OSError` durante limpieza de temporales; cambiar esta política requiere definir logging y operación productiva antes de modificarla;
- la autenticación/autorización continúa siendo responsabilidad de la arquitectura de despliegue aprobada por TIC.

### `src/parsers/`

Se revisó la estructura de parsers y extractores existentes. No se altera ninguna regla de extracción, geometría, regex, matching SPEI ni comportamiento bancario en esta auditoría.

La protección principal contra regresiones es:

- compilación de todos los módulos;
- chequeos estáticos de errores de nombre/sintaxis;
- suite sintética de parsers;
- tests HSBC de hardening y SPEI;
- tests de Mercado Pago;
- tests de CETES existentes.

Los comentarios extensos dentro de extractores complejos no se eliminan masivamente en esta pasada cuando sirven para explicar geometría OCR, continuidad contable o reglas de layout. Una limpieza puramente cosmética de esos archivos generaría diffs grandes sin beneficio proporcional y dificultaría revisar regresiones.

### `src/readers/`

Se verificó el contrato Digital/OCR:

- `PDFTextReader`;
- `PDFWordReader`;
- `TesseractPDFReader`;
- `ReaderManager`;
- modelos de lectura.

`ReaderManager` fue documentado como contrato actual y no como historia de compatibilidad. No se cambia la estrategia de lectura, coordenadas ni OCR.

### `src/engine/`

Se revisó el pipeline y la resolución de parsers. `statement_processor.py` tenía una inconsistencia documental: afirmaba que ningún parser OCR estaba en el registro aunque `banorte_ocr` sí estaba registrado. Se corrigió la documentación conservando el orden y comportamiento de resolución existente.

### `tests/`

Se encontró la principal brecha de calidad práctica: varios archivos llamados `test_*.py` eran scripts manuales que ejecutaban PDFs locales en importación y algunos incluían rutas con datos identificables.

Se convirtieron en pruebas de integración opt-in mediante variables de entorno:

- `ESTADO_CUENTA_TEST_PDF` para un PDF;
- `ESTADO_CUENTA_TEST_PDFS` para un lote, separado por `os.pathsep`.

Por defecto la CI ejecuta sólo pruebas sintéticas/autocontenidas. Los PDFs reales o autorizados permanecen fuera del repositorio.

### `vendor/tesseract/`

Se mantiene como componente de terceros sin reformatear ni alterar binarios. Para producción sigue siendo obligatorio documentar versión, procedencia, hashes, licencias y vulnerabilidades en el proceso institucional de release/SBOM.

## 4. Dependencias

`pyproject.toml` es la fuente canónica. Se conserva la identidad histórica de la distribución y se documenta el contrato real de Python `>=3.12,<3.14`. La CI comprueba Python 3.12 y 3.13.

Las dependencias están separadas en:

- runtime del motor;
- extra `streamlit`;
- extra `desktop`;
- grupo `dev`;
- grupo `packaging`.

La eliminación de `requirements.txt` evita convertir un `pip freeze` accidental en contrato del producto.

## 5. Gates automáticos

El workflow `Production readiness` ejecuta:

1. matriz Windows con Python 3.12 y 3.13;
2. instalación del paquete desde `pyproject.toml`;
3. compilación de `app/`, `src/` y `tests/`;
4. Ruff con reglas de errores críticos de sintaxis/nombres;
5. suite Pytest sintética completa (`not integration`);
6. build del paquete Python;
7. smoke test de dependencias Streamlit/Flet;
8. build real del ejecutable Flet con PyInstaller;
9. verificación de que el `.exe` esperado fue generado.

## 6. Regla de equivalencia funcional

Para esta auditoría se considera cambio funcional cualquier modificación que altere:

- selección de banco;
- selección Digital/OCR;
- parser elegido;
- fecha, concepto, referencia, cargo, abono o saldo;
- datos de cuenta o resumen;
- matching/enriquecimiento SPEI;
- validaciones emitidas;
- nombres o estructura de hojas/columnas Excel.

Los cambios de esta rama no modifican deliberadamente esos contratos. Cuando #13 había cambiado dos de ellos, fueron restaurados.

## 7. Qué no significa “listo para producción”

Que la CI esté verde significa que la versión es técnicamente consistente con los gates automatizados disponibles. No significa que el sistema ya tenga autorización institucional de producción.

Siguen siendo decisiones/entregables externos al código:

- arquitectura final de autenticación/autorización;
- servidor y hardening;
- TLS/certificado institucional;
- clasificación y retención de información;
- Documento de Seguridad y análisis de riesgos;
- revisión de Tesseract y terceros;
- SBOM y vulnerabilidades del release;
- UAT con corpus institucional autorizado;
- respaldo, restauración y rollback;
- aprobación TIC/funcional.

## 8. Recomendación de merge

Este PR sustituye al PR #13 como línea consolidada. Se recomienda aplicar este PR sólo cuando todos los jobs de `Production readiness` estén en verde. Después, el PR #13 puede cerrarse como supersedido para evitar aplicar dos veces cambios equivalentes.
