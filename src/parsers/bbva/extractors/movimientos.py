
from typing import List, Dict, Any
import re
from models.movimiento import Movimiento
from parsers.bbva.utils.words_footer_filter import remove_bbva_footer
from parsers.bbva.utils.words_resume_filter import remove_after_movimientos
from parsers.bbva.utils.words_header_filter import remove_duplicate_premium_headers

# ============================================================
# CONFIGURACION DE COLUMNAS BBVA
# ============================================================

# --- Coordenadas Layout NORMAL ---
COLS_NORMAL = {
    "FECHA_OPERACION": (10, 55),
    "FECHA_LIQUIDACION": (55, 100),
    "CONCEPTO": (100, 315),
    "CARGO": (380, 422),
    "ABONO": (422, 463),
    "SALDO_OPERACION": (463, 535),
    "SALDO_LIQUIDACION": (535, 610),
    "REFERENCIA_LABEL": (315, 365),
    "REFERENCIA_VALUE": (365, 445),
}

# --- Coordenadas Layout PREMIUM ---
# Ajustadas según el header del layout premium.
# La columna de concepto es más estrecha y la de referencia se desplaza.
COLS_PREMIUM = {
    "FECHA_OPERACION": (10, 55),
    "FECHA_LIQUIDACION": (55, 85), # Ligeramente más estrecha
    "CONCEPTO": (85, 360), # Similar
    "CARGO": (370, 422),
    "ABONO": (422, 470),
    "SALDO_OPERACION": (470, 540),
    "SALDO_LIQUIDACION": (540, 610),
    "REFERENCIA_LABEL": (218, 272), # Coordenada clave de detección
    "REFERENCIA_VALUE": (272, 370), # Valor de referencia
}


# Tesseract y PaddleOCR pueden colocar la fecha y los importes de un mismo
# movimiento en renglones distintos aunque visualmente estén alineados. En las
# muestras reales la separación máxima observada es cercana a 10 puntos.
OCR_AMOUNT_ROW_TOLERANCE = 12.0

BBVA_MONTHS = {
    "ENE",
    "FEB",
    "MAR",
    "ABR",
    "MAY",
    "JUN",
    "JUL",
    "AGO",
    "SEP",
    "OCT",
    "NOV",
    "DIC",
}

BBVA_DATE_PATTERN = re.compile(
    r"(?<![A-Z0-9])([0-3O][0-9O])\s*/\s*([A-Z]{3})(?![A-Z])",
    re.IGNORECASE,
)

BBVA_AMOUNT_PATTERN = re.compile(
    r"(?<!\d)([+-]?)((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})([-−]?)(?!\d)"
)

MONETARY_COLUMN_NAMES = (
    "CARGO",
    "ABONO",
    "SALDO_OPERACION",
    "SALDO_LIQUIDACION",
)

ACCOUNT_HEADER_VALUE_PATTERN = re.compile(r"^[A-Z]?\d{7,12}$", re.IGNORECASE)


def get_column_config(
    words: List[Dict[str, Any]]
) -> Dict[str, tuple[float, float]]:
    """
    Detecta si el estado de cuenta usa el layout de movimientos
    "Normal" o "Premium" y devuelve la configuración de columnas
    apropiada.

    La detección se basa en la posición horizontal (x0) de la
    palabra "REFERENCIA" en el encabezado de la tabla de movimientos.
    """
    # Buscamos la palabra "REFERENCIA" en la primera página,
    # que es donde suele estar el primer header de movimientos.
    for word in words:
        if word.get("page", 1) != 1:
            continue

        text = word.get("text", "").strip().upper()
        if text != "REFERENCIA":
            continue

        x0 = word.get("x0", 0)

        # Layout Premium: "REFERENCIA" tiene x0 ≈ 218.9. El OCR puede
        # desplazar varios puntos el inicio de una palabra, por lo que aquí se
        # usa una banda más amplia sin invadir el rango del layout normal.
        if 195 <= x0 < 290:
            return COLS_PREMIUM

        # Layout Normal: "REFERENCIA" tiene x0 ≈ 321.1 (326-329 en las
        # muestras OCR). La etiqueta del encabezado viene en mayúsculas, por
        # lo que no se confunde con las referencias de cada movimiento.
        if 290 <= x0 <= 350:
            return COLS_NORMAL

    # Si no se encuentra una coincidencia clara, se asume el layout normal
    # por defecto para mantener la compatibilidad con el comportamiento anterior.
    return COLS_NORMAL


