"""Adapta la entrega de eventos paralelos al orden del lote para consumidores secuenciales.

No altera la ejecución de OCR, la lectura ni el parser; sólo retiene los eventos
terminales de archivos que acabaron antes que sus predecesores. Los eventos
``started`` continúan llegando inmediatamente para mostrar OCR simultáneo.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from engine.pipeline import ProcessingEvent


TERMINAL_KINDS = frozenset({"completed", "error", "cancelled"})


def ordered_terminal_events(events: Iterable[ProcessingEvent]) -> Iterator[ProcessingEvent]:
    """Emite resultados finales en orden de índice sin impedir trabajo paralelo.

    La interfaz original agrega cada ``completed`` a su lista de exportación;
    recibirlos en orden de finalización cambiaría el orden del Excel. Nunca
    oculta los ``started`` ni descarta un resultado si otro archivo falla.
    """
    pending: dict[int, ProcessingEvent] = {}
    next_index = 0
    for event in events:
        if event.kind not in TERMINAL_KINDS:
            yield event
            continue
        if event.index in pending or event.index < next_index:
            raise ValueError("Evento terminal duplicado en lote paralelo")
        pending[event.index] = event
        while next_index in pending:
            yield pending.pop(next_index)
            next_index += 1
    # Un productor anómalo nunca debe hacer desaparecer resultados terminados.
    for index in sorted(pending):
        yield pending[index]
