"""La relectura usa píxeles y consenso; nunca cifras de la conciliación."""

from copy import deepcopy

import pytest
from PIL import Image, ImageDraw

from readers.banamex_money_rescue import is_banamex_cover, rescue_money_cells


def words():
    return [
        dict(text="CONCEPTO", x0=90, x1=140, top=80, bottom=90, page=1),
        dict(text="RETIROS", x0=330, x1=370, top=80, bottom=90, page=1),
        dict(text="DEPOSITOS", x0=420, x1=460, top=80, bottom=90, page=1),
        dict(text="SALDO", x0=510, x1=540, top=80, bottom=90, page=1),
        dict(text="25.00", x0=350, x1=380, top=120, bottom=130, page=1),
    ]


def test_consensus_recovers_a_clipped_prefix_from_expanded_image_cells():
    image = Image.new("RGB", (1200, 1600), "white")
    # Píxeles del prefijo que la caja original dejó fuera, con escala PDF 2:1.
    ImageDraw.Draw(image).rectangle((694, 243, 697, 257), fill="red")
    source = words()
    original = deepcopy(source)

    def recognize(crops):
        assert len(crops) == 2
        assert all((255, 0, 0) in list(crop.get_flattened_data()) for crop in crops)
        return [("125.00", 0.99), ("125.00", 0.98)]

    result, count = rescue_money_cells(image, source, 600, recognize)
    assert count == 1
    assert result[-1]["text"] == "125.00"
    assert result[-1]["x0"] < source[-1]["x0"]
    assert source == original


@pytest.mark.parametrize(
    "readings",
    [
        [("125.00", 0.99), ("25.00", 0.99)],
        [("125.00", 0.96), ("125.00", 0.99)],
        [("35.00", 0.99), ("35.00", 0.99)],
        [("25.00", 0.99), ("25.00", 0.99)],
        [("-125.00", 0.99), ("-125.00", 0.99)],
        [("ABONO", 0.99), ("ABONO", 0.99)],
        [("125.00", float("nan")), ("125.00", 0.99)],
        [("125.00", None), ("125.00", 0.99)],
        [],
    ],
)
def test_conflicts_low_confidence_and_changed_digits_keep_the_original(readings):
    source = words()
    image = Image.new("RGB", (600, 800), "white")
    result, count = rescue_money_cells(image, source, 600, lambda crops: readings)
    assert count == 0
    assert result == source


def test_other_sections_and_unavailable_recognizer_keep_first_pass():
    source = [words()[-1]]
    image = Image.new("RGB", (600, 800), "white")

    def unavailable(crops):
        raise RuntimeError("reconocedor no disponible")

    assert rescue_money_cells(image, source, 600, unavailable) == (source, 0)
    assert rescue_money_cells(image, words(), 600, unavailable) == (words(), 0)


def test_gate_requires_banamex_and_the_specific_account_cover():
    text = "Citibanamex Numero de contrato Nunero de cuenta de cheques CLABE Saldo al corte"
    source = [{"text": token} for token in text.split()]
    assert is_banamex_cover(source)
    assert not is_banamex_cover([{"text": "Santander"}] + source[1:])
    assert not is_banamex_cover([{"text": "Banamex"}, {"text": "MiCuenta"}])