# ============================================================
# UTILIDADES ESPACIALES
# ============================================================


def group_words_into_lines(
    words: List[Dict[str, Any]],
    tolerance: float = 3.0
) -> List[List[Dict[str, Any]]]:
    """
    Agrupa palabras por coordenada vertical.
    Mantiene las palabras originales con coordenadas.
    """

    if not words:
        return []


    words = sorted(
        words,
        key=lambda w: (
            w.get("page", 1),
            w.get("top", 0),
            w.get("x0", 0)
        )
    )


    lines = []

    current = []

    current_page = None
    current_top = None


    for word in words:

        page = word.get("page", 1)
        top = word.get("top", 0)


        if current_top is None:

            current.append(word)
            current_top = top
            current_page = page


        elif (
            page == current_page
            and abs(top - current_top) <= tolerance
        ):

            current.append(word)


        else:

            current.sort(
                key=lambda w: w.get("x0", 0)
            )

            lines.append(current)


            current = [word]
            current_top = top
            current_page = page



    if current:

        current.sort(
            key=lambda w: w.get("x0", 0)
        )

        lines.append(current)


    return lines



def words_in_column(
    line: List[Dict[str, Any]],
    xmin: float,
    xmax: float
) -> List[str]:
    """
    Obtiene palabras dentro de una columna X.
    """

    result = []

    for word in line:

        x0 = word.get("x0", 0)
        x1 = word.get("x1", 0)
        # Usamos el centro de la palabra para decidir si pertenece a la columna.
        # Esto evita que números grandes se desborden a la columna siguiente.
        word_center = (x0 + x1) / 2

        if xmin <= word_center <= xmax:
            result.append(word["text"])


    return result



def column_text(
    line: List[Dict[str,Any]],
    column: tuple[float, float]
) -> str:

    words = words_in_column(
        line,
        column[0], # xmin
        column[1]  # xmax
    )

    return " ".join(words).strip()



def canonical_amount_text(value: str) -> str | None:
    """Devuelve un importe OCR en una forma que ``float`` pueda interpretar.

    La corrección se limita a texto que contiene una estructura monetaria con
    exactamente dos decimales. De este modo, referencias, cuentas y otros
    identificadores numéricos no se convierten accidentalmente en importes.
    """

    if not value:
        return None

    normalized = (
        value
        .replace("O", "0")
        .replace("o", "0")
        .replace(" ", "")
        .replace("\u2212", "-")
        .strip()
    )

    match = BBVA_AMOUNT_PATTERN.search(normalized)

    if not match:
        return None

    leading_sign, number, trailing_sign = match.groups()

    if leading_sign == "-" or trailing_sign in {"-", "−"}:
        return f"-{number}"

    if leading_sign == "+":
        return f"+{number}"

    return number


def parse_amount(value:str)->float:

    if not value:
        return 0.0

    canonical = canonical_amount_text(value)

    if canonical is not None:
        value = canonical

    value = (
        value
        .replace(",","")
        .strip()
    )


    try:
        return float(value)

    except (TypeError, ValueError):

        return 0.0


def normalize_bbva_date(value: str) -> str | None:
    """Normaliza una fecha corta BBVA y elimina ruido puntual del OCR."""

    if not value:
        return None

    match = BBVA_DATE_PATTERN.search(value.strip().upper())

    if not match:
        return None

    day_text, month = match.groups()
    day_text = day_text.replace("O", "0")

    try:
        day = int(day_text)
    except ValueError:
        return None

    if not 1 <= day <= 31 or month not in BBVA_MONTHS:
        return None

    return f"{day:02d}/{month}"



def is_start_movement(line, cols):

    fecha = column_text(
        line,
        cols["FECHA_OPERACION"]
    )


    return normalize_bbva_date(fecha) is not None


def line_page(line: List[Dict[str, Any]]) -> int:
    """Obtiene la página de una línea espacial."""

    if not line:
        return 1

    return int(line[0].get("page", 1))


def line_top(line: List[Dict[str, Any]]) -> float:
    """Obtiene una coordenada vertical estable para una línea espacial."""

    if not line:
        return 0.0

    return sum(float(word.get("top", 0)) for word in line) / len(line)


