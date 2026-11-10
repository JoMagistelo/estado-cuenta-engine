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
| Verde | Campos del movimiento; clasificación en Tipo de Operación, fechas normalizadas y datos del titular | La extracción original permanece disponible; las correcciones de consulta se hacen en azul |
| Azul | Los seis campos del TXT, después de la trazabilidad de fechas oculta | Fuente de verdad del TXT y del cruce |
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

Concepto, Concepto Original, Cargo, Abono y Sucursal se conservan. La
clasificación automática se escribe en **Tipo de Operación**. La recuperación
completa campos SPEI faltantes del parser que ya existan en Movimientos
(rastreo, referencia o cuenta/CLABE beneficiaria), sin crear más columnas
verdes. Los bancos, cuentas del ordenante y referencias intermedias se usan
en memoria para preparar el bloque azul. Los valores existentes se conservan.
El archivo original conserva sus bytes y ningún parser se modifica.

El formato de salida retira las antiguas columnas Banco del Beneficiario,
Código Banco Beneficiario, Código Plaza/Producto CLABE, Banco Emisor, Banco
Receptor, Cuenta del Ordenante, CLABE del Ordenante, Referencia SPEI,
Referencia Original, Origen Datos Titular, Revisión Normalización y
Clasificación SPEI. Se leen al importar versiones anteriores cuando son
necesarias para preparar la consulta; no se vuelven a exportar. Las
anotaciones particulares del analista se conservan.

Este mismo contrato se aplica al normalizado y a ambos Excel cruzados del ZIP.
La hoja Clasificador SPEI también se retira de archivos de versiones anteriores.

## Clasificación y recuperación SPEI al normalizar

**Tipo de Operación**, con encabezado verde, permite filtrar SPEI Enviado,
SPEI Recibido, SPEI Devuelto, Traspaso y Transferencia cuentas del mismo banco.
Los tipos de movimientos ajenos a estas reglas se conservan. Cuando hay
indicios SPEI pero el importe/sentido es ambiguo, la clasificación queda como
SPEI por revisar.

El programa incluye las 57 filas del vocabulario de clasificación, con ambas
columnas de palabras clave y sus variantes OCR. El clasificador funciona dentro
de la aplicación; no se exportan sus reglas en una hoja ni se incorpora
ningún movimiento utilizado para analizar formatos. El reconocimiento tolera mayúsculas, acentos y saltos
de línea. No sustituye letras o dígitos dentro de cuentas ni rastreos.

Las palabras ambiguas se resuelven con cargo/abono y las señales del
encabezado. PAGO RECIBIDO DE puede representar un traspaso interno o un SPEI:
se considera también el banco explícito y el rastreo. Un abono por sí solo no
es evidencia SPEI. CGO se clasifica conforme al vocabulario, pero puede no
incluir los datos necesarios para consultar: esos campos azules quedan vacíos.

La recuperación reconoce etiquetas y bloques de Banamex, Banorte, BBVA,
Santander y Azteca, incluidas variaciones de OCR. Los ejemplos de HSBC y
Mercado Pago también sirven para clasificar; algunos solo describen el pago o
un movimiento interno y no contienen rastreo/cuenta recuperables. Otros
bancos pueden usar la recuperación de campos explícitamente etiquetados.
No se elige un número largo cualquiera, una autorización o una referencia
como rastreo. Las posiciones bancarias permiten recuperar el rastreo de BBVA
aunque la cuenta sea tarjeta u otro identificador sin checksum CLABE válido;
el pie de Banorte permite recuperar los datos situados después del concepto.
Si hay varias candidatas o datos contradictorios, la consulta queda pendiente.

En enviados el destino es el tercero; en recibidos es el titular. La cuenta
del ordenante identifica al remitente, **no** es el destino de un SPEI recibido.
Una devolución se mantiene visible, pero no se enruta automáticamente como un
nuevo SPEI recibido: sus datos de la operación original deben comprobarse y
completarse en azul para consultar.

## Normalizar una vez y corregir directamente

1. Cargar el Excel original, antiguo, mejorado o previamente cruzado.
2. Pulsar **Normalizar Excel** para clasificar y recuperar datos faltantes,
   o para preparar el bloque azul en un archivo antiguo.
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
segunda normalización. Cuando el concepto permite recuperar un dato nuevo que
el normalizador anterior tampoco podía obtener, Normalizar puede completar
ese hueco azul; no repone vacíos cuyo dato de origen ya era utilizable.
Generar TXT directamente siempre lee las seis celdas existentes sin cambios.
Los encabezados TXT duplicados requieren corrección;
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
  o su valor no se puede usar, el movimiento permanece en el Excel y no entra
  al TXT. La vista previa y CEP Estado / CEP Detalle al cruzar indican qué
  celda TXT corregir, sin agregar columnas de revisión.
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
preservación de importes y conceptos de parser, clasificación en Tipo de
Operación, retiro de intermediarios/hoja de clasificación, ediciones independientes de los seis campos
TXT, vacíos sin respaldos silenciosos, compatibilidad entre generaciones,
cuentas de distintas longitudes, identificación textual, filas filtradas,
colores, orden, trazabilidad oculta, catálogo y cruce/reimportación de ZIP.
El self-test Excel/CEP también se ejecuta dentro del EXE portable.
