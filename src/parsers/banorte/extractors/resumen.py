from __future__ import annotations

import re

from typing import Any, Dict, List, Optional

from models.resumen_financiero import ResumenFinanciero


# ============================================================
# CONFIGURACIÓN ESPACIAL — BANORTE RESUMEN FINANCIERO
# ============================================================
#
# Este extractor trabaja principalmente mediante coordenadas.
#
# El encabezado del producto NO tiene nombre fijo.
#
# Ejemplos:
#
#     DETALLE NÓMINA BANORTE S/CH ▼
#     DETALLE ENLACE NEGOCIOS BASICA ▼
#     ...
#
# Lo estable es su posición espacial.
#
# ============================================================


# ------------------------------------------------------------
# ENCABEZADO DEL PRODUCTO
# ------------------------------------------------------------

PRODUCT_HEADER_TOP_MIN = 240.0
PRODUCT_HEADER_TOP_MAX = 252.0


# ------------------------------------------------------------
# INICIO DEL RESUMEN
# ------------------------------------------------------------

RESUMEN_TOP_MIN = 258.0


# ------------------------------------------------------------
# COLUMNA DE IMPORTES
# ------------------------------------------------------------

AMOUNT_X1_MIN = 252.0
AMOUNT_X1_MAX = 262.0


# ------------------------------------------------------------
# TOLERANCIAS
# ------------------------------------------------------------

LINE_Y_TOLERANCE = 3.5
FIELD_Y_TOLERANCE = 4.0


# ============================================================
# UTILIDADES BÁSICAS
# ============================================================

