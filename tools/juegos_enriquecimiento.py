from __future__ import annotations

import csv
import ftplib
import hashlib
import os
import re
import struct

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path


VERSION = "1.0.0"

INVENTARIO_JUEGOS_VERSION = "1.1.0"

CACHE_PREDETERMINADA = Path(
    "/var/lib/ctps3/"
    "centro-transferencias-ps3/"
    "iconos-juegos"
)

NOMBRE_CACHE_RE = re.compile(
    r"^[0-9]{3,10}_"
    r"[A-Z0-9_-]+"
    r"_ICON0\.png$"
)

MAX_ENTRADAS = 300000
MAX_ICONO_BYTES = 16 * 1024 * 1024


def _utc():

    return (
        datetime.now(
            timezone.utc
        )
        .isoformat(
            timespec="milliseconds"
        )
        .replace(
            "+00:00",
            "Z"
        )
    )


def _ftp(
    host,
    puerto,
    usuario,
    password,
    timeout,
):

    ftp = ftplib.FTP()

    ftp.encoding = "latin-1"

    ftp.connect(
        host,
        int(puerto),
        timeout=float(
            timeout
        ),
    )

    ftp.login(
        usuario,
        password,
    )

    return ftp


def _cerrar(ftp):

    if ftp is None:
        return

    try:
        ftp.quit()

    except Exception:

        try:
            ftp.close()

        except Exception:
            pass


def _tamano_directorio(
    ftp,
    raiz,
):

    raiz = str(
        raiz
    ).rstrip("/")

    if not raiz.startswith(
        "/dev_hdd0/"
    ):
        raise RuntimeError(
            "Ruta de tamaño fuera de /dev_hdd0"
        )

    pendientes = [
        raiz
    ]

    visitados = set()

    total = 0
    archivos = 0
    directorios = 0
    entradas = 0

    while pendientes:

        actual = (
            pendientes.pop()
        )

        if actual in visitados:
            continue

        visitados.add(
            actual
        )

        directorios += 1

        for nombre, facts in ftp.mlsd(
            actual,
            facts=[
                "type",
                "size",
            ],
        ):

            if nombre in (
                ".",
                "..",
            ):
                continue

            if any(
                x in nombre
                for x in (
                    "/",
                    "\x00",
                    "\n",
                    "\r",
                )
            ):
                raise RuntimeError(
                    "Nombre FTP no seguro en "
                    + actual
                )

            entradas += 1

            if (
                entradas
                > MAX_ENTRADAS
            ):
                raise RuntimeError(
                    "Límite de entradas FTP alcanzado"
                )

            tipo = str(
                facts.get(
                    "type",
                    "",
                )
            ).lower()

            hijo = (
                actual
                + "/"
                + nombre
            )

            if tipo == "dir":

                pendientes.append(
                    hijo
                )

                continue

            if tipo in (
                "cdir",
                "pdir",
            ):
                continue

            size = facts.get(
                "size"
            )

            if size is None:

                if tipo == "file":
                    raise RuntimeError(
                        "Archivo sin SIZE: "
                        + hijo
                    )

                continue

            try:
                size = int(
                    size
                )

            except (
                TypeError,
                ValueError,
            ) as exc:
                raise RuntimeError(
                    "SIZE inválido: "
                    + hijo
                ) from exc

            if size < 0:
                raise RuntimeError(
                    "SIZE negativo: "
                    + hijo
                )

            total += size
            archivos += 1

    return (
        total,
        archivos,
        directorios,
    )


def _ruta_icono(
    tipo,
    ruta,
):

    ruta = str(
        ruta
    ).rstrip("/")

    if (
        tipo == "JB_FOLDER"
        and ruta.startswith(
            "/dev_hdd0/GAMES/"
        )
    ):
        return (
            ruta
            + "/PS3_GAME/ICON0.PNG"
        )

    if (
        tipo in (
            "HDD_JUEGO",
            "DATOS_GAME",
            "CACHE_GAME",
        )
        and ruta.startswith(
            "/dev_hdd0/game/"
        )
    ):
        return (
            ruta
            + "/ICON0.PNG"
        )

    return None


