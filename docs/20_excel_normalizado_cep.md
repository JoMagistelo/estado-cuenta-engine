# Excel mejorado y CEP integrado

## Contrato de las versiones 7.0.0 y 7.1.0

- **Extracción:** parsers y procesador bancario sin modificaciones. `Generar Excel` sigue descargando
  `reporte_estados_de_cuenta.xlsx`, con la misma estructura y los valores originales.
- **Interfaz Windows:** exportación fija, fuera de la columna desplazable de resultados;
  zona independiente de arrastre PDF de 96 DIP al pie de la ventana, con margen DPI
  calculado por una única función y sin superponerse al botón de exportación.
- **CEP:** pestaña y pasos completos conservados. Recupera metadatos y homologa fechas
  **únicamente a partir del Excel exportado**. La copia normalizada es opcional:
  el TXT también puede generarse directamente desde Excel antiguos o corregidos.
- **Cobertura progresiva:** el módulo muestra cuántos candidatos están listos y cuáles
  requieren revisión manual. Los patrones documentados de nuevos bancos se incorporarán
  en futuras versiones a la normalización, no a los parsers; no se inventan claves,
  CLABE, cuentas ni bancos faltantes.
- **Control de calidad:** no se fusiona hasta comprobar en Windows el botón de
  descarga, arrastre de varios PDF, navegación de las pestañas, integridad del Excel
  original y validación del TXT/ZIP con casos autorizados.

Para probar la rama antes del merge:

```powershell
Set-Location (git rev-parse --show-toplevel)
git fetch origin
git switch -c feature/cep-excel-retrocompatible-reconsulta --track origin/feature/cep-excel-retrocompatible-reconsulta
.\.venv\Scripts\python.exe -m pytest -m "not integration" -q
.\.venv\Scripts\python.exe app\main_desktop.py
```


El experimento `experimentos/cep-banxico-gui` se conserva intacto. La integración usa módulos independientes en `src/cep` y el exportador existente para conservar el formato del Excel original.

## Cobertura de identificadores CEP en 7.0.0

La Cuenta Beneficiaria exigida por Banxico puede ser una **CLABE de 18 dígitos**,
una **tarjeta de débito de 16 dígitos** o un **número de celular de 10 dígitos**.
No asumir que la columna denominada `CLABE del Beneficiario` contiene siempre
una CLABE: algunos bancos imprimen `00` seguido de los 16 dígitos de tarjeta.

**Regla de consulta segura:**
1. Una CLABE de 18 dígitos con checksum válido se conserva íntegra.
2. Sólo cuando el valor de 18 dígitos **no** es CLABE válida, empieza por
   `00` y los otros 16 dígitos superan Luhn, el TXT usa los **16 dígitos**
   como identificador de tarjeta. La columna original del Excel no se modifica.
3. La institución receptora debe proceder de la evidencia bancaria existente
   (institución del estado, columna de banco o concepto), **no de los primeros
   dígitos de la tarjeta**.
4. No se reparan automáticamente montos vacíos/cero ni fechas ambiguas: esas
   operaciones permanecen pendientes. Sólo se admite reparar el formato OCR
   exacto `DD ENEPAGO` (o abreviaturas equivalentes) si el periodo del estado
   permite fijar una fecha única.

La hoja **Control CEP** incluye `Cuenta Beneficiaria TXT` y
`Formato Cuenta TXT` para auditar el identificador enviado, por ejemplo una
tarjeta `TARJETA_16_DESDE_00`.

**Prueba antes de merge:** se añadieron casos sintéticos para tarjetas de
16 dígitos con prefijo `00`, CLABE válida que inicia con `00`,
tarjeta con checksum inválido, ausencia de banco receptor, importe cero y
`02 ENEPAGO`. Los movimientos y los parsers siguen intactos.

## Reconsulta manual y compatibilidad histórica (PR #95)

**Excel admitidos:** exportación original antigua (con `Número de Cuenta` y
sin CLABE Titular), exportación original actual, copia mejorada y cualquiera
de los dos Excel previamente cruzados. Al subir un libro se activa la
consulta TXT **sin necesidad de normalizar de nuevo**. El archivo cargado
permanece intacto; solo se crea una copia cuando se solicita normalizar
o se genera un nuevo Excel cruzado.

### ¿Dónde corregir para generar otro TXT?

**Todas las correcciones se hacen en la hoja `Movimientos`**, en estas
columnas, guardando el XLSX y volviéndolo a cargar:

| Columna en Movimientos | Uso para Banxico |
| --- | --- |
| `Tipo de Operación` | Marca `SPEI` cuando corresponda (no sustituye otros campos) |
| `Fecha de Operación` | Fecha del TXT; corregir como fecha Excel o `dd/mm/aaaa` |
| `Clave de Rastreo` | Rastreo real; lo escrito manualmente prevalece sobre el concepto |
| `Cargo` / `Abono` | Importe y sentido; no inventar un valor faltante |
| `Banco Emisor`, `Banco Receptor` | Código Banxico de cinco dígitos o nombre admitido; se pueden **crear** estas columnas si faltan |
| `CLABE del Beneficiario` | **Cargos/enviados**: preferido; se admite CLABE18, tarjeta16 o celular10 según la validación del módulo |
| `Cuenta del Beneficiario` | Cargos/enviados: respaldo cuando falta la CLABE/identificador preferido |
| `CLABE Titular` | **Abonos/recibidos**: preferida y única cuenta beneficiaria si existe; no confundir con ordenante |
| `Número de Cuenta` | Cuenta del titular. **Se conserva** como nombre canónico; `Cuenta Titular` duplicada se retira de las copias procesadas |

En los Excel históricos sin `CLABE Titular`, CEP intenta recuperarla solo
desde la hoja **Datos de la Cuenta** de ese mismo `id_estado` y nombre de
archivo. Si no existe allí, añade manualmente `CLABE Titular` a
`Movimientos` (como texto para conservar ceros). Una cuenta de 11 dígitos
no debe convertirse por suposiciones en una CLABE de 18.

### Hojas y resultados

- **Movimientos:** las columnas bancarias originales y cinco columnas CEP:
  `CEP Estado`, `CEP Detalle`, `CEP Tiene PDF`,
  `CEP Archivo PDF`, `CEP Archivo XML`. Las ligas PDF/XML se pueden abrir
  después de extraer el ZIP completo. Es aquí donde se corrigen los datos.
- **Control CEP:** una fila por candidato, con identificación del movimiento,
  los seis valores del TXT, formato de cuenta, línea TXT de fecha base,
  `Estado de datos`, `Datos por corregir`, `Resultado CEP`,
  `Motivo resultado`, disponibilidad de PDF y rutas a evidencia.
  Los datos de los XML **no** se duplican aquí.
- **Datos CEP:** XML oficiales y enlaces a archivos preservados.
- **Sin hojas** `Revisión Excel` ni `Revisión CEP` en el Excel procesado;
  los XLSX originales proporcionados jamás se alteran en disco.

**Ciclo de reconsulta:** filtra los SPEI en Movimientos, revisa
`CEP Estado` y `CEP Detalle`, corrige los seis datos en las columnas
anteriores, guarda un XLSX nuevo, cárgalo en CEP, pulsa **Descargar TXT
Banxico** inmediatamente y repite el cruce con los ZIP del lote correcto.
Para operaciones que siguen sin comprobarse, puedes continuar la consulta
manual en Banxico. El sistema no inventa información ni ejecuta CAPTCHA.

**Protección de celdas:** cuando `Cuenta Titular` y `Número de Cuenta`
contienen valores diferentes, la compactación se detiene y solicita
corregir la contradicción; no pierde la edición. Si hay fórmulas o tablas
que dependen de columnas, permite generar el TXT directo, pero exige una
copia sin dependencias antes de eliminar columnas potencialmente referenciadas.

## Flujo de uso

1. **Extracción de movimientos:** cargar o arrastrar los PDF, procesarlos y descargar el **Excel original**, con sus hojas y formato habituales. El arrastre usa una franja de 96 píxeles lógicos que sólo aparece cuando el receptor nativo está disponible; no inserta una ventana hija en el renderizador Flutter ni deja un aviso permanente si falla.
2. **CEP Banxico:** cargar un Excel anterior o pulsar **Usar extracción actual**. Esta acción carga el archivo sin normalizarlo todavía.
3. **Descargar TXT Banxico inmediatamente**, sin normalizar, o pulsar
   **Normalizar Excel** de manera opcional para homologar fechas y enriquecer
   datos. El normalizado nunca sustituye al XLSX cargado.
4. Guardar el archivo **.txt directamente**, cargarlo en Banxico y solicitar PDF y XML. Si hay más de 500 consultas se guardan varios TXT planos, sin ZIP intermedio.
5. Importar uno o varios ZIP de Banxico y descargar el ZIP final. Incluye ambos Excel cruzados con las columnas CEP al final de Movimientos y los comprobantes renombrados.
6. **Extraer todo el ZIP final en una misma carpeta.** Las celdas CEP Archivo PDF/XML contienen hipervínculos relativos a sus subcarpetas. Un clic abre el comprobante local correspondiente; los enlaces se conservan al mover la carpeta completa.

