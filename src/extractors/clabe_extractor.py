from __future__ import annotations

import re

from utils.text_digit_cleaner import clean_digits


# ---------------------------------------------------------------------------
# PATRONES GENERALES
# ---------------------------------------------------------------------------
#
# Estos patrones se utilizan únicamente cuando el caso Banorte
# no produce una CLABE válida.
#
# La captura debe devolver únicamente la CLABE o una versión con espacios.
#

CLABE_PATTERNS = [
    # Caso BBVA:
    # "No. Cuenta CLABE 012 180 01576395513 3"
    r"CLABE\s+((?:\d{3}\s+\d{3}\s+\d{11}\s+\d))",

    # Caso HSBC:
    # "NÚMERO DE CUENTA CLABE Personalizada 021975212054495123"
    r"CLABE\s+Personalizada\s+((?:\d[\s-]*){18})",

    # Caso HSBC:
    # "CLABE INTERBANCARIA 021..."
    r"CLABE\s+INTERBANCARIA\s+((?:\d[\s-]*){18})",

    # Caso Afirme:
    # "Clave Bancaria Estándar (CLABE): 062580008378270190"
    r"CLABE\):\s*((?:\d[\s-]*){18})",

    # Caso Banamex / Nu / Scotiabank:
    # "CLABE Interbancaria 002..."
    # "CLABE: 638..."
    # "CLABE 044..."
    r"CLABE(?:\s+Interbancaria|:)?\s*((?:\d[\s-]*){18})",

    # Fallback genérico con ancla CLABE.
    r"CLABE(?:.|\n){0,80}?((?:\d[\s-]*){18})",
]


# ---------------------------------------------------------------------------
# REGEX PRECOMPILADOS
# ---------------------------------------------------------------------------
#
# Se compilan una sola vez. Así cada llamada a extract_clabes()
# no vuelve a construir los objetos regex.
#

_CLABE_PATTERNS_COMPILED = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in CLABE_PATTERNS
]

_RE_FIRST_CLABE = re.compile(
    r"\bCLABE\b",
    re.IGNORECASE,
)

_RE_BANORTE_CONTIGUOUS = re.compile(
    r"\b\d{18}\b",
)

_RE_BANORTE_SPACED = re.compile(
    r"\b\d{3}\s+\d{3}\s+\d{11}\s+\d\b",
)

_RE_BANORTE_GENERIC = re.compile(
    r"\b(?:\d[\s-]*){18}\b",
)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _normalize_clabe_candidate(candidate: str) -> str | None:
    """
    Limpia una candidata y valida que tenga exactamente 18 dígitos.
    """
    digits = clean_digits(candidate)

    if len(digits) == 18:
        return digits

    return None


def _first_clabe_match(text: str) -> re.Match[str] | None:
    """
    Devuelve únicamente la primera aparición de la palabra CLABE.
    """
    return _RE_FIRST_CLABE.search(text)


def _is_numeric_after_clabe(
    text: str,
    clabe_match: re.Match[str],
) -> bool:
    """
    Determina si inmediatamente después de CLABE aparecen números.

    Ejemplo NO Banorte:

        CLABE 012 180 01576395513 3

    Ejemplo Banorte:

        CLABE
        Saldo anterior
        Saldo al corte
    """
    after_clabe = text[clabe_match.end():].lstrip()

    if not after_clabe:
        return False

    return after_clabe[0].isdigit()