def page_has_account_header(
    lines: List[List[Dict[str, Any]]],
    page: int,
) -> bool:
    """Reconoce páginas BBVA por el valor de cuenta/cliente del encabezado."""

    for line in lines:
        if line_page(line) != page or line_top(line) > 180:
            continue

        for word in line:
            if float(word.get("x0", 0)) < 500:
                continue

            text = re.sub(r"[\s-]+", "", word.get("text", "").strip().upper())

            if ACCOUNT_HEADER_VALUE_PATTERN.fullmatch(text):
                return True

    return False


def attach_split_monetary_rows(
    lines: List[List[Dict[str, Any]]],
    cols: Dict[str, tuple[float, float]],
) -> tuple[List[List[Dict[str, Any]]], bool]:
    """Une importes OCR separados verticalmente con su fecha de movimiento.

    El PDF digital suele entregar fecha e importes en una misma línea. Los
    motores OCR, en cambio, pueden crear una línea exclusiva para importes unos
    puntos antes o después de la fecha. Cada importe se asigna a la fecha más
    cercana de su página y sólo si conserva un patrón monetario estricto.

    Se devuelven líneas nuevas únicamente cuando es necesario; las palabras de
    entrada nunca se mutan.
    """

    starts = [
        {
            "index": index,
            "page": line_page(line),
            "top": line_top(line),
        }
        for index, line in enumerate(lines)
        if is_start_movement(line, cols)
    ]

    if not starts:
        return lines, False

    assignments: Dict[tuple[int, str], tuple[float, str, int]] = {}
    split_row_found = False

    for source_index, line in enumerate(lines):
        page = line_page(line)
        source_top = line_top(line)

        for column_name in MONETARY_COLUMN_NAMES:
            raw_amount = column_text(line, cols[column_name])
            canonical = canonical_amount_text(raw_amount)

            if canonical is None:
                continue

            candidates = [
                start
                for start in starts
                if start["page"] == page
                and abs(start["top"] - source_top) <= OCR_AMOUNT_ROW_TOLERANCE
            ]

            if not candidates:
                continue

            closest = min(
                candidates,
                key=lambda start: abs(start["top"] - source_top),
            )
            distance = abs(closest["top"] - source_top)
            key = (int(closest["index"]), column_name)

            previous = assignments.get(key)
            if previous is None or distance < previous[0]:
                assignments[key] = (distance, canonical, source_index)

            if source_index != closest["index"]:
                split_row_found = True

    if not assignments:
        return lines, False

    augmented = [list(line) for line in lines]

    for (start_index, column_name), (_, canonical, _) in assignments.items():
        first_line_value = canonical_amount_text(
            column_text(augmented[start_index], cols[column_name])
        )

        if first_line_value is not None:
            continue

        xmin, xmax = cols[column_name]
        start = next(
            item for item in starts if item["index"] == start_index
        )
        top = float(start["top"])

        augmented[start_index].append(
            {
                "text": canonical,
                "x0": xmin,
                "x1": xmax,
                "top": top,
                "bottom": top,
                "page": int(start["page"]),
            }
        )
        augmented[start_index].sort(key=lambda word: word.get("x0", 0))

    # Cuando el importe quedó arriba de la fecha, PaddleOCR puede haber dejado
    # también ahí la primera línea del concepto. Sólo se mueve si la línea de
    # fecha no contiene ningún concepto; esto evita apropiarse de la última
    # línea descriptiva del movimiento anterior en páginas con ligera torsión.
    for start in starts:
        start_index = int(start["index"])

        if column_text(augmented[start_index], cols["CONCEPTO"]):
            continue

        source_indices = {
            source_index
            for (assigned_start, _), (_, _, source_index) in assignments.items()
            if assigned_start == start_index and source_index < start_index
        }

        for source_index in sorted(
            source_indices,
            key=lambda index: abs(line_top(lines[index]) - float(start["top"])),
        ):
            concept_words = [
                word
                for word in augmented[source_index]
                if cols["CONCEPTO"][0]
                <= (word.get("x0", 0) + word.get("x1", 0)) / 2
                <= cols["CONCEPTO"][1]
            ]

            if not concept_words:
                continue

            concept_word_ids = {id(word) for word in concept_words}
            augmented[source_index] = [
                word
                for word in augmented[source_index]
                if id(word) not in concept_word_ids
            ]
            augmented[start_index].extend(concept_words)
            augmented[start_index].sort(key=lambda word: word.get("x0", 0))
            break

    return augmented, split_row_found



