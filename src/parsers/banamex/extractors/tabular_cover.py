"""Portada MiCuenta con tabla Producto/Servicio y resumen del periodo."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date

from cep.catalog import valid_clabe
from models.datos_cuenta import DatosCuenta
from models.movimiento import Movimiento
from models.otros_productos import OtrosProductos
from models.resumen_financiero import ResumenFinanciero
from validators.resultado_validacion import ResultadoValidacion

from .anchored_header import MONTHS, NATURAL_DATE
from .movimientos import group_words_into_lines, line_text, normalize_upper, word_center_x


MONTH_ABBREVIATIONS = {key[:3]: month for key, month in MONTHS.items()}
SHORT_DATE = r"(\d{1,2})\s*/\s*([A-Z0-9 ]{3,5})\s*/\s*(\d{4})"
PERIOD = re.compile(rf"RESUMEN\s+DEL\s+{SHORT_DATE}\s+AL\s+{SHORT_DATE}")
MONEY = re.compile(
    r"(?<![\d.,])(?:\$\s*)?(\d{1,3}(?:\s*[, .]\s*\d{3})+|\d+)\s*[.,]\s*(\d{2})(?!\d)"
)
RFC = re.compile(r"\b([A-ZÑ&]{3,4})\s*(\d{6})\s*([A-Z0-9]{3})\b")
PRODUCT_HEADER = re.compile(r"PRODUCTO\s*/?\s*SERVICIO\s+.*?CONTRATO\s+.*?SALDO\s+ANTERIOR")
ACCESS_HEADER = re.compile(r"RESUMEN\s+POR\s+MEDI[OQ]S\s+DE\s+ACCESO")


def _text(line: list[dict]) -> str:
    return normalize_upper(line_text(line))


def _amounts(text: str) -> list[float]:
    return [float(re.sub(r"\D", "", m[1]) + "." + m[2]) for m in MONEY.finditer(text)]


def _short_date(day: str, month: str, year: str) -> str | None:
    month = month.replace(" ", "").replace("0", "O")
    month = MONTH_ABBREVIATIONS.get(month, MONTH_ABBREVIATIONS.get(re.sub(r"O+", "O", month)))
    if month is not None:
        try:
            return date(int(year), month, int(day)).strftime("%d/%m/%Y")
        except ValueError:
            pass
    return None


class TabularSummary(ResumenFinanciero):
    validar_sin_movimientos = True
    deposit_count: int | None = None
    withdrawal_count: int | None = None

    def validar_componentes(self, movimientos: list[Movimiento]) -> list[ResultadoValidacion]:
        def check(name: str, expected: int, actual: int, detail: str) -> ResultadoValidacion:
            return ResultadoValidacion(
                name, expected, actual, actual - expected, expected == actual, detail
            )

        results = []
        missing = sum(
            v is None
            for v in (
                self.saldo_anterior,
                self.saldo_final,
                self.retiros_cargos,
                self.depositos_abonos,
            )
        )
        if missing:
            results.append(
                check("Resumen MiCuenta", 0, missing, "Importes impresos pendientes de lectura")
            )
        for expected, name, field in (
            (self.deposit_count, "Depósitos impresos", "abono"),
            (self.withdrawal_count, "Retiros impresos", "cargo"),
        ):
            if expected is not None:
                results.append(
                    check(
                        name,
                        expected,
                        sum(bool(getattr(m, field)) for m in movimientos),
                        "Número de operaciones frente a la portada",
                    )
                )

        if movimientos and self.saldo_anterior is not None:
            previous = round(self.saldo_anterior * 100)
            mismatches = 0
            for movement in movimientos:
                printed = round(movement.saldo_operacion * 100)
                change = round(movement.abono * 100) - round(movement.cargo * 100)
                mismatches += previous + change != printed
                previous = printed
            results.append(
                check(
                    "Continuidad de saldos MiCuenta",
                    0,
                    mismatches,
                    "Renglones con diferencia entre importe y saldo impreso",
                )
            )
        return results


@dataclass(frozen=True, slots=True)
class TabularCover:
    lines: list[list[dict]]
    product_row: int
    period_row: int

    @classmethod
    def detect(cls, words: list[dict]) -> TabularCover | None:
        joined = normalize_upper(" ".join(str(w.get("text", "")) for w in words))
        if not all(label in joined for label in ("PRODUCTO", "CONTRATO", "CLABE")):
            return None
        lines = group_words_into_lines(words)
        texts = [_text(line) for line in lines]
        if not any("ESTADO DE CUENTA AL" in text for text in texts):
            return None
        # Estas dos tablas y la CLABE de Banamex identifican la portada aunque
        # el logotipo se lea como letras separadas o quede fuera del recorte.
        header = next((i for i, text in enumerate(texts) if PRODUCT_HEADER.search(text)), None)
        if header is None:
            return None
        product = next(
            (
                i
                for i in range(header + 1, min(header + 4, len(texts)))
                if re.search(r"\bMI\s*CUENTA\b", texts[i])
            ),
            None,
        )
        if product is None:
            return None
        following = " ".join(texts[product + 1 : product + 5])
        if not re.search(r"\bCLABE\s+INTERBANCARIA\s+002", following):
            return None
        period = next(
            (
                i
                for i in range(product + 1, min(product + 8, len(texts)))
                if re.search(r"\bRESUMEN\s+DEL\b", texts[i])
            ),
            None,
        )
        return cls(lines, product, period) if period is not None else None

    def period_dates(self) -> tuple[str | None, str | None]:
        match = PERIOD.search(
            " ".join(_text(line) for line in self.lines[self.period_row : self.period_row + 2])
        )
        if not match:
            return None, None
        return _short_date(*match.groups()[:3]), _short_date(*match.groups()[3:])

    def extract(self, words: list[dict]) -> tuple[DatosCuenta, ResumenFinanciero, OtrosProductos]:
        texts = [_text(line) for line in self.lines]
        end = next(
            (i for i in range(self.period_row + 1, len(texts)) if ACCESS_HEADER.search(texts[i])),
            len(texts),
        )
        product = texts[self.product_row]
        account = re.search(r"\b(\d{7,16})(?!\d|[.,]\d)", product)
        period_rows = texts[self.period_row : end]
        contract = next(
            (
                m[1]
                for text in period_rows
                if (m := re.match(r"^CONTRATO\s*:?\s*(\d{7,16})\b", text))
            ),
            None,
        )
        contract = contract or (account[1] if account else None)
        clabe = next(
            (
                m[1].replace(" ", "")
                for text in texts[self.product_row + 1 : self.period_row]
                if (m := re.search(r"CLABE\s+INTERBANCARIA\s+((?:\d\s*){18})(?!\s*\d)", text))
            ),
            None,
        )
        start, finish = self.period_dates()
        cutoff = None
        for text in [*texts[: self.product_row], *period_rows]:
            if "SALDO AL" in text or "ESTADO DE CUENTA AL" in text:
                m = NATURAL_DATE.search(text)
                if not m:
                    continue
                try:
                    cutoff = date(int(m[3]), MONTHS[m[2]], int(m[1])).strftime("%d/%m/%Y")
                except ValueError:
                    continue
                break

        rfc = None
        client = next(
            (
                m[1]
                for text in texts[: self.product_row]
                if (m := re.search(r"\bCLIENTE\s*:?\s*(\d{6,12})\b", text))
            ),
            None,
        )
        for i, text in enumerate(texts[: self.product_row]):
            if re.search(r"REGISTRO\s+FEDERAL\s+DE\s+CONTRIBUYENTES|\bR\.?F\.?C\.?\b", text):
                if match := RFC.search(text):
                    rfc = "".join(match.groups())
                # El número de cliente está en el renglón anterior de este
                # mismo recuadro, incluso cuando el OCR pierde su etiqueta.
                rfc_x = max(word_center_x(w) for w in self.lines[i])
                for line in reversed(self.lines[max(0, i - 3) : i]) if client is None else ():
                    candidates = [
                        str(w["text"])
                        for w in line
                        if word_center_x(w) >= rfc_x * 0.78
                        and re.fullmatch(r"\d{6,12}", str(w["text"]))
                    ]
                    if len(candidates) == 1:
                        client = candidates[0]
                        break
                break

        # El cliente se vuelve a imprimir encima de cada página de detalle.
        # Una lectura repetida permite descartar un carácter mal leído en la
        # portada. Se conserva el de portada si hay empate o falta el dato.
        if any(int(word.get("page") or 1) != 1 for word in words):
            top = max(float(w["bottom"]) for line in self.lines[:4] for w in line)
            counts = Counter(
                m[1]
                for line in group_words_into_lines(
                    [
                        w
                        for w in words
                        if int(w.get("page") or 1) != 1 and float(w["top"]) < top * 1.55
                    ]
                )
                if (m := re.search(r"\bCLIENTE\s*:?\s*(\d{6,12})\b", _text(line)))
            )
            most_common = counts.most_common(2)
            if most_common and (
                not client
                or (
                    most_common[0][1] >= 2
                    and (len(most_common) == 1 or most_common[0][1] > most_common[1][1])
                )
            ):
                client = most_common[0][0]

        name = self._client_name()
        data = DatosCuenta(
            producto_principal="MiCuenta",
            periodo_inicio=start,
            periodo_fin=finish,
            fecha_corte=cutoff,
            numero_cuenta=contract,
            numero_cliente=client,
            clabe=clabe if valid_clabe(clabe) else None,
            nombre_cliente=name,
            rfc=rfc,
        )

        def value(label: str, rows: list[str] = period_rows) -> float | None:
            for row in rows:
                if match := re.search(label, row):
                    amounts = _amounts(row[match.end() :])
                    if len(amounts) == 1:
                        return amounts[0]
            return None

        balances = _amounts(product)
        opening = value(r"\bSALDO\s+ANTERIOR\b")
        closing = value(r"\bSALDO\s+AL\b")
        if len(balances) == 2:
            opening = balances[0] if opening is None else opening
            closing = balances[1] if closing is None else closing
        days = next(
            (
                int(m[1])
                for text in period_rows
                if (m := re.search(r"DIAS\s+TRANSCURRIDOS[\s|:]+(\d{1,3})\b", text))
            ),
            None,
        )
        fees = value(r"\bC?OMISIONES\s+EFECTIVAMENTE\s+COBRADAS\b", texts[: self.product_row])
        summary = TabularSummary(
            saldo_promedio=value(r"\bSALDO\s+PROMEDIO\b"),
            dias_periodo=days,
            tasa_bruta_anual=None,
            saldo_promedio_gravable=None,
            intereses_a_favor=value(
                r"\bINTERES\s+APLICABLE\s+O\s+RENDIMIENTOS\b", texts[: self.product_row]
            ),
            isr_retenido=None,
            cheques_pagados=None,
            manejo_cuenta=fees,
            cargos_objetados=None,
            abonos_objetados=None,
            saldo_anterior=opening,
            depositos_abonos=value(r"\bDEP[OA]+S[IÍ]TOS\b"),
            retiros_cargos=value(r"\bRETIROS\b"),
            saldo_final=closing,
            saldo_promedio_minimo_mensual=None,
            saldo_global=closing,
        )
        for field, label in (
            ("deposit_count", r"DEP[OA]+S[IÍ]TOS"),
            ("withdrawal_count", "RETIROS"),
        ):
            match = re.search(rf"(?<![.,\d])(\d{{1,4}})\s+{label}\b", "\n".join(period_rows))
            if match:
                setattr(summary, field, int(match[1]))
        from .productos import extract_otros_productos_words

        products = extract_otros_productos_words([w for line in self.lines for w in line])
        return data, summary, products

    def _client_name(self) -> str | None:
        # El titular y el domicilio empiezan en la misma guía izquierda. La
        # sucursal tiene su propio bloque y un renglón con código postal.
        previous: list[dict] = []
        for line in self.lines[: self.product_row]:
            text = _text(line)
            address = re.match(r"^\d{1,3}\s+\D+\s+\d+\b", text)
            if address and previous:
                left = float(line[0]["x0"])
                tokens = [
                    str(w["text"])
                    for w in previous
                    if float(w["x0"]) >= left - 4 and word_center_x(w) < left * 3.4
                ]
                candidate = " ".join(tokens).strip()
                if len(tokens) >= 2 and re.fullmatch(r"[A-ZÁÉÍÓÚÜÑ .'-]+", candidate.upper()):
                    return candidate
            previous = line
        return None
