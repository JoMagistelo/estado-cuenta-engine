"""Perfiles de tabla extensibles; las posiciones se descubren en cada página."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .extractors.common import Line, center_x, normalized


@dataclass(frozen=True)
class SantanderLayout:
    name: str
    date_labels: tuple[str, ...] = ("FECHA",)
    reference_labels: tuple[str, ...] = ("FOLIO", "REFERENCIA")
    description_labels: tuple[str, ...] = ("DESCRIPCION", "CONCEPTO")
    deposit_labels: tuple[str, ...] = ("DEPOSITO", "DEPOSITOS", "ABONO", "ABONOS")
    withdrawal_labels: tuple[str, ...] = ("RETIRO", "RETIROS", "CARGO", "CARGOS")
    balance_labels: tuple[str, ...] = ("SALDO",)

    def columns(self, line: Line) -> Columns | None:
        labels = {
            "fecha": self.date_labels,
            "folio": self.reference_labels,
            "concepto": self.description_labels,
            "abono": self.deposit_labels,
            "cargo": self.withdrawal_labels,
            "saldo": self.balance_labels,
        }
        anchors = {}
        for field, aliases in labels.items():
            word = next(
                (w for w in line.words if normalized(str(w["text"])).strip(".: ") in aliases),
                None,
            )
            if word is not None:
                anchors[field] = word
        if not {"fecha", "concepto", "abono", "cargo"}.issubset(anchors):
            return None
        first_money = min(
            float(anchors[k]["x0"]) for k in ("abono", "cargo", "saldo") if k in anchors
        )
        if not float(anchors["fecha"]["x0"]) < float(anchors["concepto"]["x0"]) < first_money:
            return None
        previous = anchors.get("folio", anchors["fecha"])
        concept_left = (float(previous["x0"]) + float(anchors["concepto"]["x0"])) / 2
        height = float(anchors["concepto"].get("bottom", line.y)) - float(
            anchors["concepto"]["top"]
        )
        return Columns(
            concept_left=concept_left,
            money_left=first_money - max(height, 0) * 0.8,
            centers={k: center_x(anchors[k]) for k in ("abono", "cargo", "saldo") if k in anchors},
        )


@dataclass(frozen=True)
class Columns:
    concept_left: float
    money_left: float
    centers: dict[str, float]

    def amount_cells(self, line: Line) -> dict[str, str]:
        cells: dict[str, list[str]] = {}
        for word in line.words:
            if float(word["x0"]) < self.money_left:
                continue
            key = min(self.centers, key=lambda k: abs(self.centers[k] - center_x(word)))
            cells.setdefault(key, []).append(str(word["text"]))
        return {key: " ".join(value) for key, value in cells.items()}

    def concept(self, line: Line) -> str:
        return " ".join(
            str(w["text"])
            for w in line.words
            if self.concept_left <= float(w["x0"]) < self.money_left
        ).strip()


# Añadir perfiles aquí cuando cambie la estructura, manteniendo los extractores
# semánticos y las pruebas comunes de digital/OCR.
LAYOUTS = (SantanderLayout("cuenta_cheques"),)


def detect_columns(line: Line) -> Columns | None:
    return next((cols for layout in LAYOUTS if (cols := layout.columns(line))), None)


def is_section_end(text: str) -> bool:
    return bool(
        re.match(
            r"^(?:TOTAL\b|SALDO FINAL\b|GLOSARIO\b|COMPROBANTE\b|"
            r"DETALLE DE MOVIMIENTOS (?:INVERSION|CREDITO)|MENSAJES IMPORTANTES\b)",
            normalized(text),
        )
    )
