# Banamex y Santander: lectura de layouts y periodos

## Banamex

La portada MiCuenta con datos etiquetados se reconoce por sus encabezados de
contrato, cuenta de cheques y saldo al corte. Los campos se buscan junto a sus
etiquetas y dentro de la columna correspondiente, evitando los importes del
gráfico. La fecha de corte se conserva separada de los extremos del periodo.
El resumen detallado permite leer el total de retiros y otros cargos impreso;
los movimientos no se utilizan para fabricar ese total.

La tabla mantiene la detección de columnas por encabezados. En escaneados se
puede retirar la inclinación a partir de esos encabezados y conservar las
columnas de la página anterior cuando falta parte de una cabecera. El perfil
etiquetado permite separar filas financieras consecutivas cuando el OCR pierde
una fecha, conservando los importes y la fecha disponible. Los formatos
históricos conservan su ruta habitual.

El título «Resumen de Operaciones de Tarjeta», incluidas sus variantes y el
título partido en dos líneas, termina el detalle. Las cifras de ese resumen,
sus contadores y las páginas posteriores no son movimientos de la cuenta.
Un nuevo periodo abre su propia tabla y utiliza su propio corte.

La lectura de importes acepta separadores OCR inequívocos y fragmentos
contiguos de una misma celda; no completa dígitos utilizando los saldos. Para
la portada etiquetada, PaddleOCR puede releer celdas monetarias con márgenes
ampliados. Reutiliza el reconocedor y los modelos locales ya cargados. Un
prefijo recortado sólo se acepta si dos recortes coinciden, ambos tienen alta
confianza y conservan todos los dígitos originales. Los demás bancos y los
formatos históricos quedan fuera de esa relectura.

## Santander

La misma extracción semántica admite words digitales y words procedentes de
OCR. La normalización reconoce letras acentuadas de fuentes PDF que utilizan
el área privada de Unicode. No traduce caracteres desconocidos a cifras.
Las pasadas tipográficas superpuestas se eliminan sólo cuando coinciden texto,
página y caja; las operaciones repetidas en filas distintas se conservan.

## Varios periodos en un PDF

Las portadas identificadas delimitan cada periodo. Se extraen y comprueban
individualmente antes de reunir sus movimientos en el resultado del archivo.
La consolidación requiere una misma cuenta identificada. El saldo inicial
procede del primer resumen y el final del último; depósitos, retiros y otros
totales se suman a partir de los resúmenes impresos. El saldo promedio se
pondera por los días declarados cuando todos están disponibles.

La validación comprueba también cada periodo, la continuidad de sus fechas y
sus saldos. Una diferencia no puede ocultarse mediante otra diferencia de
signo contrario en un periodo distinto. Un resumen incompleto, un hueco,
un solapamiento o una repetición producen una validación fallida.

La separación y la alineación del parser trabajan sobre copias de las words
del reader. Las columnas de exportación conservan su
contrato. Los demás parsers conservan sus políticas de conciliación.

## Regresión y empaquetado

Las pruebas versionadas utilizan exclusivamente datos ficticios y cubren
geometría variable, celdas fragmentadas, pérdida de fechas, cortes de tabla,
fuentes superpuestas, periodos consecutivos y errores reales de conciliación.
Los documentos particulares y sus salidas se verifican fuera del repositorio.

```powershell
python -m pytest -m "not integration" -q
.\scripts\build_windows_release.ps1 -Version "6.0.0" -PortableOffline
```

La versión 6.0.0 conserva las dependencias de 5.0.0. Con el entorno de build
ya preparado y actualizado, estas mejoras no requieren reinstalar paquetes.
