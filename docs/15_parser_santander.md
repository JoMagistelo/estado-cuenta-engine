# Parser Santander

## Cobertura

Perfil de cuenta de cheques con columnas Fecha, Folio, Descripción,
Depósito, Retiro y Saldo. Cubre SUPER NÓMINA y variantes con la misma
estructura; también reconoce los encabezados Referencia, Concepto, Abonos y
Cargos. Los tres estados escaneados usados en la validación local pertenecen
a este perfil. Otros formatos requieren muestras y su propia regresión.

El parser recibe `DocumentData.spatial_words`. Usa la misma lógica para
PDFs digitales y OCR, incluida la ruta de producción
`PaddleOCR -> PDF con capa de texto verificada -> PDFWordReader`.
No ejecuta OCR dentro del parser ni modifica las palabras originales.

## Contrato de extracción

- Datos: producto, titular, RFC, cliente, cuenta, CLABE, periodo y corte.
- Resumen: valores impresos de la cuenta principal; distingue las columnas
  izquierda/derecha, los intereses brutos, el ISR y las comisiones. La gráfica
  y la tasa porcentual de ISR no sustituyen los importes del resumen.
- Movimientos: fecha, cargo/abono por columna, saldo, folio como referencia
  cuando no hay REF, y detalle completo en `concepto`. No deduplica folios
  repetidos y conserva filas parciales sin inventar sus datos faltantes.
- SPEI: cliente/beneficiario, cuenta o CLABE, banco emisor/receptor en el campo
  `sucursal` del modelo vigente, rastreo, REF, RFC, hora y mensaje etiquetado
  CONCEPTO en `concepto_original`. Una cuenta corta no se convierte en CLABE.
- Transferencias rápidas: nombre completo hasta las etiquetas técnicas;
  los mensajes pueden cruzar páginas. Los textos que escribe el usuario con
  palabras como REF permanecen en el mensaje.
- Otros productos: `N/A`, conforme al contrato del modelo principal.

Los errores inequívocos `AG0` en fechas y `O` en horas se interpretan dentro
de esos campos. El detalle conserva el texto que entregó el reader. El parser
no corrige nombres, cuentas, rastreos o importes por suposición ni reconstruye
montos desde saldos para forzar una conciliación.

## Extender layouts

`src/parsers/santander/layouts.py` contiene `LAYOUTS` y `SantanderLayout`.
Cada perfil define aliases de encabezados; las anclas se detectan por página,
sin coordenadas absolutas ni dependencia del DPI. Las columnas pueden moverse
o intercambiar depósito/retiro. Para una variante de encabezados, registrar un
perfil nuevo y añadir una muestra sintética. Si cambia la estructura de datos
de cuenta o resumen, extender su extractor con una regresión independiente.

No añadir PDFs, JSON originales, nombres, identificadores o movimientos reales
al repositorio. Las pruebas versionadas usan exclusivamente datos ficticios.

## Validación

```powershell
python -m pytest tests/parsers/test_santander_parser.py -q
python -m pytest -m "not integration" -q
python -m ruff check .
```

La suite incluye readers digitales reales, proyección OCR a PDF y relectura,
escala/desplazamiento/desorden de palabras, aliases y columnas invertidas,
detalles entre páginas, mensajes multilínea, transferencias rápidas,
filas parciales, importes con signo y exclusión de otra cuenta.

Para repetir la validación local con documentos autorizados y sus words
PaddleOCR originales juntos en una carpeta:

```powershell
$env:SANTANDER_SAMPLE_DIR = 'C:\ruta\muestras-autorizadas'
python -m pytest tests/parsers/test_santander_local_integration.py -m integration -q
```

Este replay verifica igualdad entre el JSON nativo y la proyección canónica,
inmutabilidad de las words, fechas, las cuatro conciliaciones financieras y
el saldo impreso de cada movimiento contra el saldo anterior más abonos menos cargos.
No requiere instalar PaddleOCR: utiliza la salida OCR ya disponible. La prueba
digital es sintética; la validación con un PDF digital original de cada nuevo
layout debe agregarse a la aceptación funcional local.