def _leer_png(
    ftp,
    ruta,
):

    memoria = BytesIO()

    ftp.retrbinary(
        "RETR " + ruta,
        memoria.write,
    )

    datos = (
        memoria.getvalue()
    )

    if (
        len(datos)
        > MAX_ICONO_BYTES
    ):
        raise RuntimeError(
            "ICON0 excede 16 MiB"
        )

    if (
        len(datos) < 24
        or datos[:8]
        != b"\x89PNG\r\n\x1a\n"
        or datos[12:16]
        != b"IHDR"
    ):
        raise RuntimeError(
            "ICON0 no es PNG válido"
        )

    ancho, alto = struct.unpack(
        ">II",
        datos[16:24],
    )

    if not (
        1 <= ancho <= 8192
        and
        1 <= alto <= 8192
    ):
        raise RuntimeError(
            "Dimensiones PNG inválidas"
        )

    return (
        datos,
        ancho,
        alto,
    )


def _manifiesto(
    cache,
):

    ruta = (
        cache
        / "manifiesto.tsv"
    )

    if (
        not cache.is_dir()
        or not ruta.is_file()
    ):
        raise RuntimeError(
            "Caché visual/manifiesto ausente"
        )

    with ruta.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as fh:

        lector = csv.DictReader(
            fh,
            delimiter="\t",
        )

        campos = (
            lector.fieldnames
        )

        requeridos = {
            "juego_id",
            "archivo_cache",
            "bytes",
            "ancho",
            "alto",
            "sha256",
        }

        if (
            not campos
            or not requeridos.issubset(
                set(
                    campos
                )
            )
        ):
            raise RuntimeError(
                "Manifiesto incompleto"
            )

        filas = [
            dict(
                fila
            )
            for fila
            in lector
        ]

    por_id = {}

    for fila in filas:

        juego_id = int(
            fila[
                "juego_id"
            ]
        )

        if (
            juego_id < 1
            or juego_id
            in por_id
        ):
            raise RuntimeError(
                "juego_id inválido/duplicado "
                "en manifiesto"
            )

        por_id[
            juego_id
        ] = fila

    return (
        ruta,
        list(
            campos
        ),
        filas,
        por_id,
    )


def _cache_presente(
    cache,
    fila,
):

    archivo = str(
        fila.get(
            "archivo_cache",
            "",
        )
    )

    return bool(
        NOMBRE_CACHE_RE.fullmatch(
            archivo
        )
        and Path(
            archivo
        ).name
        == archivo
        and (
            cache
            / archivo
        ).is_file()
    )


def _pendientes(
    con,
    cache,
):

    (
        ruta_manifest,
        campos,
        filas,
        por_id,
    ) = _manifiesto(
        cache
    )

    componentes = con.execute("""
        SELECT
            c.id,
            c.juego_id,
            c.tipo,
            c.ruta_remota
        FROM juegos_ps3_componentes c
        JOIN juegos_ps3 j
            ON j.id=c.juego_id
        WHERE
            j.disponible=1
            AND c.disponible=1
            AND c.tamano_bytes IS NULL
            AND c.tipo IN (
                'JB_FOLDER',
                'HDD_JUEGO',
                'DATOS_GAME',
                'CACHE_GAME'
            )
        ORDER BY
            c.juego_id,
            c.id
    """).fetchall()

    juegos = con.execute("""
        SELECT
            id,
            title_id,
            nombre
        FROM juegos_ps3
        WHERE
            disponible=1
            AND title_id IS NOT NULL
            AND trim(title_id) <> ''
        ORDER BY id
    """).fetchall()

    iconos = []

    for (
        juego_id,
        title_id,
        nombre,
    ) in juegos:

        fila = por_id.get(
            int(
                juego_id
            )
        )

        if (
            fila is not None
            and _cache_presente(
                cache,
                fila,
            )
        ):
            continue

        comps = con.execute("""
            SELECT
                id,
                tipo,
                ruta_remota
            FROM juegos_ps3_componentes
            WHERE
                juego_id=?
                AND disponible=1
                AND tipo IN (
                    'JB_FOLDER',
                    'HDD_JUEGO',
                    'DATOS_GAME',
                    'CACHE_GAME'
                )
            ORDER BY
                CASE tipo
                    WHEN 'JB_FOLDER'
                        THEN 1
                    WHEN 'HDD_JUEGO'
                        THEN 2
                    WHEN 'DATOS_GAME'
                        THEN 3
                    WHEN 'CACHE_GAME'
                        THEN 4
                    ELSE 99
                END,
                id
        """, (
            juego_id,
        )).fetchall()

        if not comps:
            continue

        iconos.append({
            "juego_id":
                int(
                    juego_id
                ),

            "title_id":
                str(
                    title_id
                ).upper(),

            "nombre":
                str(
                    nombre
                ),

            "componentes":
                comps,
        })

    return (
        componentes,
        {
            "ruta":
                ruta_manifest,

            "campos":
                campos,

            "filas":
                filas,

            "iconos":
                iconos,
        },
    )


