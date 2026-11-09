"""End-to-end synthetic check also executed inside the portable executable."""

from datetime import datetime
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from openpyxl import Workbook, load_workbook

from cep.evidence import CepEvidence
from cep.columns import TRACE_COLUMNS, TXT_COLUMNS
from cep.package import export_cep_zip
from cep.queries import batch_texts, queries_from_workbook
from exporters.excel.normalization import get, rows_from_sheet
from exporters.excel.workbook_bundle import WorkbookBundle


def run_excel_cep_self_test():
    holder = "002180032240946700"
    workbook = Workbook()
    account = workbook.active
    account.title = "Datos de la Cuenta"
    account.append(["id_estado", "Nombre del Archivo", "Banco", "Número de Cuenta", "CLABE",
                    "Periodo de Inicio", "Periodo de Fin", "Fecha de Corte"])
    account.append([1, "SINTETICO.pdf", "banamex", "03224094670", holder,
                    "15/12/2025", "14/01/2026", "14/01/2026"])
    movements = workbook.create_sheet("Movimientos")
    movements.append(["id_estado", "Nombre del Archivo", "Banco", "Fecha de Corte", "No. de Movimiento",
                      "Fecha de Operación", "Cargo", "Abono", "Clave de Rastreo", "CLABE del Beneficiario", "Concepto"])
    movements.append([1, "SINTETICO.pdf", "banamex", "14/01/2026", 1, "03 ENE", 1.25, 0, None, holder,
                      "SPEI ENVIADO CVE RAST: SYNTHETIC001"])
    content = BytesIO()
    workbook.save(content)
    workbook.close()
    bundle = WorkbookBundle.from_excel(content.getvalue())
    queries = queries_from_workbook(bundle.improved)
    if len(batch_texts(queries)["lote_001.txt"].splitlines()) != 3:
        raise RuntimeError("El EXE no generó las tres consultas de fecha")
    xml = (f'<SPEI_Tercero fechaOperacion="03/01/2026" claveRastreo="SYNTHETIC001">'
           f'<Ordenante cuenta="{holder}" bancoEmisor="40002" nombre="ORIGEN SINTETICO"/>'
           f'<Beneficiario cuenta="{holder}" bancoReceptor="40002" nombre="DESTINO SINTETICO"/>'
           '<DatosPago monto="1.25"/></SPEI_Tercero>').encode()
    official = BytesIO()
    with ZipFile(official, "w") as archive:
        archive.writestr("cep.xml", xml)
        archive.writestr("cep.pdf", b"%PDF-1.4\nsynthetic")
    evidence = CepEvidence()
    evidence.add_zip(official.getvalue())
    with TemporaryDirectory(prefix="engine_cep_selftest_") as folder:
        path = Path(folder) / "final.zip"
        if export_cep_zip(bundle, queries, evidence, path) != {"EXITO": 1}:
            raise RuntimeError("El EXE no pudo cruzar la evidencia CEP")
        with ZipFile(path) as archive:
            check = load_workbook(BytesIO(archive.read("excel_mejorado_con_CEP.xlsx")))
            row = rows_from_sheet(check["Movimientos"])[0]
            if get(row, "Fecha de Operación") != datetime(2026, 1, 3):
                raise RuntimeError("El EXE no guardó una fecha real de Excel con año correcto")
            if get(row, "CEP Archivo PDF") not in archive.namelist():
                raise RuntimeError("El EXE perdió el PDF vinculado al movimiento")
            ws = check["Movimientos"]
            headers = [cell.value for cell in ws[1]]
            position = headers.index("Revisión Normalización") + 1
            if headers[position:position + 6] != list(TXT_COLUMNS):
                raise RuntimeError("El EXE no conservó las seis columnas TXT después de Revisión Normalización")
            if "Control CEP" in check:
                raise RuntimeError("El EXE volvió a generar la hoja Control CEP obsoleta")
            from openpyxl.utils import get_column_letter
            for label in TRACE_COLUMNS:
                if not ws.column_dimensions[get_column_letter(headers.index(label) + 1)].hidden:
                    raise RuntimeError("El EXE no ocultó la trazabilidad de fechas")
            column = next(c.column for c in ws[1] if c.value == "CEP Archivo PDF")
            if ws.cell(2, column).hyperlink.target != get(row, "CEP Archivo PDF"):
                raise RuntimeError("El EXE no conservó el enlace al PDF CEP")
            ws.cell(2, headers.index("TXT Monto") + 1).value = 2.50
            edited = BytesIO()
            check.save(edited)
            check.close()
            uploaded = WorkbookBundle.from_uploaded(edited.getvalue())
            retried = queries_from_workbook(uploaded.improved)[0]
            if not retried.ready or not retried.line().endswith(",2.50"):
                raise RuntimeError("El EXE no respetó la corrección del bloque TXT sin renormalizar")
