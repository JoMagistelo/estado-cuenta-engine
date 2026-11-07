# Preparador CEP Banxico — piloto con interfaz visual

Aplicación Python de escritorio para leer archivos `.xlsx` o `.csv` de Estado Cuenta Engine, **sin depender de que la columna Tipo de Operación esté clasificada**. Lee cargos y abonos, identifica candidatos SPEI mediante conceptos y claves de rastreo y genera consultas individuales CSV y archivos TXT de CEP por lotes. **No realiza scraping, no resuelve CAPTCHA y todavía no descarga comprobantes CEP.**

## Ejecutar en Windows

1. Instala Python 3.10 o superior desde python.org y activa «Add python.exe to PATH».
2. Descarga este proyecto y descomprime el ZIP.
3. Haz doble clic en `INICIAR_WINDOWS.bat` (o ejecuta `py CEP_Banxico_GUI.py`). **No necesitas instalar librerías externas.**
4. Selecciona tu Excel: las hojas esperadas son `Movimientos` y, opcionalmente, `Datos de la Cuenta`. También acepta un CSV de movimientos.
5. Pulsa **Analizar movimientos** y revisa la columna Estado. **Generar archivos** crea un subdirectorio con `consultas_individuales.csv`, `pendientes_revision.csv` y, cuando haya dos o más registros listos, `lote_001.txt` (hasta 500 operaciones por archivo).
6. El botón **Abrir CEP por lotes** abre el portal de Banxico para cargar el TXT manualmente. El botón **Probar acceso Banxico** hace únicamente solicitudes HTTP GET y no envía información bancaria.

## Criterios

- SPEI enviado (cargo): banco emisor es el banco del estado de cuenta; cuenta beneficiaria es la cuenta/CLABE del tercero.
- SPEI recibido (abono): banco receptor es el banco del estado; cuenta beneficiaria es la **CLABE del titular** de `Datos de la Cuenta` (por `id_estado`) o la CLABE introducida manualmente. El banco emisor se busca en el concepto; si no está identificado, se marca **PENDIENTE**, no se inventa.
- Se buscan claves de rastreo explícitas; si falta una, la referencia queda para consulta individual, no para TXT por lotes.
- Fecha de operación `28 ABR` se interpreta con fechas de inicio/fin del estado; en su ausencia se usan fecha de corte y nombre del archivo. Las fechas ambiguas se revisan.
- Se valida el dígito verificador de las CLABE de 18 dígitos; una cuenta con error requiere revisión documental.
- **LISTO no significa CEP encontrado ni SPEI liquidado.** Es únicamente un registro completo para intentar consulta.

## Privacidad y límites

El procesamiento es local. No se adjuntan expedientes, hojas de movimientos reales, CLABE, salidas ni descargas al repositorio. No subas los CSV/TXT generados a GitHub: contienen datos bancarios de personas. La consulta y eventual descarga debe respetar las condiciones y mecanismos de Banxico. No intentes automatizar la evasión de CAPTCHAs.

Los códigos bancarios incluidos son un catálogo inicial, no una enumeración exhaustiva de participantes SPEI; revisa códigos y cuentas antes de enviar lotes. Revisa también las operaciones sospechosas cuando el extractor haya colocado texto en columnas erróneas.

## Ejecutar pruebas

`python -m unittest discover -s tests -v`

Sitios oficiales: https://www.banxico.org.mx/cep/ y https://www.banxico.org.mx/cep-scl/inicio.do

## Nuevo: Importar ZIP de Banxico y generar Excel de CEP

**Importante:** este software **no fabrica ni descarga automáticamente** los CEP. El botón «Generar archivos» prepara el TXT para que realices la consulta oficial en Banxico, donde se requiere correo y token. Consulta por lotes: https://www.banxico.org.mx/cep-scl/ ; consulta de resultados: https://www.banxico.org.mx/cep-scl/inicio2.do. Pide formato **PDF y XML** y conserva el ZIP original. Sólo los CEP localizados por Banxico vendrán en él.

1. Abre `CEP_Banxico_GUI.py`, selecciona el Excel y pulsa «Analizar movimientos» → «Generar archivos».
2. En «Abrir CEP por lotes», carga `lote_001.txt`, indica tu correo, elige **ambos formatos (PDF y XML)** y anota el token.
3. Obtén el ZIP de resultados por el correo/token en la página oficial.
4. En la aplicación pulsa **«Importar ZIP con PDF + XML»**. Selecciona el ZIP, después `consultas_individuales.csv` generado por el programa (si es necesario) y la carpeta de destino.
5. La aplicación crea una carpeta `CEP_RECUPERADOS_...` con `PDF/`, `XML/`, `resultado_CEP.xlsx` (hojas `Resumen`, `Datos CEP`, `Pendientes`) y la copia del `resumen.txt` original de Banxico cuando está presente.

