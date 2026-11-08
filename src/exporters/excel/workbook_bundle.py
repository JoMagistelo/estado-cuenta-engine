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


def verify_pair(original: bytes, improved: bytes) -> int:
    """Reopen both serialized files and check row identity, money and date types."""
    raw = load_workbook(BytesIO(original), data_only=False)
    clean = load_workbook(BytesIO(improved), data_only=False)
    try:
        a, b = rows_from_sheet(raw["Movimientos"]), rows_from_sheet(clean["Movimientos"])
        if len(a) != len(b):
            raise ValueError("La comprobación del Excel detectó un cambio en el número de movimientos")
        for left, right in zip(a, b):
            allowed = {"Fecha de Operación", "Fecha de Liquidación", "Fecha de Corte", "Número de Cuenta",
                       "Referencia", "Clave de Rastreo", "Cuenta del Beneficiario", "CLABE del Beneficiario",
                       "Cuenta del Ordenante", "CLABE del Ordenante", "Sucursal", "Cuenta Titular", "CLABE Titular",
                       "Estado de Fecha", "Revisión Normalización", "Origen Datos Titular", "Banco del Beneficiario",
                       "Código Banco Beneficiario", "Código Plaza/Producto CLABE"}
            for name in left:
                if name in allowed or name == '_row':
                    continue
                if get(left, name) != get(right, name):
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

    @classmethod
    def from_excel(cls, source: str | Path | bytes, *, source_name="reporte_estados_de_cuenta.xlsx"):
        original = source if isinstance(source, bytes) else Path(source).read_bytes()
        with tempfile.TemporaryDirectory(prefix="engine_excel_") as folder:
            improved_path = Path(folder) / "mejorado.xlsx"
            report = normalize_workbook(original, improved_path)
            improved = improved_path.read_bytes()
        verify_pair(original, improved)
        return cls(original, improved, report, source_name)

    @classmethod
    def from_results(cls, results):
        with tempfile.TemporaryDirectory(prefix="engine_export_") as folder:
            path = export_batch_excel(results, Path(folder) / "original.xlsx")
            return cls.from_excel(path)

    def content(self, variant: str):
        if variant not in {"original", "mejorado"}:
            raise ValueError("Elige original o mejorado")
        return self.original if variant == "original" else self.improved
