import csv
import tempfile
import unittest
from pathlib import Path
from cep_core import analizar, clabe_valida, fecha_operacion, exportar, preparar, clave
from datetime import date


def clabe_ejemplo(pref='012', n='12345678901234'):
    c = pref + n
    assert len(c) == 17
    return c + str((10 - sum((int(v) * (3,7,1)[i % 3]) % 10 for i,v in enumerate(c)) % 10) % 10)


class Tests(unittest.TestCase):
    def setUp(self):
        self.destino = clabe_ejemplo()
        self.propia = clabe_ejemplo('002', '98765432101234')
        self.headers = ['id_estado','Nombre del Archivo','Banco','Fecha de Corte','No. de Movimiento',
                        'Fecha de Operación','Concepto','Cargo','Abono','Clave de Rastreo','Referencia',
                        'CLABE del Beneficiario','Tipo de Operación']
        self.cols = {clave(v):i for i,v in enumerate(self.headers)}
        self.meta = {'1': {'inicio':date(2025,4,8),'fin':date(2025,5,7),'clabe':self.propia}}

    def fila(self, **kw):
        obj = {'id_estado':1, 'Nombre del Archivo':'Banamex_Abr25.pdf','Banco':'banamex',
               'Fecha de Corte':'07/MAY/2025','No. de Movimiento':83,'Fecha de Operación':'28 ABR',
               'Concepto':'PAGO INTERBANCARIO A BBVA MEXICO RASTREO PRUEBASINTETICA0001',
               'Cargo':10000,'Abono':0,'Clave de Rastreo':'PRUEBASINTETICA0001',
               'Referencia':'0280425','CLABE del Beneficiario':self.destino, 'Tipo de Operación':''}
        obj.update(kw)
        return [obj[h] for h in self.headers]

    def test_sin_tipo_cargo(self):
        x = preparar(self.fila(),self.cols,2,self.meta)
        self.assertEqual((x['tipo'],x['estado'],x['fecha'],x['monto']),
                         ('ENVIADO','LISTO','2025-04-28','10000.00'))
        self.assertIn(',40002,40012,',x['linea_lote'])

    def test_sin_tipo_abono_usa_clabe_propia(self):
        x = preparar(self.fila(Cargo=0, Abono=220, Concepto='SPEI DE BBVA MEXICO RASTREO PRUEBASINTETICA0001',
                 **{'CLABE del Beneficiario':''}), self.cols,2,self.meta)
        self.assertEqual((x['tipo'],x['estado'],x['cuenta_beneficiaria']),('RECIBIDO','LISTO',self.propia))
        self.assertEqual((x['emisor'],x['receptor']),('40012','40002'))

    def test_fecha_cruce_anio(self):
        d=fecha_operacion('31 DIC',date(2023,12,8),date(2024,1,7),'Dic23.pdf')
        self.assertEqual(d,date(2023,12,31))

    def test_ignora_gasto(self):
        x=preparar(self.fila(Concepto='RETIRO EN CAJERO',**{'Clave de Rastreo':''}),self.cols,2,self.meta)
        self.assertIsNone(x)

    def test_excluye_clabe_invalida(self):
        x=preparar(self.fila(**{'CLABE del Beneficiario':self.destino[:-1]+'9'}),self.cols,2,self.meta)
        if self.destino[-1]!='9': self.assertEqual(x['estado'],'PENDIENTE')

    def test_csv_realista_sin_columna_tipo(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'movimientos.csv'
            h=[v for v in self.headers if v != 'Tipo de Operación']
            with p.open('w',newline='',encoding='utf-8') as f:
                w=csv.writer(f); w.writerow(h)
                w.writerow([v for n,v in zip(self.headers,self.fila()) if n!='Tipo de Operación'])
            registros,num=analizar(p)
            self.assertEqual((num,len(registros),registros[0]['estado']),(1,1,'LISTO'))
            out=exportar(registros,Path(d)/'salida')
            self.assertEqual(out['lotes'],0)
            self.assertTrue((Path(d)/'salida'/'consultas_individuales.csv').exists())

if __name__=='__main__': unittest.main()