from __future__ import annotations

import re

VERSION = "1.2.0"

PATRON_TITLE_ID = re.compile(
    r"^(?:BC|BL|NP)[A-Z0-9]{2}[0-9]{5}$"
)

PATRON_HOMEBREW = re.compile(
    r"^BLES80[0-9]{3}$"
)


def es_title_id_juego(valor):
    title_id = str(
        valor or ""
    ).upper()

    return (
        bool(
            PATRON_TITLE_ID.fullmatch(
                title_id
            )
        )
        and not bool(
            PATRON_HOMEBREW.fullmatch(
                title_id
            )
        )
    )


import struct


def parsear_sfo(datos):
    if (
        len(datos) < 20
        or datos[:4] != b"\x00PSF"
    ):
        raise ValueError(
            "PARAM.SFO inválido"
        )

    (
        _magic,
        _version,
        inicio_claves,
        inicio_datos,
        cantidad,
    ) = struct.unpack(
        "<4s4I",
        datos[:20],
    )

    resultado = {}

    for indice in range(cantidad):
        posicion = (
            20
            + indice * 16
        )

        if posicion + 16 > len(datos):
            break

        (
            desplazamiento_clave,
            formato,
            largo,
            _largo_maximo,
            desplazamiento_dato,
        ) = struct.unpack(
            "<HHIII",
            datos[
                posicion:
                posicion + 16
            ],
        )

        posicion_clave = (
            inicio_claves
            + desplazamiento_clave
        )

        fin_clave = datos.find(
            b"\x00",
            posicion_clave,
        )

        if fin_clave < 0:
            continue

        clave = datos[
            posicion_clave:
            fin_clave
        ].decode(
            "utf-8",
            errors="replace",
        )

        posicion_dato = (
            inicio_datos
            + desplazamiento_dato
        )

        bruto = datos[
            posicion_dato:
            posicion_dato + largo
        ]

        if (
            formato == 0x0404
            and len(bruto) >= 4
        ):
            valor = struct.unpack(
                "<I",
                bruto[:4],
            )[0]

        else:
            valor = bruto.rstrip(
                b"\x00"
            ).decode(
                "utf-8",
                errors="replace",
            )

        resultado[clave] = valor

    return resultado


from ftplib import FTP
from io import BytesIO
import time


REINTENTOS_FTP = 3


def conectar_ftp(
    host,
    puerto,
    usuario,
    password,
    timeout,
):
    ftp = FTP()
    ftp.encoding = "latin-1"

    ftp.connect(
        host,
        puerto,
        timeout=timeout,
    )

    ftp.login(
        usuario,
        password,
    )

    return ftp


def cerrar_ftp(ftp):
    try:
        ftp.quit()

    except Exception:
        try:
            ftp.close()

        except Exception:
            pass


def obtener_sfo_remoto(
    *,
    host,
    puerto,
    usuario,
    password,
    timeout,
    ruta,
):
    ultimo_error = None

    for intento in range(
        1,
        REINTENTOS_FTP + 1,
    ):
        ftp = None

        try:
            ftp = conectar_ftp(
                host,
                puerto,
                usuario,
                password,
                timeout,
            )

            memoria = BytesIO()

            ftp.retrbinary(
                "RETR " + ruta,
                memoria.write,
            )

            cerrar_ftp(ftp)

            return parsear_sfo(
                memoria.getvalue()
            )

        except Exception as exc:
            ultimo_error = exc

            if ftp is not None:
                cerrar_ftp(ftp)

            if intento < REINTENTOS_FTP:
                time.sleep(0.5)

    raise RuntimeError(
        f"No se pudo leer {ruta}: "
        f"{type(ultimo_error).__name__}: "
        f"{ultimo_error}"
    )


