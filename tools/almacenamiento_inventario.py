from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

VERSION = "1.1.0"

META_VERSION = "almacenamiento_inventario_version"
META_ULTIMA_OK = "almacenamiento_inventario_ultima_ok_utc"
META_ULTIMO_ERROR = "almacenamiento_inventario_ultimo_error"
META_DURACION = "almacenamiento_inventario_duracion_ms"
META_RUTAS = "almacenamiento_inventario_rutas"
META_TOTAL_BYTES = "almacenamiento_inventario_total_bytes"


def utc():
    return datetime.now(
        timezone.utc
    ).isoformat(
        timespec="milliseconds"
    ).replace(
        "+00:00",
        "Z",
    )


def _meta(con, clave, valor):
    con.execute(
        """
        INSERT INTO meta (clave, valor)
        VALUES (?, ?)
        ON CONFLICT(clave)
        DO UPDATE SET valor=excluded.valor
        """,
        (
            str(clave),
            str(valor),
        ),
    )


def cargar_j3(con):
    filas = con.execute(
        """
        SELECT
            c.id AS juego_componente_id,
            c.juego_id,
            c.tipo,
            c.ruta_remota,
            c.title_id_sfo,
            c.nombre_sfo,
            c.categoria_sfo,
            c.tamano_bytes
        FROM juegos_ps3_componentes AS c
        JOIN juegos_ps3 AS j
          ON j.id=c.juego_id
        WHERE
            c.disponible=1
            AND j.disponible=1
            AND c.ruta_remota LIKE '/dev_hdd0/game/%'
        ORDER BY c.ruta_remota
        """
    ).fetchall()

    salida = []

    for fila in filas:
        (
            componente_id,
            juego_id,
            tipo,
            ruta,
            title_id,
            nombre,
            categoria,
            tamano,
        ) = fila

        if tamano is None:
            raise RuntimeError(
                "Componente J3 sin tamaño: "
                + str(ruta)
            )

        salida.append({
            "ruta": str(ruta),
            "title_id": title_id,
            "title": nombre,
            "category": categoria,
            "tamano_bytes": int(tamano),
            "tipo_j3": str(tipo),
            "correlacion_j3": True,
            "origen": "J3",
            "juego_id": int(juego_id),
            "juego_componente_id": int(componente_id),
        })

    return salida


def construir_snapshot(
    con,
    *,
    clasificador,
    politica,
    suplementarios,
):
    if not isinstance(
        suplementarios,
        list,
    ):
        raise RuntimeError(
            "suplementarios debe ser lista"
        )

    base = cargar_j3(
        con
    )

    registros = []
    rutas = set()

    for item in base:
        ruta = item["ruta"]

        if ruta in rutas:
            raise RuntimeError(
                "Ruta J3 duplicada: "
                + ruta
            )

        rutas.add(
            ruta
        )

        clasificado = clasificador.clasificar(
            item,
            politica,
        )

        clasificado["origen"] = "J3"
        clasificado["juego_id"] = item["juego_id"]
        clasificado[
            "juego_componente_id"
        ] = item[
            "juego_componente_id"
        ]

        registros.append(
            clasificado
        )

    for bruto in suplementarios:
        if not isinstance(
            bruto,
            dict,
        ):
            raise RuntimeError(
                "Suplementario no es dict"
            )

        ruta = str(
            bruto.get(
                "ruta",
                ""
            )
        )

        if ruta in rutas:
            raise RuntimeError(
                "Solapamiento J3/suplementario: "
                + ruta
            )

        rutas.add(
            ruta
        )

        entrada = dict(
            bruto
        )

        entrada[
            "correlacion_j3"
        ] = False

        clasificado = clasificador.clasificar(
            entrada,
            politica,
        )

        clasificado[
            "origen"
        ] = "ESP_SUPLEMENTARIO"

        clasificado[
            "juego_id"
        ] = None

        clasificado[
            "juego_componente_id"
        ] = None

        registros.append(
            clasificado
        )

    if any(
        item[
            "eliminacion_automatica_permitida"
        ]
        is not False
        for item in registros
    ):
        raise RuntimeError(
            "Contrato violado: borrado automático"
        )

    if len(rutas) != len(registros):
        raise RuntimeError(
            "Rutas no únicas"
        )

    return sorted(
        registros,
        key=lambda x: x["ruta"],
    )


