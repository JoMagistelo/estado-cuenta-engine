# Excel mejorado y CEP integrado

PR de prueba contra master. El experimento `experimentos/cep-banxico-gui` se conserva con archivos idénticos a la rama `feature/cep-banxico-gui-piloto`; no se modificó su código ni sus ramas. Se incorpora esa copia intacta porque master todavía no contenía el experimento. La integración usa módulos independientes en `src/cep` y el exportador existente para conservar el Excel original.

## Checklist de las 11 mejoras

1. **Fechas Excel:** las columnas Fecha de Operación y Fecha de Liquidación de la copia mejorada contienen fechas de calendario, con formato `dd/mm/yyyy`. El año de las fechas parciales se obtiene del intervalo del estado. Del 15/12/2025 al 14/01/2026, `03 ENE` corresponde al **03/01/2026**. No se usa el año actual. Las fechas inválidas, sin evidencia o ambiguas quedan visibles para revisión.
2. **Original y mejorado:** el original conserva el contenido previo. La copia se comprueba después de escribir el XLSX: misma cantidad y orden de filas, mismos importes, saldos, conceptos y columnas no corregidas. Se conservan las columnas añadidas por el analista y sus hojas. Las fechas anteriores y los cambios quedan en columnas de trazabilidad y Revisión Excel.
3. **Segunda pasada:** recuperación de rastreo, referencia, cuenta y CLABE desde etiquetas del concepto, sin tomar números largos arbitrarios. CLABE con dígito verificador; números de cuenta como texto para conservar ceros. Los identificadores que Excel ya redondeó no se dan por válidos.
4. **Titular por cuenta:** Cuenta Titular y CLABE Titular junto al corte en los libros simples del Engine. En libros con fórmulas/tablas/gráficas se añaden al final para conservar las coordenadas. Se recuperan datos faltantes de estados compatibles del mismo banco/cuenta; nombre o RFC por sí solos no fusionan cuentas. Una familia de nombres de archivo sirve sólo si apunta inequívocamente a una cuenta sin contradicciones. Se registra el archivo donante.
5. **TXT:** siempre desde el **mejorado**, también al cargar Excel anteriores. Cada movimiento con rastreo es candidato SPEI; los que tienen los seis datos suficientes entran en consultas con fecha original, −1 y +1. Un abono usa la cuenta del titular de ese estado; un cargo usa la del beneficiario. Un solo conjunto de TXT enriquecidos: se divide únicamente para respetar 2–500 líneas por archivo, sin dejar archivos de una línea. Duplicados de consulta no duplican las solicitudes, pero se conservan todos los movimientos.
6. **Dos pestañas:** Extracción de movimientos y CEP Banxico, tanto en Flet como en Streamlit. El escritorio paralelo reutiliza la interfaz principal y conserva su configuración OCR.
7. **Arrastrar PDF:** zona nativa Windows al pie de Extracción; acepta varios PDF locales, rutas Unicode y añade al lote. Usa el mismo procesamiento y controles de cancelación. No modifica el cliente Flutter portable ni añade una extensión incompatible. Streamlit conserva su cargador con arrastre del navegador.
8. **Importar ZIP:** lectura de XML oficiales, vinculación de PDF y cruce por rastreo, importe exacto, fecha original/±1 y cuentas/bancos disponibles. Los datos oficiales se añaden a la misma fila de Movimientos, después de las columnas existentes. Un rastreo coincidente con importe/cuenta/banco contradictorios se marca REVISAR y no recibe datos de otro movimiento.
9. **Paquete final:** `excel_original_con_CEP.xlsx`, `excel_mejorado_con_CEP.xlsx`, PDF/XML con nombres que incluyen fecha y participantes, y archivos recibidos de Banxico preservados. Admite varios ZIP acumulados y elimina duplicados de evidencia sin perder filas. CEP Estado y CEP Archivo PDF/XML permiten identificar pendientes manualmente.
10. **Regresión y empaquetado:** pruebas de fechas, cuentas, TXT, XLSX reabierto, ZIP, contradicciones de cruce, controles Flet y WM_DROPFILES real en Windows. El constructor ejecuta `--self-test-excel-cep` dentro del EXE generado, además de las comprobaciones existentes de OCR y paralelismo.
11. **Catálogo bancario:** catálogo local de participantes Banxico, códigos oficiales y alias de los parsers. Los primeros tres dígitos de una CLABE válida determinan Banco del Beneficiario y Código Banco Beneficiario. Completa Sucursal cuando esté vacía (uso histórico como banco). No reemplaza una sucursal ya extraída ni afirma una oficina física. Los dígitos 4–6 se muestran como código de plaza/producto.

## Formatos revisados en todos los parsers registrados

La capa de exportación evita alterar los parsers o sus totales ya validados.

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
git switch feature/excel-normalizado-cep-integrado
git pull --ff-only
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[desktop]"
.\.venv\Scripts\python.exe -m pip install --group dev
.\.venv\Scripts\python.exe -m pytest -m "not integration" -q
.\.venv\Scripts\python.exe app\main_desktop.py --self-test-excel-cep
.\.venv\Scripts\python.exe app\main_desktop.py
```

Si ya utilizas un entorno con PaddleOCR, usa su Python y conserva esa instalación; no hace falta descargar de nuevo modelos para probar Excel/CEP. Para habilitar PaddleOCR en un entorno nuevo, instala el extra `.[desktop,paddleocr]` y sigue el procedimiento de modelos existente.

### Verificación con tus estados reales

- Cargar varios bancos/cuentas, incluidos estados diciembre–enero; comprobar cargos/abonos y ordenar Fecha de Operación por año en el mejorado.
- Revisar Cuenta Titular/CLABE Titular y el archivo donante en casos incompletos; confirmar que ninguna cuenta recibió datos de otra.
- Preparar TXT en CEP: revisar los seis campos y sus fechas ±1 en el archivo de cada lote. Descargar ambos Excel para comparar.
- Solicitar PDF y XML en Banxico e importar sus ZIP aquí. Revisar EXITO, EXITO_FECHA_ALTERNATIVA, REVISAR, NO_APARECE_EN_ZIP y NO_CONSULTABLE.
- Descargar ZIP final y comprobar que los campos oficiales y nombres de comprobantes de cada fila correspondan al movimiento correcto.

No se automatizan correo/token/CAPTCHA. Una ausencia de XML no implica que la transferencia fallara. La extracción y el cotejo no verifican criptográficamente el sello. PDF sin XML y XML inválidos se conservan entre los originales para revisión.

## Fuentes del formato y catálogo

- https://www.banxico.org.mx/cep-scl/ — seis campos, UTF-8 y límites del lote.
- https://www.banxico.org.mx/cep-scl/listaInstituciones.do — catálogo consultado el 07/11/2026.
- https://www.banxico.org.mx/footer-es/preguntas-frecuentes-dudas-ba.html — estructura CLABE.

Las pruebas automáticas utilizan exclusivamente información sintética. La validación con estados reales y Microsoft Excel de Windows corresponde a la prueba local del PR.
