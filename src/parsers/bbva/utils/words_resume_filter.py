from typing import List, Dict, Any


# ============================================================
# CONFIGURACION
# ============================================================

LINE_TOLERANCE = 2.0
X_TOLERANCE = 20.0


# ============================================================
# BUSCAR "TOTAL DE MOVIMIENTOS"
# ============================================================


def find_movimientos_end(
    words: List[Dict[str, Any]]
):
    """
    Encuentra el inicio del bloque:
    
    Total de Movimientos

    Retorna:
        {
            "page": int,
            "top": float
        }

    """

    # ordenar por página, y, x

    ordered = sorted(
        words,
        key=lambda w: (
            w.get("page", 1),
            w.get("top", 0),
            w.get("x0", 0)
        )
    )


    for i, word in enumerate(ordered):

        text = (
            word.get("text","")
            .strip()
            .upper()
        )


        if text != "TOTAL":
            continue


        page = word.get(
            "page",
            1
        )

        top = word.get(
            "top",
            0
        )

        x = word.get(
            "x0",
            0
        )


        found_de = False
        found_mov = False


        # buscar las siguientes palabras

        for next_word in ordered[i+1:]:

            # ya cambiamos de página
            if next_word.get("page",1) != page:
                break


            next_top = next_word.get(
                "top",
                0
            )


            next_x = next_word.get(
                "x0",
                0
            )


            # debe estar en la misma línea

            if abs(next_top - top) > LINE_TOLERANCE:
                continue


            next_text = (
                next_word.get("text","")
                .strip()
                .upper()
            )


            # palabra siguiente "DE"

            if (
                not found_de
                and next_text == "DE"
                and next_x > x
                and next_x - x < X_TOLERANCE * 3
            ):
                found_de = True
                continue


            # palabra siguiente "MOVIMIENTOS"

            if (
                found_de
                and next_text == "MOVIMIENTOS"
            ):
                found_mov = True
                break



        if found_mov:

            return {
                "page": page,
                "top": top
            }


    return None



# ============================================================
# ELIMINAR TODO DESPUES DEL FINAL DE MOVIMIENTOS
# ============================================================


def remove_after_movimientos(
    words: List[Dict[str,Any]]
) -> List[Dict[str,Any]]:
    """
    Conserva únicamente los movimientos.

    Elimina:
    - Total de Movimientos
    - totales
    - avisos
    - leyendas
    - páginas posteriores
    """


    cut = find_movimientos_end(
        words
    )


    # si no encontró nada
    # no modifica

    if not cut:
        return words



    cut_page = cut["page"]
    cut_top = cut["top"]



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


        # páginas posteriores completas fuera

        if page > cut_page:
            continue


        # misma página:
        # borrar desde Total de Movimientos

        if (
            page == cut_page
            and top >= cut_top
        ):
            continue


        cleaned.append(
            word
        )


    return cleaned