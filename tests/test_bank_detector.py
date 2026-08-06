from detectors.bank_detector import identify_bank


def test_bbva_by_clabe_spaces():
    """
    Debe detectar BBVA aunque la CLABE venga separada
    por espacios como ocurre en PDFs/OCR.
    """

    texto = """
    Datos de cuenta

    CLABE:
    012 180 01576395513 3
    """

    resultado = identify_bank(texto)

    print(f"BBVA detectado: {resultado}")

    assert resultado == "BBVA México"


def test_scotiabank_by_clabe():
    """
    Debe detectar Scotiabank usando el prefijo CLABE 044.
    """

    texto = """
    Estado de cuenta

    CLABE 044743115054506917
    """

    resultado = identify_bank(texto)

    print(f"Scotiabank detectado: {resultado}")

    assert resultado == "Scotiabank"


def test_unknown_bank():
    """
    Una CLABE con prefijo inexistente debe regresar
    'Desconocido'.
    """

    texto = """
    CLABE
    999999999999999999
    """

    resultado = identify_bank(texto)

    print(f"Banco desconocido: {resultado}")

    assert resultado == "Desconocido"


def test_empty_text():
    """
    No debe fallar si recibe texto vacío.
    """

    resultado = identify_bank("")

    print(f"Texto vacío: {resultado}")

    assert resultado == "Desconocido"


def test_bbva_realistic_document():
    """
    Simula un fragmento más parecido a un estado de cuenta real.
    """

    texto = """
    BBVA MÉXICO

    Cuenta:
    1234567890

    CLABE INTERBANCARIA:
    012180015763955133

    Cliente:
    JUAN PEREZ
    """

    resultado = identify_bank(texto)

    print(f"BBVA documento real: {resultado}")

    assert resultado == "BBVA México"


if __name__ == "__main__":

    test_bbva_by_clabe_spaces()
    test_scotiabank_by_clabe()
    test_unknown_bank()
    test_empty_text()
    test_bbva_realistic_document()

    print("¡Pruebas de Bank Detector OK!")