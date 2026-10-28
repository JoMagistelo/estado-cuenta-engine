# Conciliación de Nu

Los cargos y abonos del detalle se suman íntegramente. El resumen de Nu puede
mostrar un ámbito distinto: depósitos y gastos externos, mientras el detalle
incluye movimientos entre la cuenta, las Cajitas y los saldos congelados.
El saldo total también incorpora rendimientos e impuestos.

La política `ResumenFinancieroNu` conserva los importes impresos y comprueba:

- depósitos externos contra la fila Depósitos;
- gastos externos contra la fila Gastos;
- saldo inicial + depósitos - gastos - comisiones + rendimiento neto contra
  el saldo final;
- interés bruto - ISR contra el rendimiento neto, cuando existen ambos datos;
- comisiones o rendimientos explícitos del detalle contra sus partidas del
  resumen, cuando existen esas operaciones.

El desglose de la validación muestra la suma íntegra del detalle y el subtotal
externo que se comparó. Flet muestra ese desglose al colocar el cursor sobre la
tarjeta; Streamlit lo presenta bajo la validación. Los contadores, importes,
conceptos y movimientos exportados conservan la extracción existente.

## Reglas y extensión

`src/parsers/nu/validacion.py` concentra las reglas positivas `FLOW_RULES` para
traspasos internos, comisiones y rendimientos. Se reconocen etiquetas de la
operación, incluyendo depósitos/retiros de Cajita y congelación/descongelación.
La presencia de un SPEI conserva el flujo externo aunque el mensaje mencione
una Cajita. Operaciones desconocidas se mantienen como externas para que un
layout no reconocido pueda producir una discrepancia visible.

Los extractores de movimientos y datos de cuenta mantienen sus reglas actuales.
La política financiera funciona tanto con words digitales como con la ruta OCR
que vuelve a leer un PDF con capa de texto. Un periodo sin operaciones se
conserva sin movimientos artificiales y permite validar sus rendimientos.
Si falta una cifra del resumen, no se rellena a partir de la suma del detalle
que se intenta comprobar.

Los puntos de extensión del validador son opcionales. Los demás bancos siguen
su validación habitual; la conciliación existente de Azteca conserva su política.
Una nueva operación o etiqueta requiere su regla y una regresión ficticia antes
de excluirla del subtotal externo.

## Pruebas

```powershell
python -m pytest tests/parsers/test_nu_parser.py tests/parsers/test_nu_balance_validation.py -q
python -m pytest -m "not integration" -q
```

La suite añade casos ficticios de Cajitas, rendimientos, impuestos, comisiones,
periodos sin operaciones y datos faltantes. También verifica que operaciones
externas omitidas o alteradas, y componentes incompatibles, sigan fallando.
La validación con documentos particulares se realiza localmente: no se
versionan PDFs, words, capturas, identificadores ni cifras de expedientes.
