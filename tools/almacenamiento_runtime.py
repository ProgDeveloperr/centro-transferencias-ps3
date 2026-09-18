from __future__ import annotations

import time
from pathlib import Path

import almacenamiento_clasificador
import almacenamiento_inventario
import juegos_enriquecimiento


VERSION = "1.0.1"


def _politica_por_defecto():
    return (
        Path(__file__).resolve().parent
        / "politica_almacenamiento.json"
    )


def actualizar_desde_resultado_j3(
    con,
    juegos_resultado,
    *,
    host,
    puerto,
    usuario,
    password,
    timeout,
    politica_path=None,
    medir_fn=None,
):
    """
    Orquesta un snapshot ESP únicamente a partir de un barrido J3
    que YA ocurrió.

    No enumera /dev_hdd0/game.
    No modifica el resultado J3.
    Si J3 no ejecutó o falló, no toca el snapshot.
    Ante fallo ESP, conserva el último snapshot bueno y registra error.
    """

    if not isinstance(
        juegos_resultado,
        dict,
    ):
        return {
            "ejecutado": False,
            "ok": False,
            "motivo": "RESULTADO_J3_INVALIDO",
        }

    if juegos_resultado.get(
        "ejecutado"
    ) is not True:
        return {
            "ejecutado": False,
            "ok": True,
            "motivo": "J3_NO_EJECUTADO",
        }

    if juegos_resultado.get(
        "ok"
    ) is False:
        return {
            "ejecutado": False,
            "ok": False,
            "motivo": "J3_FALLO",
        }

    ignorados = juegos_resultado.get(
        "almacenamiento_ignorados"
    )

    if not isinstance(
        ignorados,
        list,
    ):
        return {
            "ejecutado": False,
            "ok": False,
            "motivo": "RAW_J3_AUSENTE",
        }

    inicio = time.monotonic()

    if politica_path is None:
        politica_path = (
            Path(
                almacenamiento_clasificador.__file__
            ).resolve().parent
            / "politica_almacenamiento.json"
        )

    if medir_fn is None:
        def medir_fn(ruta):
            medicion = (
                juegos_enriquecimiento
                ._j3_medir_componente_final(
                    host=host,
                    puerto=puerto,
                    usuario=usuario,
                    password=password,
                    timeout=timeout,
                    ruta=ruta,
                )
            )

            if not isinstance(
                medicion,
                dict,
            ):
                raise RuntimeError(
                    "Medición J3 inválida para "
                    + ruta
                    + ": se esperaba dict"
                )

            if "bytes" not in medicion:
                raise RuntimeError(
                    "Medición J3 sin campo bytes para "
                    + ruta
                )

            return int(
                medicion["bytes"]
            )

    try:
        politica = (
            almacenamiento_clasificador
            .cargar_politica(
                politica_path
            )
        )

        preparados = (
            almacenamiento_inventario
            .preparar_suplementarios_desde_ignorados(
                con,
                ignorados,
                medir=medir_fn,
            )
        )

        snapshot = (
            almacenamiento_inventario
            .construir_snapshot(
                con,
                clasificador=
                    almacenamiento_clasificador,
                politica=politica,
                suplementarios=
                    preparados["suplementarios"],
            )
        )

        duracion_ms = int(
            (
                time.monotonic()
                - inicio
            )
            * 1000
        )

        datos = (
            almacenamiento_inventario
            .persistir_snapshot(
                con,
                snapshot,
                duracion_ms=duracion_ms,
            )
        )

        return {
            "ejecutado": True,
            "ok": True,
            "version": VERSION,
            "rutas": datos["rutas"],
            "bytes_total":
                datos["bytes_total"],
            "cache":
                preparados["cache"],
            "medidos":
                preparados["medidos"],
            "duracion_ms":
                duracion_ms,
            "posibles_huerfanos":
                datos["posibles_huerfanos"],
            "desconocidos":
                datos["desconocidos"],
            "borrado_automatico":
                datos["borrado_automatico"],
        }

    except Exception as exc:
        if con.in_transaction:
            con.rollback()

        error = (
            type(exc).__name__
            + ": "
            + str(exc)
        )

        try:
            almacenamiento_inventario.registrar_error(
                con,
                error,
            )
        except Exception:
            if con.in_transaction:
                con.rollback()

        return {
            "ejecutado": True,
            "ok": False,
            "version": VERSION,
            "duracion_ms": int(
                (
                    time.monotonic()
                    - inicio
                )
                * 1000
            ),
            "error": error,
        }
