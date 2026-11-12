from PIL import Image, ImageDraw

from readers import banamex_tabular_ocr
from readers.banamex_tabular_ocr import (
    Cell,
    TableGrid,
    _account_digit_crop,
    _recover_tesseract_clabes,
    _select_money,
)


def _ruled_table(scale=1):
    width, height = 1000 * scale, 1480 * scale
    image = Image.new("L", (width, height), 255)
    pen = ImageDraw.Draw(image)
    top = 165 * scale
    pitch = 23 * scale
    for row in range(1, 31, 2):
        y = top + row * pitch
        pen.rectangle((26 * scale, y, 910 * scale, y + pitch - 1), fill=190)
    for x in (110, 486, 615, 758):
        pen.line((x * scale, top, x * scale, top + 30 * pitch), fill=0, width=3 * scale)
    return image, pitch


def test_detects_scan_rules_and_row_pitch_at_two_resolutions():
    for scale in (1, 2):
        image, pitch = _ruled_table(scale)
        grid = TableGrid.detect(image)
        assert grid is not None
        assert abs(grid.pitch - pitch) < 1.5 * scale
        assert all(
            abs(actual - expected * scale) < 5 * scale
            for actual, expected in zip(grid.dividers, (110, 486, 615, 758))
        )
    assert TableGrid.detect(Image.new("L", image.size, 255)) is None


def test_balance_chooses_an_observed_amount_only():
    dummy = Image.new("L", (10, 10), 255)
    cells = [
        Cell(0, 4, (0, 0, 10, 10), dummy),
        Cell(1, 2, (0, 0, 10, 10), dummy),
        Cell(1, 4, (0, 0, 10, 10), dummy),
    ]
    initial = [("100.00", 98), ("80.00", 99), ("80.00", 97)]
    readings = initial.copy()
    end, retry = _select_money(cells, readings, [[v] for v in initial], None)
    assert end == 8000
    assert retry == {0, 1, 2}
    assert readings[1][0] == "80.00"

    options = [[v] for v in initial]
    options[1].append(("20.00", 91))
    end, retry = _select_money(cells, readings, options, None)
    assert end == 8000
    assert retry == set()
    assert readings[1][0] == "20.00"


def test_clabe_recovery_requires_matching_crops_and_preserves_reference(monkeypatch):
    image = Image.new("L", (10, 10), 255)
    cell = Cell(0, 1, (0, 0, 10, 10), image, image)
    original = ("002000000000000000 REF. 1234567", 32.0)
    readings = [original]
    monkeypatch.setattr(banamex_tabular_ocr, "_account_digit_crop", lambda *args: cell)

    def disagree(cells, *, local, digits, alternate=False):
        assert cells == [cell] and local and digits
        return [("002000000000000000" if alternate else "002000000000000008", 80)]

    _recover_tesseract_clabes(image, [cell], [(0, "account")], readings, 15, disagree)
    assert readings == [original]

    def agree(cells, *, local, digits, alternate=False):
        assert cells == [cell] and local and digits
        return [("002000000000000008", 80)]

    _recover_tesseract_clabes(image, [cell], [(0, "account")], readings, 15, agree)
    assert readings == [("002000000000000008 REF. 1234567", 80)]


def test_clabe_crop_keeps_digit_spacing_and_stops_before_reference():
    image = Image.new("L", (440, 30), 255)
    pen = ImageDraw.Draw(image)
    for x in range(0, 360, 20):
        pen.rectangle((x, 3, x + 10, 26), fill=0)
    pen.rectangle((380, 3, 420, 26), fill=0)
    cell = Cell(0, 1, (0, 0, 440, 30), image)

    crop = _account_digit_crop(image, cell, pitch=50)

    assert crop is not None
    assert crop.image.width == 706
    assert crop.alternate is not None