La recuperación de rastreos se ejecuta **en las funciones CEP que leen el Excel ya exportado**, nunca durante el procesamiento de PDF ni en la memoria de los parsers (digital u OCR). Reconoce etiquetas completas y abreviadas, la clave inicial de SPEI recibido de Banorte y el bloque posicional de BBVA: cabecera SPEI, CLABE validada, rastreo y contraparte. No convierte referencias, autorizaciones o números largos arbitrarios en claves de rastreo. Conserva los identificadores existentes y registra diferencias para revisión. El Excel original sigue saliendo del exportador anterior a CEP.

BBVA puede entregar la referencia de diez dígitos junto al código de banco de tres dígitos. Se separan sólo si ese banco coincide con la contraparte del bloque SPEI; nunca se concatenan para inventar una referencia de trece dígitos. La referencia del pago SPEI, cuando está presente en el bloque, se conserva por separado en **Referencia SPEI**. **Referencia Original** conserva el dato anterior; se elimina la hoja Revisión Excel.

## Checklist de las 11 mejoras

1. **Fechas Excel:** las columnas Fecha de Operación y Fecha de Liquidación de la copia mejorada contienen fechas de calendario, con formato `dd/mm/yyyy`. El año de las fechas parciales se obtiene del intervalo del estado. Del 15/12/2025 al 14/01/2026, `03 ENE` corresponde al **03/01/2026**. No se usa el año actual. Las fechas inválidas, sin evidencia o ambiguas quedan visibles para revisión.
2. **Original y mejorado:** el original conserva el contenido previo. La copia se comprueba después de escribir el XLSX: misma cantidad y orden de filas, mismos importes, saldos, conceptos y columnas no corregidas. Se conservan las columnas añadidas por el analista y sus hojas. Las fechas anteriores se conservan en columnas de trazabilidad. No se crea la hoja Revisión Excel.
3. **Segunda pasada:** recuperación de rastreo, referencia, cuenta y CLABE desde etiquetas del concepto, sin tomar números largos arbitrarios. CLABE con dígito verificador; números de cuenta como texto para conservar ceros. Los identificadores que Excel ya redondeó no se dan por válidos.
4. **Titular por cuenta:** Número de Cuenta y CLABE Titular sin una columna Cuenta Titular duplicada. En libros con fórmulas/tablas/gráficas se añaden al final para conservar las coordenadas. Se recuperan datos faltantes de estados compatibles del mismo banco/cuenta; nombre o RFC por sí solos no fusionan cuentas. Una familia de nombres de archivo sirve sólo si apunta inequívocamente a una cuenta sin contradicciones. Se registra el archivo donante.
5. **TXT:** desde el Excel **cargado o normalizado**, respetando correcciones manuales y fechas resolubles sin reescribirlo. Cada movimiento con rastreo es candidato SPEI; los que tienen los seis datos suficientes entran en consultas con fecha homologada, −1 y +1. Un abono usa la cuenta del titular de ese estado; un cargo usa la del beneficiario. Los TXT se descargan directamente: se dividen únicamente para respetar 2–500 líneas por archivo, sin dejar archivos de una línea. Duplicados de consulta no duplican las solicitudes, pero se conservan todos los movimientos.
6. **Dos pestañas:** Extracción de movimientos y CEP Banxico, tanto en Flet como en Streamlit. El escritorio paralelo reutiliza la interfaz principal y conserva su configuración OCR.
7. **Arrastrar PDF:** zona nativa Windows al pie de Extracción; acepta varios PDF locales, rutas Unicode y añade al lote. Usa una ventana auxiliar sin activación, propiedad de la ventana principal, sin parentesco entre procesos. Se oculta en CEP, durante procesamiento y al minimizar, **pero permanece activa durante el arrastre aunque el Explorador tenga el foco**. Streamlit conserva su cargador con arrastre del navegador.
8. **Importar ZIP:** lectura de XML oficiales, vinculación de PDF y cruce por rastreo, importe exacto, fecha original/±1 y cuentas/bancos disponibles. En Movimientos se añaden únicamente CEP Estado, CEP Detalle, CEP Tiene PDF y vínculos PDF/XML; los datos oficiales completos quedan en Datos CEP. Un rastreo coincidente con importe/cuenta/banco contradictorios se marca REVISAR y no recibe datos de otro movimiento.
9. **Paquete final:** `excel_original_con_CEP.xlsx`, `excel_mejorado_con_CEP.xlsx`, PDF/XML con nombres que incluyen fecha y participantes, y archivos recibidos de Banxico preservados. Admite varios ZIP acumulados y elimina duplicados de evidencia sin perder filas. CEP Estado identifica pendientes y CEP Archivo PDF/XML contiene vínculos clicables al comprobante correspondiente.
10. **Regresión y empaquetado:** pruebas de fechas, cuentas, TXT, XLSX reabierto, ZIP, contradicciones de cruce, controles Flet y WM_DROPFILES real en Windows. El constructor ejecuta `--self-test-excel-cep` dentro del EXE generado, además de las comprobaciones existentes de OCR y paralelismo.
11. **Catálogo bancario:** catálogo local de participantes Banxico, códigos oficiales y alias de los parsers. Los primeros tres dígitos de una CLABE válida determinan Banco del Beneficiario y Código Banco Beneficiario. Completa Sucursal cuando esté vacía (uso histórico como banco). No reemplaza una sucursal ya extraída ni afirma una oficina física. Los dígitos 4–6 se muestran como código de plaza/producto.