def resumen(snapshot):
    clases = {}
    bytes_por_clase = {}

    for item in snapshot:
        clase = item["clase"]

        clases[clase] = (
            clases.get(
                clase,
                0,
            )
            + 1
        )

        bytes_por_clase[clase] = (
            bytes_por_clase.get(
                clase,
                0,
            )
            + int(
                item["tamano_bytes"]
            )
        )

    return {
        "rutas": len(snapshot),
        "bytes_total": sum(
            int(
                item["tamano_bytes"]
            )
            for item in snapshot
        ),
        "conteo_por_clase": clases,
        "bytes_por_clase": bytes_por_clase,
        "posibles_huerfanos": sum(
            1
            for item in snapshot
            if item[
                "posible_huerfano"
            ]
        ),
        "desconocidos": sum(
            1
            for item in snapshot
            if item["clase"]
            == "DESCONOCIDO"
        ),
        "borrado_automatico": sum(
            1
            for item in snapshot
            if item[
                "eliminacion_automatica_permitida"
            ]
        ),
    }


def persistir_snapshot(
    con,
    snapshot,
    *,
    ahora=None,
    duracion_ms=0,
):
    if not isinstance(
        snapshot,
        list,
    ):
        raise RuntimeError(
            "snapshot debe ser lista"
        )

    if ahora is None:
        ahora = utc()

    datos = resumen(
        snapshot
    )

    if datos[
        "borrado_automatico"
    ] != 0:
        raise RuntimeError(
            "Borrado automático no permitido"
        )

    rutas = set()

    for item in snapshot:
        ruta = item["ruta"]

        if ruta in rutas:
            raise RuntimeError(
                "Ruta duplicada: "
                + ruta
            )

        rutas.add(
            ruta
        )

    if con.in_transaction:
        raise RuntimeError(
            "SQLite ya tiene transacción activa"
        )

    con.execute(
        "BEGIN IMMEDIATE"
    )

    try:
        con.execute(
            """
            UPDATE almacenamiento_ps3_elementos
            SET
                disponible=0,
                actualizado_utc=?
            WHERE disponible<>0
            """,
            (
                ahora,
            ),
        )

        for item in snapshot:
            evidencia = json.dumps(
                item[
                    "evidencia"
                ],
                ensure_ascii=False,
                separators=(
                    ",",
                    ":",
                ),
            )

            nombre_directorio = (
                item["ruta"]
                .rsplit("/", 1)[-1]
            )

            con.execute(
                """
                INSERT INTO almacenamiento_ps3_elementos (
                    ruta_remota,
                    nombre_directorio,
                    title_id_sfo,
                    nombre_sfo,
                    categoria_sfo,
                    tamano_bytes,
                    origen,
                    juego_id,
                    juego_componente_id,
                    clase,
                    subtipo,
                    confianza,
                    politica,
                    evidencia_json,
                    posible_huerfano,
                    eliminacion_automatica_permitida,
                    disponible,
                    detectado_utc,
                    visto_utc,
                    actualizado_utc
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, 0, 1,
                    ?, ?, ?
                )
                ON CONFLICT(ruta_remota)
                DO UPDATE SET
                    nombre_directorio=
                        excluded.nombre_directorio,
                    title_id_sfo=
                        excluded.title_id_sfo,
                    nombre_sfo=
                        excluded.nombre_sfo,
                    categoria_sfo=
                        excluded.categoria_sfo,
                    tamano_bytes=
                        excluded.tamano_bytes,
                    origen=
                        excluded.origen,
                    juego_id=
                        excluded.juego_id,
                    juego_componente_id=
                        excluded.juego_componente_id,
                    clase=
                        excluded.clase,
                    subtipo=
                        excluded.subtipo,
                    confianza=
                        excluded.confianza,
                    politica=
                        excluded.politica,
                    evidencia_json=
                        excluded.evidencia_json,
                    posible_huerfano=
                        excluded.posible_huerfano,
                    eliminacion_automatica_permitida=0,
                    disponible=1,
                    visto_utc=
                        excluded.visto_utc,
                    actualizado_utc=
                        excluded.actualizado_utc
                """,
                (
                    item["ruta"],
                    nombre_directorio,
                    item["title_id"],
                    item["title"],
                    item["category"],
                    int(
                        item[
                            "tamano_bytes"
                        ]
                    ),
                    item["origen"],
                    item[
                        "juego_id"
                    ],
                    item[
                        "juego_componente_id"
                    ],
                    item["clase"],
                    item["subtipo"],
                    item["confianza"],
                    item["politica"],
                    evidencia,
                    1
                    if item[
                        "posible_huerfano"
                    ]
                    else 0,
                    ahora,
                    ahora,
                    ahora,
                ),
            )

        _meta(
            con,
            META_VERSION,
            VERSION,
        )

        _meta(
            con,
            META_ULTIMA_OK,
            ahora,
        )

        _meta(
            con,
            META_ULTIMO_ERROR,
            "",
        )

        _meta(
            con,
            META_DURACION,
            int(
                duracion_ms
            ),
        )

        _meta(
            con,
            META_RUTAS,
            datos["rutas"],
        )

        _meta(
            con,
            META_TOTAL_BYTES,
            datos[
                "bytes_total"
            ],
        )

        fk = con.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if fk:
            raise RuntimeError(
                "foreign_key_check falló "
                "durante persistencia"
            )

        con.commit()

    except Exception:
        con.rollback()
        raise

    return datos


