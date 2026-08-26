from __future__ import annotations

from catalog.bank_signatures import BANK_SIGNATURES
from detectors.clabe_detector import detect_by_clabe
from detectors.filename_bank_detector import detect_by_filename
from utils.text_normalizer import normalize_text


def identify_bank_key(
    raw_text: str,
    file_name: str | None = None,
) -> str | None:
    """
    Identifica el banco y retorna la clave interna.

    Estrategias utilizadas:

    1. CLABE
       La CLABE es la fuente primaria cuando existe una CLABE
       válida y su prefijo corresponde a un banco conocido.

    2. Nombre del archivo
       Se utiliza como fallback cuando la CLABE no puede
       identificar el banco.

    3. Validación cruzada
       Si ambas estrategias identifican un banco:

           - Si coinciden -> se confirma el resultado.
           - Si difieren -> se conserva el resultado de la CLABE,
             ya que es una señal estructurada y más confiable.

    Si ninguna estrategia identifica el banco, devuelve None.
    """

    normalized_text = normalize_text(
        raw_text or ""
    )

    bank_by_clabe = detect_by_clabe(
        normalized_text
    )

    bank_by_filename = detect_by_filename(
        file_name or ""
    )

    # ============================================================
    # CASO 1: CLABE Y NOMBRE COINCIDEN
    # ============================================================

    if (
        bank_by_clabe
        and bank_by_filename
    ):
        if bank_by_clabe == bank_by_filename:
            return bank_by_clabe

        # ========================================================
        # CONFLICTO
        # ========================================================
        #
        # La CLABE tiene prioridad sobre el nombre del archivo.
        #
        # Ejemplo:
        #
        # archivo: "Banorte_estado.pdf"
        # CLABE: 012...
        #
        # La CLABE permite identificar BBVA de forma estructurada,
        # mientras que el nombre puede ser incorrecto o corresponder
        # a una nomenclatura administrativa.
        #
        # No se interrumpe el procesamiento.
        # ========================================================

        return bank_by_clabe

    # ============================================================
    # CASO 2: SOLO CLABE
    # ============================================================

    if bank_by_clabe:
        return bank_by_clabe

    # ============================================================
    # CASO 3: SOLO NOMBRE DEL ARCHIVO
    # ============================================================

    if bank_by_filename:
        return bank_by_filename

    # ============================================================
    # CASO 4: NINGUNA ESTRATEGIA
    # ============================================================

    return None


def identify_bank(
    raw_text: str,
    file_name: str | None = None,
) -> str:
    """
    Identifica el banco y retorna su nombre visible.
    """

    bank_key = identify_bank_key(
        raw_text=raw_text,
        file_name=file_name,
    )

    if not bank_key:
        return "Desconocido"

    return BANK_SIGNATURES.get(
        bank_key,
        {},
    ).get(
        "display_name",
        "Desconocido",
    )