# ============================================================
# EXTRACCION DE CAMPOS PRINCIPALES
# ============================================================


def extract_fecha_operacion(line, cols):

    raw_value = column_text(
        line,
        cols["FECHA_OPERACION"]
    )

    return normalize_bbva_date(raw_value) or raw_value



def extract_fecha_liquidacion(line, cols):

    raw_value = column_text(
        line,
        cols["FECHA_LIQUIDACION"]
    )

    return normalize_bbva_date(raw_value) or raw_value



def extract_concepto(lines, cols):

    contenido=[]

    for line in lines:

        texto = column_text(
            line,
            cols["CONCEPTO"]
        )

        if texto:

            contenido.append(texto)

    return "\n".join(contenido).strip()


def extract_cargo(line, cols):

    texto = column_text(
        line,
        cols["CARGO"]
    )

    return parse_amount(texto)



def extract_abono(line, cols):

    texto = column_text(
        line,
        cols["ABONO"]
    )

    return parse_amount(texto)



def extract_saldo_operacion(line, cols):

    texto = column_text(
        line,
        cols["SALDO_OPERACION"]
    )

    return parse_amount(texto)



def extract_saldo_liquidacion(line, cols):

    texto = column_text(
        line,
        cols["SALDO_LIQUIDACION"]
    )

    return parse_amount(texto)



def extract_referencia(lines: List[List[Dict[str, Any]]], cols) -> str | None:
    """
    Busca la referencia en las líneas de un movimiento.
    BBVA la coloca en una línea debajo del concepto principal,
    alineada a una columna específica.
    """
    for line in lines:
        # Buscamos la etiqueta "Referencia" para confirmar que estamos en la línea correcta.
        label = column_text(line, cols["REFERENCIA_LABEL"]).lower()
        if "referencia" in label:
            # Si encontramos la etiqueta, extraemos el valor de la columna de al lado.
            ref_value = column_text(line, cols["REFERENCIA_VALUE"])
            if ref_value:
                return ref_value

    # --- Fallback para Layout Premium ---
    # Si no se encontró la etiqueta "Referencia", se busca un patrón que
    # comience con asteriscos dentro de la columna de CONCEPTO.
    # Ejemplo: ******3855
    # El patrón busca una palabra que comience con uno o más asteriscos.
    asterisk_pattern = re.compile(r"(\*+\S+)")

    for line in lines:
        # Buscamos en la columna de concepto, que es donde aparece en el layout premium.
        concepto_text = column_text(line, cols["CONCEPTO"])
        if concepto_text:
            match = asterisk_pattern.search(concepto_text)
            if match:
                return match.group(1)

    return None



# ============================================================
# CAMPOS EXTRAIDOS DESDE CONCEPTO
# ============================================================


# ============================================================
# CAMPOS EXTRAIDOS DESDE CONCEPTO
# ============================================================

def get_concepto_lines(concepto: str) -> List[str]:
    """
    Convierte el concepto completo en una lista de líneas limpias.

    Se centraliza aquí para evitar repetir en cada extractor la misma
    lógica de split/strip/filtrado.
    """
    if not concepto:
        return []

    return [
        line.strip()
        for line in concepto.splitlines()
        if line.strip()
    ]


def get_first_concepto_line(concepto: str) -> str | None:
    """
    Devuelve la primera línea no vacía del concepto.
    """
    lines = get_concepto_lines(concepto)
    return lines[0] if lines else None


# ============================================================
# SPEI
# ============================================================

def is_spei_movement(concepto: str) -> bool:
    """
    Determina si el movimiento corresponde a un SPEI.

    BBVA puede presentar la primera línea de estas formas:

        SPEI ENVIADO INBURSA
        SPEI RECIBIDO AZTECA
        SPEI RECIBIDOAZTECA
        SPEI RECIBIDONVIO
        SPEI RECIBIDOSTP

    Por eso no se exige un límite de palabra después de
    RECIBIDO o ENVIADO.
    """
    first_line = get_first_concepto_line(concepto)

    if not first_line:
        return False

    return bool(
        re.match(
            r"^SPEI\s+(RECIBIDO|ENVIADO)",
            first_line,
            re.IGNORECASE,
        )
    )


