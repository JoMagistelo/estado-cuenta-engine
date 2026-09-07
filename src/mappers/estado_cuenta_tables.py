from __future__ import annotations

from typing import Any, Dict, List

from models.processing_result import ProcessingResult


def estado_cuenta_to_tables(
    results: list[ProcessingResult],
) -> Dict[str, List[Dict[str, Any]]]:

    """
    Convierte los estados de cuenta procesados a tablas
    normalizadas.

    Los resultados que todavía no tienen `estado_cuenta`
    se omiten temporalmente. Actualmente esto ocurre con
    documentos detectados como PDF imagen / OCR pendiente.

    Cuando el OCR genere un `EstadoCuenta` completo, ese
    resultado será procesado automáticamente por este mismo
    mapper sin requerir cambios adicionales.

    Regla:
    No se pierde ninguna variable del modelo para los
    estados de cuenta que sí fueron procesados.
    """

    estados_cuenta = []
    otros_productos = []
    resumen_financiero = []
    movimientos = []

    for estado_id, result in enumerate(results, start=1):

        # =====================================================
        # DOCUMENTO NO PROCESADO
        # =====================================================
        #
        # Actualmente corresponde principalmente a:
        #
        #     PDF imagen / OCR pendiente
        #
        # No intentamos acceder a datos_cuenta, resumen,
        # movimientos, etc. porque todavía no existe
        # un EstadoCuenta para este resultado.
        #
        # Cuando OCR genere estado_cuenta, automáticamente
        # continuará por el flujo normal de abajo.
        #
        # =====================================================

        ec = result.estado_cuenta

        if ec is None:
            continue

        # =====================================================
        # DATOS DE LA CUENTA
        # =====================================================

        dc = ec.datos_cuenta

        estados_cuenta.append(

            {

                "id_estado": estado_id,

                "Nombre del Archivo":
                    result.file_name,

                "Banco":
                    result.bank_key,

                "Número de Cliente":
                    dc.numero_cliente,

                "Nombre del Cliente":
                    dc.nombre_cliente,

                "RFC":
                    dc.rfc,

                "Producto Principal":
                    dc.producto_principal,

                "Número de Cuenta":
                    dc.numero_cuenta,

                "CLABE":
                    dc.clabe,

                "Periodo de Inicio":
                    dc.periodo_inicio,

                "Periodo de Fin":
                    dc.periodo_fin,

                "Fecha de Corte":
                    dc.fecha_corte,

            }

        )

        # =====================================================
        # OTROS PRODUCTOS
        # =====================================================

        op = ec.otros_productos

        otros_productos.append(

            {

                "id_estado": estado_id,

                "Nombre del Archivo":
                    result.file_name,

                "Banco":
                    result.bank_key,

                "Contrato":
                    op.contrato,

                "Producto":
                    op.producto,

                "Tasa de Interes Anual":
                    op.tasa_interes_anual,

                "GAT Nominal Anual":
                    op.gat_nominal_anual,

                "GAT Real Anual":
                    op.gat_real_anual,

                "Total de Comisiones":
                    op.total_comisiones,

            }

        )

        # =====================================================
        # RESUMEN FINANCIERO COMPLETO
        # =====================================================

        rf = ec.resumen_financiero

        resumen_financiero.append(

            {

                "id_estado":
                    estado_id,

                "Nombre del Archivo":
                    result.file_name,

                "Banco":
                    result.bank_key,

                "Días del Periodo ":
                    rf.dias_periodo,

                "Intereses a Favor":
                    rf.intereses_a_favor,

                "ISR Retenido":
                    rf.isr_retenido,

                "Saldo Anterior":
                    rf.saldo_anterior,

                "Depositos / Abonos (+)":
                    rf.depositos_abonos,

                "Retiros / Cargos (-)":
                    rf.retiros_cargos,

                "Saldo Final":
                    rf.saldo_final,

                "Saldo Promedio":
                    rf.saldo_promedio,

                "Saldo Promedio Mínimo Mensual":
                    rf.saldo_promedio_minimo_mensual,

                "Saldo Promedio Gravable":
                    rf.saldo_promedio_gravable,

                "Tasa Bruta Anual":
                    rf.tasa_bruta_anual,

                "Cheques Pagados":
                    rf.cheques_pagados,

                "Manejo de Cuenta":
                    rf.manejo_cuenta,

                "Cargos Objetados":
                    rf.cargos_objetados,

                "Abonos Objetados":
                    rf.abonos_objetados,

                "Saldo Global":
                    rf.saldo_global,

            }

        )

        # =====================================================
        # MOVIMIENTOS
        # =====================================================

        # Un resultado OCR válido puede no contener movimientos. La UI ya
        # normaliza ese caso como una lista vacía; el mapper hace lo mismo para
        # que la exportación conserve las demás hojas aun si un parser/lector
        # entrega `None` de forma excepcional.
        for numero, mov in enumerate(
            ec.movimientos or [],
            start=1,
        ):

            movimientos.append(

                {

                    "id_estado":
                        estado_id,

                    "Nombre del Archivo":
                        result.file_name,

                    "Banco":
                        result.bank_key,

                    "Fecha de Corte":
                        dc.fecha_corte,

                    "Número de Cuenta":
                        dc.numero_cuenta,

                    "No. de Movimiento":
                        numero,

                    "Fecha de Operación":
                        mov.fecha_operacion,

                    "Fecha de Liquidación":
                        mov.fecha_liquidacion,

                    "Concepto":
                        mov.concepto,

                    "Tipo de Operación":
                        mov.tipo_operacion,

                    "Cargo":
                        mov.cargo,

                    "Abono":
                        mov.abono,

                    "Saldo de Operación":
                        mov.saldo_operacion,

                    "Saldo de liquidacion":
                        mov.saldo_liquidacion,

                    "Referencia":
                        mov.referencia,

                    "Clave de Rastreo":
                        mov.clave_rastreo,         

                    "Autorizacion":
                        mov.autorizacion,

                    "Beneficiario":
                        mov.beneficiario,

                    "Cuenta del Beneficiario":
                        mov.cuenta_beneficiario,

                    "CLABE del Beneficiario":
                        mov.clabe_beneficiario,

                    "RFC":
                        mov.rfc,

                    "Sucursal":
                        mov.sucursal,

                    "Caja":
                        mov.caja,

                    "Hora de Operación":
                        mov.hora_operacion,

                    "Concepto Original":
                        mov.concepto_original,

                }

            )

    # =========================================================
    # TABLAS RESULTANTES
    # =========================================================

    return {

        "Datos de la Cuenta":
            estados_cuenta,

        "Resumen Financiero":
            resumen_financiero,

        "Movimientos":
            movimientos,

        "Otros Productos":
            otros_productos,

    }