**Criterios de integridad documental:** nombres de `nombre_beneficiario_cep` y `nombre_ordenante_cep` se extraen del XML, **nunca se inventan a partir del estado**; el nombre del estado original se conserva en otra columna. La coincidencia exige clave de rastreo, fecha y monto reconocibles; cuando los datos disponibles contradicen al estado, se marca `REVISAR`. El XML no sustituye la validación criptográfica oficial del sello; esta utilidad hace conciliación, no certificación legal. Los PDF sin XML se conservan con prefijo `SIN_XML_`, sin atribuirles un nombre. Los documentos originales de Banxico **no son alterados**. Si algún XML tiene un formato no reconocido, se etiqueta para revisión y hace falta una muestra despersonalizada para agregar soporte seguro.

**Límites:** no garantiza encontrar 92 comprobantes; las 92 filas listas son sólo consultas preparadas, no respuestas. Se requiere correo/token y supervisión del usuario para descargar el ZIP oficial, sin eludir captchas. No debe subirse a GitHub ninguna descarga real, CLABE, XLSX del expediente, PDF ni XML.

## Pruebas técnicas

```powershell
py -m unittest discover -s tests -v
```

Se incluyen pruebas con comprobantes sintéticos (sin datos de personas reales) para comprobar extracción de XML, copia renombrada PDF, generación de Excel, conciliación monto/fecha/rastreo, protección de rutas y ausencia de XML.

### Nombres de los archivos y múltiples bancos

Los PDF se nombran con `FECHA__TIPO__CONTRAPARTE__MONTO__RASTREO.pdf`. En un **cargo/enviado**, contraparte es el **beneficiario del XML**; en un **abono/recibido**, es el **ordenante del XML**, evitando crear cientos de PDF con el nombre repetido del evaluado. Si no hay nombre verificable en el XML se indica `SIN_NOMBRE_XML`. Ambos nombres del CEP se guardan por separado en el Excel. El catálogo local de instituciones está en `banxico_catalogo.py` y se nutre de la [lista oficial de participantes](https://www.banxico.org.mx/cep-scl/listaInstituciones.do); se ampliará por pruebas de cada parser de Estado Cuenta Engine, no por suposiciones.

## Una sola hoja de datos CEP (PDF SÍ/NO)

El Excel de resultados incluye una hoja **Datos CEP** (una fila por XML de CEP interpretable), con los **nombres y RFC provenientes únicamente del XML de Banxico**. La columna `tiene_pdf` indica **SÍ** cuando se conservó un PDF vinculado a ese XML y **NO** cuando sólo se recuperó el XML. De ese modo, ninguna información oficial del XML se pierde por no tener PDF.

La carpeta **PDF/** guarda exclusivamente PDFs emparejados con XML: su cantidad debe coincidir con las filas `tiene_pdf = SÍ`. La carpeta **XML/** conserva un XML por cada fila de **Datos CEP**, sea SÍ o NO. Los PDF sin XML válido y documentos ilegibles se conservan por separado en **REVISION/**, para no adjudicarles nombres o RFC sin sustento.

La hoja **Cruce Estado Cuenta** contiene exclusivamente metadatos de cotejo y los campos del estado bancario, incluido cualquier alias. **No se mezclan aliases con los nombres oficiales** de la hoja **Datos CEP**. Otra hoja **Pendientes** informa registros sin comprobante identificable y los casos a revisar.

El sistema **no realiza una validación criptográfica del sello** ni recupera aún automáticamente los comprobantes del servidor Banxico. Sólo organiza los archivos obtenidos mediante el servicio oficial.

## Obtener CEP y exportar ZIP final (flujo guiado)
La ventana ahora muestra **OBTENER CEP EN BANXICO Y EXPORTAR ZIP FINAL** como acción principal.
Selecciona tu Excel y pulsa ese botón. El programa identifica los SPEI y guarda el TXT
para la consulta por lotes. Abre el portal oficial https://www.banxico.org.mx/cep-scl/inicio.do
y carga allí el TXT, escribe tu correo y solicita **PDF y XML**. Completa personalmente
las verificaciones que aparezcan. Conserva el token y recupera el ZIP oficial en
https://www.banxico.org.mx/cep-scl/inicio2.do. Al regresar a la aplicación,
selecciona el ZIP descargado.

La aplicación creará un **CEP_BANXICO_FINAL_*.zip** que contiene **PDF/**,
**XML/**, **resultado_CEP.xlsx**, el resumen oficial y **REVISION/** si corresponde.
Verifica que cada PDF en PDF/ tenga una fila marcada SÍ y que cada XML corresponda
a una fila en Datos CEP. Si solamente recuperó un XML, lo conserva y marca NO.
El ZIP oficial original NO se modifica.

**Límite confirmado:** Banxico exige correo y token; su portal puede exigir CAPTCHA.
La aplicación todavía NO completa esa interacción de manera automática ni elude
controles. El botón inicia un flujo guiado y empaqueta los resultados oficiales
una vez que se descargaron. Para más de 500 operaciones se generan varios TXT
y esta versión procesa un ZIP de Banxico por vez.
