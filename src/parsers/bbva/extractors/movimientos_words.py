
from typing import List, Dict, Any
import re
from models.movimiento import Movimiento
from parsers.bbva.utils.words_footer_filter import remove_bbva_footer
from parsers.bbva.utils.words_resume_filter import remove_after_movimientos

# ============================================================
# CONFIGURACION DE COLUMNAS BBVA
# ============================================================

COL_FECHA_OPERACION = (10, 55)
COL_FECHA_LIQUIDACION = (55, 100)

COL_CONCEPTO = (100, 315)

COL_CARGO = (380, 422)

COL_ABONO = (422, 463)

COL_SALDO_OPERACION = (463, 535)

COL_SALDO_LIQUIDACION = (535, 610)

COL_REFERENCIA_VALUE = (365, 445)

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
    column
) -> str:

    words = words_in_column(
        line,
        column[0],
        column[1]
    )

    return " ".join(words).strip()



def parse_amount(value:str)->float:

    if not value:
        return 0.0


    value = (
        value
        .replace(",","")
        .strip()
    )


    try:
        return float(value)

    except:

        return 0.0



def is_start_movement(line):

    fecha = column_text(
        line,
        COL_FECHA_OPERACION
    )


    return (
        len(fecha)==6
        and "/" in fecha
    )



# ============================================================
# EXTRACCION DE CAMPOS PRINCIPALES
# ============================================================


def extract_fecha_operacion(line):

    return column_text(
        line,
        COL_FECHA_OPERACION
    )



def extract_fecha_liquidacion(line):

    return column_text(
        line,
        COL_FECHA_LIQUIDACION
    )



def extract_concepto(lines):

    contenido=[]

    for line in lines:

        texto = column_text(
            line,
            COL_CONCEPTO
        )

        if texto:

            contenido.append(texto)

    return "\n".join(contenido).strip()



def extract_cargo(line):

    texto = column_text(
        line,
        COL_CARGO
    )

    return parse_amount(texto)



def extract_abono(line):

    texto = column_text(
        line,
        COL_ABONO
    )

    return parse_amount(texto)



def extract_saldo_operacion(line):

    texto = column_text(
        line,
        COL_SALDO_OPERACION
    )

    return parse_amount(texto)



def extract_saldo_liquidacion(line):

    texto = column_text(
        line,
        COL_SALDO_LIQUIDACION
    )

    return parse_amount(texto)



def extract_referencia(lines: List[List[Dict[str, Any]]]) -> str | None:
    """
    Busca la referencia en las líneas de un movimiento.
    BBVA la coloca en una línea debajo del concepto principal,
    alineada a una columna específica.
    """
    for line in lines:
        # Buscamos la etiqueta "Referencia" para confirmar que estamos en la línea correcta.
        label = column_text(line, (315, 365)).lower()
        if "referencia" in label:
            # Si encontramos la etiqueta, extraemos el valor de la columna de al lado.
            ref_value = column_text(line, COL_REFERENCIA_VALUE)
            if ref_value:
                return ref_value

    return None



# ============================================================
# FUTURO:
# CAMPOS EXTRAIDOS DESDE CONCEPTO
# ============================================================



def extract_beneficiario_from_concepto(concepto: str) -> str | None:
    """
    Extrae el nombre del beneficiario del concepto.
    (Implementación futura)
    """
    return None



def extract_rfc_from_concepto(concepto: str) -> str | None:
    """
    Extrae el RFC del texto del concepto.
    Maneja RFCs que pueden tener espacios en medio.
    Ej: "RFC: PPL 961114GZ1" -> "PPL961114GZ1"
    """
    # Expresión regular para un RFC de persona física (13) o moral (12)
    # Permite un espacio opcional en medio, común en OCR.
    match = re.search(
        r"RFC:\s*([A-Z&Ñ]{3,4}\s?\d{6}[A-Z0-9]{3})",
        concepto,
        re.IGNORECASE
    )
    if match:
        # Limpiamos el espacio del RFC si existe
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
    # Busca un patrón como 16:12 o 9:45
    match = re.search(r"(\d{1,2}:\d{2})", concepto)
    if match:
        return match.group(1)
    return None



# ============================================================
# CONSTRUCTOR MOVIMIENTO
# ============================================================


def build_movimiento(block):


    primera_linea = block[0]


    concepto = extract_concepto(block)


    cargo = extract_cargo(
        primera_linea
    )


    abono = extract_abono(
        primera_linea
    )


    tipo = None

    if cargo > 0:

        tipo="CARGO"


    elif abono > 0:

        tipo="ABONO"


    referencia = extract_referencia(block)



    return Movimiento(

        fecha_operacion=
            extract_fecha_operacion(
                primera_linea
            ),


        fecha_liquidacion=
            extract_fecha_liquidacion(
                primera_linea
            ),


        concepto=concepto,


        tipo_operacion=tipo,


        cargo=cargo,


        abono=abono,


        saldo_operacion=
            extract_saldo_operacion(
                primera_linea
            ),


        saldo_liquidacion=
            extract_saldo_liquidacion(
                primera_linea
            ),


        referencia=referencia,


        autorizacion=
            extract_auth_from_concepto(
                concepto
            ),


        beneficiario=
            extract_beneficiario_from_concepto(
                concepto
            ),


        cuenta_beneficiario=None,


        clabe_beneficiario=None,


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


        concepto_original=concepto

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

    #Se elimina el pie de página
    words = remove_bbva_footer(words)

    #Se elimina todo lo que viene despues del ultimo movimiento
    words = remove_after_movimientos(words)

    lines = group_words_into_lines(
        words
    )


    movimientos=[]


    current=[]


    for line in lines:


        if is_start_movement(line):


            if current:

                movimientos.append(
                    build_movimiento(
                        current
                    )
                )


            current=[line]


        else:


            if current:

                current.append(line)



    if current:

        movimientos.append(
            build_movimiento(
                current
            )
        )



    return movimientos