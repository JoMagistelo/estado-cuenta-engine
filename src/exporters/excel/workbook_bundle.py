"""Original/mejorado pair and verification after writing real XLSX files."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

from exporters.excel.batch_exporter import export_batch_excel
from exporters.excel.normalization import NormalizationReport, get, normalize_workbook, rows_from_sheet
from exporters.excel.cells import header_key
from cep.columns import TXT_KEYS, has_txt_inputs
from cep.spei_classifier import CLASSIFICATION_COLUMN, classify_spei
from cep.spei_recovery import RECOVERABLE_FIELDS, recover_missing
from utils.statement_dates import full_date


def verify_pair(original: bytes, improved: bytes, *, report: NormalizationReport | None = None) -> int:
    """Reopen both serialized files and check row identity, money and date types."""
    raw = load_workbook(BytesIO(original), data_only=False)
    clean = load_workbook(BytesIO(improved), data_only=False)
    try:
        a, b = rows_from_sheet(raw["Movimientos"]), rows_from_sheet(clean["Movimientos"])
        if len(a) != len(b):
            raise ValueError("La comprobación del Excel detectó un cambio en el número de movimientos")
        recorded_changes = {}
        if report:
            for change in report.changes:
                recorded_changes.setdefault(change["Fila Excel"], {})[change["Campo"]] = change
        for left, right in zip(a, b):
            allowed = {"Fecha de Operación", "Fecha de Liquidación", "Fecha de Corte", "Número de Cuenta",
                       "Cuenta Titular", "CLABE Titular", "Estado de Fecha", "Revisión Normalización",
                       "Origen Datos Titular"}
            recovered, _ = recover_missing(left, classify_spei(left))
            recorded = recorded_changes.get(left["_row"], {})
            for name in left:
                if name in allowed or name == '_row' or name.startswith("CEP "):
                    # Imported previous CEP results are purposely cleared:
                    # they cannot be trusted without reloading the XML ZIP.
                    continue
                if get(left, name) != get(right, name):
                    if (name in RECOVERABLE_FIELDS and name in recovered
                            and get(right, name) == recovered[name]):
                        continue
                    if name == CLASSIFICATION_COLUMN and get(right, name) == (classify_spei(left).label or None):
                        continue
                    if header_key(name) in TXT_KEYS and name in recorded:
                        change = recorded[name]
                        previous = get(left, name)
                        actual = get(right, name)
                        displayed = actual.isoformat() if isinstance(actual, (date, datetime)) else str(actual or "")
                        equal = displayed == change["Normalizado"]
                        if isinstance(actual, (date, datetime)):
                            equal = full_date(actual) == full_date(change["Normalizado"])
                        if (previous is None or str(previous).strip() == "") and equal:
                            continue
                    raise ValueError(f"La comprobación detectó cambio en {name}, fila {left['_row']}")
            if get(right, "Estado de Fecha") not in {None, "VACIA", "REVISAR"}:
                if not isinstance(get(right, "Fecha de Operación"), (date, datetime)):
                    raise ValueError(f"Fecha guardada como texto en fila {right['_row']}")
        return len(a)
    finally:
        raw.close()
        clean.close()


@dataclass
class WorkbookBundle:
    original: bytes
    improved: bytes
    report: NormalizationReport
    source_name: str = "reporte_estados_de_cuenta.xlsx"
    prepared: bool = False

    @classmethod
    def from_excel(cls, source: str | Path | bytes, *, source_name="reporte_estados_de_cuenta.xlsx"):
        original = source if isinstance(source, bytes) else Path(source).read_bytes()
        with tempfile.TemporaryDirectory(prefix="engine_excel_") as folder:
            improved_path = Path(folder) / "mejorado.xlsx"
            report = normalize_workbook(original, improved_path)
            improved = improved_path.read_bytes()
        verify_pair(original, improved, report=report)
        return cls(original, improved, report, source_name, True)

    @classmethod
    def from_uploaded(cls, source: str | Path | bytes, *, source_name="movimientos.xlsx"):
        """Use an existing (possibly manually corrected) Excel without re-normalizing.

        Legacy exports, original exports, normalized exports and already-crossed
        exports all use the same Movimientos source-of-truth. The uploaded bytes
        remain unchanged; querying never silently rewrites user corrections.
        """
        content = source if isinstance(source, bytes) else Path(source).read_bytes()
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        try:
            if "Movimientos" not in workbook.sheetnames:
                raise ValueError("El Excel debe contener la hoja Movimientos")
            ws = workbook["Movimientos"]
            header_cells = next(ws.iter_rows(max_row=1))
            headers = {header_key(c.value) for c in header_cells}
            prepared = has_txt_inputs(header_cells)
            if not prepared and not {"FECHADEOPERACION", "CARGO", "ABONO"} <= headers:
                raise ValueError("Faltan columnas básicas de Movimientos (fecha, cargo o abono)")
            count = sum(1 for values in ws.iter_rows(min_row=2, values_only=True)
                        if any(v is not None for v in values))
        finally:
            workbook.close()
        return cls(content, content, NormalizationReport(movements=count), source_name, prepared)

    @classmethod
    def from_results(cls, results):
        return cls.from_excel(original_from_results(results))

    def content(self, variant: str):
        if variant not in {"original", "mejorado"}:
            raise ValueError("Elige original o mejorado")
        return self.original if variant == "original" else self.improved


def original_from_results(results) -> bytes:
    """The extraction tab exports without running any normalization."""
    with tempfile.TemporaryDirectory(prefix="engine_export_") as folder:
        path = export_batch_excel(results, Path(folder) / "original.xlsx")
        return path.read_bytes()
