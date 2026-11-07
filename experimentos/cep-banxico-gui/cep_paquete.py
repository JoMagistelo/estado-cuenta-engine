"""Exportación segura de CEP oficiales ya descargados a un único ZIP final.

No descarga CEP ni automatiza verificación humana de Banxico.
"""
from __future__ import annotations
from pathlib import Path
from xml.etree import ElementTree as ET
import os
import tempfile
import zipfile

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def _text(c):
    v = c.find(NS + 'v')
    if v is not None:
        return v.text or ''
    e = c.find(NS + 'is')
    return ''.join(e.itertext()) if e is not None else ''


def _filas_cep(excel):
    with zipfile.ZipFile(excel) as f:
        wb = ET.fromstring(f.read('xl/workbook.xml'))
        sheets = wb.find(NS + 'sheets')
        if sheets is None or len(sheets) < 2 or sheets[1].get('name') != 'Datos CEP':
            raise ValueError('No se encontró la hoja Datos CEP.')
        sh = ET.fromstring(f.read('xl/worksheets/sheet2.xml'))
    data = sh.find(NS + 'sheetData')
    rr = data.findall(NS + 'row') if data is not None else []
    if not rr:
        raise ValueError('Datos CEP está vacía.')
    titles = [_text(c).strip() for c in rr[0].findall(NS+'c')]
    for name in ('tiene_pdf', 'archivo_pdf', 'archivo_xml'):
        if name not in titles:
            raise ValueError('Falta la columna ' + name)
    indices = {t: titles.index(t) for t in ('tiene_pdf','archivo_pdf','archivo_xml')}
    filas = []
    for row in rr[1:]:
        cells = row.findall(NS+'c')
        if len(cells) != len(titles):
            raise ValueError('Excel CEP con fila incompleta.')
        filas.append({k: _text(cells[i]).strip() for k, i in indices.items()})
    return filas


def exportar_zip_cep(carpeta_resultados, destino_zip):
    """Un PDF en PDF/ por cada fila Tiene PDF=SÍ, XML para todas las filas."""
    root = Path(carpeta_resultados).resolve()
    destino = Path(destino_zip).resolve()
    if destino.exists():
        raise FileExistsError('El ZIP final ya existe; cambia el nombre.')
    if root in destino.parents:
        raise ValueError('El ZIP final debe guardarse fuera de la carpeta de resultados.')
    excel = root/'resultado_CEP.xlsx'
    if not excel.is_file():
        raise FileNotFoundError('Primero procesa el ZIP oficial de Banxico.')
    fichas = _filas_cep(excel)
    pdfs = sorted((root/'PDF').glob('*.pdf')) if (root/'PDF').is_dir() else []
    xmls = sorted((root/'XML').glob('*.xml')) if (root/'XML').is_dir() else []
    con_pdf = [r for r in fichas if r['tiene_pdf'].upper() in ('SÍ','SI')]
    sin_pdf = [r for r in fichas if r['tiene_pdf'].upper() == 'NO']
    if len(con_pdf)+len(sin_pdf) != len(fichas):
        raise ValueError('La columna tiene_pdf debe contener SÍ o NO.')
    if len(con_pdf) != len(pdfs) or len(fichas) != len(xmls):
        raise ValueError('No coincide el número de PDF/XML con el Excel de CEP.')
    if {r['archivo_pdf'].replace('\\','/') for r in con_pdf} != {p.relative_to(root).as_posix() for p in pdfs}:
        raise ValueError('Los PDF no corresponden a las filas marcadas SÍ.')
    if any(r['archivo_pdf'] for r in sin_pdf):
        raise ValueError('Una fila marcada NO tiene una ruta PDF.')
    if {r['archivo_xml'].replace('\\','/') for r in fichas} != {p.relative_to(root).as_posix() for p in xmls}:
        raise ValueError('Los XML no corresponden a las filas de Datos CEP.')
    archivos = [excel]
    for folder in ('PDF','XML','REVISION'):
        d = root/folder
        if d.is_dir():
            archivos.extend(sorted(p for p in d.rglob('*') if p.is_file()))
    resumen = root/'resumen_original_banxico.txt'
    if resumen.is_file():
        archivos.append(resumen)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.cep_',suffix='.zip',dir=destino.parent,delete=False) as f:
            temp = Path(f.name)
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
            for p in archivos:
                z.write(p,p.relative_to(root).as_posix())
            z.writestr('LEEME.txt', 'Datos CEP: nombres y RFC extraídos de XML de Banxico.\\n'
                       'tiene_pdf SÍ: PDF asociado, NO: únicamente XML.\\n'
                       'REVISION: archivos incompletos o ilegibles.\\n'
                       'La herramienta no valida criptográficamente el sello.\\n')
        os.replace(temp,destino)
    finally:
        if temp and temp.exists():
            temp.unlink()
    return {'zip':str(destino),'registros_cep':len(fichas),
            'pdf_vinculados':len(pdfs),'xml_sin_pdf':len(sin_pdf)}