## Formatos revisados en todos los parsers registrados

Los parsers, el procesador de estados y el escritor del Excel original están restaurados respecto del commit pre-CEP `c98577e`; la recuperación adicional de rastreo se limita al Excel normalizado.

| Parser | Salida de fecha observada en código | Tratamiento |
| --- | --- | --- |
| Banamex | `DD MES`, incluidas fechas OCR ya limpiadas | Día/mes contra el periodo |
| BBVA | `DD/MES`, operación y liquidación | Año por periodo; mes sin día requiere revisión |
| Banorte | `DD-MMM-YY` / `DD-MMM-YYYY` | Conserva año explícito |
| Banorte OCR | `DD-MMM-YY` / `DD-MMM-YYYY` | Conserva año explícito |
| HSBC | `DD/MM/YYYY`, también recuperado de tablas SPEI | Fecha completa; cotejo con periodo |
| Scotiabank | `DD/MM/YYYY`; `DD MES` sin periodo | Fecha completa o año por periodo |
| Mifel | `DD/MM/YYYY` | Fecha completa |
| Cetes Directo | `DD/MM/YYYY` en operación y liquidación | Fecha completa |
| Mercado Pago | `DD/MM/YYYY` | Fecha completa |
| Nu | `DD/MM/YYYY` | Fecha completa |
| Banco Azteca | `DD/MM/YYYY` | Fecha completa |
| Santander | `DD/MM/YYYY` desde `DD/MES/YYYY` o numérica | Fecha completa |

## Prueba en VS Code (PowerShell)

Desde cualquier carpeta del clon de Estado Cuenta Engine abierto en VS Code:

```powershell
Set-Location (git rev-parse --show-toplevel)
git fetch origin
git switch -c feature/cep-excel-retrocompatible-reconsulta --track origin/feature/cep-excel-retrocompatible-reconsulta
git pull --ff-only
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[desktop]"
.\.venv\Scripts\python.exe -m pip install --group dev
.\.venv\Scripts\python.exe -m pytest -m "not integration" -q
.\.venv\Scripts\python.exe app\main_desktop.py --self-test-excel-cep
.\.venv\Scripts\python.exe app\main_desktop.py
```

Si ya utilizas un entorno con PaddleOCR, usa su Python y conserva esa instalación; no hace falta descargar de nuevo modelos para probar Excel/CEP. Para habilitar PaddleOCR en un entorno nuevo, instala el extra `.[desktop,paddleocr]` y sigue el procedimiento de modelos existente.

### Verificación con tus estados reales

- Cargar varios bancos/cuentas, incluidos estados diciembre–enero; comprobar cargos/abonos y ordenar Fecha de Operación por año en el mejorado.
- Revisar Número de Cuenta/CLABE Titular y el archivo donante en casos incompletos; confirmar que ninguna cuenta recibió datos de otra.
- Cargar los movimientos en CEP, descargar el TXT directamente o normalizar opcionalmente. Revisar los seis campos y sus fechas ±1. Descargar original y normalizado para comparar.
- Solicitar PDF y XML en Banxico e importar sus ZIP aquí. Revisar EXITO, EXITO_FECHA_ALTERNATIVA, REVISAR, NO_APARECE_EN_ZIP y NO_CONSULTABLE.
- Descargar y extraer el ZIP final. Comprobar campos oficiales y abrir el PDF de cada fila mediante su hipervínculo en ambos Excel.

No se automatizan correo/token/CAPTCHA. Una ausencia de XML no implica que la transferencia fallara. La extracción y el cotejo no verifican criptográficamente el sello. PDF sin XML y XML inválidos se conservan entre los originales para revisión.

## Fuentes del formato y catálogo

- https://www.banxico.org.mx/cep-scl/ — seis campos, UTF-8 y límites del lote.
- https://www.banxico.org.mx/cep-scl/listaInstituciones.do — catálogo consultado el 07/11/2026.
- https://www.banxico.org.mx/footer-es/preguntas-frecuentes-dudas-ba.html — estructura CLABE.

Las pruebas automáticas utilizan exclusivamente información sintética. La validación con estados reales y Microsoft Excel de Windows corresponde a la prueba local del PR.
