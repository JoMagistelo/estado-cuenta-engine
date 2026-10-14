from __future__ import annotations

import re

from models.resumen_financiero import ResumenFinanciero

from .common import Line, amount_after_label, center_x, group_lines, money, normalized
from .datos import account_heading


def extract_resumen_financiero_lines(lines: list[Line]) -> ResumenFinanciero:
    header = [line for line in lines if line.page == 1]
    heading = account_heading(header)
    section = []
    if heading:
        for line in header[header.index(heading) + 1 :]:
            if re.search(r"GRAFICO|CUENTA\s+CLABE", normalized(line.text)):
                break
            section.append(line)

    def value(pattern: str) -> float | None:
        return next(
            (v for line in section if (v := amount_after_label(line, pattern)) is not None), None
        )

    days, rate = 0, 0.0
    for line in section:
        match = re.search(r"DIAS DEL PERIODO\s+(\d+)\b", normalized(line.text))
        if match:
            days = int(match[1])
        match = re.search(r"TASA BRUTA DE INTERES ANUAL\s+([\d.]+)\s*%", normalized(line.text))
        if match:
            rate = float(match[1])

    # Alineación del resumen informativo, no la tasa de ISR entre paréntesis.
    earnings: dict[str, float] = {}
    columns = None
    for line in header:
        upper = normalized(line.text)
        if "INTERESES BRUTOS" in upper and "ISR RETENIDO" in upper:
            centers = []
            for phrase in (
                "INTERESES BRUTOS",
                "ISR RETENIDO",
                "INTERESES NETOS",
                "COMISIONES COBRADAS",
            ):
                tokens = phrase.split()
                for i, word in enumerate(line.words):
                    if (
                        normalized(str(word["text"])) == tokens[0]
                        and i + 1 < len(line.words)
                        and normalized(str(line.words[i + 1]["text"])) == tokens[1]
                    ):
                        centers.append(
                            (phrase, (float(word["x0"]) + float(line.words[i + 1]["x1"])) / 2)
                        )
            columns = dict(centers)
            continue
        if columns and heading:
            account = re.search(r"\d{2}-\d{8}-\d", heading.text)
            if account and account[0] in line.text:
                for w in line.words:
                    amount = money(str(w["text"]))
                    if amount is not None:
                        key = min(columns, key=lambda k: abs(columns[k] - center_x(w)))
                        earnings[key] = amount
                break
    final = value(r"\bSALDO FINAL\b")
    return ResumenFinanciero(
        saldo_promedio=value(r"\bSALDO PROMEDIO(?!\s+MINIMO)\b"),
        dias_periodo=days,
        tasa_bruta_anual=rate,
        saldo_promedio_gravable=0.0,
        intereses_a_favor=earnings.get("INTERESES BRUTOS"),
        isr_retenido=earnings.get("ISR RETENIDO"),
        cheques_pagados=0,
        manejo_cuenta=earnings.get("COMISIONES COBRADAS"),
        cargos_objetados=0.0,
        abonos_objetados=0.0,
        saldo_anterior=value(r"\bSALDO INICIAL\b"),
        depositos_abonos=value(r"\bDEPOSITOS\b"),
        retiros_cargos=value(r"\bRETIROS\b"),
        saldo_final=final,
        saldo_promedio_minimo_mensual=value(r"\bSALDO PROMEDIO MINIMO\b"),
        saldo_global=final,
    )


def extract_resumen_financiero_words(words: list[dict]) -> ResumenFinanciero:
    return extract_resumen_financiero_lines(group_lines(words))