def registrar_error(
    con,
    error,
):
    if con.in_transaction:
        con.rollback()

    con.execute(
        "BEGIN IMMEDIATE"
    )

    try:
        _meta(
            con,
            META_ULTIMO_ERROR,
            str(error),
        )

        con.commit()

    except Exception:
        con.rollback()
        raise


# ============================================================
# ESP-3F-B — suplementos derivados del RAW ignorados de J3
# ============================================================

def cargar_cache_suplementarios(con):
    # No ejecuta red, FTP ni mediciones.
    filas = con.execute(
        """
        SELECT
            ruta_remota,
            tamano_bytes
        FROM almacenamiento_ps3_elementos
        WHERE
            disponible=1
            AND origen='ESP_SUPLEMENTARIO'
            AND tamano_bytes IS NOT NULL
        """
    ).fetchall()

    return {
        str(ruta):
            int(tamano)
        for ruta, tamano
        in filas
    }


def preparar_suplementarios_desde_ignorados(
    con,
    ignorados,
    *,
    medir,
):
    # Reutiliza el RAW del mismo barrido J3 y sólo mide rutas sin cache.
    if not isinstance(
        ignorados,
        list,
    ):
        raise RuntimeError(
            "ignorados debe ser lista"
        )

    if not callable(
        medir
    ):
        raise RuntimeError(
            "medir debe ser callable"
        )

    cache = cargar_cache_suplementarios(
        con
    )

    vistos = set()
    salida = []
    usados_cache = 0
    medidos = 0

    for bruto in ignorados:
        if not isinstance(
            bruto,
            dict,
        ):
            raise RuntimeError(
                "ignorado no es dict"
            )

        ruta = str(
            bruto.get(
                "ruta",
                ""
            )
        ).strip()

        prefijo = "/dev_hdd0/game/"

        if not ruta.startswith(
            prefijo
        ):
            raise RuntimeError(
                "ignorado fuera de /dev_hdd0/game: "
                + ruta
            )

        relativo = ruta[
            len(prefijo):
        ]

        if (
            not relativo
            or "/" in relativo
            or "\\" in relativo
            or ".." in relativo
        ):
            raise RuntimeError(
                "ruta ignorada insegura: "
                + ruta
            )

        if ruta in vistos:
            raise RuntimeError(
                "ruta ignorada duplicada: "
                + ruta
            )

        vistos.add(
            ruta
        )

        if ruta in cache:
            tamano = int(
                cache[ruta]
            )
            usados_cache += 1

        else:
            tamano = int(
                medir(
                    ruta
                )
            )

            if tamano < 0:
                raise RuntimeError(
                    "tamaño negativo: "
                    + ruta
                )

            medidos += 1

        salida.append({
            "ruta":
                ruta,

            "title_id":
                str(
                    bruto.get(
                        "title_id",
                        ""
                    )
                ).upper(),

            "title":
                str(
                    bruto.get(
                        "nombre",
                        relativo,
                    )
                ),

            "category":
                str(
                    bruto.get(
                        "categoria",
                        ""
                    )
                ).upper(),

            "tamano_bytes":
                tamano,

            "tipo_j3":
                None,

            "correlacion_j3":
                False,

            "origen":
                "ESP_SUPLEMENTARIO",
        })

    return {
        "suplementarios":
            salida,

        "cache":
            usados_cache,

        "medidos":
            medidos,
    }
