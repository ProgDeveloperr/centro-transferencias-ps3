#!/usr/bin/env python3

from __future__ import annotations

import configparser
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


CONFIG = Path("/opt/ctps3/config/config.ini")
BD = Path("/var/lib/ctps3/transferencias.sqlite3")


def utc() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def parsear_nombre(nombre: str) -> dict:
    stem = Path(nombre).stem

    codigo = None
    origen = None
    parte = None

    codigo_match = re.search(
        r"\[([A-Za-z]{4}\d{5})\]",
        stem
    )

    if codigo_match:
        codigo = codigo_match.group(1).upper()

    origen_match = re.search(
        r"-\[([^\]]+)\]",
        stem
    )

    if origen_match:
        origen = origen_match.group(1).strip()

    parte_match = re.search(
        r"(?:^|[\s._-])(?:Pt|Part|Parte)\s*0*(\d+)\s*$",
        stem,
        re.IGNORECASE
    )

    if parte_match:
        parte = int(parte_match.group(1))

    titulo = stem

    titulo = re.sub(
        r"\s*\[[A-Za-z]{4}\d{5}\]",
        "",
        titulo
    )

    titulo = re.sub(
        r"\s*-\[[^\]]+\]",
        "",
        titulo
    )

    titulo = re.sub(
        r"\s+(?:Pt|Part|Parte)\s*0*\d+\s*$",
        "",
        titulo,
        flags=re.IGNORECASE
    )

    titulo = re.sub(r"\s{2,}", " ", titulo).strip(" -_.")

    return {
        "titulo_juego": titulo or stem,
        "codigo_juego": codigo,
        "etiqueta_origen": origen,
        "parte_numero": parte,
        "es_fragmentado": 1 if parte is not None else 0,
        "extension": Path(nombre).suffix.lower().lstrip(".")
    }


