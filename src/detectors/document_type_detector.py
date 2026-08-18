from __future__ import annotations

from enum import Enum
from typing import Any
import re
import unicodedata


# ============================================================
# TIPOS DE DOCUMENTO
# ============================================================


class DocumentType(str, Enum):
    """
    Tipo de documento detectado por el motor.
    """

    PDF_DIGITAL = "pdf_digital"

    PDF_IMAGEN = "pdf_imagen"


# ============================================================
# CONFIGURACIÓN
# ============================================================


# Patrones típicos de texto que indica una extracción
# PDF defectuosa / fuente CID mal decodificada.
#
# Ejemplos:
#
#   (cid:240)
#   @(cid:240)K(cid:240)(cid:240)
#   ˆ(cid:228)¯(cid:213)ª
#
CID_PATTERN = re.compile(
    r"\(cid:\d+\)",
    re.IGNORECASE,
)


# Algunos PDFs con fuentes codificadas incorrectamente
# producen secuencias con muchos caracteres de este tipo.
#
# No declaramos que UN carácter extraño sea suficiente para
# clasificar un documento como corrupto.
#
# Lo importante es la proporción de caracteres sospechosos.
SUSPICIOUS_CHARS = frozenset(
    {
        "ˆ",
        "˜",
        "¯",
        "ª",
        "˛",
        "˚",
        "˙",
        "¨",
        "´",
        "¸",
        "ł",
        "ø",
        "Ø",
        "ı",
        "Œ",
        "œ",
        "Š",
        "š",
        "Ž",
        "ž",
        "ƒ",
    }
)


# ============================================================
# HELPERS DE CALIDAD
# ============================================================


def _normalize_text_for_analysis(text: str) -> str:
    """
    Normaliza mínimamente el texto únicamente para analizar
    su calidad.

    NO modifica el texto almacenado en DocumentData.
    """

    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)

    # Normalizamos espacios consecutivos.
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def _count_cid_tokens(text: str) -> int:
    """
    Cuenta cuántos tokens CID aparecen en el texto.

    Ejemplo:

        @(cid:240)K(cid:240)

    devuelve 2.
    """

    if not text:
        return 0

    return len(CID_PATTERN.findall(text))


def _count_suspicious_characters(text: str) -> int:
    """
    Cuenta caracteres que frecuentemente aparecen en
    extracciones de fuentes PDF mal codificadas.
    """

    if not text:
        return 0

    return sum(
        1
        for char in text
        if char in SUSPICIOUS_CHARS
    )


def _count_alphanumeric_characters(text: str) -> int:
    """
    Cuenta caracteres alfanuméricos.

    Se utiliza como referencia para calcular la proporción
    de caracteres sospechosos.
    """

    if not text:
        return 0

    return sum(
        1
        for char in text
        if char.isalnum()
    )


def _count_printable_characters(text: str) -> int:
    """
    Cuenta caracteres imprimibles.
    """

    if not text:
        return 0

    return sum(
        1
        for char in text
        if char.isprintable()
    )


def _has_meaningful_words(text: str) -> bool:
    """
    Determina si el texto contiene palabras razonablemente
    normales.

    No intenta entender el contenido del documento.
    Solamente busca evidencia de que la extracción produjo
    palabras legibles.

    Ejemplos positivos:

        ESTADO
        DE
        CUENTA
        CLIENTE
        FEBRERO
        2026

    """

    if not text:
        return False

    words = re.findall(
        r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,}",
        text,
    )

    if not words:
        return False

    # Una sola palabra podría ser ruido.
    #
    # Pedimos al menos 2 palabras normales.
    return len(words) >= 2


def _looks_like_corrupted_encoding(text: str) -> bool:
    """
    Determina si el texto parece provenir de una fuente PDF
    mal codificada.

    Esta función es deliberadamente conservadora:
    un carácter extraño aislado NO convierte un PDF en
    corrupto.

    Sí consideramos corrupción cuando encontramos señales
    fuertes como:

        - tokens (cid:XXX)
        - una concentración elevada de caracteres extraños
        - texto mayormente no alfanumérico y sin palabras
          reconocibles
    """

    if not text:
        return True

    text = _normalize_text_for_analysis(text)

    if not text:
        return True

    # --------------------------------------------------------
    # 1. CID
    # --------------------------------------------------------
    #
    # Esta es nuestra señal más fuerte.
    #
    # Ejemplo:
    #
    # @(cid:240)K(cid:240)(cid:240)
    #
    # Si aparecen suficientes tokens CID, consideramos que
    # la extracción está corrupta.
    #

    text_len = max(len(text), 1)
    cid_count = _count_cid_tokens(text)

    if cid_count > 0:

        # Un solo CID en un texto muy corto es mala señal.
        if cid_count == 1 and text_len < 100:
            return True

        # Calculamos el ratio de tokens CID.
        # Asumimos una longitud promedio de 8 chars por token, ej: "(cid:123)"
        cid_ratio = (cid_count * 8) / text_len

        # Si más del 5% del texto son tokens CID, es corrupto.
        if cid_ratio >= 0.05:
            return True

    # --------------------------------------------------------
    # 2. Caracteres sospechosos
    # --------------------------------------------------------

    suspicious_count = _count_suspicious_characters(text)

    alphanumeric_count = _count_alphanumeric_characters(text)

    if suspicious_count > 0:

        # Si prácticamente no existen caracteres normales,
        # probablemente toda la extracción está corrupta.
        if alphanumeric_count == 0:
            return True

        suspicious_ratio = suspicious_count / text_len

        # Un porcentaje alto de estos caracteres es una señal
        # fuerte de fuente mal codificada.
        if suspicious_ratio >= 0.08:
            return True

    # --------------------------------------------------------
    # 3. Texto sin palabras reconocibles
    # --------------------------------------------------------

    meaningful_words = _has_meaningful_words(text)

    if not meaningful_words:

        printable_count = _count_printable_characters(text)

        if printable_count == 0:
            return True

        alnum_ratio = alphanumeric_count / text_len

        # Texto con muy poca información alfanumérica y sin
        # palabras reconocibles.
        if alnum_ratio < 0.20:
            return True

    return False


