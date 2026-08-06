# extractors/clabe_extractor.py

from __future__ import annotations

import re

from utils.text_digit_cleaner import clean_digits

# Patrones probados sobre estados de cuenta reales.
# La captura debe devolver solo la CLABE o una versión con espacios.
CLABE_PATTERNS = [
    # Caso BBVA: "No. Cuenta CLABE 012 180 01576395513 3"
    r"CLABE\s+((?:\d{3}\s+\d{3}\s+\d{11}\s+\d))",

    # Caso HSBC: "NÚMERO DE CUENTA CLABE ... 021975212054495123"
    r"CLABE\s+Personalizada\s+((?:\d[\s-]*){18})",

    # Caso Afirme: "Clave Bancaria Estándar (CLABE): 062580008378270190"
    r"CLABE\):\s*((?:\d[\s-]*){18})",

    # Caso Banamex / Nu / Scotiabank: "CLABE Interbancaria 002..."
    # o "CLABE: 638..." o "CLABE 044..."
    r"CLABE(?:\s+Interbancaria|:)?\s*((?:\d[\s-]*){18})",

    # Fallback genérico con ancla CLABE.
    r"CLABE(?:.|\n){0,80}?((?:\d[\s-]*){18})",
]


def _normalize_clabe_candidate(candidate: str) -> str | None:
    digits = clean_digits(candidate)
    return digits if len(digits) == 18 else None


def extract_clabes(text: str) -> list[str]:
    """
    Encuentra CLABEs probando patrones específicos.
    Devuelve una lista sin duplicados.
    """
    found_clabes: list[str] = []
    seen: set[str] = set()

    for pattern in CLABE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)

        for match in matches:
            clean = _normalize_clabe_candidate(match)
            if clean and clean not in seen:
                seen.add(clean)
                found_clabes.append(clean)

    return found_clabes


def extract_clabe_prefixes(text: str) -> list[str]:
    """
    Obtiene el código bancario (los primeros 3 dígitos).
    """
    clabes = extract_clabes(text)
    return [clabe[:3] for clabe in clabes]