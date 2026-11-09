# Excel normalizado, TXT editable y cruce CEP

El flujo CEP trabaja sobre una copia del Excel exportado. No modifica parsers,
OCR, clasificador, engine, mapper, escritor ni descarga del Excel original.

## Referencia de las versiones 5.0 y 6.0

Se compararon estos archivos con los commits históricos
[`425a676` (5.0.0)](https://github.com/JoMagistelo/estado-cuenta-engine/commit/425a67696993b0a9cbfd4d8f80f946f3c8fe9869) y
[`78d5614` (6.0.0)](https://github.com/JoMagistelo/estado-cuenta-engine/commit/78d561431da33fc568a3fe930b1647f9834c8a66):

- `src/mappers/estado_cuenta_tables.py`
- `src/exporters/excel/batch_exporter.py`
- `src/exporters/excel/writer.py`
- `src/exporters/excel/styles.py`

Son idénticos a la referencia histórica. El original mantiene sus cuatro hojas:
Datos de la Cuenta, Resumen Financiero, Movimientos y Otros Productos; conserva
sus 25 encabezados de movimientos, desde id_estado hasta Concepto Original.
El formato verde/azul/naranja se aplica a las copias de trabajo CEP.

## Una fila, tres bloques en Movimientos

| Bloque | Contenido | Edición |
| --- | --- | --- |
| Verde | Campos originales, fechas normalizadas y datos del titular | La extracción original permanece disponible; las correcciones de consulta se hacen en azul |
| Azul | Los seis campos del TXT, después de Revisión Normalización | Fuente de verdad del TXT y del cruce |
| Naranja | Resultado de la búsqueda y datos oficiales del XML CEP | Se recalcula al importar los ZIP |

Las seis columnas azules aparecen en este orden, sin campos intermedios:

| Columna | Valor del TXT |
| --- | --- |
| TXT Fecha de Operación | Fecha base, AAAA-MM-DD |
| TXT Clave de Rastreo | Clave de rastreo del SPEI |
| TXT Banco Emisor | Código de la institución emisora |
| TXT Banco Receptor | Código de la institución receptora |
| TXT Cuenta Beneficiaria | Cuenta destino conservada como texto |
| TXT Monto | Importe con dos decimales |

Los encabezados originales quedan verdes, los TXT azules y los resultados CEP
naranja. La normalización puede corregir Fecha de Operación, Fecha de
Liquidación, Fecha de Corte, Número de Cuenta y CLABE Titular. Número de Cuenta
sigue siendo la cuenta del titular: no se añade otra Cuenta Titular duplicada.

Las siguientes columnas se conservan, pero quedan **ocultas**:

- Fecha de Operación Original
- Estado de Fecha
- Fecha de Liquidación Original
- Fecha de Corte Original

Los valores SPEI extraídos por el parser (concepto, referencia, rastreo,
beneficiario, cuentas, Sucursal, etc.) **no se reescriben**. La recuperación
conservadora ya existente puede preparar una copia para las columnas TXT.
La ampliación mediante un catálogo de patrones SPEI por banco queda pendiente;
no se incorpora ni se cambia ningún parser en esta revisión.

## Normalizar una vez y corregir directamente

1. Cargar el Excel original, antiguo, mejorado o previamente cruzado.
2. Si todavía no tiene el bloque TXT, pulsar **Normalizar Excel**.
3. Descargar el Excel normalizado. Revisar o corregir las seis celdas azules
   del movimiento que interese y guardar el archivo.
4. Volver a cargar ese archivo. **Generar TXT sin normalizar de nuevo**.
5. Cargar los TXT en Banxico y solicitar PDF y XML.
6. Importar sus ZIP. Los resultados completos quedan en naranja, en la misma
   fila: CEP Estado, CEP Detalle, fecha, monto, participantes, cuentas,
   concepto, disponibilidad de PDF y vínculos PDF/XML.
7. Filtrar los SPEI pendientes, corregir sus celdas azules y repetir el ciclo.

Si ya existe cualquiera de las seis columnas TXT, ese bloque es autoritativo:
una celda vacía se informa como pendiente y **no** se sustituye por un valor
antiguo del parser. Tampoco se sobrescriben las ediciones si se solicita una
segunda normalización. Los encabezados TXT duplicados requieren corrección;
no se elige silenciosamente una columna.

Las fechas del bloque azul son independientes de las fechas verdes:
al corregir una consulta no se altera la evidencia original. La opción de
fechas ±1 día genera reintentos respecto a la fecha azul; se puede desactivar.

## Compatibilidad y conservación

- Los originales de las versiones 5/6, los originales actuales, los mejorados
  antiguos y los cruzados se pueden cargar sin modificar sus bytes.
- Sin bloque azul, la consulta directa histórica sigue disponible. Para ver y
  corregir los seis datos en Excel, normalizar una vez prepara ese bloque.
- En enviados se copia la cuenta del tercero; en recibidos, la del titular del
  estado. Los donantes de datos del titular deben corresponder al mismo estado
  y archivo o a una coincidencia única comprobable de banco y cuenta.
- Un rastreo mantiene al movimiento como candidato SPEI. No se eliminan filas
  por tener cuenta, CLABE o tarjeta, por estar filtradas o por estar ocultas.
- Una cuenta distinta de CLABE no se descarta por su longitud ni se convierte
  por suposición en otra cuenta. El formato histórico 00 + tarjeta16 puede
  prepararse como tarjeta16; las ediciones posteriores del bloque azul se
  respetan literalmente, incluidos sus ceros.
- No se inventan bancos, dígitos ni importes. Si falta uno de los seis datos,
  o su valor no se puede usar, Revisión Normalización y CEP Detalle indican
  qué celda TXT corregir. El movimiento permanece en el Excel.
- Identificadores de más de 15 dígitos que Excel ya haya redondeado deben
  corregirse como texto; nunca se recuperan dígitos por suposición.
- Cuando reordenar columnas pueda romper fórmulas, tablas u otras referencias,
  la reorganización se detiene con un mensaje. La consulta directa de un
  archivo con columnas TXT sigue disponible.

## Catálogo y formato oficial Banxico

La hoja **Catálogo Bancos** incluye las 97 instituciones del
[listado oficial CEP-SCL](https://www.banxico.org.mx/cep-scl/listaInstituciones.do),
verificado el **9 de noviembre de 2026**, con su clave y nombre.
El catálogo está incluido en el programa y funciona sin conexión.
Las celdas TXT Banco Emisor/Receptor admiten esas claves o nombres reconocidos.

El [formato oficial por lotes](https://www.banxico.org.mx/cep-scl/) utiliza
fecha, rastreo, institución emisora, institución receptora, cuenta beneficiaria
e importe. Banxico publica como identificadores CLABE, tarjeta de débito y
celular. El módulo también conserva otros números de cuenta suministrados para
consulta, sin afirmar que Banxico aceptará cualquier identificador.
La solicitud usa UTF-8 sin BOM, seis campos separados por comas y entre 2 y 500
líneas por archivo. Los lotes se dividen sin dejar archivos de una sola línea.

## Cruce y paquete final

El cruce compara los datos explícitos del TXT: rastreo, fecha base/±1,
importe, emisor, receptor y cuenta destino. Las correcciones azules no se
invalidan por valores anteriores de los campos verdes. Un XML ambiguo o
contradictorio se marca para revisión; no se asigna a filas indistinguibles.

No se genera Control CEP ni las hojas Revisión CEP/Revisión Excel: la consulta
y su resultado están en Movimientos. **Datos CEP** conserva la tabla de XML
oficiales importados, incluidos los no asignados, para no perder evidencia.

El ZIP final conserva ambos Excel cruzados, PDF/XML renombrados y los archivos
originales de Banxico. Las ligas relativas funcionan al extraer todo en una
misma carpeta. Un cruce nuevo reemplaza los resultados anteriores y conserva
los datos del TXT; normalizar otra vez limpia resultados CEP obsoletos en la
copia, sin alterar el archivo de entrada.

## Verificación

La suite cubre el contrato original histórico, fechas y cuentas del titular,
preservación de campos de parser, ediciones independientes de los seis campos
TXT, vacíos sin respaldos silenciosos, compatibilidad entre generaciones,
cuentas de distintas longitudes, identificación textual, filas filtradas,
colores, orden, trazabilidad oculta, catálogo y cruce/reimportación de ZIP.
El self-test Excel/CEP también se ejecuta dentro del EXE portable.
