from __future__ import annotations

from copy import copy, deepcopy

from models.processing_result import ProcessingResult


def snapshot_results_for_export(
    results: list[ProcessingResult],
) -> list[ProcessingResult]:
    """Congela el estado visible de cada resultado al iniciar la exportación.

    Se copia profundamente únicamente la información que puede cambiar por una
    selección OCR posterior (estado de cuenta y validaciones). El ``ocr_review``
    se elimina del snapshot porque el exportador no lo necesita y puede contener
    miles de ``spatial_words`` de ambos motores.
    """
    snapshots: list[ProcessingResult] = []

    for result in results:
        snapshot = copy(result)
        snapshot.estado_cuenta = deepcopy(result.estado_cuenta)
        snapshot.validaciones = deepcopy(result.validaciones)
        snapshot.ocr_review = None
        snapshots.append(snapshot)

    return snapshots
