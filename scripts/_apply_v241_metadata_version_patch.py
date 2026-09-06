from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/readers/paddleocr_pdf_reader.py",
    """        doctop_offset = 0.0

        for physical_index in range(start_page, len(pdf)):
""",
    """        doctop_offset = 0.0
        backend_recovered = False

        for physical_index in range(start_page, len(pdf)):
""",
    "reader recovery state",
)
replace_once(
    "src/readers/paddleocr_pdf_reader.py",
    """            if recovered_backend:
                config = {**config, \"enable_mkldnn\": False}

            all_words.extend(words)
""",
    """            if recovered_backend:
                config = {**config, \"enable_mkldnn\": False}
                backend_recovered = True

            all_words.extend(words)
""",
    "reader recovery state update",
)
replace_once(
    "src/readers/paddleocr_pdf_reader.py",
    '                "mkldnn_backend_recovered": not config["enable_mkldnn"] and cls.DEFAULT_ENABLE_MKLDNN,\n',
    '                "mkldnn_backend_recovered": backend_recovered,\n',
    "reader recovery metadata",
)

replace_once(
    "src/readers/cancelable_ocr_reader.py",
    """    doctop_offset = 0.0

    for physical_index in range(start_page, len(pdf)):
        _raise_if_cancelled(cancel_event)
        page = pdf[physical_index]
        page_width, page_height = page.get_size()
        bitmap = page.render(scale=dpi / 72.0)
""",
    """    doctop_offset = 0.0
    backend_recovered = False

    for physical_index in range(start_page, len(pdf)):
        _raise_if_cancelled(cancel_event)
        page = pdf[physical_index]
        page_width, page_height = page.get_size()
        bitmap = page.render(scale=dpi / 72.0)
""",
    "cancelable recovery state",
)
replace_once(
    "src/readers/cancelable_ocr_reader.py",
    """        if recovered_backend:
            config = {**config, \"enable_mkldnn\": False}
        _raise_if_cancelled(cancel_event)
""",
    """        if recovered_backend:
            config = {**config, \"enable_mkldnn\": False}
            backend_recovered = True
        _raise_if_cancelled(cancel_event)
""",
    "cancelable recovery state update",
)
replace_once(
    "src/readers/cancelable_ocr_reader.py",
    '            "mkldnn_backend_recovered": not config["enable_mkldnn"] and PaddleOCRPDFReader.DEFAULT_ENABLE_MKLDNN,\n',
    '            "mkldnn_backend_recovered": backend_recovered,\n',
    "cancelable recovery metadata",
)

replace_once("app/main_flet.py", "APP_VERSION = '2.4'", "APP_VERSION = '2.4.1'", "Flet version")
replace_once("app/main_streamlit.py", "APP_VERSION = '2.4'", "APP_VERSION = '2.4.1'", "Streamlit version")
replace_once("pyproject.toml", 'version = "2.4.0"', 'version = "2.4.1"', "package version")
replace_once("EstadoCuentaEngine.spec", "APP_VERSION = (2, 4, 0, 0)", "APP_VERSION = (2, 4, 1, 0)", "EXE version")
replace_once("scripts/build_windows_release.ps1", '[string]$Version = "2.4.0"', '[string]$Version = "2.4.1"', "build version")
replace_once(".github/workflows/quality.yml", '--version "2.4.0"', '--version "2.4.1"', "quality version")
replace_once(".github/workflows/tics-desktop-release.yml", '--version "2.4.0"', '--version "2.4.1"', "TICS version")