def _preparar_iconos(
    ftp,
    manifest,
):

    preparados = []

    for juego in manifest[
        "iconos"
    ]:

        elegido = None
        errores = []

        for (
            tipo,
            ruta_remota,
        ) in juego[
            "componentes"
        ]:

            ruta = _ruta_icono(
                tipo,
                ruta_remota,
            )

            if ruta is None:
                continue

            try:

                (
                    datos,
                    ancho,
                    alto,
                ) = _leer_png(
                    ftp,
                    ruta,
                )

                elegido = (
                    tipo,
                    ruta,
                    datos,
                    ancho,
                    alto,
                )

                break

            except Exception as exc:

                errores.append(
                    ruta
                    + " -> "
                    + type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                )

        if elegido is None:
            raise RuntimeError(
                "Sin ICON0 para "
                + juego[
                    "title_id"
                ]
                + ": "
                + " | ".join(
                    errores[-4:]
                )
            )

        (
            tipo,
            ruta,
            datos,
            ancho,
            alto,
        ) = elegido

        seguro = re.sub(
            r"[^A-Z0-9_-]+",
            "_",
            juego[
                "title_id"
            ],
        ).strip("_")

        archivo = (
            f"{juego['juego_id']:03d}_"
            f"{seguro}_ICON0.png"
        )

        if not NOMBRE_CACHE_RE.fullmatch(
            archivo
        ):
            raise RuntimeError(
                "Nombre de caché inválido: "
                + archivo
            )

        fila = {
            campo: ""
            for campo
            in manifest[
                "campos"
            ]
        }

        fila.update({
            "juego_id":
                str(
                    juego[
                        "juego_id"
                    ]
                ),

            "archivo_cache":
                archivo,

            "bytes":
                str(
                    len(
                        datos
                    )
                ),

            "ancho":
                str(
                    ancho
                ),

            "alto":
                str(
                    alto
                ),

            "sha256":
                hashlib.sha256(
                    datos
                ).hexdigest(),
        })

        opcionales = {
            "title_id":
                juego[
                    "title_id"
                ],

            "nombre":
                juego[
                    "nombre"
                ],

            "tipo":
                tipo,

            "ruta_remota":
                ruta,

            "ruta_origen":
                ruta,

            "origen_remoto":
                ruta,
        }

        for (
            campo,
            valor,
        ) in opcionales.items():

            if campo in fila:
                fila[
                    campo
                ] = str(
                    valor
                )

        preparados.append({
            "juego_id":
                juego[
                    "juego_id"
                ],

            "archivo":
                archivo,

            "datos":
                datos,

            "fila":
                fila,

            "ruta_origen":
                ruta,
        })

    return preparados


def _guardar_cache(
    cache,
    manifest,
    preparados,
):

    if not preparados:
        return

    reemplazos = {
        item[
            "juego_id"
        ]:
            item[
                "fila"
            ]
        for item
        in preparados
    }

    finales = []
    vistos = set()

    for fila in manifest[
        "filas"
    ]:

        juego_id = int(
            fila[
                "juego_id"
            ]
        )

        if juego_id in reemplazos:

            finales.append(
                reemplazos[
                    juego_id
                ]
            )

            vistos.add(
                juego_id
            )

        else:

            finales.append(
                fila
            )

    for juego_id in sorted(
        reemplazos
    ):

        if juego_id not in vistos:

            finales.append(
                reemplazos[
                    juego_id
                ]
            )

    for item in preparados:

        destino = (
            cache
            / item[
                "archivo"
            ]
        )

        temporal = (
            cache
            / (
                "."
                + item[
                    "archivo"
                ]
                + ".tmp-"
                + str(
                    os.getpid()
                )
            )
        )

        temporal.write_bytes(
            item[
                "datos"
            ]
        )

        os.chmod(
            temporal,
            0o640,
        )

        os.replace(
            temporal,
            destino,
        )

        os.chmod(
            destino,
            0o640,
        )

    temporal = (
        cache
        / (
            ".manifiesto.tsv.tmp-"
            + str(
                os.getpid()
            )
        )
    )

    with temporal.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as fh:

        escritor = csv.DictWriter(
            fh,
            fieldnames=
                manifest[
                    "campos"
                ],
            delimiter="\t",
            lineterminator="\n",
            extrasaction="ignore",
        )

        escritor.writeheader()

        escritor.writerows(
            finales
        )

        fh.flush()

        os.fsync(
            fh.fileno()
        )

    os.chmod(
        temporal,
        0o660,
    )

    os.replace(
        temporal,
        manifest[
            "ruta"
        ],
    )

    os.chmod(
        manifest[
            "ruta"
        ],
        0o660,
    )


