"""Regresión: Excel debe aceptar las hojas sin reparaciones OOXML."""
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from cep_importador import crear_excel_sin_dependencias

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


class TestExcelValido(unittest.TestCase):
    def test_orden_ooxml_y_datos_cep_preservados(self):
        with tempfile.TemporaryDirectory() as d:
            archivo = Path(d) / 'resultado_CEP.xlsx'
            crear_excel_sin_dependencias(
                archivo,
                {'CEP con XML': 2, 'PDF encontrados': 1},
                [
                    {'nombre_beneficiario_cep': 'NOMBRE OFICIAL & PRUEBA',
                     'rfc_beneficiario_cep': 'ABCD010101AAA',
                     'monto_cep': '1000.20', 'tiene_pdf': 'SÍ',
                     'archivo_pdf': 'PDF/demo.pdf', 'archivo_xml': 'XML/demo.xml'},
                    {'nombre_beneficiario_cep': 'SIN PDF',
                     'rfc_beneficiario_cep': 'WXYZ010101BBB',
                     'monto_cep': '55.30', 'tiene_pdf': 'NO',
                     'archivo_xml': 'XML/otro.xml'},
                ],
                [{'clave_rastreo': 'FALLIDO', 'motivo': 'No encontrado'}],
                [{'clave_rastreo': 'ABCDEF', 'estado': 'LISTO',
                  'monto': '1000.20', 'nombre_beneficiario': 'ALIAS NO OFICIAL'}]
            )
            self.assertTrue(zipfile.is_zipfile(archivo))
            with zipfile.ZipFile(archivo) as z:
                self.assertIsNone(z.testzip())
                nombres = z.namelist()
                hojas = sorted(n for n in nombres if
                               n.startswith('xl/worksheets/sheet') and n.endswith('.xml'))
                self.assertEqual(len(hojas), 3)
                for nombre in hojas:
                    texto = z.read(nombre)
                    raiz = ET.fromstring(texto)
                    self.assertEqual(raiz.tag, NS + 'worksheet')
                    hijos = [e.tag.rsplit('}', 1)[-1] for e in raiz]
                    self.assertEqual(
                        hijos[:5],
                        ['dimension', 'sheetViews', 'sheetFormatPr', 'cols', 'sheetData'])
                    self.assertEqual(hijos[-1], 'autoFilter')
                    self.assertNotIn(b'<ns0:worksheet', texto)
                dato = z.read('xl/worksheets/sheet2.xml')
                self.assertIn('NOMBRE OFICIAL &amp; PRUEBA'.encode(), dato)
                self.assertIn(b'ABCD010101AAA', dato)
                self.assertIn('SÍ'.encode(), dato)
                self.assertIn(b'WXYZ010101BBB', dato)
                self.assertNotIn(b'ALIAS NO OFICIAL', dato)

    def test_limpia_caracteres_ilegales(self):
        with tempfile.TemporaryDirectory() as d:
            archivo = Path(d) / 'resultado_CEP.xlsx'
            crear_excel_sin_dependencias(
                archivo, {'Pruebas': 1},
                [{'nombre_beneficiario_cep': 'A\x00B\x01C\ud800D',
                  'tiene_pdf': 'NO'}],
                [], [])
            with zipfile.ZipFile(archivo) as z:
                for n in z.namelist():
                    if n.endswith('.xml'):
                        ET.fromstring(z.read(n))
                texto = z.read('xl/worksheets/sheet2.xml')
                self.assertIn(b'ABCD', texto)
                self.assertNotIn(b'\x00', texto)


if __name__ == '__main__':
    unittest.main()