def main() -> int:
    if not CONFIG.is_file():
        print(
            f"ERROR: no existe {CONFIG}",
            file=sys.stderr
        )
        return 1

    bd = Path(
        os.environ.get(
            "CTPS3_BD",
            str(BD)
        )
    ).resolve()

    if not bd.is_file():
        print(
            f"ERROR: no existe {bd}",
            file=sys.stderr
        )
        return 1

    config = configparser.ConfigParser()
    config.read(CONFIG)

    raiz_pkg = Path(
        os.environ.get(
            "CTPS3_PKG_ROOT",
            config["local"]["directorio_pkg"]
        )
    ).resolve()

    raiz_iso = Path(
        os.environ.get(
            "CTPS3_PS3ISO_ROOT",
            str(
                raiz_pkg.parent
                / "PS3ISO"
            )
        )
    ).resolve()

    raiz_ps2 = Path(
        os.environ.get(
            "CTPS3_PS2ISO_ROOT",
            str(
                raiz_pkg.parent
                / "PS2ISO"
            )
        )
    ).resolve()

    if not raiz_pkg.is_dir():
        print(
            f"ERROR: biblioteca PKG inexistente: {raiz_pkg}",
            file=sys.stderr
        )
        return 1

    if not raiz_iso.is_dir():
        print(
            f"ERROR: biblioteca PS3ISO inexistente: {raiz_iso}",
            file=sys.stderr
        )
        return 1

    if not raiz_ps2.is_dir():
        print(
            f"ERROR: biblioteca PS2ISO inexistente: {raiz_ps2}",
            file=sys.stderr
        )
        return 1

    ahora = utc()

    con = sqlite3.connect(
        bd,
        timeout=5
    )

    con.row_factory = sqlite3.Row

    con.execute(
        "PRAGMA foreign_keys=ON"
    )

    con.execute(
        "PRAGMA busy_timeout=5000"
    )

    try:
        schema = con.execute(
            """
            SELECT valor
            FROM meta
            WHERE clave='schema_version'
            """
        ).fetchone()

        if (
            schema is None
            or str(schema["valor"])
            not in {"11", "12", "13"}
        ):
            raise RuntimeError(
                "El catalogador multiformato "
                "requiere schema compatible "
                "11, 12 o 13"
            )


        columnas = {
            fila["name"]
            for fila in con.execute(
                "PRAGMA table_info(archivos_locales)"
            )
        }

        if "formato" not in columnas:
            raise RuntimeError(
                "Falta archivos_locales.formato"
            )


        con.execute(
            "BEGIN IMMEDIATE"
        )


        con.execute(
            """
            UPDATE archivos_locales
            SET
                disponible=0,
                actualizado_utc=?
            WHERE formato IN (
                'PKG',
                'PS3ISO',
                'PS2ISO'
            )
            """,
            (ahora,)
        )


        estadisticas = {
            "PKG": {
                "detectados": 0,
                "nuevos": 0,
                "actualizados": 0,
                "sin_cambios": 0,
            },

            "PS3ISO": {
                "detectados": 0,
                "nuevos": 0,
                "actualizados": 0,
                "sin_cambios": 0,
            },

            "PS2ISO": {
                "detectados": 0,
                "nuevos": 0,
                "actualizados": 0,
                "sin_cambios": 0,
            },
        }


        fuentes = (
            (
                "PKG",
                raiz_pkg,
                ".pkg",
            ),
            (
                "PS3ISO",
                raiz_iso,
                ".iso",
            ),
            (
                "PS2ISO",
                raiz_ps2,
                ".BIN.ENC",
            ),
        )


        for (
            formato,
            raiz,
            extension_permitida,
        ) in fuentes:

            for (
                directorio,
                _subdirectorios,
                nombres,
            ) in os.walk(raiz):

                if formato in (
                    "PS3ISO",
                    "PS2ISO",
                ):
                    _subdirectorios[:] = []

                nombres.sort(
                    key=str.casefold
                )

                for nombre in nombres:

                    if formato == "PS2ISO":
                        if not nombre.endswith(
                            ".BIN.ENC"
                        ):
                            continue
                    else:
                        if not nombre.lower().endswith(
                            extension_permitida
                        ):
                            continue


                    ruta = (
                        Path(directorio)
                        / nombre
                    ).resolve()


                    try:
                        relativa_path = (
                            ruta.relative_to(
                                raiz
                            )
                        )

                    except ValueError:
                        raise RuntimeError(
                            "Ruta fuera de raíz "
                            f"permitida: {ruta}"
                        )


                    if not ruta.is_file():
                        continue


                    relativa = (
                        relativa_path.as_posix()
                    )


                    stat = ruta.stat()


                    if formato == "PKG":

                        metadata = parsear_nombre(
                            nombre
                        )

                    else:

                        if formato == "PS2ISO":
                            stem_iso = nombre[
                                :-len(".BIN.ENC")
                            ]

                            extension_logica = (
                                "bin.enc"
                            )

                        else:
                            stem_iso = Path(
                                nombre
                            ).stem

                            extension_logica = (
                                "iso"
                            )

                        codigo_iso = None
                        origen_iso = None


                        codigo_match_iso = re.search(
                            r"\[([A-Za-z]{4}\d{5})\]",
                            stem_iso
                        )


                        if codigo_match_iso:

                            codigo_iso = (
                                codigo_match_iso
                                .group(1)
                                .upper()
                            )


                        origen_match_iso = re.search(
                            r"-\[([^\]]+)\]",
                            stem_iso
                        )


                        if origen_match_iso:

                            origen_iso = (
                                origen_match_iso
                                .group(1)
                                .strip()
                            )


                        titulo_iso = stem_iso


                        titulo_iso = re.sub(
                            r"\s*\[[A-Za-z]{4}\d{5}\]",
                            "",
                            titulo_iso
                        )


                        titulo_iso = re.sub(
                            r"\s*-\[[^\]]+\]",
                            "",
                            titulo_iso
                        )


                        titulo_iso = re.sub(
                            r"\s{2,}",
                            " ",
                            titulo_iso
                        ).strip(
                            " -_."
                        )


                        metadata = {
                            "titulo_juego":
                                titulo_iso
                                or stem_iso,

                            "codigo_juego":
                                codigo_iso,

                            "etiqueta_origen":
                                origen_iso,

                            "parte_numero":
                                None,

                            "es_fragmentado":
                                0,

                            "extension":
                                extension_logica,
                        }


                    estadisticas[
                        formato
                    ]["detectados"] += 1


                    previo = con.execute(
                        """
                        SELECT
                            id,
                            nombre,
                            tamano_bytes,
                            mtime_ns,
                            titulo_juego,
                            codigo_juego,
                            etiqueta_origen,
                            parte_numero,
                            es_fragmentado,
                            extension,
                            formato,
                            disponible
                        FROM archivos_locales
                        WHERE
                            formato=?
                            AND ruta_relativa=?
                        """,
                        (
                            formato,
                            relativa,
                        )
                    ).fetchone()


                    valores_logicos = (
                        nombre,
                        int(stat.st_size),
                        int(stat.st_mtime_ns),
                        metadata[
                            "titulo_juego"
                        ],
                        metadata[
                            "codigo_juego"
                        ],
                        metadata[
                            "etiqueta_origen"
                        ],
                        metadata[
                            "parte_numero"
                        ],
                        int(
                            metadata[
                                "es_fragmentado"
                            ]
                        ),
                        metadata[
                            "extension"
                        ],
                        formato,
                    )


                    if previo is None:

                        con.execute(
                            """
                            INSERT INTO archivos_locales (
                                nombre,
                                ruta_relativa,
                                tamano_bytes,
                                mtime_ns,
                                sha256,
                                sha256_estado,
                                disponible,
                                detectado_utc,
                                visto_utc,
                                actualizado_utc,
                                titulo_juego,
                                codigo_juego,
                                etiqueta_origen,
                                parte_numero,
                                es_fragmentado,
                                extension,
                                formato
                            )
                            VALUES (
                                ?, ?, ?, ?,
                                NULL,
                                'PENDIENTE',
                                1,
                                ?, ?, ?,
                                ?, ?, ?, ?, ?, ?, ?
                            )
                            """,
                            (
                                nombre,
                                relativa,
                                int(
                                    stat.st_size
                                ),
                                int(
                                    stat.st_mtime_ns
                                ),
                                ahora,
                                ahora,
                                ahora,
                                metadata[
                                    "titulo_juego"
                                ],
                                metadata[
                                    "codigo_juego"
                                ],
                                metadata[
                                    "etiqueta_origen"
                                ],
                                metadata[
                                    "parte_numero"
                                ],
                                int(
                                    metadata[
                                        "es_fragmentado"
                                    ]
                                ),
                                metadata[
                                    "extension"
                                ],
                                formato,
                            )
                        )

                        estadisticas[
                            formato
                        ]["nuevos"] += 1

                        continue


                    previo_logico = (
                        previo["nombre"],
                        int(
                            previo[
                                "tamano_bytes"
                            ]
                        ),
                        int(
                            previo[
                                "mtime_ns"
                            ]
                        ),
                        previo[
                            "titulo_juego"
                        ],
                        previo[
                            "codigo_juego"
                        ],
                        previo[
                            "etiqueta_origen"
                        ],
                        previo[
                            "parte_numero"
                        ],
                        int(
                            previo[
                                "es_fragmentado"
                            ]
                        ),
                        previo[
                            "extension"
                        ],
                        previo[
                            "formato"
                        ],
                    )


                    cambio_contenido = (
                        int(
                            previo[
                                "tamano_bytes"
                            ]
                        )
                        != int(
                            stat.st_size
                        )
                        or int(
                            previo[
                                "mtime_ns"
                            ]
                        )
                        != int(
                            stat.st_mtime_ns
                        )
                    )


                    cambio_logico = (
                        previo_logico
                        != valores_logicos
                    )


                    if (
                        cambio_contenido
                        or cambio_logico
                    ):

                        con.execute(
                            """
                            UPDATE archivos_locales
                            SET
                                nombre=?,
                                tamano_bytes=?,
                                mtime_ns=?,
                                sha256=
                                    CASE
                                        WHEN
                                            tamano_bytes != ?
                                            OR mtime_ns != ?
                                        THEN NULL
                                        ELSE sha256
                                    END,
                                sha256_estado=
                                    CASE
                                        WHEN
                                            tamano_bytes != ?
                                            OR mtime_ns != ?
                                        THEN 'PENDIENTE'
                                        ELSE sha256_estado
                                    END,
                                disponible=1,
                                visto_utc=?,
                                actualizado_utc=?,
                                titulo_juego=?,
                                codigo_juego=?,
                                etiqueta_origen=?,
                                parte_numero=?,
                                es_fragmentado=?,
                                extension=?,
                                formato=?
                            WHERE id=?
                            """,
                            (
                                nombre,
                                int(
                                    stat.st_size
                                ),
                                int(
                                    stat.st_mtime_ns
                                ),

                                int(
                                    stat.st_size
                                ),
                                int(
                                    stat.st_mtime_ns
                                ),

                                int(
                                    stat.st_size
                                ),
                                int(
                                    stat.st_mtime_ns
                                ),

                                ahora,
                                ahora,

                                metadata[
                                    "titulo_juego"
                                ],
                                metadata[
                                    "codigo_juego"
                                ],
                                metadata[
                                    "etiqueta_origen"
                                ],
                                metadata[
                                    "parte_numero"
                                ],
                                int(
                                    metadata[
                                        "es_fragmentado"
                                    ]
                                ),
                                metadata[
                                    "extension"
                                ],
                                formato,

                                int(
                                    previo["id"]
                                ),
                            )
                        )

                        estadisticas[
                            formato
                        ]["actualizados"] += 1

                    else:

                        con.execute(
                            """
                            UPDATE archivos_locales
                            SET
                                disponible=1,
                                visto_utc=?
                            WHERE id=?
                            """,
                            (
                                ahora,
                                int(
                                    previo["id"]
                                ),
                            )
                        )

                        estadisticas[
                            formato
                        ]["sin_cambios"] += 1


        con.execute(
            """
            INSERT INTO meta(
                clave,
                valor
            )
            VALUES(
                'catalogador_formatos_version',
                '1.1.0'
            )
            ON CONFLICT(clave)
            DO UPDATE SET
                valor=excluded.valor
            """
        )


        con.commit()


    except Exception:
        con.rollback()
        raise


    finally:
        con.close()


    print(
        "Catalogador multiformato 1.1.0"
    )

    print(
        "PKG     :",
        estadisticas["PKG"]
    )

    print(
        "PS3ISO  :",
        estadisticas["PS3ISO"]
    )

    print(
        "PS2ISO  :",
        estadisticas["PS2ISO"]
    )

    print(
        "Raíz PKG:",
        raiz_pkg
    )

    print(
        "Raíz PS3ISO:",
        raiz_iso
    )

    print(
        "Raíz PS2ISO:",
        raiz_ps2
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