def _extract_banorte_clabe(text: str) -> str | None:
    """
    Intenta extraer exclusivamente la CLABE del formato Banorte.

    Reglas:

    1. Solo se considera la PRIMERA aparición de CLABE.
    2. Si después de CLABE aparece un número:
       no es Banorte y se devuelve None.
    3. Si después de CLABE aparece texto:
       se considera candidato al formato tabular Banorte.
    4. Se busca una CLABE válida únicamente dentro de una ventana
       de 500 caracteres posteriores a CLABE.
    5. Si se encuentra una CLABE válida, se devuelve inmediatamente.
    6. Si no se encuentra, devuelve None para permitir el fallback
       general.

    IMPORTANTE:
    Se conserva deliberadamente el orden de las tres búsquedas:
        1. contigua
        2. 3-3-11-1
        3. arbitrariamente separada
    """

    # ---------------------------------------------------------------
    # 1. PRIMERA APARICIÓN DE CLABE
    # ---------------------------------------------------------------

    clabe_match = _first_clabe_match(text)

    if not clabe_match:
        return None

    # ---------------------------------------------------------------
    # 2. DETERMINAR SI ES FORMATO TABULAR
    # ---------------------------------------------------------------

    if _is_numeric_after_clabe(text, clabe_match):
        # Ejemplo:
        #
        # CLABE 012...
        #
        # No es Banorte tabular.
        return None

    # ---------------------------------------------------------------
    # 3. VENTANA DEL CASO BANORTE
    # ---------------------------------------------------------------

    after_clabe = text[
        clabe_match.end():
        clabe_match.end() + 500
    ]

    # ---------------------------------------------------------------
    # 4. CLABE CONTIGUA
    # ---------------------------------------------------------------

    contiguous_match = _RE_BANORTE_CONTIGUOUS.search(
        after_clabe
    )

    if contiguous_match:
        candidate = _normalize_clabe_candidate(
            contiguous_match.group(0)
        )

        if candidate:
            return candidate

    # ---------------------------------------------------------------
    # 5. CLABE SEPARADA EN BLOQUES
    # ---------------------------------------------------------------

    spaced_match = _RE_BANORTE_SPACED.search(
        after_clabe
    )

    if spaced_match:
        candidate = _normalize_clabe_candidate(
            spaced_match.group(0)
        )

        if candidate:
            return candidate

    # ---------------------------------------------------------------
    # 6. CLABE SEPARADA ARBITRARIAMENTE
    # ---------------------------------------------------------------

    generic_match = _RE_BANORTE_GENERIC.search(
        after_clabe
    )

    if generic_match:
        candidate = _normalize_clabe_candidate(
            generic_match.group(0)
        )

        if candidate:
            return candidate

    # No se confirmó un caso Banorte.
    return None


def _extract_first_generic_clabe(text: str) -> str | None:
    """
    Ejecuta los patrones generales y devuelve una sola CLABE válida.

    Se detiene inmediatamente al encontrar la primera coincidencia
    válida según el orden de los patrones.

    Se usa search() porque nunca necesitamos recorrer coincidencias
    adicionales dentro de un mismo patrón.
    """

    for pattern in _CLABE_PATTERNS_COMPILED:

        match = pattern.search(text)

        if not match:
            continue

        candidate = match.group(1)

        clean = _normalize_clabe_candidate(candidate)

        if clean:
            return clean

    return None


# ---------------------------------------------------------------------------
# API PÚBLICA
# ---------------------------------------------------------------------------

def extract_clabes(text: str) -> list[str]:
    """
    Extrae UNA Y SOLO UNA CLABE.

    Prioridad:

        1. Caso Banorte tabular.
        2. Patrones generales.

    Reglas:

        - Solo se considera la primera aparición de CLABE
          para decidir si se trata del caso Banorte.
        - Si después de CLABE hay números, se salta Banorte.
        - Si después de CLABE hay texto, se intenta confirmar
          el caso Banorte dentro de una ventana de 500 caracteres.
        - Si Banorte encuentra una CLABE válida, esa es la única
          CLABE que se devuelve.
        - Si Banorte no encuentra una CLABE válida, se ejecutan
          los patrones generales.
        - Los patrones generales se detienen en la primera CLABE
          válida que encuentren.
        - Nunca se devuelven múltiples CLABEs.
    """

    # ===============================================================
    # PRIORIDAD 1: BANORTE
    # ===============================================================

    banorte_clabe = _extract_banorte_clabe(text)

    if banorte_clabe:
        return [banorte_clabe]

    # ===============================================================
    # PRIORIDAD 2: OTROS BANCOS
    # ===============================================================

    generic_clabe = _extract_first_generic_clabe(text)

    if generic_clabe:
        return [generic_clabe]

    # ===============================================================
    # SIN RESULTADO
    # ===============================================================

    return []


def extract_clabe_prefixes(text: str) -> list[str]:
    """
    Obtiene el prefijo bancario de la única CLABE extraída.

    Mantiene la API existente para no romper imports.
    """

    clabes = extract_clabes(text)

    return [
        clabe[:3]
        for clabe in clabes
    ]