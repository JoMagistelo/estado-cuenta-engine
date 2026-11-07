# CEP Banxico — asistente por pasos

Herramienta Python 3.10+ con interfaz Tkinter para preparar consultas SPEI a Banxico
y organizar en un ZIP final los PDF, XML y datos oficiales (incluidos nombres y RFC).
No elude CAPTCHA ni realiza descargas desatendidas del portal.

## Iniciar desde VS Code

En \`C:\Proyectos\CEP_Banxico_GitHub\experimentos\cep-banxico-gui\`:

\`\`\`powershell
py -m unittest discover -s tests -v
py CEP_Banxico_GUI.py
\`\`\`

## Flujo guiado (6 pasos)

1. **Seleccionar Excel / CSV** exportado por Estado Cuenta Engine.
2. **Detectar transferencias SPEI**: no necesita «Tipo de Operación» clasificado.
3. **Generar TXT + Excel SPEI**: crea exactamente **un Excel** llamado
   \`resultado_CEP.xlsx\` y TXT de consulta. No se generan CSV auxiliares.
4. **Abrir Banxico y subir TXT**: el archivo **principal** es
   \`lote_001.txt\` (o sus consecutivos). Selecciona ambos formatos: PDF y XML.
5. **Recuperar ZIP**: usa correo y token que proporciona Banxico al recibir el lote.
6. **Exportar ZIP final**: selecciona el ZIP oficial descargado y la herramienta
   crea \`CEP_BANXICO_FINAL_*.zip\` con PDF renombrados, XML conservados,
   \`resultado_CEP.xlsx\`, resumen oficial y archivos en revisión.

**Acceso independiente:** «Procesar ZIP existente (sin Excel ni TXT)» permite
procesar directamente un ZIP previo de Banxico. Los nombres y RFC se obtienen
exclusivamente del XML; no es necesario introducir el Excel de movimientos.

## Fechas alternativas: un día antes y uno después

El botón 3 genera además \`reintento_fecha_001.txt\` (y sus consecutivos si hacen
falta). Para cada SPEI consultable agrega dos variantes de la fecha: **−1 y +1 día**,
con idéntica clave de rastreo, códigos de banco, cuenta beneficiaria y monto.
Las fechas alternativas fuera del intervalo 16-mar-2018 a hoy se omiten.
Cada TXT tiene entre **2 y 500** registros; no se crean lotes de una sola línea.

**Cargar primero los archivos originales \`lote_*.txt\`.** Los archivos
\`reintento_fecha_*.txt\` son un **recurso opcional** para usar si la consulta
original no encuentra un comprobante. Mezclarlos desde el inicio desperdicia
consultas y complica atribuir resultados. Cada carga en Banxico tiene correo,
token y ZIP propio. Esta versión procesa **un ZIP por vez** (todavía no fusiona
automáticamente varias descargas).

Ejemplo del formato oficial, donde **los códigos de banco sí están presentes**:
\`\`\`text
2025-04-28,085901042960311856,40002,40012,012180015392699598,10000.00
\`\`\`
Los campos son: fecha, rastreo, código emisor, código receptor,
**cuenta del beneficiario**, monto. En un cargo, la cuenta beneficiaria es la
del tercero; en un abono, es la cuenta receptora del evaluado.

## Un solo libro Excel

Se produce un único archivo \`resultado_CEP.xlsx\`, con hojas:
- **Resumen**: conteos de candidatos, TXT, XML, PDF, cruces y resultados.
- **Datos CEP**: una fila por XML oficial interpretable, incluso si no vino PDF.
  Contiene nombres, RFC, cuentas, montos, banco, rastreo, fecha oficial y
  columna \`tiene_pdf\` (SÍ o NO). No se sustituyen nombres oficiales por alias.
- **SPEI**: todos los SPEI detectados del Excel de origen, incluso los que
  tienen información insuficiente para consulta por lotes. Incluye clave, bancos,
  cuenta, monto, fecha del estado, resultado de búsqueda, fecha del XML si difiere
  y diferencia de días. Las operaciones incompletas siguen visibles.

**Estados en la hoja SPEI:**
- \`PENDIENTE_BANXICO\`: TXT generado, consulta todavía no confirmada.
- \`EXITO\`: existe XML vinculado que coincide en los campos cotejados.
- \`EXITO_FECHA_ALTERNATIVA\`: XML vinculado con fecha distinta **exactamente
  un día**; se registra la fecha original y la oficial, sin modificarlas.
- \`REVISAR\`: hay datos de XML pero presentan discrepancias no explicadas.
- \`FALLO_BUSQUEDA_CEP\`: el \`resumen.txt\` de Banxico declara que
  **no pudo localizar** esa operación y se identifica inequívocamente el rastreo.
  **No significa que el SPEI haya fallado o que no se haya realizado.**
- \`NO_APARECE_EN_ZIP\`: no hay XML asociado en la descarga introducida.
  No permite concluir que la búsqueda haya fallado.
- \`NO_CONSULTABLE\`: faltan uno o más datos obligatorios o existen
  contradicciones de formato que impiden enviar datos fiables.
- \`SIN_LOTE\`: no hay mínimo de dos transferencias distintas para cargar TXT.

La consulta por lotes exige seis campos completos: fecha, clave de rastreo,
código de banco emisor, código de banco receptor, cuenta beneficiaria y monto.
**No se inventan** fechas, cuentas, rastreos, RFC ni instituciones. Todos los
candidatos SPEI quedan documentados, aunque algunos no puedan entrar en TXT.

## Integridad, privacidad y límites

- PDF vinculados en \`PDF/\`: su número debe coincidir exactamente con filas
  \`Datos CEP.tiene_pdf = SÍ\`; cada XML interpretado queda en \`XML/\`.
- PDF sin XML, XML ilegibles o material sin vínculo seguro quedan en \`REVISION/\`.
- No se altera el ZIP original. No se suben expedientes, TXT, XML ni datos
  bancarios a GitHub: el repositorio contiene únicamente código y pruebas sintéticas.
- **No hay validación criptográfica del sello CEP** ni descarga automática
  de Banxico en este piloto; para ello utiliza el portal y validador oficiales.
- Los datos de fecha ±1 generan intentos independientes, no acreditan un pago
  ni garantizan que Banxico entregue comprobantes.
- La versión actual procesa una descarga oficial de ZIP cada vez; consolidar
  los resultados de varios ZIP es una etapa posterior.

Consulta por lotes: https://www.banxico.org.mx/cep-scl/inicio.do

Recuperar por correo y token: https://www.banxico.org.mx/cep-scl/inicio2.do