# ============================================================
# CALIDAD DE RAW TEXT
# ============================================================


def _is_usable_raw_text(raw_text: Any) -> bool:
    """
    Determina si raw_text contiene texto digital utilizable.

    Retorna:

        True  -> texto razonablemente legible
        False -> vacío, inexistente o corrupto
    """

    if raw_text is None:
        return False

    if not isinstance(raw_text, str):
        raw_text = str(raw_text)

    text = _normalize_text_for_analysis(raw_text)

    if not text:
        return False

    return not _looks_like_corrupted_encoding(text)


# ============================================================
# CALIDAD DE SPATIAL WORDS
# ============================================================


def _is_usable_spatial_words(
    spatial_words: Any,
) -> bool:
    """
    Determina si las palabras espaciales contienen texto
    razonablemente legible.

    NO basta con que spatial_words tenga elementos.

    Esto es precisamente lo que corrige el problema original.

    Un PDF con:

        [
            {"text": "ˆ(cid:228)¯(cid:213)..."},
            {"text": "(cid:217)(cid:133)..."}
        ]

    tiene palabras espaciales, pero esas palabras NO son
    evidencia suficiente de un PDF digital utilizable.
    """

    if not spatial_words:
        return False

    valid_texts: list[str] = []

    for word in spatial_words:

        if not isinstance(word, dict):
            continue

        text = word.get("text")

        if not isinstance(text, str):
            continue

        text = text.strip()

        if not text:
            continue

        valid_texts.append(text)

    if not valid_texts:
        return False

    # Unimos una muestra representativa de las palabras.
    #
    # No necesitamos analizar absolutamente todo el documento
    # para detectar una corrupción evidente.
    sample = " ".join(valid_texts[:500])

    return _is_usable_raw_text(sample)


# ============================================================
# DETECCIÓN PRINCIPAL
# ============================================================


def detect_document_type(document: Any) -> DocumentType:
    """
    Determina si un documento PDF contiene texto digital
    utilizable o si debe considerarse un documento que
    necesita OCR.

    La detección contempla tres casos:

    1. PDF digital normal
       -------------------
       raw_text y/o spatial_words contienen texto legible.

    2. PDF imagen / escaneado
       ----------------------
       No existe texto extraíble.

    3. PDF con extracción corrupta
       ----------------------------
       Existe texto, pero la codificación de la fuente PDF
       produce basura como:

           (cid:240)
           @(cid:240)K(cid:240)(cid:240)
           ˆ(cid:228)¯(cid:213)ª
           ˜¯ª`(cid:211)

       En este caso NO se considera PDF_DIGITAL.

       Se clasifica como PDF_IMAGEN para que el pipeline
       posterior pueda enviarlo a OCR.

    IMPORTANTE
    ----------
    El detector NO intenta reparar la codificación.

    Su responsabilidad es solamente decidir:

        ¿El texto extraído es confiable?

    Si la respuesta es NO:

        -> PDF_IMAGEN
        -> OCR posteriormente
    """

    # ========================================================
    # 1. RAW TEXT
    # ========================================================

    raw_text = getattr(
        document,
        "raw_text",
        None,
    )

    raw_text_ok = _is_usable_raw_text(
        raw_text
    )

    if raw_text_ok:
        return DocumentType.PDF_DIGITAL

    # ========================================================
    # 2. SPATIAL WORDS
    # ========================================================

    spatial_words = getattr(
        document,
        "spatial_words",
        None,
    )

    spatial_words_ok = _is_usable_spatial_words(
        spatial_words
    )

    if spatial_words_ok:
        return DocumentType.PDF_DIGITAL

    # ========================================================
    # 3. SIN TEXTO UTILIZABLE
    # ========================================================
    #
    # Aquí entran:
    #
    #   - PDFs escaneados
    #   - PDFs basados en imágenes
    #   - PDFs cuya fuente está mal codificada
    #   - PDFs cuya extracción produce basura
    #
    # Para el pipeline todos tienen la misma consecuencia:
    #
    #                    OCR
    #
    # ========================================================

    return DocumentType.PDF_IMAGEN


# ============================================================
# HELPERS PÚBLICOS
# ============================================================


def is_digital_pdf(document: Any) -> bool:
    """
    Indica si el documento contiene texto digital utilizable.
    """

    return (
        detect_document_type(document)
        == DocumentType.PDF_DIGITAL
    )


def is_image_pdf(document: Any) -> bool:
    """
    Indica si el documento debe tratarse mediante OCR.

    Esto incluye:

        - PDF imagen
        - PDF escaneado
        - PDF con extracción corrupta
    """

    return (
        detect_document_type(document)
        == DocumentType.PDF_IMAGEN
    )