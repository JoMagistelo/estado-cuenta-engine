from __future__ import annotations

from typing import Any, Dict, List

from models.processing_result import ProcessingResult



def estado_cuenta_to_tables(
    results: list[ProcessingResult]
) -> Dict[str, List[Dict[str, Any]]]:

    """
    Convierte todos los modelos del dominio
    a tablas normalizadas estilo SQL.

    Regla:
    NO SE PIERDE NINGUNA VARIABLE DEL MODELO.
    """


    estados_cuenta = []
    otros_productos = []
    resumen_financiero = []
    movimientos = []



    for estado_id, result in enumerate(results, start=1):


        ec = result.estado_cuenta



        # =====================================================
        # DATOS CUENTA
        # =====================================================

        dc = ec.datos_cuenta


        estados_cuenta.append({

            "id_estado": estado_id,

            "archivo": result.file_name,

            "banco": result.bank_key,


            "producto_principal":
                dc.producto_principal,

            "periodo_inicio":
                dc.periodo_inicio,

            "periodo_fin":
                dc.periodo_fin,

            "fecha_corte":
                dc.fecha_corte,


            "numero_cuenta":
                dc.numero_cuenta,

            "numero_cliente":
                dc.numero_cliente,

            "clabe":
                dc.clabe,


            "nombre_cliente":
                dc.nombre_cliente,

            "rfc":
                dc.rfc,

        })



        # =====================================================
        # OTROS PRODUCTOS
        # =====================================================

        op = ec.otros_productos


        otros_productos.append({

            "id_estado": estado_id,

            "contrato":
                op.contrato,

            "producto":
                op.producto,

            "tasa_interes_anual":
                op.tasa_interes_anual,

            "gat_nominal_anual":
                op.gat_nominal_anual,

            "gat_real_anual":
                op.gat_real_anual,

            "total_comisiones":
                op.total_comisiones,

        })



        # =====================================================
        # RESUMEN FINANCIERO COMPLETO
        # =====================================================

        rf = ec.resumen_financiero


        resumen_financiero.append({

            "id_estado": estado_id,


            "saldo_promedio":
                rf.saldo_promedio,


            "dias_periodo":
                rf.dias_periodo,


            "tasa_bruta_anual":
                rf.tasa_bruta_anual,


            "saldo_promedio_gravable":
                rf.saldo_promedio_gravable,


            "intereses_a_favor":
                rf.intereses_a_favor,


            "isr_retenido":
                rf.isr_retenido,


            "cheques_pagados":
                rf.cheques_pagados,


            "manejo_cuenta":
                rf.manejo_cuenta,


            "cargos_objetados":
                rf.cargos_objetados,


            "abonos_objetados":
                rf.abonos_objetados,


            "saldo_anterior":
                rf.saldo_anterior,


            "depositos_abonos":
                rf.depositos_abonos,


            "retiros_cargos":
                rf.retiros_cargos,


            "saldo_final":
                rf.saldo_final,


            "saldo_promedio_minimo_mensual":
                rf.saldo_promedio_minimo_mensual,


            "saldo_global":
                rf.saldo_global,

        })



        # =====================================================
        # MOVIMIENTOS
        # =====================================================

        for numero, mov in enumerate(
            ec.movimientos,
            start=1
        ):

            movimientos.append({

                "id_estado":
                    estado_id,

                "numero_movimiento":
                    numero,


                "fecha_operacion":
                    mov.fecha_operacion,

                "fecha_liquidacion":
                    mov.fecha_liquidacion,


                "concepto":
                    mov.concepto,

                "tipo_operacion":
                    mov.tipo_operacion,


                "cargo":
                    mov.cargo,

                "abono":
                    mov.abono,

                "saldo_operacion":
                    mov.saldo_operacion,

                "saldo_liquidacion":
                    mov.saldo_liquidacion,


                "referencia":
                    mov.referencia,

                "autorizacion":
                    mov.autorizacion,


                "beneficiario":
                    mov.beneficiario,

                "cuenta_beneficiario":
                    mov.cuenta_beneficiario,

                "clabe_beneficiario":
                    mov.clabe_beneficiario,


                "rfc":
                    mov.rfc,


                "sucursal":
                    mov.sucursal,

                "caja":
                    mov.caja,

                "hora_operacion":
                    mov.hora_operacion,


                "concepto_original":
                    mov.concepto_original,

            })



    return {

        "estados_cuenta":
            estados_cuenta,


        "otros_productos":
            otros_productos,


        "resumen_financiero":
            resumen_financiero,


        "movimientos":
            movimientos,

    }