def _meta(
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
        valor,
    ))


def _persistir(
    con,
    mediciones,
):

    ahora = _utc()

    if con.in_transaction:
        raise RuntimeError(
            "SQLite ya tiene una transacción activa"
        )

    con.execute(
        "BEGIN IMMEDIATE"
    )

    try:

        for item in mediciones:

            con.execute("""
                UPDATE juegos_ps3_componentes
                SET
                    tamano_bytes=?,
                    actualizado_utc=?
                WHERE
                    id=?
                    AND disponible=1
                    AND tamano_bytes IS NULL
            """, (
                item[
                    "bytes"
                ],
                ahora,
                item[
                    "id"
                ],
            ))

        juegos = con.execute("""
            SELECT
                j.id,
                j.tamano_total_bytes,
                COUNT(c.id),
                SUM(
                    CASE
                        WHEN c.tamano_bytes
                            IS NULL
                        THEN 1
                        ELSE 0
                    END
                ),
                SUM(
                    c.tamano_bytes
                )
            FROM juegos_ps3 j
            LEFT JOIN
                juegos_ps3_componentes c
                ON
                    c.juego_id=j.id
                    AND c.disponible=1
            WHERE j.disponible=1
            GROUP BY
                j.id,
                j.tamano_total_bytes
        """).fetchall()

        actualizados = 0

        for (
            juego_id,
            actual,
            cantidad,
            sin_tamano,
            total,
        ) in juegos:

            if (
                int(
                    cantidad or 0
                ) < 1
                or int(
                    sin_tamano or 0
                ) > 0
            ):
                deseado = None

            else:
                deseado = int(
                    total or 0
                )

            if actual == deseado:
                continue

            con.execute("""
                UPDATE juegos_ps3
                SET
                    tamano_total_bytes=?,
                    actualizado_utc=?
                WHERE id=?
            """, (
                deseado,
                ahora,
                juego_id,
            ))

            actualizados += 1

        _meta(
            con,
            "inventario_juegos_version",
            INVENTARIO_JUEGOS_VERSION,
        )

        _meta(
            con,
            "inventario_juegos_automatizacion_version",
            INVENTARIO_JUEGOS_VERSION,
        )

        _meta(
            con,
            "inventario_juegos_enriquecimiento_version",
            VERSION,
        )

        _meta(
            con,
            "inventario_juegos_enriquecimiento_ultima_utc",
            ahora,
        )

        con.commit()

        return actualizados

    except Exception:

        con.rollback()

        raise


# ============================================================
# J3-B2 FINAL
#
# Enriquecimiento incremental de juegos PS3.
#
# Tamaños:
#   1. MLSD mediante ftplib + latin-1.
#   2. Si falla, fallback lftp du -b.
#   3. Un fallo individual NO aborta el lote.
#
# Carátulas:
#   - ICON0.PNG desde el componente físico real.
#   - conexión FTP corta por candidato.
#   - hasta tres intentos.
#   - un fallo individual NO aborta las demás.
#
# Persistencia:
#   - solamente componentes medidos correctamente.
#   - total lógico únicamente cuando todos los
#     componentes disponibles tienen tamaño conocido.
# ============================================================

import subprocess


def _j3_validar_texto_control(
    valor,
    nombre,
):

    valor = str(
        valor
    )

    if any(
        c in valor
        for c in (
            "\x00",
            "\n",
            "\r",
        )
    ):
        raise RuntimeError(
            f"{nombre} contiene caracteres "
            "de control"
        )

    return valor