def normalize_text(
    value: Any,
) -> str:
    if value is None:
        return ""

    value = str(value)

    value = (
        value
        .replace("\xa0", " ")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def normalize_upper(
    value: Any,
) -> str:
    return normalize_text(value).upper()


def word_top(
    word: Dict[str, Any],
) -> float:
    try:
        return float(
            word.get("top", 0) or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def word_bottom(
    word: Dict[str, Any],
) -> float:
    try:
        return float(
            word.get(
                "bottom",
                word.get("top", 0),
            )
            or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def word_center_y(
    word: Dict[str, Any],
) -> float:
    return (
        word_top(word)
        + word_bottom(word)
    ) / 2.0


def word_x0(
    word: Dict[str, Any],
) -> float:
    try:
        return float(
            word.get(
                "x0",
                0,
            )
            or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def word_x1(
    word: Dict[str, Any],
) -> float:
    try:
        return float(
            word.get(
                "x1",
                word.get("x0", 0),
            )
            or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def word_page(
    word: Dict[str, Any],
) -> int:
    try:
        return int(
            word.get(
                "page",
                1,
            )
            or 1
        )
    except (
        TypeError,
        ValueError,
    ):
        return 1


# ============================================================
# AGRUPACIÓN DE LÍNEAS
# ============================================================

def group_words_into_lines(
    words: List[Dict[str, Any]],
    tolerance: float = LINE_Y_TOLERANCE,
) -> List[List[Dict[str, Any]]]:

    if not words:
        return []

    ordered = sorted(
        words,
        key=lambda word: (
            word_page(word),
            word_center_y(word),
            word_x0(word),
        ),
    )

    lines: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []

    current_page: Optional[int] = None
    current_y: Optional[float] = None

    for word in ordered:

        page = word_page(word)
        y = word_center_y(word)

        if current_y is None:
            current = [word]
            current_page = page
            current_y = y
            continue

        same_line = (
            page == current_page
            and abs(y - current_y) <= tolerance
        )

        if same_line:
            current.append(word)

            current_y = (
                sum(
                    word_center_y(item)
                    for item in current
                )
                / len(current)
            )

        else:
            current.sort(
                key=word_x0
            )

            lines.append(current)

            current = [word]
            current_page = page
            current_y = y

    if current:
        current.sort(
            key=word_x0
        )

        lines.append(current)

    return lines


# ============================================================
# TEXTO DE LÍNEA
# ============================================================

def line_text(
    line: List[Dict[str, Any]],
) -> str:

    values: List[str] = []

    for word in sorted(
        line,
        key=word_x0,
    ):

        text = normalize_text(
            word.get(
                "text",
                "",
            )
        )

        if text:
            values.append(text)

    return " ".join(values).strip()


def line_top(
    line: List[Dict[str, Any]],
) -> float:

    if not line:
        return 0.0

    return min(
        word_top(word)
        for word in line
    )


def line_bottom(
    line: List[Dict[str, Any]],
) -> float:

    if not line:
        return 0.0

    return max(
        word_bottom(word)
        for word in line
    )


def line_page(
    line: List[Dict[str, Any]],
) -> int:

    if not line:
        return 1

    return word_page(line[0])


# ============================================================
# DETECCIÓN DEL ENCABEZADO DEL PRODUCTO
# ============================================================
#
# NO dependemos del nombre:
#
#     DETALLE NÓMINA BANORTE S/CH
#     DETALLE ENLACE NEGOCIOS BASICA
#
# El elemento realmente estable es la banda Y y la presencia
# de la flecha "▼" que forma parte del selector del producto.
#
# ============================================================

def is_product_header_line(
    line: List[Dict[str, Any]],
) -> bool:

    if not line:
        return False

    if line_page(line) != 1:
        return False

    top = line_top(line)
    bottom = line_bottom(line)

    if not (
        PRODUCT_HEADER_TOP_MIN
        <= top
        <= PRODUCT_HEADER_TOP_MAX
    ):
        return False

    if bottom > 258.0:
        return False

    text = normalize_upper(
        line_text(line)
    )

    has_arrow = any(
        normalize_text(
            word.get("text", "")
        ) == "▼"
        for word in line
    )

    # La flecha es la señal espacial/textual más estable.
    if has_arrow:
        return True

    # Fallback para PDFs donde la flecha no sea extraída.
    if "DETALLE" in text:
        return True

    # Último fallback: la banda espacial.
    return True


def find_product_header(
    lines: List[List[Dict[str, Any]]],
) -> Optional[int]:

    for index, line in enumerate(lines):

        if is_product_header_line(line):
            return index

    return None


# ============================================================
# DETECCIÓN DEL RESUMEN DEL PERIODO
# ============================================================

def find_resumen_start(
    lines: List[List[Dict[str, Any]]],
    header_index: Optional[int],
) -> Optional[int]:

    if header_index is None:
        return None

    for index in range(
        header_index + 1,
        len(lines),
    ):

        line = lines[index]

        if not line:
            continue

        if line_page(line) != 1:
            continue

        top = line_top(line)

        if top < RESUMEN_TOP_MIN:
            continue

        text = normalize_upper(
            line_text(line)
        )

        if (
            "RESUMEN" in text
            and "PERIODO" in text
        ):
            return index

    return None


# ============================================================
# DINÁMICA DE IMPORTES
# ============================================================

MONEY_PATTERN = re.compile(
    r"""
    ^
    (?:
        \$?
        \d{1,3}
        (?:,\d{3})*
        (?:\.\d{2})?
        -
        |
        -
        \$?
        \d{1,3}
        (?:,\d{3})*
        (?:\.\d{2})?
        |
        \$?
        \d{1,3}
        (?:,\d{3})*
        (?:\.\d{2})?
    )
    $
    """,
    re.VERBOSE,
)


def is_money(
    text: str,
) -> bool:

    return bool(
        MONEY_PATTERN.fullmatch(
            normalize_text(text)
        )
    )


def parse_amount(
    text: str,
) -> float:

    value = normalize_text(text)

    if not value:
        return 0.0

    value = (
        value
        .replace("$", "")
        .replace(",", "")
        .strip()
    )

    negative = False

    if value.endswith("-"):
        negative = True
        value = value[:-1].strip()

    if (
        value.startswith("(")
        and value.endswith(")")
    ):
        negative = True
        value = value[1:-1].strip()

    try:
        amount = float(value)
    except (
        ValueError,
        TypeError,
    ):
        return 0.0

    if negative:
        amount = -amount

    return amount


# ============================================================
# EXTRACCIÓN DE IMPORTE DE UNA LÍNEA
# ============================================================

def extract_amount_from_line(
    line: List[Dict[str, Any]],
) -> Optional[float]:

    candidates: List[Dict[str, Any]] = []

    for word in line:

        text = normalize_text(
            word.get(
                "text",
                "",
            )
        )

        if not is_money(text):
            continue

        x1 = word_x1(word)

        if not (
            AMOUNT_X1_MIN
            <= x1
            <= AMOUNT_X1_MAX
        ):
            continue

        candidates.append(word)

    if not candidates:
        return None

    candidates.sort(
        key=word_x1
    )

    return parse_amount(
        candidates[-1].get(
            "text",
            "",
        )
    )


# ============================================================
# SIGNO DEL RENGLÓN
# ============================================================

def get_line_sign(
    line: List[Dict[str, Any]],
) -> int:

    for word in sorted(
        line,
        key=word_x0,
    ):

        text = normalize_text(
            word.get(
                "text",
                "",
            )
        )

        if text == "+":
            return 1

        if text == "-":
            return -1

        if text.startswith("+"):
            return 1

        if text.startswith("-"):
            return -1

    return 0


def distribute_signed_amount(
    line: List[Dict[str, Any]],
    amount: Optional[float],
) -> tuple[float, float]:

    if amount is None:
        return 0.0, 0.0

    sign = get_line_sign(line)

    if sign > 0:
        return amount, 0.0

    if sign < 0:
        return 0.0, amount

    return 0.0, 0.0


# ============================================================
# LOCALIZAR LÍNEA POR TEXTO EXACTO / PARCIAL
# ============================================================

def line_contains_all(
    line: List[Dict[str, Any]],
    patterns: tuple[str, ...],
) -> bool:

    text = normalize_upper(
        line_text(line)
    )

    return all(
        pattern in text
        for pattern in patterns
    )


def find_line_by_patterns(
    lines: List[List[Dict[str, Any]]],
    patterns: tuple[tuple[str, ...], ...],
    start_index: int,
    end_index: int,
) -> Optional[int]:

    for index in range(
        start_index,
        end_index,
    ):

        line = lines[index]

        for pattern_group in patterns:

            if line_contains_all(
                line,
                pattern_group,
            ):
                return index

    return None


# ============================================================
# BUSCAR IMPORTE EN LA MISMA LÍNEA
# ============================================================

def extract_same_line_amount(
    lines: List[List[Dict[str, Any]]],
    line_index: int,
) -> Optional[float]:

    if not (
        0 <= line_index < len(lines)
    ):
        return None

    return extract_amount_from_line(
        lines[line_index]
    )


# ============================================================
# BUSCAR IMPORTE EN LÍNEAS POSTERIORES
# ============================================================
#
# Útil para:
#
#     SALDO PROMEDIO
#
# donde la etiqueta no comparte línea con el importe.
#
# ============================================================

def find_next_amount(
    lines: List[List[Dict[str, Any]]],
    start_index: int,
    end_index: int,
    max_lines: int = 4,
) -> Optional[float]:

    last_index = min(
        end_index,
        start_index + max_lines + 1,
    )

    for index in range(
        start_index + 1,
        last_index,
    ):

        amount = extract_amount_from_line(
            lines[index]
        )

        if amount is not None:
            return amount

    return None


# ============================================================
# CAMPO NORMAL
# ============================================================

def extract_field_same_line(
    lines: List[List[Dict[str, Any]]],
    patterns: tuple[tuple[str, ...], ...],
    start_index: int,
    end_index: int,
) -> Optional[float]:

    line_index = find_line_by_patterns(
        lines,
        patterns,
        start_index,
        end_index,
    )

    if line_index is None:
        return None

    return extract_same_line_amount(
        lines,
        line_index,
    )


# ============================================================
# SALDO PROMEDIO
# ============================================================
#
# IMPORTANTE:
#
# No buscamos solamente:
#
#     SALDO PROMEDIO
#
# porque eso también coincide con:
#
#     SALDO PROMEDIO MÍNIMO
#
# La estructura observada es:
#
#     Saldo
#     Promedio
#
#     Saldo promedio mínimo       $ 0.00
#
#     En el Periodo 01 Jun al 30 Jun:     $ 590.36
#
# Por ello tomamos el primer bloque "SALDO PROMEDIO" que NO
# contenga "MÍNIMO", y buscamos posteriormente el importe.
#
# ============================================================

def extract_saldo_promedio(
    lines: List[List[Dict[str, Any]]],
    start_index: int,
    end_index: int,
) -> Optional[float]:

    for index in range(
        start_index,
        end_index,
    ):

        text = normalize_upper(
            line_text(lines[index])
        )

        if "SALDO" not in text:
            continue

        if "PROMEDIO" not in text:
            continue

        if "MÍNIMO" in text:
            continue

        # Primero intentamos la misma línea.
        amount = extract_same_line_amount(
            lines,
            index,
        )

        if amount is not None:
            return amount

        # En el layout actual el importe aparece después.
        #
        # Buscamos hasta encontrar:
        #
        #   En el Periodo ...
        #

        for next_index in range(
            index + 1,
            min(
                end_index,
                index + 6,
            ),
        ):

            next_text = normalize_upper(
                line_text(
                    lines[next_index]
                )
            )

            amount = extract_same_line_amount(
                lines,
                next_index,
            )

            if amount is not None:

                # No tomar el importe del saldo promedio
                # mínimo.
                if (
                    "SALDO PROMEDIO"
                    in next_text
                    and
                    "MÍNIMO"
                    in next_text
                ):
                    continue

                return amount

    return None


# ============================================================
# SALDO PROMEDIO MÍNIMO
# ============================================================

def extract_saldo_promedio_minimo(
    lines: List[List[Dict[str, Any]]],
    start_index: int,
    end_index: int,
) -> Optional[float]:

    return extract_field_same_line(
        lines,
        (
            (
                "SALDO",
                "PROMEDIO",
                "MÍNIMO",
            ),
            (
                "SALDO",
                "PROMEDIO",
                "MINIMO",
            ),
        ),
        start_index,
        end_index,
    )


# ============================================================
# DÍAS DEL PERIODO
# ============================================================

def extract_days(
    lines: List[List[Dict[str, Any]]],
    start_index: int,
    end_index: int,
) -> Optional[int]:

    for index in range(
        start_index,
        end_index,
    ):

        text = normalize_upper(
            line_text(lines[index])
        )

        if "DÍAS" not in text:
            continue

        for word in lines[index]:

            value = normalize_text(
                word.get(
                    "text",
                    "",
                )
            )

            if value.isdigit():

                number = int(value)

                if 1 <= number <= 366:
                    return number

    return None


# ============================================================
# TASA BRUTA ANUAL
# ============================================================

def extract_tasa_bruta_anual(
    lines: List[List[Dict[str, Any]]],
    start_index: int,
    end_index: int,
) -> Optional[float]:

    pattern = re.compile(
        r"^\d+(?:\.\d+)?%$"
    )

    for index in range(
        start_index,
        end_index,
    ):

        text = normalize_upper(
            line_text(lines[index])
        )

        if not (
            "TASA" in text
            and "BRUTA" in text
            and "ANUAL" in text
        ):
            continue

        for word in lines[index]:

            value = normalize_text(
                word.get(
                    "text",
                    "",
                )
            )

            if pattern.fullmatch(value):

                try:
                    return float(
                        value.rstrip("%")
                    )

                except ValueError:
                    return None

    return None


# ============================================================
# LÍMITE DEL BLOQUE RESUMEN
# ============================================================

def find_resumen_end(
    lines: List[List[Dict[str, Any]]],
    start_index: int,
) -> int:

    for index in range(
        start_index + 1,
        len(lines),
    ):

        text = normalize_upper(
            line_text(lines[index])
        )

        if "TOTAL DE USOS" in text:
            return index + 1

    return len(lines)


# ============================================================
# EXTRACTOR PRINCIPAL
# ============================================================

def extract_resumen_financiero_words(
    words: List[Dict[str, Any]],
) -> ResumenFinanciero:

    if not words:
        return ResumenFinanciero()

    # --------------------------------------------------------
    # 1. SOLO PRIMERA PÁGINA
    # --------------------------------------------------------

    page_one_words = [
        word
        for word in words
        if word_page(word) == 1
    ]

    if not page_one_words:
        return ResumenFinanciero()

    # --------------------------------------------------------
    # 2. AGRUPAR LÍNEAS
    # --------------------------------------------------------

    lines = group_words_into_lines(
        page_one_words
    )

    if not lines:
        return ResumenFinanciero()

    # --------------------------------------------------------
    # 3. ENCABEZADO DEL PRODUCTO
    # --------------------------------------------------------

    header_index = find_product_header(
        lines
    )

    if header_index is None:
        return ResumenFinanciero()

    # --------------------------------------------------------
    # 4. INICIO DEL RESUMEN
    # --------------------------------------------------------

    resumen_start = find_resumen_start(
        lines,
        header_index,
    )

    if resumen_start is None:
        return ResumenFinanciero()

    # --------------------------------------------------------
    # 5. FIN DEL RESUMEN
    # --------------------------------------------------------

    resumen_end = find_resumen_end(
        lines,
        resumen_start,
    )

    # --------------------------------------------------------
    # 6. EXTRACCIÓN
    # --------------------------------------------------------

    saldo_anterior = extract_field_same_line(
        lines,
        (
            (
                "SALDO",
                "INICIAL",
                "DEL",
                "PERIODO",
            ),
        ),
        resumen_start,
        resumen_end,
    )

    # --------------------------------------------------------
    # TOTAL DE DEPÓSITOS — VALOR ORIGINAL
    # --------------------------------------------------------

    total_depositos = extract_field_same_line(
        lines,
        (
            (
                "TOTAL",
                "DE",
                "DEPÓSITOS",
            ),
            (
                "TOTAL",
                "DE",
                "DEPOSITOS",
            ),
        ),
        resumen_start,
        resumen_end,
    )

    # --------------------------------------------------------
    # TOTAL DE RETIROS — VALOR ORIGINAL
    # --------------------------------------------------------

    total_retiros = extract_field_same_line(
        lines,
        (
            (
                "TOTAL",
                "DE",
                "RETIROS",
            ),
        ),
        resumen_start,
        resumen_end,
    )

    # --------------------------------------------------------
    # INTERESES NETOS GANADOS
    # --------------------------------------------------------
    #
    # Este renglón está inmediatamente debajo de:
    #
    #     Total de retiros
    #
    # y su importe es el que corresponde a intereses_a_favor.
    #
    # --------------------------------------------------------

    intereses_a_favor = extract_field_same_line(
        lines,
        (
            (
                "INTERESES",
                "NETOS",
                "GANADOS",
            ),
        ),
        resumen_start,
        resumen_end,
    )

    # --------------------------------------------------------
    # TOTAL DE DEPÓSITOS — AJUSTADO
    # --------------------------------------------------------
    #
    # Al total de depósitos reportado por Banorte le restamos
    # los intereses netos ganados.
    #
    # --------------------------------------------------------

    depositos_abonos = total_depositos

    if depositos_abonos is not None:

        depositos_abonos += (
            intereses_a_favor
            if intereses_a_favor is not None
            else 0.0
        )

    # --------------------------------------------------------
    # SALDO PROMEDIO
    # --------------------------------------------------------

    saldo_promedio = extract_saldo_promedio(
        lines,
        resumen_start,
        resumen_end,
    )

    # --------------------------------------------------------
    # SALDO PROMEDIO MÍNIMO
    # --------------------------------------------------------

    saldo_promedio_minimo_mensual = (
        extract_saldo_promedio_minimo(
            lines,
            resumen_start,
            resumen_end,
        )
    )

    # --------------------------------------------------------
    # COMISIONES COBRADAS / PAGADAS
    # --------------------------------------------------------

    comisiones_cobradas_pagadas = (
        extract_field_same_line(
            lines,
            (
                (
                    "TOTAL",
                    "DE",
                    "COMISIONES",
                    "COBRADAS",
                    "/",
                    "PAGADAS",
                ),
            ),
            resumen_start,
            resumen_end,
        )
    )

    # Localizamos el renglón para conocer su signo.
    comisiones_line_index = find_line_by_patterns(
        lines,
        (
            (
                "TOTAL",
                "DE",
                "COMISIONES",
                "COBRADAS",
                "/",
                "PAGADAS",
            ),
        ),
        resumen_start,
        resumen_end,
    )

    comisiones_depositos = 0.0
    comisiones_retiros = 0.0

    if comisiones_line_index is not None:

        (
            comisiones_depositos,
            comisiones_retiros,
        ) = distribute_signed_amount(
            lines[comisiones_line_index],
            comisiones_cobradas_pagadas,
        )

    # --------------------------------------------------------
    # IVA SOBRE COMISIONES
    # --------------------------------------------------------

    iva_sobre_comisiones = extract_field_same_line(
        lines,
        (
            (
                "IVA",
                "SOBRE",
                "COMISIONES",
            ),
        ),
        resumen_start,
        resumen_end,
    )

    # --------------------------------------------------------
    # INTERESES COBRADOS / PAGADOS
    # --------------------------------------------------------

    intereses_cobrados_pagados = (
        extract_field_same_line(
            lines,
            (
                (
                    "INTERESES",
                    "COBRADOS",
                    "/",
                    "PAGADOS",
                ),
            ),
            resumen_start,
            resumen_end,
        )
    )

    # Localizamos el renglón para conocer su signo.
    intereses_cobrados_line_index = (
        find_line_by_patterns(
            lines,
            (
                (
                    "INTERESES",
                    "COBRADOS",
                    "/",
                    "PAGADOS",
                ),
            ),
            resumen_start,
            resumen_end,
        )
    )

    intereses_depositos = 0.0
    intereses_retiros = 0.0

    if intereses_cobrados_line_index is not None:

        (
            intereses_depositos,
            intereses_retiros,
        ) = distribute_signed_amount(
            lines[intereses_cobrados_line_index],
            intereses_cobrados_pagados,
        )

    # --------------------------------------------------------
    # AJUSTES DE DEPÓSITOS
    # --------------------------------------------------------
    #
    # Comisiones:
    #     + -> depósitos
    #     - -> retiros
    #
    # Intereses cobrados/pagados:
    #     + -> depósitos
    #     - -> retiros
    #
    # --------------------------------------------------------

    if depositos_abonos is not None:

        depositos_abonos += comisiones_depositos
        depositos_abonos += intereses_depositos

    # --------------------------------------------------------
    # AJUSTES DE RETIROS
    # --------------------------------------------------------
    #
    # Siempre agregamos el IVA sobre comisiones a retiros.
    #
    # Además:
    #
    #     comisiones negativas -> retiros
    #     intereses negativos  -> retiros
    #
    # --------------------------------------------------------

    retiros_cargos = total_retiros

    if retiros_cargos is not None:

        retiros_cargos += (
            iva_sobre_comisiones
            if iva_sobre_comisiones is not None
            else 0.0
        )

        retiros_cargos += comisiones_retiros
        retiros_cargos += intereses_retiros

    # --------------------------------------------------------
    # INTERESES A FAVOR
    # --------------------------------------------------------
    #
    # Se conserva exactamente el valor extraído de:
    #
    #     Intereses Netos Ganados
    #
    # --------------------------------------------------------

    # --------------------------------------------------------
    # MANEJO DE CUENTA
    # --------------------------------------------------------

    manejo_cuenta = extract_field_same_line(
        lines,
        (
            (
                "TOTAL",
                "DE",
                "COMISIONES",
            ),
        ),
        resumen_start,
        resumen_end,
    )

    # --------------------------------------------------------
    # ISR RETENIDO
    # --------------------------------------------------------

    isr_retenido = extract_field_same_line(
        lines,
        (
            (
                "RETENCIÓN",
                "DE",
                "ISR",
            ),
            (
                "RETENCION",
                "DE",
                "ISR",
            ),
        ),
        resumen_start,
        resumen_end,
    )

    # --------------------------------------------------------
    # SALDO FINAL
    # --------------------------------------------------------

    saldo_final = extract_field_same_line(
        lines,
        (
            (
                "SALDO",
                "ACTUAL",
            ),
        ),
        resumen_start,
        resumen_end,
    )

    # --------------------------------------------------------
    # DÍAS DEL PERIODO
    # --------------------------------------------------------

    dias_periodo = extract_days(
        lines,
        resumen_start,
        resumen_end,
    )

    # --------------------------------------------------------
    # TASA BRUTA ANUAL
    # --------------------------------------------------------

    tasa_bruta_anual = extract_tasa_bruta_anual(
        lines,
        resumen_start,
        resumen_end,
    )

    # --------------------------------------------------------
    # 7. CONSTRUIR MODELO
    # --------------------------------------------------------

    return ResumenFinanciero(
        saldo_promedio=saldo_promedio,
        dias_periodo=dias_periodo,
        tasa_bruta_anual=tasa_bruta_anual,
        saldo_promedio_gravable=None,
        intereses_a_favor=intereses_a_favor,
        isr_retenido=isr_retenido,
        cheques_pagados=None,
        manejo_cuenta=manejo_cuenta,
        cargos_objetados=None,
        abonos_objetados=None,
        saldo_anterior=saldo_anterior,
        depositos_abonos=depositos_abonos,
        retiros_cargos=retiros_cargos,
        saldo_final=saldo_final,
        saldo_promedio_minimo_mensual=(
            saldo_promedio_minimo_mensual
        ),
        saldo_global=None,
    )