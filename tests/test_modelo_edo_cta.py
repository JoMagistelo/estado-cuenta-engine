from models.datos_cuenta import DatosCuenta
from models.otros_productos import OtrosProductos
from models.resumen_financiero import ResumenFinanciero
from models.movimiento import Movimiento
from models.estado_cuenta import EstadoCuenta


datos = DatosCuenta(
    producto_principal="Cuenta Maestra",
    periodo_inicio="01/01/2026",
    periodo_fin="31/01/2026",
    fecha_corte="31/01/2026",
    numero_cuenta="123456789",
    numero_cliente="987654",
    clabe="012345678901234567",
    nombre_cliente="CLIENTE PRUEBA",
    rfc="XAXX010101000"
)


otros_productos = OtrosProductos(
    contrato="000123456",
    producto="Cuenta Maestra",
    tasa_interes_anual=5.5,
    gat_nominal_anual=5.7,
    gat_real_anual=4.2,
    total_comisiones=0
)


resumen = ResumenFinanciero(
    saldo_promedio=10000,
    dias_periodo=31,
    tasa_bruta_anual=5.5,
    saldo_promedio_gravable=9000,
    intereses_a_favor=40,
    isr_retenido=8,
    cheques_pagados=0,
    manejo_cuenta=0,
    cargos_objetados=0,
    abonos_objetados=0,
    saldo_anterior=9000,
    depositos_abonos=5000,
    retiros_cargos=3000,
    saldo_final=11000,
    saldo_promedio_minimo_mensual=8000,
    saldo_global=11000
)


movimiento = Movimiento(
    fecha_operacion="10/01/2026",
    fecha_liquidacion=None,

    concepto="TRANSFERENCIA SPEI RECIBIDA",
    tipo_operacion="DEPOSITO",

    cargo=0,
    abono=5000,
    saldo_liquidacion=11000,

    referencia="123456",
    autorizacion=None,

    beneficiario=None,
    cuenta_beneficiario=None,
    clabe_beneficiario=None,

    rfc=None,

    sucursal=None,
    caja=None,
    hora_operacion=None,

    concepto_original="TRANSFERENCIA SPEI RECIBIDA"
)


estado = EstadoCuenta(
    datos_cuenta=datos,
    otros_productos=otros_productos,
    resumen_financiero=resumen,
    movimientos=[movimiento]
)


print("Estado de cuenta creado correctamente:")
print("------------------------------------")
print(estado)

print("\nMovimientos:")
for movimiento in estado.movimientos:
    print(movimiento.concepto, movimiento.abono)