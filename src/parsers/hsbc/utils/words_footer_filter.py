from typing import List, Dict, Any


# ============================================================
# CONFIGURACION FOOTER BBVA
# ============================================================

FOOTER_MIN_Y = 750

FOOTER_START_WORDS = {
    "BBVA",
    "MEXICO,",
    "MEXICO",
    "R.F.C.",
    "RFC",
    "BBA830831LJ2",
    "GAT",
}


# ============================================================
# DETECTAR INICIO FOOTER EN UNA PAGINA
# ============================================================


def find_footer_start(
    words: List[Dict[str, Any]]
) -> Dict[int, float]:
    """
    Detecta la coordenada top donde inicia
    el footer por página.

    Retorna:

    {
        pagina: top_inicio_footer
    }

    Ejemplo:

    {
        1: 752.36,
        8: 764.24
    }

    """

    footer_pages = {}


    # Agrupar por página

    pages = {}

    for word in words:

        page = word.get(
            "page",
            1
        )

        pages.setdefault(
            page,
            []
        ).append(word)



    for page, page_words in pages.items():


        # Solo revisamos zona inferior

        candidates = [
            w
            for w in page_words
            if w.get("top", 0) >= FOOTER_MIN_Y
        ]


        if not candidates:
            continue



        # Orden vertical

        candidates.sort(
            key=lambda w: (
                w.get("top",0),
                w.get("x0",0)
            )
        )


        # Buscar patrón:
        # alguna palabra característica
        # en la zona inferior izquierda

        for word in candidates:

            text = (
                word.get("text","")
                .strip()
                .upper()
            )

            x0 = word.get(
                "x0",
                0
            )

            top = word.get(
                "top",
                0
            )


            if (
                text in FOOTER_START_WORDS
                and x0 < 50
            ):

                footer_pages[page] = top
                break



    return footer_pages



# ============================================================
# REMOVER FOOTER
# ============================================================


def remove_bbva_footer(
    words: List[Dict[str,Any]]
) -> List[Dict[str,Any]]:
    """
    Elimina únicamente el footer BBVA.

    Regla:
    - detecta inicio del footer por coordenadas
    - elimina desde esa línea hasta abajo
    - conserva todo lo anterior intacto
    """


    footer_starts = find_footer_start(
        words
    )


    if not footer_starts:
        return words



    cleaned = []


    for word in words:


        page = word.get(
            "page",
            1
        )

        top = word.get(
            "top",
            0
        )


        if page in footer_starts:


            footer_top = footer_starts[page]


            # cortar todo desde inicio footer

            if top >= footer_top:
                continue



        cleaned.append(
            word
        )


    return cleaned