def extract_beneficiario_from_spei(
    concepto: str
) -> str | None:
    """
    Extrae el beneficiario de un SPEI.

    Estructura BBVA:

        línea 1 -> SPEI RECIBIDO / SPEI ENVIADO
        línea 2 -> concepto
        línea 3 -> CLABE
        línea 4 -> código
        línea 5 -> beneficiario

    El beneficiario corresponde exactamente a la quinta línea.
    """
    lines = get_concepto_lines(concepto)

    if len(lines) < 5:
        return None

    if not is_spei_movement(concepto):
        return None

    beneficiario = lines[4].strip()

    return beneficiario or None


def extract_clabe_beneficiario_from_spei(
    concepto: str
) -> str | None:
    """
    Extrae la CLABE de un SPEI.

    La CLABE se encuentra en la tercera línea del bloque SPEI.

    BBVA puede incluir dígitos adicionales junto con la CLABE.
    La CLABE real corresponde a los últimos 18 dígitos.
    """
    lines = get_concepto_lines(concepto)

    if len(lines) < 3:
        return None

    if not is_spei_movement(concepto):
        return None

    linea_clabe = lines[2]

    digits = re.sub(
        r"\D",
        "",
        linea_clabe,
    )

    if len(digits) < 18:
        return None

    return digits[-18:]


def extract_concepto_original_from_spei(
    concepto: str
) -> str | None:
    """
    Extrae el concepto real del pago de un SPEI.

    Estructura BBVA:

        línea 1 -> SPEI RECIBIDO / SPEI ENVIADO
        línea 2 -> código + concepto real
        línea 3 -> CLABE
        línea 4 -> código
        línea 5 -> beneficiario

    Ejemplos:

        1234567A loan
        -> loan

        1234567A Pago renta
        -> Pago renta

        0054303388 036 0811250Gerardo Cruz Rosas
        -> Gerardo Cruz Rosas
    """
    lines = get_concepto_lines(concepto)

    if len(lines) < 2:
        return None

    if not is_spei_movement(concepto):
        return None

    segunda_linea = lines[1]

    # --------------------------------------------------------
    # CASO:
    #
    # 1234567A loan
    #
    # El código termina antes del espacio y el texto comienza
    # después de él. Aunque a veces viene junto por lo que simplemente
    # extraemos todo el renglon.
    # --------------------------------------------------------

    segunda_linea = lines[1].strip()

    return segunda_linea or None


    # --------------------------------------------------------
    # CASO:
    #
    # 0054303388 036 0811250Gerardo Cruz Rosas
    #
    # Hay varios bloques numéricos y el texto comienza
    # inmediatamente después del último bloque numérico.
    # --------------------------------------------------------

    match = re.match(
        r"^(?:\d+\s+)\d+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ].*)$",
        segunda_linea,
    )

    if match:
        texto = match.group(1).strip()

        if texto:
            return texto

    return None


# ============================================================
# PAGO CUENTA DE TERCERO
# ============================================================

def is_pago_cuenta_tercero_movement(concepto: str) -> bool:
    """
    Determina si el movimiento corresponde a:

        PAGO CUENTA DE TERCERO

    La identificación se realiza sobre la primera línea no vacía
    del concepto.
    """
    first_line = get_first_concepto_line(concepto)

    if not first_line:
        return False

    return bool(
        re.match(
            r"^PAGO\s+CUENTA\s+DE\s+TERCERO$",
            first_line,
            re.IGNORECASE,
        )
    )


