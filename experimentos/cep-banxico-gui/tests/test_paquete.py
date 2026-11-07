import csv
import tempfile
import unittest
import zipfile
from pathlib import Path

from cep_importador import procesar_zip
from cep_paquete import exportar_zip_cep

XML = b'''<?xml version="1.0" encoding="UTF-8"?>
<CEP><FechaOperacion>2025-04-28</FechaOperacion><ClaveRastreo>TEST-123456</ClaveRastreo>
<Monto>100.00</Monto><Ordenante><Nombre>ORDENANTE PRUEBA</Nombre><RFC>AAAA010101AAA</RFC></Ordenante>
<Beneficiario><Nombre>BENEFICIARIO PRUEBA</Nombre><RFC>BBBB010101BBB</RFC></Beneficiario></CEP>'''


class TestPaqueteFinal(unittest.TestCase):
    def _caso(self, base):
        with (base/'consultas.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['clave_rastreo','fecha','monto','cuenta_beneficiaria',
                                            'nombre_beneficiario','tipo','fila_excel','id_estado','estado'])
            w.writeheader()
            w.writerow({'clave_rastreo':'TEST-123456','fecha':'2025-04-28','monto':'100.00',
                        'cuenta_beneficiaria':'012123456789012346','nombre_beneficiario':'ALIAS',
                        'tipo':'ENVIADO','fila_excel':'1','id_estado':'1','estado':'LISTO'})
        with zipfile.ZipFile(base/'banxico.zip','w') as z:
            z.writestr('001.xml',XML)
            z.writestr('001.pdf',b'%PDF-1.4\nPDF de prueba')
            z.writestr('002.xml',XML.replace(b'TEST-123456',b'TEST-654321'))
        procesar_zip(base/'banxico.zip',base/'consultas.csv',base/'organizados')

    def test_empaqueta_pdf_xml_y_excel_con_conteos_exclusivos(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self._caso(root)
            result=exportar_zip_cep(root/'organizados',root/'CEP_FINAL.zip')
            self.assertEqual(result['registros_cep'],2)
            self.assertEqual(result['pdf_vinculados'],1)
            self.assertEqual(result['xml_sin_pdf'],1)
            with zipfile.ZipFile(root/'CEP_FINAL.zip') as z:
                items=z.namelist()
                self.assertIn('resultado_CEP.xlsx',items)
                self.assertEqual(len([n for n in items if n.startswith('PDF/') and n.endswith('.pdf')]),1)
                self.assertEqual(len([n for n in items if n.startswith('XML/') and n.endswith('.xml')]),2)

    def test_no_permita_exportar_si_falta_un_pdf(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self._caso(root)
            next((root/'organizados'/'PDF').glob('*.pdf')).unlink()
            with self.assertRaises(ValueError):
                exportar_zip_cep(root/'organizados',root/'CEP_FINAL.zip')
            self.assertFalse((root/'CEP_FINAL.zip').exists())


if __name__ == '__main__':
    unittest.main()
