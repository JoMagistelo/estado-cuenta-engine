from __future__ import annotations

import re
import unicodedata

from catalog.bank_signatures import BANK_SIGNATURES


# ============================================================
# CONFIGURACIÓN
# ============================================================


# Máximo número de caracteres permitidos antes de una firma
# bancaria cuando viene pegada dentro de un token.
#
# Ejemplos válidos:
#
#   AHSBC   -> A + HSBC
#   DHSBC   -> D + HSBC
#   XBBVA   -> X + BBVA
#
# Se mantiene pequeño para evitar coincidencias demasiado
# permisivas.
MAX_PREFIX_CHARS_FOR_FALLBACK = 3


# Longitud mínima de una firma para permitir el fallback.
#
# Evita relajar firmas excesivamente cortas que pudieran
# producir falsos positivos.
MIN_KEYWORD_LENGTH_FOR_FALLBACK = 4


# ============================================================
# NORMALIZACIÓN
# ============================================================


def _normalize_filename(filename: str) -> str:
    """
    Normaliza el nombre de archivo para facilitar la detección.

    Ejemplo:

        "12.1_Nómina_Banorte_dic_23_TO..."

    se convierte aproximadamente en:

        "12 1 NOMINA BANORTE DIC 23 TO"

    Se eliminan acentos y caracteres no alfanuméricos,
    conservando separadores de palabras.
    """

    if not filename:
        return ""

    text = unicodedata.normalize(
        "NFKD",
        filename,
    )

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    text = text.upper()

    text = re.sub(
        r"[^A-Z0-9]+",
        " ",
        text,
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


# ============================================================
# ÍNDICE DE FIRMAS
# ============================================================


def _build_filename_signature_index() -> list[tuple[str, str]]:
    """
    Construye un índice de búsqueda a partir del catálogo.

    Cada elemento contiene:

        (
            keyword_normalized,
            bank_key,
        )

    Las palabras clave más largas se colocan primero para evitar
    que una coincidencia corta opaque a una más específica.

    Ejemplo:

        "BANCO MERCANTIL DEL NORTE"

    debe evaluarse antes que:

        "BANORTE"
    """

    signatures: list[tuple[str, str]] = []

    for bank_key, bank_data in BANK_SIGNATURES.items():

        keywords = bank_data.get(
            "filename_keywords",
            [],
        )

        for keyword in keywords:

            normalized_keyword = _normalize_filename(
                keyword
            )

            if not normalized_keyword:
                continue

            signatures.append(
                (
                    normalized_keyword,
                    bank_key,
                )
            )

    signatures.sort(
        key=lambda item: len(item[0]),
        reverse=True,
    )

    return signatures


FILENAME_SIGNATURE_INDEX = (
    _build_filename_signature_index()
)


# ============================================================
# DETECCIÓN ESTRICTA
# ============================================================


def _detect_strict(
    normalized_filename: str,
) -> str | None:
    """
    Ejecuta la detección original.

    La firma bancaria debe encontrarse delimitada por caracteres
    no alfanuméricos.

    Ejemplos:

        "AHORRO HSBC ABR25"
                 ^^^^
        -> detecta HSBC

        "ESTADO BANORTE ENERO"
                ^^^^^^^
        -> detecta BANORTE

    Esta función conserva exactamente el comportamiento seguro
    del detector original.
    """

    for keyword, bank_key in FILENAME_SIGNATURE_INDEX:

        pattern = (
            rf"(?<![A-Z0-9])"
            rf"{re.escape(keyword)}"
            rf"(?![A-Z0-9])"
        )

        if re.search(
            pattern,
            normalized_filename,
        ):
            return bank_key

    return None


# ============================================================
# FALLBACK PARA FIRMAS PEGADAS
# ============================================================


def _detect_attached_signature(
    normalized_filename: str,
) -> str | None:
    """
    Fallback controlado para nombres donde la firma bancaria
    está pegada a un prefijo corto.

    Ejemplos:

        AHSBC_1.pdf
            -> "AHSBC 1 PDF"
            -> HSBC

        DHSBC_2.pdf
            -> "DHSBC 2 PDF"
            -> HSBC

        XBBVA.pdf
            -> "XBBVA PDF"
            -> BBVA

    IMPORTANTE:

    Este fallback:

        - solamente se ejecuta si falló la detección estricta;
        - solamente considera firmas de una sola palabra;
        - exige una longitud mínima de firma;
        - solamente acepta un prefijo corto;
        - no acepta coincidencias arbitrarias en medio del token.

    Esto evita convertir el detector en un simple:

        if "HSBC" in filename

    que sería demasiado permisivo.
    """

    tokens = normalized_filename.split()

    if not tokens:
        return None

    for keyword, bank_key in FILENAME_SIGNATURE_INDEX:

        # ----------------------------------------------------
        # Solamente firmas simples.
        #
        # No relajamos:
        #
        #   BANCO MERCANTIL DEL NORTE
        #   BANCO NACIONAL DE MEXICO
        #
        # etc.
        # ----------------------------------------------------

        if " " in keyword:
            continue

        # ----------------------------------------------------
        # Evitar firmas demasiado cortas.
        # ----------------------------------------------------

        if (
            len(keyword)
            < MIN_KEYWORD_LENGTH_FOR_FALLBACK
        ):
            continue

        for token in tokens:

            # -----------------------------------------------
            # La igualdad exacta normalmente ya fue detectada
            # por _detect_strict(), pero mantenerla aquí hace
            # este helper seguro de utilizar por separado.
            # -----------------------------------------------

            if token == keyword:
                return bank_key

            # -----------------------------------------------
            # El token debe terminar exactamente con la firma.
            #
            # AHSBC
            #  HSBC
            #
            # Sí.
            #
            # HSBCXYZ
            #
            # No.
            # -----------------------------------------------

            if not token.endswith(keyword):
                continue

            prefix_length = (
                len(token) - len(keyword)
            )

            # -----------------------------------------------
            # Debe existir realmente un prefijo.
            # -----------------------------------------------

            if prefix_length <= 0:
                continue

            # -----------------------------------------------
            # El prefijo debe ser corto.
            #
            # AHSBC  -> 1 carácter -> válido
            # DHSBC  -> 1 carácter -> válido
            #
            # Esto evita que cualquier palabra larga que
            # casualmente termine con el nombre del banco sea
            # aceptada automáticamente.
            # -----------------------------------------------

            if (
                prefix_length
                > MAX_PREFIX_CHARS_FOR_FALLBACK
            ):
                continue

            return bank_key

    return None


# ============================================================
# DETECCIÓN PÚBLICA
# ============================================================


def detect_by_filename(
    filename: str,
) -> str | None:
    """
    Detecta el banco a partir del nombre del archivo.

    Estrategia:

        1. Normalizar filename.

        2. Ejecutar detección estricta original.

        3. Si no hay coincidencia, ejecutar fallback controlado
           para firmas bancarias pegadas a un prefijo corto.

    Ejemplos:

        "12.1_Nómina_Banorte_dic_23.pdf"
            -> "banorte"

        "estado_cuenta_BBVA_enero.pdf"
            -> "bbva"

        "2025_CITIBANAMEX_cuenta.pdf"
            -> "banamex"

        "12. Ahorro HSBC_ABR25.pdf"
            -> "hsbc"

        "AHSBC_1.pdf"
            -> "hsbc"

        "AHSBC_2.pdf"
            -> "hsbc"

        "DHSBC_1.pdf"
            -> "hsbc"

    Si no encuentra una firma conocida, devuelve None.
    """

    normalized_filename = _normalize_filename(
        filename
    )

    if not normalized_filename:
        return None

    # ========================================================
    # 1. DETECCIÓN ESTRICTA ORIGINAL
    # ========================================================

    bank_key = _detect_strict(
        normalized_filename
    )

    if bank_key is not None:
        return bank_key

    # ========================================================
    # 2. FALLBACK CONTROLADO
    # ========================================================

    bank_key = _detect_attached_signature(
        normalized_filename
    )

    if bank_key is not None:
        return bank_key

    # ========================================================
    # 3. SIN COINCIDENCIA
    # ========================================================

    return None