def extract_cuenta_beneficiario_from_pago_cuenta_tercero(
    concepto: str
) -> str | None:
    """
    Extrae la cuenta del beneficiario de un movimiento
    PAGO CUENTA DE TERCERO.

    Estructura esperada:

        línea 1 -> PAGO CUENTA DE TERCERO
        línea 2 -> BNET 0459455663 Transf a Ma. Guada

    Resultado:

        0459455663
    """
    lines = get_concepto_lines(concepto)

    if len(lines) < 2:
        return None

    if not is_pago_cuenta_tercero_movement(concepto):
        return None

    segunda_linea = lines[1]

    match = re.match(
        r"^BNET\s+(\d+)(?:\s|$)",
        segunda_linea,
        re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(1)


def extract_beneficiario_from_pago_cuenta_tercero(
    concepto: str
) -> str | None:
    """
    Para PAGO CUENTA DE TERCERO, el beneficiario se representa
    mediante la propia cuenta beneficiaria.

    Ejemplo:

        BNET 0459455663 Transf a Ma. Guada

    Resultado:

        0459455663
    """
    return extract_cuenta_beneficiario_from_pago_cuenta_tercero(
        concepto
    )


def extract_concepto_original_from_pago_cuenta_tercero(
    concepto: str
) -> str | None:
    """
    Extrae el concepto original de un movimiento
    PAGO CUENTA DE TERCERO.

    Estructura:

        BNET 0459455663 Transf a Ma. Guada

    Resultado:

        Transf a Ma. Guada

    Es decir:
        - se elimina BNET
        - se elimina la cuenta
        - se conserva exactamente el texto posterior.
    """
    lines = get_concepto_lines(concepto)

    if len(lines) < 2:
        return None

    if not is_pago_cuenta_tercero_movement(concepto):
        return None

    segunda_linea = lines[1]

    match = re.match(
        r"^BNET\s+\d+\s*(.*)$",
        segunda_linea,
        re.IGNORECASE,
    )

    if not match:
        return None

    texto = match.group(1).strip()

    return texto or None


# ============================================================
# DISPATCHERS DE CAMPOS EXTRAIDOS DESDE CONCEPTO
# ============================================================

def extract_beneficiario_from_concepto(
    concepto: str
) -> str | None:
    """
    Extrae el beneficiario de acuerdo con el tipo de movimiento.

    SPEI:
        usa el beneficiario propio del bloque SPEI.

    PAGO CUENTA DE TERCERO:
        el beneficiario se representa mediante la cuenta.
    """
    if is_spei_movement(concepto):
        return extract_beneficiario_from_spei(concepto)

    if is_pago_cuenta_tercero_movement(concepto):
        return extract_beneficiario_from_pago_cuenta_tercero(concepto)

    return None


def extract_clabe_beneficiario_from_concepto(
    concepto: str
) -> str | None:
    """
    Extrae la CLABE del beneficiario según el tipo de movimiento.
    """
    if is_spei_movement(concepto):
        return extract_clabe_beneficiario_from_spei(concepto)

    return None


def extract_cuenta_beneficiario_from_concepto(
    concepto: str
) -> str | None:
    """
    Extrae la cuenta del beneficiario según el tipo de movimiento.
    """
    if is_pago_cuenta_tercero_movement(concepto):
        return extract_cuenta_beneficiario_from_pago_cuenta_tercero(
            concepto
        )

    return None


def extract_concepto_original_from_concepto(
    concepto: str
) -> str | None:
    """
    Extrae el concepto original según el tipo de movimiento.
    """
    if is_spei_movement(concepto):
        return extract_concepto_original_from_spei(concepto)

    if is_pago_cuenta_tercero_movement(concepto):
        return extract_concepto_original_from_pago_cuenta_tercero(
            concepto
        )

    return None


# ============================================================
# OTROS CAMPOS EXTRAIDOS DESDE CONCEPTO
# ============================================================

def extract_rfc_from_concepto(concepto: str) -> str | None:
    """
    Extrae el RFC del texto del concepto.

    Maneja RFCs que pueden tener espacios en medio.
    Ej: "RFC: PPL 961114GZ1" -> "PPL961114GZ1"
    """
    match = re.search(
        r"RFC:\s*([A-Z&Ñ]{3,4}\s?\d{6}[A-Z0-9]{3})",
        concepto,
        re.IGNORECASE
    )

    if match:
        return match.group(1).replace(" ", "")

    return None


def extract_auth_from_concepto(concepto: str) -> str | None:
    """
    Extrae el número de autorización (AUT) del concepto.
    Busca "AUT:" seguido de un código alfanumérico.
    """
    match = re.search(
        r"AUT:\s*([A-Z0-9]+)",
        concepto,
        re.IGNORECASE
    )

    if match:
        return match.group(1)

    return None


def extract_hora_from_concepto(concepto: str) -> str | None:
    """
    Extrae la hora de la operación del concepto.
    Busca un formato HH:MM.
    """
    match = re.search(r"(\d{1,2}:\d{2})", concepto)

    if match:
        return match.group(1)

    return None


# ============================================================
# CONSTRUCTOR MOVIMIENTO
# ============================================================

def build_movimiento(block, cols):
    primera_linea = block[0]

    concepto = extract_concepto(
        block,
        cols
    )

    cargo = extract_cargo(
        primera_linea,
        cols
    )

    abono = extract_abono(
        primera_linea,
        cols
    )

    tipo = None

    if cargo > 0:
        tipo = "CARGO"
    elif abono > 0:
        tipo = "ABONO"

    referencia = extract_referencia(
        block,
        cols
    )

    beneficiario = extract_beneficiario_from_concepto(
        concepto
    )

    cuenta_beneficiario = extract_cuenta_beneficiario_from_concepto(
        concepto
    )

    clabe_beneficiario = extract_clabe_beneficiario_from_concepto(
        concepto
    )

    concepto_original = extract_concepto_original_from_concepto(
        concepto
    )

    return Movimiento(
        fecha_operacion=
            extract_fecha_operacion(
                primera_linea,
                cols
            ),

        fecha_liquidacion=
            extract_fecha_liquidacion(
                primera_linea,
                cols
            ),

        concepto=concepto,

        tipo_operacion=tipo,

        cargo=cargo,

        abono=abono,

        saldo_operacion=
            extract_saldo_operacion(
                primera_linea,
                cols
            ),

        saldo_liquidacion=
            extract_saldo_liquidacion(
                primera_linea,
                cols
            ),

        referencia=referencia,

        clave_rastreo=None,

        autorizacion=
            extract_auth_from_concepto(
                concepto
            ),

        beneficiario=beneficiario,

        cuenta_beneficiario=cuenta_beneficiario,

        clabe_beneficiario=clabe_beneficiario,

        rfc=
            extract_rfc_from_concepto(
                concepto
            ),

        sucursal=None,

        caja=None,

        hora_operacion=
            extract_hora_from_concepto(
                concepto
            ),

        concepto_original=concepto_original
    )

# ============================================================
# FUNCION PRINCIPAL PUBLICA
# ============================================================


def extract_movimientos_words(
    words: List[Dict[str,Any]]
) -> List[Movimiento]:

    """
    Parser espacial BBVA.

    Usa coordenadas X/Y del PDF.
    """

    # 1. Detectar layout y obtener configuración de columnas
    cols = get_column_config(words)

    #Se elimina el pie de página
    words = remove_bbva_footer(words)

    # Se eliminan encabezados repetidos únicamente en layout Premium
    words = remove_duplicate_premium_headers(words)

    #Se elimina todo lo que viene despues del ultimo movimiento
    words = remove_after_movimientos(words)

    lines = group_words_into_lines(
        words
    )

    # En OCR los importes pueden quedar en una línea distinta a la fecha.
    # Se reconstruye la fila por proximidad vertical y columna monetaria.
    lines, has_split_monetary_rows = attach_split_monetary_rows(
        lines,
        cols,
    )

    # Algunas emisiones BBVA intercalan una hoja publicitaria entre páginas de
    # movimientos. Sólo en el caso OCR confirmado por filas monetarias partidas
    # se omiten páginas que no contienen ninguna fecha de movimiento. Así se
    # evita contaminar conceptos sin cambiar el flujo digital histórico.
    if has_split_monetary_rows:
        movement_pages = {
            line_page(line)
            for line in lines
            if is_start_movement(line, cols)
        }
        candidate_pages = {line_page(line) for line in lines}
        statement_pages = movement_pages | {
            page
            for page in candidate_pages
            if page_has_account_header(lines, page)
        }
        lines = [
            line
            for line in lines
            if line_page(line) in statement_pages
        ]


    movimientos=[]


    current=[]


    for line in lines:


        if is_start_movement(line, cols):


            if current:

                movimientos.append(
                    build_movimiento(
                        current, cols
                    )
                )


            current=[line]


        else:


            if current:

                current.append(line)



    if current:

        movimientos.append(
            build_movimiento(
                current, cols
            )
        )



    return movimientos
