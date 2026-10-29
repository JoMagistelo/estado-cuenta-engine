"""Separación y conciliación de periodos consecutivos de una misma cuenta."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal

from models.estado_cuenta import EstadoCuenta
from models.resumen_financiero import ResumenFinanciero
from validators.resultado_validacion import ResultadoValidacion


def split_word_periods(
    words: list[dict], is_cover: Callable[[list[dict]], bool]
) -> list[list[dict]]:
    pages: dict[int, list[dict]] = {}
    for word in words:
        pages.setdefault(int(word.get("page") or 1), []).append(word)
    if not pages:
        return [words]
    starts = sorted({min(pages)} | {p for p, items in pages.items() if is_cover(items)})
    if len(starts) == 1:
        return [words]
    result = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else max(pages) + 1
        offset = min(float(w.get("doctop", w["top"])) - float(w["top"]) for w in pages[start])
        result.append(
            [
                {
                    **w,
                    "page": p - start + 1,
                    **({"doctop": float(w["doctop"]) - offset} if "doctop" in w else {}),
                }
                for p in sorted(pages)
                if start <= p < end
                for w in pages[p]
            ]
        )
    return result


def _day(value: str | None):
    try:
        return datetime.strptime(value or "", "%d/%m/%Y").date()
    except ValueError:
        return None


@dataclass
class PeriodSummary(ResumenFinanciero):
    # Se conservan los resúmenes impresos para comprobar cada periodo además
    # del consolidado; los exportadores mantienen sus columnas habituales.
    periods: list[EstadoCuenta] = field(default_factory=list, repr=False)
    validar_sin_movimientos = True

    def validar_componentes(self, movimientos) -> list[ResultadoValidacion]:
        from validators.movimiento_validator import validar_movimientos

        checks = []
        for i, part in enumerate(self.periods, 1):
            missing = [
                name
                for name in ("saldo_anterior", "depositos_abonos", "retiros_cargos", "saldo_final")
                if getattr(part.resumen_financiero, name) is None
            ]
            if missing:
                checks.append(
                    ResultadoValidacion(
                        nombre=f"Periodo {i}: resumen incompleto",
                        esperado=None,
                        obtenido=None,
                        diferencia=None,
                        correcto=False,
                        mensaje="Faltan importes impresos para conciliar el periodo",
                    )
                )
            for check in validar_movimientos(part.movimientos, part.resumen_financiero):
                checks.append(replace(check, nombre=f"Periodo {i}: {check.nombre}"))
            if i == 1:
                continue
            previous = self.periods[i - 2]
            closing = previous.resumen_financiero.saldo_final
            opening = part.resumen_financiero.saldo_anterior
            difference = opening - closing if opening is not None and closing is not None else None
            checks.append(
                ResultadoValidacion(
                    nombre=f"Periodo {i}: continuidad de saldos",
                    esperado=closing,
                    obtenido=opening,
                    diferencia=difference,
                    correcto=difference is not None and abs(difference) <= 0.01,
                    mensaje="El saldo inicial debe coincidir con el cierre del periodo anterior",
                )
            )
            end = _day(previous.datos_cuenta.periodo_fin)
            start = _day(part.datos_cuenta.periodo_inicio)
            checks.append(
                ResultadoValidacion(
                    nombre=f"Periodo {i}: continuidad de fechas",
                    esperado=None,
                    obtenido=None,
                    diferencia=None,
                    correcto=end is not None and start == end + timedelta(days=1),
                    mensaje="Los periodos deben ser consecutivos, sin duplicados, solapamientos ni huecos",
                )
            )
        return checks


def combine_periods(parts: list[EstadoCuenta]) -> EstadoCuenta:
    if not parts:
        raise ValueError("No hay periodos para consolidar")
    if len(parts) == 1:
        return parts[0]
    accounts = {re.sub(r"\D", "", p.datos_cuenta.numero_cuenta or "") for p in parts}
    if len(accounts) != 1 or not next(iter(accounts)):
        raise ValueError("No se pueden consolidar periodos sin una misma cuenta identificada")
    first, last = parts[0], parts[-1]
    data = replace(
        first.datos_cuenta,
        periodo_fin=last.datos_cuenta.periodo_fin,
        fecha_corte=last.datos_cuenta.fecha_corte,
    )
    for name in ("nombre_cliente", "numero_cliente", "clabe", "rfc"):
        values = [getattr(p.datos_cuenta, name) for p in parts if getattr(p.datos_cuenta, name)]
        if not getattr(data, name) and values:
            setattr(data, name, values[0])
    values = asdict(first.resumen_financiero)

    def total(name):
        amounts = [getattr(p.resumen_financiero, name) for p in parts]
        return (
            float(sum(Decimal(str(v)) for v in amounts))
            if all(v is not None for v in amounts)
            else None
        )

    for name in (
        "depositos_abonos",
        "retiros_cargos",
        "intereses_a_favor",
        "isr_retenido",
        "manejo_cuenta",
        "cargos_objetados",
        "abonos_objetados",
        "cheques_pagados",
    ):
        values[name] = total(name)
    if values["cheques_pagados"] is not None:
        values["cheques_pagados"] = int(values["cheques_pagados"])
    days = [p.resumen_financiero.dias_periodo for p in parts]
    values["dias_periodo"] = sum(days) if all(isinstance(d, int) and d > 0 for d in days) else None
    for name in ("saldo_promedio", "saldo_promedio_gravable"):
        amounts = [getattr(p.resumen_financiero, name) for p in parts]
        values[name] = (
            round(float(sum(Decimal(str(v)) * d for v, d in zip(amounts, days)) / sum(days)), 2)
            if values["dias_periodo"] and all(v is not None for v in amounts)
            else None
        )
    for name in ("tasa_bruta_anual", "saldo_promedio_minimo_mensual"):
        amounts = [getattr(p.resumen_financiero, name) for p in parts]
        values[name] = amounts[0] if all(v == amounts[0] for v in amounts) else None
    values.update(
        saldo_final=last.resumen_financiero.saldo_final,
        saldo_global=last.resumen_financiero.saldo_global,
    )
    return EstadoCuenta(
        datos_cuenta=data,
        otros_productos=first.otros_productos,
        resumen_financiero=PeriodSummary(**values, periods=parts),
        movimientos=[m for p in parts for m in p.movimientos],
    )
