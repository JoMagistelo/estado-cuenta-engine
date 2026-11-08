import tempfile
import unittest
import zipfile
from pathlib import Path

from cep_core import exportar, xlsx_hojas
from cep_importador import procesar_zip
from cep_paquete import exportar_zip_cep

XML = b'''<?xml version="1.0" encoding="UTF-8"?>
<CEP><FechaOperacion>2025-04-28</FechaOperacion>
<ClaveRastreo>RASTREO-PRUEBA-001</ClaveRastreo><Monto>100.00</Monto>
<Ordenante><Nombre>ORDENANTE PRUEBA</Nombre><RFC>AAAA010101AAA</RFC></Ordenante>
<Beneficiario><Nombre>BENEFICIARIO PRUEBA</Nombre><RFC>BBBB010101BBB</RFC>
<Cuenta>012123456789012346</Cuenta></Beneficiario></CEP>'''


class TestFlujoUnico(unittest.TestCase):
    def registro(self, num, cuenta='012123456789012346', listo=True):
        clave = f'RASTREO-PRUEBA-00{num}'
        return dict(fila_excel=str(num), id_estado='1', num_movimiento=str(num),
                    tipo='ENVIADO', fecha='2025-04-28', monto='100.00',
                    clave_rastreo=clave, referencia='1234567',
                    emisor='40002', receptor='40012',
                    cuenta_beneficiaria=cuenta,
                    nombre_beneficiario='ALIAS NO VERIFICADO',
                    estado='LISTO' if listo else 'PENDIENTE',
                    observacion='' if listo else 'Cuenta destino no disponible',
                    linea_lote=f'2025-04-28,{clave},40002,40012,{cuenta},100.00'
                    if listo else '')

    def test_ciclo_excel_txt_a_zip_final_y_estados(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            salida = d/'solicitud'
            regs = [self.registro(1), self.registro(2), self.registro(3, cuenta='', listo=False)]
            generado = exportar(regs, salida)
            self.assertEqual(generado['lotes'], 1)
            self.assertEqual(len(list(salida.glob('*.xlsx'))), 1)
            self.assertEqual(len(list(salida.glob('*.csv'))), 0)
            txt = (salida/'lote_001.txt').read_text(encoding='utf-8').splitlines()
            self.assertEqual(len(txt), 2)
            original = xlsx_hojas(salida/'resultado_CEP.xlsx')
            self.assertEqual(len(original['SPEI'])-1, 3)
            self.assertEqual(len(original['Datos CEP'])-1, 0)

            with zipfile.ZipFile(d/'banxico.zip','w') as z:
                z.writestr('001.xml', XML)
                z.writestr('001.pdf', b'%PDF-1.4\nSINTETICO')
                z.writestr('resumen.txt',
                           '2025-04-29,RASTREO-PRUEBA-002,No se pudo localizar la transferencia')
            proc = procesar_zip(d/'banxico.zip', salida/'resultado_CEP.xlsx', d/'resultado')
            self.assertEqual(proc['resumen']['Registros en Datos CEP'], 1)
            self.assertEqual(proc['resumen']['Registros con PDF'], 1)
            libro = xlsx_hojas(d/'resultado'/'resultado_CEP.xlsx')
            self.assertEqual(len(libro['SPEI'])-1, 3)
            cabecera = libro['SPEI'][0]
            status_col = cabecera.index('resultado_cep')
            estados = [r[status_col] for r in libro['SPEI'][1:]]
            self.assertEqual(estados, ['EXITO', 'FALLO_BUSQUEDA_CEP', 'NO_CONSULTABLE'])
            self.assertIn('BBBB010101BBB', libro['Datos CEP'][1])
            self.assertNotIn('ALIAS NO VERIFICADO', libro['Datos CEP'][1])
            paquete = exportar_zip_cep(d/'resultado', d/'CEP_BANXICO_FINAL.zip')
            self.assertEqual(paquete['pdf_vinculados'],1)
            self.assertEqual(paquete['registros_cep'],1)
            with zipfile.ZipFile(d/'CEP_BANXICO_FINAL.zip') as z:
                self.assertEqual(z.namelist().count('resultado_CEP.xlsx'),1)


if __name__ == '__main__':
    unittest.main()
