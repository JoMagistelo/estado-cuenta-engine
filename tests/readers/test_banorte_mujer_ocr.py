from PIL import Image, ImageDraw

from readers.banorte_mujer_ocr import MujerOCR, MujerTable, _money_path


def test_table_detects_balance_rows_and_stops_at_the_next_section():
    image = Image.new("L", (1000, 1294), 255)
    pen = ImageDraw.Draw(image)
    pen.rectangle((85, 154, 913, 156), fill=0)
    for y in (175, 195, 240):
        pen.rectangle((869, y, 907, y + 6), fill=0)
    pen.rectangle((85, 270, 913, 282), fill=0)
    pen.rectangle((869, 297, 907, 303), fill=0)

    table = MujerTable.detect(image)

    assert table is not None
    assert len(table.rows) == 3
    assert table.bottom == 270
    assert MujerTable.detect(Image.new("L", image.size, 255)) is None


def test_reconciliation_selects_an_amount_observed_by_ocr():
    readings = {(0, 3): [("80.00", 99), ("20.00", 91)], (0, 4): [("80.00", 97)]}
    rows, weak = _money_path(readings, size=1, opening=10000)
    assert rows[0][1][0] == 2000
    assert weak == set()


def test_incomplete_supplemental_reading_returns_original_words():
    state = MujerOCR()
    raw = [{"page": 1, "text": "portada"}, {"page": 2, "text": "original"}]
    state.corrected[2] = [{"page": 2, "text": "relectura"}]
    state.pages[2] = {"rows": [110]}
    state.failed = True
    assert state.finish(raw) == (raw, {})
