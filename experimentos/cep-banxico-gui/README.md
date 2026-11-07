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