def listar_remoto(
    *,
    host,
    puerto,
    usuario,
    password,
    timeout,
    ruta,
):
    ultimo_error = None

    for intento in range(
        1,
        REINTENTOS_FTP + 1,
    ):
        ftp = None

        try:
            ftp = conectar_ftp(
                host,
                puerto,
                usuario,
                password,
                timeout,
            )

            entradas = list(
                ftp.mlsd(ruta)
            )

            cerrar_ftp(ftp)

            return [
                (nombre, hechos)
                for nombre, hechos
                in entradas
                if nombre not in (
                    ".",
                    "..",
                )
            ]

        except Exception as exc:
            ultimo_error = exc

            if ftp is not None:
                cerrar_ftp(ftp)

            if intento < REINTENTOS_FTP:
                time.sleep(0.5)

    raise RuntimeError(
        f"No se pudo listar {ruta}: "
        f"{type(ultimo_error).__name__}: "
        f"{ultimo_error}"
    )


def normalizar_bootable(valor):
    if valor is None:
        return None

    try:
        return int(valor)

    except (
        TypeError,
        ValueError,
    ):
        return None


def clasificar_sfo(
    carpeta,
    sfo,
):
    title_id = str(
        sfo.get(
            "TITLE_ID",
            "",
        )
    ).upper()

    categoria = str(
        sfo.get(
            "CATEGORY",
            "",
        )
    ).upper()

    bootable = normalizar_bootable(
        sfo.get(
            "BOOTABLE"
        )
    )

    if (
        categoria in (
            "DG",
            "HG",
        )
        and bootable == 1
        and es_title_id_juego(
            title_id
        )
    ):
        return "HDD_JUEGO"

    if (
        categoria == "GD"
        and es_title_id_juego(
            title_id
        )
    ):
        if carpeta.lower().endswith(
            "_cache"
        ):
            return "CACHE_GAME"

        return "DATOS_GAME"

    return None


def componente_desde_sfo(
    *,
    carpeta,
    tipo,
    ruta,
    sfo,
):
    title_id = str(
        sfo.get(
            "TITLE_ID",
            "",
        )
    ).upper()

    return {
        "clave_logica":
            title_id,

        "tipo":
            tipo,

        "ruta_remota":
            ruta,

        "title_id_sfo":
            title_id or None,

        "nombre_sfo":
            str(
                sfo.get(
                    "TITLE",
                    "",
                )
            ).strip()
            or None,

        "categoria_sfo":
            str(
                sfo.get(
                    "CATEGORY",
                    "",
                )
            ).upper()
            or None,

        "bootable":
            normalizar_bootable(
                sfo.get(
                    "BOOTABLE"
                )
            ),

        "app_ver":
            str(
                sfo.get(
                    "APP_VER",
                    "",
                )
            ).strip()
            or None,

        "version":
            str(
                sfo.get(
                    "VERSION",
                    "",
                )
            ).strip()
            or None,

        "tamano_bytes":
            None,
    }


import posixpath