def _j3_lftp_quote(
    valor,
):

    valor = _j3_validar_texto_control(
        valor,
        "valor lftp",
    )

    return (
        '"'
        + valor
        .replace(
            "\\",
            "\\\\"
        )
        .replace(
            '"',
            '\\"'
        )
        + '"'
    )


def _j3_tamano_lftp(
    *,
    host,
    puerto,
    usuario,
    password,
    ruta,
):

    host = _j3_validar_texto_control(
        host,
        "host",
    )

    usuario = _j3_validar_texto_control(
        usuario,
        "usuario",
    )

    password = _j3_validar_texto_control(
        password,
        "password",
    )

    ruta = _j3_validar_texto_control(
        ruta,
        "ruta",
    ).rstrip("/")


    if not ruta.startswith(
        "/dev_hdd0/"
    ):
        raise RuntimeError(
            "Ruta lftp fuera de /dev_hdd0"
        )


    script = "\n".join([
        "set cmd:fail-exit yes",
        "set ftp:ssl-allow no",
        "set ftp:passive-mode true",
        "set net:timeout 20",
        "set net:max-retries 3",
        "set net:reconnect-interval-base 2",
        "set net:reconnect-interval-max 8",

        (
            "open -u "
            + _j3_lftp_quote(
                usuario
            )
            + ","
            + _j3_lftp_quote(
                password
            )
            + " -p "
            + str(
                int(
                    puerto
                )
            )
            + " "
            + _j3_lftp_quote(
                host
            )
        ),

        (
            "du -b "
            + _j3_lftp_quote(
                ruta
            )
        ),

        "bye",
        "",
    ])


    try:

        proc = subprocess.run(
            [
                "lftp",
            ],
            input=script.encode(
                "utf-8"
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300,
            check=False,
        )

    except subprocess.TimeoutExpired as exc:

        raise RuntimeError(
            "lftp du excedió 300 s"
        ) from exc


    stdout = proc.stdout.decode(
        "latin-1",
        errors="replace",
    )

    stderr = proc.stderr.decode(
        "latin-1",
        errors="replace",
    )


    if proc.returncode != 0:

        raise RuntimeError(
            "lftp du falló rc="
            + str(
                proc.returncode
            )
            + ": "
            + stderr[-1000:]
        )


    encontrados = []


    for linea in stdout.splitlines():

        partes = linea.strip().split(
            None,
            1,
        )

        if len(
            partes
        ) != 2:
            continue

        valor, nombre = partes

        if (
            nombre.rstrip("/")
            != ruta
        ):
            continue

        try:

            tamano = int(
                valor
            )

        except ValueError:
            continue

        if tamano < 0:
            continue

        encontrados.append(
            tamano
        )


    if len(
        encontrados
    ) != 1:

        raise RuntimeError(
            "No se pudo identificar "
            "un único total raíz en lftp: "
            + ruta
        )


    return encontrados[0]


def _j3_medir_componente_final(
    *,
    host,
    puerto,
    usuario,
    password,
    timeout,
    ruta,
):

    errores = []


    # --------------------------------------------------
    # Método 1: MLSD Python.
    #
    # Un único intento del componente completo.
    # No repetimos árboles enormes tres veces.
    # --------------------------------------------------

    ftp = None

    try:

        ftp = _ftp(
            host,
            puerto,
            usuario,
            password,
            timeout,
        )

        (
            total,
            archivos,
            directorios,
        ) = _tamano_directorio(
            ftp,
            ruta,
        )

        return {
            "bytes":
                int(
                    total
                ),

            "archivos":
                int(
                    archivos
                ),

            "directorios":
                int(
                    directorios
                ),

            "metodo":
                "MLSD",
        }

    except Exception as exc:

        errores.append(
            (
                "MLSD: "
                + type(
                    exc
                ).__name__
                + ": "
                + str(
                    exc
                )
            )
        )

    finally:

        _cerrar(
            ftp
        )


    # --------------------------------------------------
    # Método 2: lftp du -b.
    # --------------------------------------------------

    try:

        total = _j3_tamano_lftp(
            host=host,
            puerto=puerto,
            usuario=usuario,
            password=password,
            ruta=ruta,
        )

        return {
            "bytes":
                int(
                    total
                ),

            "archivos":
                None,

            "directorios":
                None,

            "metodo":
                "LFTP_DU",
        }

    except Exception as exc:

        errores.append(
            (
                "LFTP_DU: "
                + type(
                    exc
                ).__name__
                + ": "
                + str(
                    exc
                )
            )
        )


    raise RuntimeError(
        " | ".join(
            errores
        )
    )


def _j3_preparar_icono_final(
    *,
    host,
    puerto,
    usuario,
    password,
    timeout,
    manifest,
    juego,
):

    errores = []


    for componente in juego[
        "componentes"
    ]:

        if len(
            componente
        ) != 3:

            raise RuntimeError(
                "Componente de icono "
                "sin id/tipo/ruta"
            )


        (
            componente_id,
            tipo,
            ruta_remota,
        ) = componente


        ruta_icono = _ruta_icono(
            tipo,
            ruta_remota,
        )


        if ruta_icono is None:
            continue


        for intento in range(
            1,
            4,
        ):

            ftp = None

            try:

                ftp = _ftp(
                    host,
                    puerto,
                    usuario,
                    password,
                    timeout,
                )

                (
                    datos,
                    ancho,
                    alto,
                ) = _leer_png(
                    ftp,
                    ruta_icono,
                )


                seguro = re.sub(
                    r"[^A-Z0-9_-]+",
                    "_",
                    juego[
                        "title_id"
                    ],
                ).strip("_")


                archivo = (
                    f"{juego['juego_id']:03d}_"
                    f"{seguro}_ICON0.png"
                )


                if not NOMBRE_CACHE_RE.fullmatch(
                    archivo
                ):
                    raise RuntimeError(
                        "Nombre de caché inválido: "
                        + archivo
                    )


                fila = {
                    campo: ""
                    for campo
                    in manifest[
                        "campos"
                    ]
                }


                valores = {
                    "juego_id":
                        str(
                            juego[
                                "juego_id"
                            ]
                        ),

                    "title_id":
                        str(
                            juego[
                                "title_id"
                            ]
                        ),

                    "nombre":
                        str(
                            juego[
                                "nombre"
                            ]
                        ),

                    "componente_id":
                        str(
                            componente_id
                        ),

                    "componente_tipo":
                        str(
                            tipo
                        ),

                    "ruta_icono_remota":
                        str(
                            ruta_icono
                        ),

                    "archivo_cache":
                        archivo,

                    "bytes":
                        str(
                            len(
                                datos
                            )
                        ),

                    "ancho":
                        str(
                            ancho
                        ),

                    "alto":
                        str(
                            alto
                        ),

                    "sha256":
                        hashlib.sha256(
                            datos
                        ).hexdigest(),
                }


                for (
                    campo,
                    valor,
                ) in valores.items():

                    if campo in fila:
                        fila[
                            campo
                        ] = valor


                return {
                    "juego_id":
                        int(
                            juego[
                                "juego_id"
                            ]
                        ),

                    "archivo":
                        archivo,

                    "datos":
                        datos,

                    "fila":
                        fila,

                    "ruta_origen":
                        ruta_icono,

                    "intento":
                        intento,
                }


            except Exception as exc:

                errores.append(
                    (
                        f"{ruta_icono} "
                        f"intento {intento}: "
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )
                )

            finally:

                _cerrar(
                    ftp
                )


    raise RuntimeError(
        " | ".join(
            errores[-12:]
        )
        or
        "No hay ruta ICON0 candidata"
    )


def enriquecer_juegos(
    con,
    *,
    host,
    puerto,
    usuario,
    password,
    timeout,
    cache_directorio=None,
):

    cache = Path(
        cache_directorio
        or CACHE_PREDETERMINADA
    )


    (
        componentes,
        manifest,
    ) = _pendientes(
        con,
        cache,
    )


    print(
        "[J3] Componentes sin tamaño:",
        len(
            componentes
        ),
        flush=True,
    )

    print(
        "[J3] Juegos sin carátula:",
        len(
            manifest[
                "iconos"
            ]
        ),
        flush=True,
    )


    mediciones = []
    fallos_tamano = []


    # ==================================================
    # TAMAÑOS
    # ==================================================

    for (
        componente_id,
        juego_id,
        tipo,
        ruta,
    ) in componentes:

        print()
        print(
            "[J3] Midiendo:",
            componente_id,
            tipo,
            ruta,
            flush=True,
        )


        try:

            resultado = (
                _j3_medir_componente_final(
                    host=host,
                    puerto=puerto,
                    usuario=usuario,
                    password=password,
                    timeout=timeout,
                    ruta=ruta,
                )
            )

        except Exception as exc:

            fallo = {
                "id":
                    int(
                        componente_id
                    ),

                "juego_id":
                    int(
                        juego_id
                    ),

                "tipo":
                    str(
                        tipo
                    ),

                "ruta":
                    str(
                        ruta
                    ),

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


            fallos_tamano.append(
                fallo
            )


            print(
                "[J3] FALLO tamaño:",
                fallo[
                    "error"
                ],
                flush=True,
            )


            continue


        medicion = {
            "id":
                int(
                    componente_id
                ),

            "juego_id":
                int(
                    juego_id
                ),

            "tipo":
                str(
                    tipo
                ),

            "ruta":
                str(
                    ruta
                ),

            "bytes":
                int(
                    resultado[
                        "bytes"
                    ]
                ),

            "archivos":
                resultado[
                    "archivos"
                ],

            "directorios":
                resultado[
                    "directorios"
                ],

            "metodo":
                resultado[
                    "metodo"
                ],
        }


        mediciones.append(
            medicion
        )


        print(
            "[J3] ->",
            medicion[
                "bytes"
            ],
            "bytes | método:",
            medicion[
                "metodo"
            ],
            flush=True,
        )


    # ==================================================
    # CARÁTULAS
    # ==================================================

    preparados = []
    fallos_icono = []


    for juego in manifest[
        "iconos"
    ]:

        print()
        print(
            "[J3] ICON0:",
            juego[
                "juego_id"
            ],
            juego[
                "title_id"
            ],
            juego[
                "nombre"
            ],
            flush=True,
        )


        try:

            preparado = (
                _j3_preparar_icono_final(
                    host=host,
                    puerto=puerto,
                    usuario=usuario,
                    password=password,
                    timeout=timeout,
                    manifest=manifest,
                    juego=juego,
                )
            )

        except Exception as exc:

            fallo = {
                "juego_id":
                    int(
                        juego[
                            "juego_id"
                        ]
                    ),

                "title_id":
                    juego[
                        "title_id"
                    ],

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


            fallos_icono.append(
                fallo
            )


            print(
                "[J3] FALLO ICON0:",
                fallo[
                    "error"
                ],
                flush=True,
            )


            continue


        preparados.append(
            preparado
        )


        print(
            "[J3] ->",
            preparado[
                "archivo"
            ],
            len(
                preparado[
                    "datos"
                ]
            ),
            "bytes",
            flush=True,
        )


    # ==================================================
    # PERSISTENCIA
    # ==================================================

    totales_actualizados = (
        _persistir(
            con,
            mediciones,
        )
    )


    _guardar_cache(
        cache,
        manifest,
        preparados,
    )


    return {
        "ok":
            (
                len(
                    fallos_tamano
                )
                == 0
                and
                len(
                    fallos_icono
                )
                == 0
            ),

        "version":
            VERSION,

        "componentes_pendientes":
            len(
                componentes
            ),

        "componentes_medidos":
            len(
                mediciones
            ),

        "componentes_fallidos":
            len(
                fallos_tamano
            ),

        "totales_actualizados":
            int(
                totales_actualizados
            ),

        "iconos_pendientes":
            len(
                manifest[
                    "iconos"
                ]
            ),

        "iconos_nuevos":
            len(
                preparados
            ),

        "iconos_fallidos":
            len(
                fallos_icono
            ),

        "mediciones":
            mediciones,

        "fallos_tamano":
            fallos_tamano,

        "iconos":
            [
                {
                    "juego_id":
                        item[
                            "juego_id"
                        ],

                    "archivo":
                        item[
                            "archivo"
                        ],

                    "bytes":
                        len(
                            item[
                                "datos"
                            ]
                        ),

                    "ruta_origen":
                        item[
                            "ruta_origen"
                        ],
                }

                for item
                in preparados
            ],

        "fallos_icono":
            fallos_icono,
    }