def descubrir_juegos(
    *,
    host,
    puerto,
    usuario,
    password,
    timeout,
):
    inicio = time.monotonic()

    ruta_games = "/dev_hdd0/GAMES"
    ruta_game = "/dev_hdd0/game"
    ruta_iso = "/dev_hdd0/PS3ISO"

    principales = []
    auxiliares = []
    ignorados = []
    errores_sfo = []

    # ======================================================
    # /dev_hdd0/GAMES
    # ======================================================

    entradas_games = listar_remoto(
        host=host,
        puerto=puerto,
        usuario=usuario,
        password=password,
        timeout=timeout,
        ruta=ruta_games,
    )

    for carpeta, hechos in entradas_games:
        if hechos.get("type") != "dir":
            continue

        raiz = posixpath.join(
            ruta_games,
            carpeta,
        )

        ruta_sfo = (
            raiz
            + "/PS3_GAME/PARAM.SFO"
        )

        try:
            sfo = obtener_sfo_remoto(
                host=host,
                puerto=puerto,
                usuario=usuario,
                password=password,
                timeout=timeout,
                ruta=ruta_sfo,
            )

        except Exception as exc:
            errores_sfo.append({
                "ruta": ruta_sfo,
                "error": str(exc),
            })
            continue

        title_id = str(
            sfo.get(
                "TITLE_ID",
                "",
            )
        ).upper()

        if not es_title_id_juego(
            title_id
        ):
            ignorados.append({
                "ruta": raiz,
                "motivo":
                    "JB_FOLDER_TITLE_ID_INVALIDO",
            })
            continue

        principales.append(
            componente_desde_sfo(
                carpeta=carpeta,
                tipo="JB_FOLDER",
                ruta=raiz,
                sfo=sfo,
            )
        )

    # ======================================================
    # /dev_hdd0/game
    # ======================================================

    entradas_game = listar_remoto(
        host=host,
        puerto=puerto,
        usuario=usuario,
        password=password,
        timeout=timeout,
        ruta=ruta_game,
    )

    for carpeta, hechos in entradas_game:
        if hechos.get("type") != "dir":
            continue

        raiz = posixpath.join(
            ruta_game,
            carpeta,
        )

        ruta_sfo = (
            raiz
            + "/PARAM.SFO"
        )

        try:
            sfo = obtener_sfo_remoto(
                host=host,
                puerto=puerto,
                usuario=usuario,
                password=password,
                timeout=timeout,
                ruta=ruta_sfo,
            )

        except Exception as exc:
            errores_sfo.append({
                "ruta": ruta_sfo,
                "error": str(exc),
            })
            continue

        tipo = clasificar_sfo(
            carpeta,
            sfo,
        )

        if tipo is None:
            ignorados.append({
                "ruta": raiz,
                "nombre": str(
                    sfo.get(
                        "TITLE",
                        carpeta,
                    )
                ).strip(),
                "categoria": str(
                    sfo.get(
                        "CATEGORY",
                        "",
                    )
                ),
                "title_id": str(
                    sfo.get(
                        "TITLE_ID",
                        "",
                    )
                ),
                "bootable":
                    normalizar_bootable(
                        sfo.get(
                            "BOOTABLE"
                        )
                    ),
            })
            continue

        comp = componente_desde_sfo(
            carpeta=carpeta,
            tipo=tipo,
            ruta=raiz,
            sfo=sfo,
        )

        if tipo in (
            "DATOS_GAME",
            "CACHE_GAME",
        ):
            auxiliares.append(
                comp
            )
        else:
            principales.append(
                comp
            )

    # ======================================================
    # /dev_hdd0/PS3ISO
    # ======================================================

    entradas_iso = listar_remoto(
        host=host,
        puerto=puerto,
        usuario=usuario,
        password=password,
        timeout=timeout,
        ruta=ruta_iso,
    )

    for nombre, hechos in entradas_iso:
        if hechos.get("type") != "file":
            continue

        if not nombre.lower().endswith(
            ".iso"
        ):
            continue

        ruta = posixpath.join(
            ruta_iso,
            nombre,
        )

        try:
            tamano = int(
                hechos.get(
                    "size",
                    0,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            tamano = None

        principales.append({
            "clave_logica":
                "ISO:"
                + ruta.casefold(),

            "tipo":
                "PS3_ISO",

            "ruta_remota":
                ruta,

            "title_id_sfo":
                None,

            "nombre_sfo":
                nombre[:-4],

            "categoria_sfo":
                None,

            "bootable":
                None,

            "app_ver":
                None,

            "version":
                None,

            "tamano_bytes":
                tamano,
        })

    # ======================================================
    # Correlación lógica
    # ======================================================

    prioridad = {
        "JB_FOLDER": 30,
        "HDD_JUEGO": 20,
        "PS3_ISO": 10,
    }

    juegos = {}

    for comp in principales:
        clave = comp[
            "clave_logica"
        ]

        nombre = (
            comp[
                "nombre_sfo"
            ]
            or clave
        )

        if clave not in juegos:
            juegos[clave] = {
                "clave_logica":
                    clave,

                "title_id":
                    comp[
                        "title_id_sfo"
                    ],

                "nombre":
                    nombre,

                "tipo_principal":
                    comp[
                        "tipo"
                    ],

                "tamano_total_bytes":
                    None,

                "componentes":
                    [],
            }

        juego = juegos[
            clave
        ]

        if (
            prioridad[
                comp["tipo"]
            ]
            > prioridad[
                juego[
                    "tipo_principal"
                ]
            ]
        ):
            juego[
                "tipo_principal"
            ] = comp[
                "tipo"
            ]

            juego[
                "nombre"
            ] = nombre

            if comp[
                "title_id_sfo"
            ]:
                juego[
                    "title_id"
                ] = comp[
                    "title_id_sfo"
                ]

        juego[
            "componentes"
        ].append(
            comp
        )

    auxiliares_asociados = 0

    for comp in auxiliares:
        clave = comp[
            "clave_logica"
        ]

        if clave not in juegos:
            continue

        juegos[
            clave
        ][
            "componentes"
        ].append(
            comp
        )

        auxiliares_asociados += 1

    componentes_asociados = sum(
        len(
            juego[
                "componentes"
            ]
        )
        for juego
        in juegos.values()
    )

    return {
        "juegos":
            list(
                juegos.values()
            ),

        "principales":
            len(principales),

        "auxiliares_candidatos":
            len(auxiliares),

        "auxiliares_asociados":
            auxiliares_asociados,

        "componentes_asociados":
            componentes_asociados,

        "ignorados":
            ignorados,

        "errores_sfo":
            errores_sfo,

        "ps3iso":
            sum(
                1
                for comp
                in principales
                if comp[
                    "tipo"
                ] == "PS3_ISO"
            ),

        "duracion_ms":
            int(
                (
                    time.monotonic()
                    - inicio
                )
                * 1000
            ),
    }


# ==========================================================
# CTPS3 — AUTOMATIZACIÓN JUEGOS 1.0.0
# ==========================================================

from datetime import datetime, timezone


CTPS3_JUEGOS_AUTO_VERSION = "1.1.0"
CADENCIA_JUEGOS_SEGUNDOS = 300


def _utc_juegos():
    return datetime.now(
        timezone.utc
    ).isoformat(
        timespec="milliseconds"
    ).replace(
        "+00:00",
        "Z"
    )


def _meta_obtener(
    con,
    clave,
):
    fila = con.execute("""
        SELECT valor
        FROM meta
        WHERE clave=?
    """, (
        clave,
    )).fetchone()

    return (
        fila[0]
        if fila
        else None
    )


def _meta_guardar(
    con,
    clave,
    valor,
):
    con.execute("""
        INSERT INTO meta (
            clave,
            valor
        )
        VALUES (?, ?)

        ON CONFLICT(clave)
        DO UPDATE SET
            valor=excluded.valor
    """, (
        clave,
        str(valor),
    ))


def _parsear_utc_juegos(
    valor,
):
    if not valor:
        return None

    try:
        return datetime.fromisoformat(
            str(valor).replace(
                "Z",
                "+00:00"
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def corresponde_actualizar_juegos(
    con,
    cadencia_segundos=
        CADENCIA_JUEGOS_SEGUNDOS,
):
    ultimo = _meta_obtener(
        con,
        "inventario_juegos_ultimo_intento_utc",
    )

    if not ultimo:
        ultimo = _meta_obtener(
            con,
            "inventario_juegos_ultima_ok_utc",
        )

    fecha = _parsear_utc_juegos(
        ultimo
    )

    if fecha is None:
        return True, 0

    ahora = datetime.now(
        timezone.utc
    )

    transcurrido = (
        ahora - fecha
    ).total_seconds()

    restante = max(
        0,
        int(
            cadencia_segundos
            - transcurrido
        ),
    )

    return (
        transcurrido
        >= cadencia_segundos,
        restante,
    )


def persistir_juegos(
    con,
    resultado,
    ahora,
):
    if resultado.get(
        "errores_sfo"
    ):
        raise RuntimeError(
            "Inventario Juegos incompleto: "
            "existen errores SFO"
        )

    con.execute(
        "BEGIN IMMEDIATE"
    )

    try:
        con.execute("""
            UPDATE juegos_ps3
            SET disponible=0
        """)

        con.execute("""
            UPDATE juegos_ps3_componentes
            SET disponible=0
        """)

        for juego in resultado[
            "juegos"
        ]:

            con.execute("""
                INSERT INTO juegos_ps3 (
                    clave_logica,
                    title_id,
                    nombre,
                    tipo_principal,
                    tamano_total_bytes,
                    disponible,
                    inventario_completo,
                    detectado_utc,
                    visto_utc,
                    actualizado_utc
                )
                VALUES (
                    ?, ?, ?, ?, ?,
                    1, 1,
                    ?, ?, ?
                )

                ON CONFLICT(clave_logica)
                DO UPDATE SET
                    title_id=
                        excluded.title_id,

                    nombre=
                        excluded.nombre,

                    tipo_principal=
                        excluded.tipo_principal,

                    tamano_total_bytes=
                        COALESCE(
                            excluded.tamano_total_bytes,
                            juegos_ps3.tamano_total_bytes
                        ),

                    disponible=1,
                    inventario_completo=1,

                    visto_utc=
                        excluded.visto_utc,

                    actualizado_utc=
                        excluded.actualizado_utc
            """, (
                juego[
                    "clave_logica"
                ],

                juego[
                    "title_id"
                ],

                juego[
                    "nombre"
                ],

                juego[
                    "tipo_principal"
                ],

                juego.get(
                    "tamano_total_bytes"
                ),

                ahora,
                ahora,
                ahora,
            ))

            juego_id = con.execute("""
                SELECT id
                FROM juegos_ps3
                WHERE clave_logica=?
            """, (
                juego[
                    "clave_logica"
                ],
            )).fetchone()[0]

            for comp in juego[
                "componentes"
            ]:

                con.execute("""
                    INSERT INTO
                        juegos_ps3_componentes
                    (
                        juego_id,
                        tipo,
                        ruta_remota,
                        title_id_sfo,
                        nombre_sfo,
                        categoria_sfo,
                        bootable,
                        app_ver,
                        version,
                        tamano_bytes,
                        disponible,
                        detectado_utc,
                        visto_utc,
                        actualizado_utc
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        1,
                        ?, ?, ?
                    )

                    ON CONFLICT(ruta_remota)
                    DO UPDATE SET
                        juego_id=
                            excluded.juego_id,

                        tipo=
                            excluded.tipo,

                        title_id_sfo=
                            excluded.title_id_sfo,

                        nombre_sfo=
                            excluded.nombre_sfo,

                        categoria_sfo=
                            excluded.categoria_sfo,

                        bootable=
                            excluded.bootable,

                        app_ver=
                            excluded.app_ver,

                        version=
                            excluded.version,

                        tamano_bytes=
                            COALESCE(
                                excluded.tamano_bytes,
                                juegos_ps3_componentes.tamano_bytes
                            ),

                        disponible=1,

                        visto_utc=
                            excluded.visto_utc,

                        actualizado_utc=
                            excluded.actualizado_utc
                """, (
                    juego_id,
                    comp["tipo"],
                    comp["ruta_remota"],
                    comp["title_id_sfo"],
                    comp["nombre_sfo"],
                    comp["categoria_sfo"],
                    comp["bootable"],
                    comp["app_ver"],
                    comp["version"],
                    comp.get(
                        "tamano_bytes"
                    ),
                    ahora,
                    ahora,
                    ahora,
                ))

        _meta_guardar(
            con,
            "inventario_juegos_version",
            VERSION,
        )

        _meta_guardar(
            con,
            "inventario_juegos_automatizacion_version",
            CTPS3_JUEGOS_AUTO_VERSION,
        )

        _meta_guardar(
            con,
            "inventario_juegos_ultima_ok_utc",
            ahora,
        )

        _meta_guardar(
            con,
            "inventario_juegos_ultimo_error",
            "",
        )

        fk = con.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if fk:
            raise RuntimeError(
                "foreign_key_check detectó "
                "inconsistencias"
            )

        con.commit()

    except Exception:
        con.rollback()
        raise

    return {
        "juegos":
            con.execute("""
                SELECT COUNT(*)
                FROM juegos_ps3
                WHERE disponible=1
            """).fetchone()[0],

        "componentes":
            con.execute("""
                SELECT COUNT(*)
                FROM juegos_ps3_componentes
                WHERE disponible=1
            """).fetchone()[0],

        "juegos_no_disponibles":
            con.execute("""
                SELECT COUNT(*)
                FROM juegos_ps3
                WHERE disponible=0
            """).fetchone()[0],

        "componentes_no_disponibles":
            con.execute("""
                SELECT COUNT(*)
                FROM juegos_ps3_componentes
                WHERE disponible=0
            """).fetchone()[0],
    }


def actualizar_juegos_si_corresponde(
    con,
    *,
    host,
    puerto,
    usuario,
    password,
    timeout,
    forzar=False,
):
    corresponde, restante = (
        corresponde_actualizar_juegos(
            con
        )
    )

    if (
        not forzar
        and not corresponde
    ):
        return {
            "ejecutado":
                False,

            "ok":
                True,

            "restante_segundos":
                restante,
        }

    intento_utc = (
        _utc_juegos()
    )

    # El intento se registra ANTES del FTP.
    # Si el FTP falla, no se volverá a castigar
    # el ciclo rápido cada 15 segundos.
    try:
        con.execute(
            "BEGIN IMMEDIATE"
        )

        _meta_guardar(
            con,
            "inventario_juegos_ultimo_intento_utc",
            intento_utc,
        )

        con.commit()

    except Exception:
        con.rollback()
        raise

    inicio = time.monotonic()

    try:
        resultado = descubrir_juegos(
            host=host,
            puerto=puerto,
            usuario=usuario,
            password=password,
            timeout=timeout,
        )

        if resultado[
            "errores_sfo"
        ]:
            raise RuntimeError(
                "Barrido Juegos con "
                f"{len(resultado['errores_sfo'])} "
                "errores SFO"
            )

        ahora = _utc_juegos()

        datos = persistir_juegos(
            con,
            resultado,
            ahora,
        )

        duracion_ms = int(
            (
                time.monotonic()
                - inicio
            )
            * 1000
        )

        con.execute(
            "BEGIN IMMEDIATE"
        )

        _meta_guardar(
            con,
            "inventario_juegos_duracion_ms",
            duracion_ms,
        )

        con.commit()

        return {
            "ejecutado":
                True,

            "ok":
                True,

            "duracion_ms":
                duracion_ms,

            "juegos":
                datos["juegos"],

            "componentes":
                datos["componentes"],

            "ignorados":
                len(
                    resultado[
                        "ignorados"
                    ]
                ),

            "almacenamiento_ignorados":
                [
                    dict(
                        item
                    )
                    for item
                    in resultado[
                        "ignorados"
                    ]
                ],

            "errores_sfo":
                0,

            "juegos_no_disponibles":
                datos[
                    "juegos_no_disponibles"
                ],

            "componentes_no_disponibles":
                datos[
                    "componentes_no_disponibles"
                ],
        }

    except Exception as exc:

        duracion_ms = int(
            (
                time.monotonic()
                - inicio
            )
            * 1000
        )

        try:
            con.execute(
                "BEGIN IMMEDIATE"
            )

            _meta_guardar(
                con,
                "inventario_juegos_ultimo_error",
                (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            )

            _meta_guardar(
                con,
                "inventario_juegos_duracion_ms",
                duracion_ms,
            )

            con.commit()

        except Exception:
            con.rollback()

        return {
            "ejecutado":
                True,

            "ok":
                False,

            "duracion_ms":
                duracion_ms,

            "error":
                (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
        }


# ============================================================
# J3-B2 — enriquecimiento incremental
# ============================================================

from juegos_enriquecimiento import (
    enriquecer_juegos as _j3_enriquecer_juegos,
)


_j3_actualizar_juegos_base = (
    actualizar_juegos_si_corresponde
)


def actualizar_juegos_si_corresponde(
    con,
    *,
    host,
    puerto,
    usuario,
    password,
    timeout,
):

    resultado = (
        _j3_actualizar_juegos_base(
            con,
            host=host,
            puerto=puerto,
            usuario=usuario,
            password=password,
            timeout=timeout,
        )
    )

    if (
        isinstance(
            resultado,
            dict,
        )
        and resultado.get(
            "ejecutado"
        ) is True
        and resultado.get(
            "ok"
        ) is not False
    ):

        try:

            resultado[
                "enriquecimiento"
            ] = _j3_enriquecer_juegos(
                con,
                host=host,
                puerto=puerto,
                usuario=usuario,
                password=password,
                timeout=timeout,
            )

        except Exception as exc:

            if con.in_transaction:
                con.rollback()

            resultado[
                "enriquecimiento"
            ] = {
                "ok":
                    False,

                "version":
                    "1.0.0",

                "error":
                    (
                        type(
                            exc
                        ).__name__
                        + ": "
                        + str(
                            exc
                        )
                    ),
            }

    return resultado
