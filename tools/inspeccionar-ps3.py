#!/usr/bin/env python3

from __future__ import annotations
import re
import html

import configparser
from datetime import datetime, timezone
from ftplib import FTP
from urllib.request import Request, urlopen
import json
from pathlib import Path
import socket
import sqlite3
import sys
import time

import inventario_juegos
import almacenamiento_runtime


VERSION = "2.5.0"
UMBRAL_FALLOS = 3

CONFIG_PATH = Path(
    "/opt/ctps3/admin/"
    "centro-transferencias-ps3/"
    "config.ini"
)

DB_PATH = Path(
    "/var/lib/ctps3/"
    "centro-transferencias-ps3/"
    "transferencias.sqlite3"
)


ESTADO_LISTA = "LISTA"

ESTADO_TRANSITORIO = (
    "TRANSITORIO"
)

ESTADO_SIN_WEBMAN = (
    "ENCENDIDA_SIN_WEBMAN"
)

ESTADO_NO_DISPONIBLE = (
    "NO_DISPONIBLE"
)


def utc() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat(
        timespec="milliseconds"
    ).replace(
        "+00:00",
        "Z"
    )


def abrir_db() -> sqlite3.Connection:
    con = sqlite3.connect(
        DB_PATH,
        timeout=5
    )

    con.row_factory = sqlite3.Row

    con.execute(
        "PRAGMA foreign_keys=ON"
    )

    con.execute(
        "PRAGMA busy_timeout=5000"
    )

    return con


def registrar_evento(
    con: sqlite3.Connection,
    nivel: str,
    tipo: str,
    mensaje: str,
    datos: dict | None = None,
) -> None:
    con.execute("""
        INSERT INTO eventos (
            nivel,
            tipo,
            mensaje,
            datos_json
        )
        VALUES (?, ?, ?, ?)
    """, (
        nivel,
        tipo,
        mensaje,
        (
            json.dumps(
                datos,
                ensure_ascii=False
            )
            if datos is not None
            else None
        ),
    ))


def cargar_config():
    config = configparser.ConfigParser()

    if not CONFIG_PATH.is_file():
        raise RuntimeError(
            f"No existe {CONFIG_PATH}"
        )

    config.read(CONFIG_PATH)

    host = config["ps3"]["host"]

    puerto = config.getint(
        "ps3",
        "port",
        fallback=21
    )

    usuario = config["ps3"][
        "usuario"
    ]

    password = config["ps3"][
        "password"
    ]

    packages = config["ps3"][
        "directorio_remoto"
    ].rstrip("/")

    timeout = config.getint(
        "transferencias",
        "timeout_segundos",
        fallback=30
    )

    return (
        host,
        puerto,
        usuario,
        password,
        packages,
        timeout,
    )


def probar_tcp(
    host: str,
    puerto: int,
    timeout: float = 1.5,
) -> tuple[str, bool]:
    """
    Devuelve:
        ("ABIERTO", True)
        ("RECHAZADO", True)
        ("INACCESIBLE", False)

    RECHAZADO es importante:
    prueba que existe una pila TCP
    respondiendo en esa IP aunque
    el servicio concreto esté cerrado.
    """

    try:
        with socket.create_connection(
            (host, puerto),
            timeout=timeout
        ):
            return (
                "ABIERTO",
                True,
            )

    except ConnectionRefusedError:
        return (
            "RECHAZADO",
            True,
        )

    except OSError:
        return (
            "INACCESIBLE",
            False,
        )


def clasificar_fallo(
    red_responde: bool,
) -> str:
    if red_responde:
        return (
            ESTADO_SIN_WEBMAN
        )

    return (
        ESTADO_NO_DISPONIBLE
    )


def texto_estado(
    estado: str,
) -> str:
    mapa = {
        ESTADO_LISTA:
            "PS3 lista para transferencias",

        ESTADO_TRANSITORIO:
            "Comprobando estabilidad del servicio",

        ESTADO_SIN_WEBMAN:
            (
                "PS3 accesible, pero "
                "HEN/webMAN/FTP no está listo"
            ),

        ESTADO_NO_DISPONIBLE:
            (
                "PS3 sin respuesta en "
                "los servicios supervisados"
            ),
    }

    return mapa.get(
        estado,
        estado
    )



# ============================================================
# ALM-PS3 1.0.0 — TELEMETRIA DE ESPACIO LIBRE
#
# Fuente: webMAN /popup.ps3.
# La cifra de webMAN es redondeada; por eso se persiste como
# bytes aproximados y también se conserva el texto original.
#
# El fallo de esta sonda queda aislado: no invalida FTP,
# inventarios ni la ultima lectura HDD valida.
# ============================================================

PATRON_HDD_LIBRE = re.compile(
    r"HDD\s*:\s*"
    r"(?P<valor>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unidad>KB|MB|GB|TB)\s*"
    r"(?:libres?|free)\b",
    re.IGNORECASE
)

MULTIPLICADORES_HDD = {
    "KB": 1024,
    "MB": 1024 ** 2,
    "GB": 1024 ** 3,
    "TB": 1024 ** 4,
}


def parsear_espacio_libre_webman(
    contenido: str,
) -> tuple[int, str]:
    texto = html.unescape(
        contenido
    )

    coincidencia = (
        PATRON_HDD_LIBRE.search(
            texto
        )
    )

    if coincidencia is None:
        raise ValueError(
            "HDD_LIBRE_NO_ENCONTRADO"
        )

    valor_texto = (
        coincidencia
        .group("valor")
        .replace(",", ".")
    )

    valor = float(
        valor_texto
    )

    unidad = (
        coincidencia
        .group("unidad")
        .upper()
    )

    if (
        valor < 0
        or valor > 100000
    ):
        raise ValueError(
            "HDD_LIBRE_FUERA_DE_RANGO"
        )

    bytes_aprox = int(
        round(
            valor
            * MULTIPLICADORES_HDD[
                unidad
            ]
        )
    )

    texto_normalizado = (
        f"{valor_texto} "
        f"{unidad} libres"
    )

    return (
        bytes_aprox,
        texto_normalizado,
    )


def consultar_espacio_libre_webman(
    host: str,
    timeout: int,
) -> tuple[int, str, str]:
    url = (
        f"http://{host}/popup.ps3"
    )

    solicitud = Request(
        url,
        headers={
            "User-Agent":
                "CTPS3-ALM/1.0",
        },
        method="GET",
    )

    with urlopen(
        solicitud,
        timeout=timeout,
    ) as respuesta:
        codigo = getattr(
            respuesta,
            "status",
            200
        )

        if int(codigo) != 200:
            raise RuntimeError(
                "HTTP_"
                + str(codigo)
            )

        cuerpo = respuesta.read(
            128 * 1024
        )

    contenido = cuerpo.decode(
        "utf-8",
        errors="replace"
    )

    (
        bytes_aprox,
        texto_normalizado,
    ) = parsear_espacio_libre_webman(
        contenido
    )

    return (
        bytes_aprox,
        texto_normalizado,
        "webMAN:/popup.ps3",
    )


def comprobar_schema(
    con: sqlite3.Connection,
) -> None:
    requeridas = {
        "estado_operativo",
        "estado_detectado",
        "red_responde",
        "ftp_disponible",
        "http_disponible",
        "fallos_consecutivos",
        "detalle_estado",
        "ultima_red_ok_utc",
        "ultimo_ftp_ok_utc",
        "ultimo_http_ok_utc",
            "hdd_libre_bytes_aprox",
        "hdd_libre_texto",
        "hdd_fuente",
        "hdd_ultimo_intento_utc",
        "hdd_ultima_lectura_ok_utc",
        "hdd_ultimo_error",
}

    disponibles = {
        fila[1]
        for fila in con.execute(
            "PRAGMA table_info(ps3_estado)"
        )
    }

    faltan = (
        requeridas
        - disponibles
    )

    if faltan:
        raise RuntimeError(
            "Faltan columnas PS3: "
            + ", ".join(
                sorted(faltan)
            )
        )


def modo_check() -> int:
    (
        host,
        puerto,
        _usuario,
        _password,
        packages,
        _timeout,
    ) = cargar_config()

    con = abrir_db()

    try:
        comprobar_schema(con)

        integridad = con.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        print(
            "Inspector          : OK"
        )

        print(
            "Versión            :",
            VERSION
        )

        print(
            "SQLite             :",
            integridad
        )

        print(
            "PS3                :",
            f"{host}:{puerto}"
        )

        print(
            "Destino            :",
            packages
        )

        print(
            "Umbral fallos      :",
            UMBRAL_FALLOS
        )

        return (
            0
            if integridad == "ok"
            else 1
        )

    finally:
        con.close()


def inventariar(
    ftp: FTP,
    packages: str,
) -> list[dict]:
    ftp.voidcmd(
        "TYPE I"
    )

    elementos = list(
        ftp.mlsd(
            packages
        )
    )

    archivos = []

    for nombre, hechos in elementos:

        if (
            hechos.get("type")
            != "file"
        ):
            continue

        try:
            tamano = int(
                hechos.get(
                    "size",
                    "0"
                )
            )

        except ValueError:
            continue

        archivos.append({
            "nombre":
                nombre,

            "ruta_remota":
                packages
                + "/"
                + nombre,

            "tamano_bytes":
                tamano,

            "fecha_modificacion_ftp":
                hechos.get(
                    "modify"
                ),

            "unix_mode":
                hechos.get(
                    "unix.mode"
                ),

            "unix_uid":
                hechos.get(
                    "unix.uid"
                ),

            "unix_gid":
                hechos.get(
                    "unix.gid"
                ),
        })

    archivos.sort(
        key=lambda item:
            item["nombre"].casefold()
    )

    return archivos


def actualizar_inventario(
    con: sqlite3.Connection,
    archivos: list[dict],
    ahora: str,
) -> tuple[int, int, int]:

    con.execute("""
        UPDATE archivos_remotos
        SET disponible=0
    """)

    nuevos = 0
    modificados = 0

    for archivo in archivos:

        previo = con.execute("""
            SELECT
                id,
                tamano_bytes,
                fecha_modificacion_ftp,
                actualizado_utc
            FROM archivos_remotos
            WHERE nombre=?
        """, (
            archivo["nombre"],
        )).fetchone()

        if previo is None:

            con.execute("""
                INSERT INTO archivos_remotos (
                    nombre,
                    ruta_remota,
                    tamano_bytes,
                    fecha_modificacion_ftp,
                    unix_mode,
                    unix_uid,
                    unix_gid,
                    disponible,
                    detectado_utc,
                    visto_utc,
                    actualizado_utc
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    1,
                    ?, ?, ?
                )
            """, (
                archivo["nombre"],
                archivo[
                    "ruta_remota"
                ],
                archivo[
                    "tamano_bytes"
                ],
                archivo[
                    "fecha_modificacion_ftp"
                ],
                archivo[
                    "unix_mode"
                ],
                archivo[
                    "unix_uid"
                ],
                archivo[
                    "unix_gid"
                ],
                ahora,
                ahora,
                ahora,
            ))

            nuevos += 1

            continue

        cambio = (
            int(
                previo[
                    "tamano_bytes"
                ]
            )
            != archivo[
                "tamano_bytes"
            ]
            or (
                previo[
                    "fecha_modificacion_ftp"
                ]
                != archivo[
                    "fecha_modificacion_ftp"
                ]
            )
        )

        con.execute("""
            UPDATE archivos_remotos
            SET
                ruta_remota=?,
                tamano_bytes=?,
                fecha_modificacion_ftp=?,
                unix_mode=?,
                unix_uid=?,
                unix_gid=?,
                disponible=1,
                visto_utc=?,
                actualizado_utc=?
            WHERE id=?
        """, (
            archivo[
                "ruta_remota"
            ],
            archivo[
                "tamano_bytes"
            ],
            archivo[
                "fecha_modificacion_ftp"
            ],
            archivo[
                "unix_mode"
            ],
            archivo[
                "unix_uid"
            ],
            archivo[
                "unix_gid"
            ],
            ahora,
            (
                ahora
                if cambio
                else previo[
                    "actualizado_utc"
                ]
            ),
            previo["id"],
        ))

        if cambio:
            modificados += 1

    desaparecidos = con.execute("""
        SELECT COUNT(*)
        FROM archivos_remotos
        WHERE disponible=0
    """).fetchone()[0]

    return (
        nuevos,
        modificados,
        int(desaparecidos),
    )



RAIZ_PS3ISO = "/dev_hdd0/PS3ISO"


def nombre_iso_seguro(
    nombre: str,
) -> bool:

    if not isinstance(
        nombre,
        str
    ):
        return False

    if (
        nombre == ""
        or nombre in (
            ".",
            "..",
        )
        or "/" in nombre
        or "\\" in nombre
        or "\x00" in nombre
        or "\n" in nombre
        or "\r" in nombre
    ):
        return False

    return nombre.lower().endswith(
        ".iso"
    )


def inventariar_iso(
    ftp,
    raiz: str = RAIZ_PS3ISO,
) -> list[dict]:

    if raiz != RAIZ_PS3ISO:
        raise RuntimeError(
            "Raíz PS3ISO no permitida"
        )

    ftp.voidcmd(
        "TYPE I"
    )

    elementos = list(
        ftp.mlsd(
            raiz
        )
    )

    archivos = []

    for nombre, hechos in elementos:

        if (
            hechos.get("type")
            != "file"
        ):
            continue

        if not nombre_iso_seguro(
            nombre
        ):
            continue

        try:
            tamano = int(
                hechos.get(
                    "size",
                    "0"
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        if tamano < 0:
            continue

        archivos.append({
            "nombre":
                nombre,

            "ruta_remota":
                raiz
                + "/"
                + nombre,

            "tamano_bytes":
                tamano,

            "fecha_modificacion_ftp":
                hechos.get(
                    "modify"
                ),

            "unix_mode":
                hechos.get(
                    "unix.mode"
                ),

            "unix_uid":
                hechos.get(
                    "unix.uid"
                ),

            "unix_gid":
                hechos.get(
                    "unix.gid"
                ),
        })

    archivos.sort(
        key=lambda item:
            item["nombre"].casefold()
    )

    return archivos


def actualizar_inventario_iso(
    con: sqlite3.Connection,
    archivos: list[dict],
    ahora: str,
) -> tuple[int, int, int]:

    con.execute(
        """
        UPDATE archivos_remotos_iso
        SET disponible=0
        """
    )

    nuevos = 0
    modificados = 0

    for archivo in archivos:

        nombre = str(
            archivo["nombre"]
        )

        ruta = str(
            archivo["ruta_remota"]
        )

        if not nombre_iso_seguro(
            nombre
        ):
            raise RuntimeError(
                "Nombre ISO inválido"
            )

        ruta_esperada = (
            RAIZ_PS3ISO
            + "/"
            + nombre
        )

        if ruta != ruta_esperada:
            raise RuntimeError(
                "Ruta ISO remota inválida"
            )

        previo = con.execute(
            """
            SELECT
                id,
                nombre,
                tamano_bytes,
                fecha_modificacion_ftp,
                actualizado_utc
            FROM archivos_remotos_iso
            WHERE ruta_remota=?
            """,
            (ruta,)
        ).fetchone()

        if previo is None:

            con.execute(
                """
                INSERT INTO archivos_remotos_iso (
                    nombre,
                    ruta_remota,
                    tamano_bytes,
                    fecha_modificacion_ftp,
                    unix_mode,
                    unix_uid,
                    unix_gid,
                    disponible,
                    detectado_utc,
                    visto_utc,
                    actualizado_utc
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    1,
                    ?, ?, ?
                )
                """,
                (
                    nombre,
                    ruta,
                    int(
                        archivo[
                            "tamano_bytes"
                        ]
                    ),
                    archivo[
                        "fecha_modificacion_ftp"
                    ],
                    archivo[
                        "unix_mode"
                    ],
                    archivo[
                        "unix_uid"
                    ],
                    archivo[
                        "unix_gid"
                    ],
                    ahora,
                    ahora,
                    ahora,
                )
            )

            nuevos += 1

            continue

        cambio = (
            previo["nombre"]
            != nombre

            or int(
                previo[
                    "tamano_bytes"
                ]
            )
            != int(
                archivo[
                    "tamano_bytes"
                ]
            )

            or previo[
                "fecha_modificacion_ftp"
            ]
            != archivo[
                "fecha_modificacion_ftp"
            ]
        )

        con.execute(
            """
            UPDATE archivos_remotos_iso
            SET
                nombre=?,
                tamano_bytes=?,
                fecha_modificacion_ftp=?,
                unix_mode=?,
                unix_uid=?,
                unix_gid=?,
                disponible=1,
                visto_utc=?,
                actualizado_utc=
                    CASE
                        WHEN ?=1
                        THEN ?
                        ELSE actualizado_utc
                    END
            WHERE id=?
            """,
            (
                nombre,
                int(
                    archivo[
                        "tamano_bytes"
                    ]
                ),
                archivo[
                    "fecha_modificacion_ftp"
                ],
                archivo[
                    "unix_mode"
                ],
                archivo[
                    "unix_uid"
                ],
                archivo[
                    "unix_gid"
                ],
                ahora,
                1 if cambio else 0,
                ahora,
                int(
                    previo["id"]
                ),
            )
        )

        if cambio:
            modificados += 1

    desaparecidos = con.execute(
        """
        SELECT COUNT(*)
        FROM archivos_remotos_iso
        WHERE disponible=0
        """
    ).fetchone()[0]

    return (
        nuevos,
        modificados,
        int(
            desaparecidos
        ),
    )



def inventariar_iso_conexion(
    host: str,
    puerto: int,
    usuario: str,
    password: str,
    timeout: int,
) -> list[dict]:

    ftp_iso = FTP(
        encoding="latin-1"
    )

    conectado = False

    try:
        ftp_iso.connect(
            host,
            puerto,
            timeout=timeout
        )

        conectado = True

        ftp_iso.login(
            usuario,
            password
        )

        return inventariar_iso(
            ftp_iso
        )

    finally:

        if conectado:

            try:
                ftp_iso.quit()

            except Exception:
                ftp_iso.close()




RAIZ_PS2ISO = "/dev_hdd0/PS2ISO"


def nombre_ps2iso_seguro(
    nombre: str,
) -> bool:

    if not isinstance(
        nombre,
        str
    ):
        return False

    if (
        nombre == ""
        or nombre in (
            ".",
            "..",
        )
        or "/" in nombre
        or "\\" in nombre
        or "\x00" in nombre
        or "\n" in nombre
        or "\r" in nombre
    ):
        return False

    return nombre.endswith(
        ".BIN.ENC"
    )


def inventariar_ps2iso(
    ftp,
    raiz: str = RAIZ_PS2ISO,
) -> list[dict]:

    if raiz != RAIZ_PS2ISO:
        raise RuntimeError(
            "Raíz PS2ISO no permitida"
        )

    ftp.voidcmd(
        "TYPE I"
    )

    elementos = list(
        ftp.mlsd(
            raiz
        )
    )

    archivos = []

    for nombre, hechos in elementos:

        if (
            hechos.get("type")
            != "file"
        ):
            continue

        if not nombre_ps2iso_seguro(
            nombre
        ):
            continue

        try:
            tamano = int(
                hechos.get(
                    "size",
                    "0"
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        if tamano < 0:
            continue

        archivos.append({
            "nombre":
                nombre,

            "ruta_remota":
                raiz
                + "/"
                + nombre,

            "tamano_bytes":
                tamano,

            "fecha_modificacion_ftp":
                hechos.get(
                    "modify"
                ),

            "unix_mode":
                hechos.get(
                    "unix.mode"
                ),

            "unix_uid":
                hechos.get(
                    "unix.uid"
                ),

            "unix_gid":
                hechos.get(
                    "unix.gid"
                ),
        })

    archivos.sort(
        key=lambda item:
            item["nombre"].casefold()
    )

    return archivos


def actualizar_inventario_ps2iso(
    con: sqlite3.Connection,
    archivos: list[dict],
    ahora: str,
) -> tuple[int, int, int]:

    con.execute(
        """
        UPDATE archivos_remotos_ps2iso
        SET disponible=0
        """
    )

    nuevos = 0
    modificados = 0

    for archivo in archivos:

        nombre = str(
            archivo["nombre"]
        )

        ruta = str(
            archivo["ruta_remota"]
        )

        if not nombre_ps2iso_seguro(
            nombre
        ):
            raise RuntimeError(
                "Nombre PS2ISO inválido"
            )

        ruta_esperada = (
            RAIZ_PS2ISO
            + "/"
            + nombre
        )

        if ruta != ruta_esperada:
            raise RuntimeError(
                "Ruta PS2ISO remota inválida"
            )

        previo = con.execute(
            """
            SELECT
                id,
                nombre,
                tamano_bytes,
                fecha_modificacion_ftp,
                actualizado_utc
            FROM archivos_remotos_ps2iso
            WHERE ruta_remota=?
            """,
            (ruta,)
        ).fetchone()

        if previo is None:

            con.execute(
                """
                INSERT INTO archivos_remotos_ps2iso (
                    nombre,
                    ruta_remota,
                    tamano_bytes,
                    fecha_modificacion_ftp,
                    unix_mode,
                    unix_uid,
                    unix_gid,
                    disponible,
                    detectado_utc,
                    visto_utc,
                    actualizado_utc
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    1,
                    ?, ?, ?
                )
                """,
                (
                    nombre,
                    ruta,
                    int(
                        archivo[
                            "tamano_bytes"
                        ]
                    ),
                    archivo[
                        "fecha_modificacion_ftp"
                    ],
                    archivo[
                        "unix_mode"
                    ],
                    archivo[
                        "unix_uid"
                    ],
                    archivo[
                        "unix_gid"
                    ],
                    ahora,
                    ahora,
                    ahora,
                )
            )

            nuevos += 1

            continue

        cambio = (
            previo["nombre"]
            != nombre

            or int(
                previo[
                    "tamano_bytes"
                ]
            )
            != int(
                archivo[
                    "tamano_bytes"
                ]
            )

            or previo[
                "fecha_modificacion_ftp"
            ]
            != archivo[
                "fecha_modificacion_ftp"
            ]
        )

        con.execute(
            """
            UPDATE archivos_remotos_ps2iso
            SET
                nombre=?,
                tamano_bytes=?,
                fecha_modificacion_ftp=?,
                unix_mode=?,
                unix_uid=?,
                unix_gid=?,
                disponible=1,
                visto_utc=?,
                actualizado_utc=
                    CASE
                        WHEN ?=1
                        THEN ?
                        ELSE actualizado_utc
                    END
            WHERE id=?
            """,
            (
                nombre,
                int(
                    archivo[
                        "tamano_bytes"
                    ]
                ),
                archivo[
                    "fecha_modificacion_ftp"
                ],
                archivo[
                    "unix_mode"
                ],
                archivo[
                    "unix_uid"
                ],
                archivo[
                    "unix_gid"
                ],
                ahora,
                1 if cambio else 0,
                ahora,
                int(
                    previo["id"]
                ),
            )
        )

        if cambio:
            modificados += 1

    desaparecidos = con.execute(
        """
        SELECT COUNT(*)
        FROM archivos_remotos_ps2iso
        WHERE disponible=0
        """
    ).fetchone()[0]

    return (
        nuevos,
        modificados,
        int(
            desaparecidos
        ),
    )



def inventariar_ps2iso_conexion(
    host: str,
    puerto: int,
    usuario: str,
    password: str,
    timeout: int,
) -> list[dict]:

    ftp_iso = FTP(
        encoding="latin-1"
    )

    conectado = False

    try:
        ftp_iso.connect(
            host,
            puerto,
            timeout=timeout
        )

        conectado = True

        ftp_iso.login(
            usuario,
            password
        )

        return inventariar_ps2iso(
            ftp_iso
        )

    finally:

        if conectado:

            try:
                ftp_iso.quit()

            except Exception:
                ftp_iso.close()




def actualizar_almacenamiento_desde_juegos(
    con,
    juegos_resultado,
    *,
    host,
    puerto,
    usuario,
    password,
    timeout,
):
    """
    Integra ESP a partir del resultado J3 ya obtenido.
    Nunca enumera /dev_hdd0/game por cuenta propia.
    Cualquier fallo queda aislado del estado operativo PS3.
    """

    try:
        return (
            almacenamiento_runtime
            .actualizar_desde_resultado_j3(
                con,
                juegos_resultado,
                host=host,
                puerto=puerto,
                usuario=usuario,
                password=password,
                timeout=timeout,
            )
        )

    except Exception as exc:
        if con.in_transaction:
            con.rollback()

        return {
            "ejecutado": True,
            "ok": False,
            "version": getattr(
                almacenamiento_runtime,
                "VERSION",
                None,
            ),
            "error": (
                type(exc).__name__
                + ": "
                + str(exc)
            ),
        }


def main() -> int:

    if (
        len(sys.argv) > 1
        and sys.argv[1] == "--check"
    ):
        return modo_check()

    (
        host,
        puerto,
        usuario,
        password,
        packages,
        timeout,
    ) = cargar_config()

    con = abrir_db()

    comprobar_schema(con)

    inicio = time.monotonic()
    ahora = utc()

    estado_previo = con.execute("""
        SELECT
            conectado,
            paquetes_remotos,
            estado_operativo,
            estado_detectado,
            fallos_consecutivos
        FROM ps3_estado
        WHERE id=1
    """).fetchone()

    conectado_previo = (
        bool(
            estado_previo[
                "conectado"
            ]
        )
        if estado_previo
        else False
    )

    operativo_previo = (
        estado_previo[
            "estado_operativo"
        ]
        if estado_previo
        else ESTADO_NO_DISPONIBLE
    )

    fallos_previos = (
        int(
            estado_previo[
                "fallos_consecutivos"
            ]
            or 0
        )
        if estado_previo
        else 0
    )

    ftp = FTP()
    ftp.encoding = "latin-1"

    try:
        ftp.connect(
            host,
            puerto,
            timeout=timeout
        )

        banner = (
            ftp.getwelcome()
            or ""
        )

        ftp.login(
            usuario,
            password
        )

        archivos = inventariar(
            ftp,
            packages
        )

        http_estado, _ = probar_tcp(
            host,
            80
        )

        http_ok = (
            http_estado
            == "ABIERTO"
        )

        hdd_ahora = utc()
        hdd_libre_bytes_aprox = None
        hdd_libre_texto = None
        hdd_fuente = None
        hdd_error = None

        if http_ok:
            try:
                (
                    hdd_libre_bytes_aprox,
                    hdd_libre_texto,
                    hdd_fuente,
                ) = (
                    consultar_espacio_libre_webman(
                        host,
                        timeout,
                    )
                )

            except Exception as hdd_exc:
                hdd_error = (
                    type(
                        hdd_exc
                    ).__name__
                    + ": "
                    + str(
                        hdd_exc
                    )
                )

        else:
            hdd_error = (
                "webMAN HTTP no disponible"
            )

        con.execute(
            "BEGIN IMMEDIATE"
        )

        (
            nuevos,
            modificados,
            desaparecidos,
        ) = actualizar_inventario(
            con,
            archivos,
            ahora
        )

        duracion_ms = int(
            (
                time.monotonic()
                - inicio
            ) * 1000
        )

        con.execute("""
            UPDATE ps3_estado
            SET
                conectado=1,
                host=?,
                puerto=?,
                banner=?,
                ruta_packages=?,
                paquetes_remotos=?,

                estado_operativo='LISTA',
                estado_detectado='LISTA',

                red_responde=1,
                ftp_disponible=1,
                http_disponible=?,

                fallos_consecutivos=0,

                detalle_estado=
                    'FTP operativo; inventario remoto actualizado',

                ultima_consulta_utc=?,
                ultima_conexion_ok_utc=?,
                ultima_red_ok_utc=?,
                ultimo_ftp_ok_utc=?,

                ultimo_http_ok_utc =
                    CASE
                        WHEN ?=1
                            THEN ?
                        ELSE ultimo_http_ok_utc
                    END,

                ultimo_error=NULL,
                duracion_consulta_ms=?

            WHERE id=1
        """, (
            host,
            puerto,
            banner,
            packages,
            len(archivos),
            1 if http_ok else 0,
            ahora,
            ahora,
            ahora,
            ahora,
            1 if http_ok else 0,
            ahora,
            duracion_ms,
        ))

        con.execute(
            """
            UPDATE ps3_estado
            SET
                hdd_ultimo_intento_utc=?,

                hdd_libre_bytes_aprox =
                    CASE
                        WHEN ? IS NOT NULL
                            THEN ?
                        ELSE hdd_libre_bytes_aprox
                    END,

                hdd_libre_texto =
                    CASE
                        WHEN ? IS NOT NULL
                            THEN ?
                        ELSE hdd_libre_texto
                    END,

                hdd_fuente =
                    CASE
                        WHEN ? IS NOT NULL
                            THEN ?
                        ELSE hdd_fuente
                    END,

                hdd_ultima_lectura_ok_utc =
                    CASE
                        WHEN ? IS NOT NULL
                            THEN ?
                        ELSE hdd_ultima_lectura_ok_utc
                    END,

                hdd_ultimo_error=?

            WHERE id=1
            """,
            (
                hdd_ahora,

                hdd_libre_bytes_aprox,
                hdd_libre_bytes_aprox,

                hdd_libre_texto,
                hdd_libre_texto,

                hdd_fuente,
                hdd_fuente,

                hdd_libre_bytes_aprox,
                hdd_ahora,

                hdd_error,
            )
        )

        hubo_cambios = (
            nuevos > 0
            or modificados > 0
            or desaparecidos > 0
        )

        if hubo_cambios:
            registrar_evento(
                con,
                "INFO",
                "INVENTARIO_PS3_ACTUALIZADO",
                (
                    "Inventario PS3 actualizado: "
                    f"{len(archivos)} archivos"
                ),
                {
                    "nuevos":
                        nuevos,

                    "modificados":
                        modificados,

                    "desaparecidos":
                        desaparecidos,

                    "total":
                        len(archivos),
                }
            )

        if (
            operativo_previo
            != ESTADO_LISTA
        ):
            registrar_evento(
                con,
                "INFO",
                "PS3_LISTA",
                (
                    "PS3 lista para "
                    "transferencias"
                ),
                {
                    "host":
                        host,

                    "banner":
                        banner,

                    "estado_previo":
                        operativo_previo,
                }
            )

        con.commit()

        if hdd_libre_bytes_aprox is not None:
            print(
                "HDD libre        :",
                hdd_libre_texto,
            )
        else:
            print(
                "HDD libre        :",
                (
                    "SIN LECTURA NUEVA"
                    + (
                        " · "
                        + hdd_error
                        if hdd_error
                        else ""
                    )
                ),
            )

        # --------------------------------------------------
        # Inventario PS3ISO
        #
        # Se ejecuta después de que /packages confirmó
        # el estado LISTA.
        #
        # Utiliza una conexión FTP independiente con
        # Latin-1 porque webMAN puede devolver caracteres
        # no UTF-8 en el canal de control.
        #
        # Su fallo queda aislado y nunca modifica
        # ps3_estado.
        # --------------------------------------------------

        iso_resultado = {
            "ok": False,
            "archivos": 0,
            "nuevos": 0,
            "modificados": 0,
            "desaparecidos": 0,
            "error": None,
        }

        try:
            archivos_iso = (
                inventariar_iso_conexion(
                    host=host,
                    puerto=puerto,
                    usuario=usuario,
                    password=password,
                    timeout=timeout,
                )
            )

            ahora_iso = utc()

            con.execute(
                "BEGIN IMMEDIATE"
            )

            try:
                (
                    nuevos_iso,
                    modificados_iso,
                    desaparecidos_iso,
                ) = actualizar_inventario_iso(
                    con,
                    archivos_iso,
                    ahora_iso
                )

                con.commit()

            except Exception:
                con.rollback()
                raise

            iso_resultado = {
                "ok": True,

                "archivos":
                    len(
                        archivos_iso
                    ),

                "nuevos":
                    nuevos_iso,

                "modificados":
                    modificados_iso,

                "desaparecidos":
                    desaparecidos_iso,

                "error":
                    None,
            }

        except Exception as iso_exc:

            if con.in_transaction:
                con.rollback()

            iso_resultado = {
                "ok": False,
                "archivos": 0,
                "nuevos": 0,
                "modificados": 0,
                "desaparecidos": 0,

                "error":
                    (
                        type(
                            iso_exc
                        ).__name__
                        + ": "
                        + str(
                            iso_exc
                        )
                    ),
            }

        print(
            "PS3ISO          :",
            (
                "OK"
                if iso_resultado["ok"]
                else "ERROR AISLADO"
            )
        )

        print(
            "ISO remotas     :",
            iso_resultado[
                "archivos"
            ]
        )

        if (
            not iso_resultado["ok"]
            and iso_resultado["error"]
        ):
            print(
                "ISO detalle    :",
                iso_resultado[
                    "error"
                ]
            )

        # Inventario PS2ISO
        #
        # Se ejecuta después de que /packages confirmó
        # el estado LISTA.
        #
        # Utiliza una conexión FTP independiente con
        # Latin-1 porque webMAN puede devolver caracteres
        # no UTF-8 en el canal de control.
        #
        # Su fallo queda aislado y nunca modifica
        # ps3_estado.
        # --------------------------------------------------

        ps2_resultado = {
            "ok": False,
            "archivos": 0,
            "nuevos": 0,
            "modificados": 0,
            "desaparecidos": 0,
            "error": None,
        }

        try:
            archivos_ps2 = (
                inventariar_ps2iso_conexion(
                    host=host,
                    puerto=puerto,
                    usuario=usuario,
                    password=password,
                    timeout=timeout,
                )
            )

            ahora_ps2 = utc()

            con.execute(
                "BEGIN IMMEDIATE"
            )

            try:
                (
                    nuevos_ps2,
                    modificados_ps2,
                    desaparecidos_ps2,
                ) = actualizar_inventario_ps2iso(
                    con,
                    archivos_ps2,
                    ahora_ps2
                )

                con.commit()

            except Exception:
                con.rollback()
                raise

            ps2_resultado = {
                "ok": True,

                "archivos":
                    len(
                        archivos_ps2
                    ),

                "nuevos":
                    nuevos_ps2,

                "modificados":
                    modificados_ps2,

                "desaparecidos":
                    desaparecidos_ps2,

                "error":
                    None,
            }

        except Exception as ps2_exc:

            if con.in_transaction:
                con.rollback()

            ps2_resultado = {
                "ok": False,
                "archivos": 0,
                "nuevos": 0,
                "modificados": 0,
                "desaparecidos": 0,

                "error":
                    (
                        type(
                            ps2_exc
                        ).__name__
                        + ": "
                        + str(
                            ps2_exc
                        )
                    ),
            }

        print(
            "PS2ISO          :",
            (
                "OK"
                if ps2_resultado["ok"]
                else "ERROR AISLADO"
            )
        )

        print(
            "PS2 remotas     :",
            ps2_resultado[
                "archivos"
            ]
        )

        if (
            not ps2_resultado["ok"]
            and ps2_resultado["error"]
        ):
            print(
                "PS2 detalle    :",
                ps2_resultado[
                    "error"
                ]
            )

        # Inventario de Juegos
        #
        # Se ejecuta únicamente después de que el inventario
        # principal /packages terminó y confirmó PS3 LISTA.
        #
        # Cualquier fallo queda aislado y NO modifica el
        # estado operativo de la PS3.
        # --------------------------------------------------

        try:
            juegos_resultado = (
                inventario_juegos
                .actualizar_juegos_si_corresponde(
                    con,
                    host=host,
                    puerto=puerto,
                    usuario=usuario,
                    password=password,
                    timeout=min(
                        timeout,
                        10,
                    ),
                )
            )

        except Exception as juegos_exc:
            juegos_resultado = {
                "ejecutado": True,
                "ok": False,
                "error": (
                    f"{type(juegos_exc).__name__}: "
                    f"{juegos_exc}"
                ),
            }

        # --------------------------------------------------
        # ESP — inventario físico de /dev_hdd0/game
        #
        # Reutiliza exclusivamente el resultado del barrido J3.
        # Si J3 no ejecutó o falló, conserva el último snapshot.
        # --------------------------------------------------
        almacenamiento_resultado = (
            actualizar_almacenamiento_desde_juegos(
                con,
                juegos_resultado,
                host=host,
                puerto=puerto,
                usuario=usuario,
                password=password,
                timeout=min(
                    timeout,
                    10,
                ),
            )
        )


        print(
            "PS3             : LISTA"
        )

        print(
            "Estado detectado:",
            ESTADO_LISTA
        )

        print(
            "Red             : RESPONDE"
        )

        print(
            "FTP 21          : ABIERTO"
        )

        print(
            "HTTP 80         :",
            (
                "ABIERTO"
                if http_ok
                else "NO DISPONIBLE"
            )
        )

        print(
            "Banner          :",
            banner
        )

        print(
            "Packages        :",
            packages
        )

        print(
            "Archivos remotos:",
            len(archivos)
        )

        print(
            "Nuevos          :",
            nuevos
        )

        print(
            "Modificados     :",
            modificados
        )

        print(
            "No disponibles  :",
            desaparecidos
        )

        print(
            "Fallos seguidos : 0"
        )

        print(
            "Duración        :",
            f"{duracion_ms} ms"
        )

        if not juegos_resultado[
            "ejecutado"
        ]:
            print(
                "Juegos          : EN ESPERA"
            )

            print(
                "Próximo Juegos  :",
                f"~{juegos_resultado.get('restante_segundos', 0)} s"
            )

        elif juegos_resultado[
            "ok"
        ]:
            print(
                "Juegos          : OK"
            )

            print(
                "Juegos detectados:",
                juegos_resultado.get(
                    "juegos",
                    "-"
                )
            )

            print(
                "Comp. Juegos    :",
                juegos_resultado.get(
                    "componentes",
                    "-"
                )
            )

            print(
                "Duración Juegos :",
                f"{juegos_resultado.get('duracion_ms', 0)} ms"
            )

        else:
            print(
                "Juegos          : ERROR AISLADO"
            )

            print(
                "Error Juegos    :",
                juegos_resultado.get(
                    "error",
                    "desconocido"
                )
            )

        return 0

    except Exception as exc:

        duracion_ms = int(
            (
                time.monotonic()
                - inicio
            ) * 1000
        )

        mensaje = (
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        ftp_estado, ftp_responde = (
            probar_tcp(
                host,
                puerto
            )
        )

        http_estado, http_responde = (
            probar_tcp(
                host,
                80
            )
        )

        red_responde = (
            ftp_responde
            or http_responde
        )

        ftp_ok = (
            ftp_estado
            == "ABIERTO"
        )

        http_ok = (
            http_estado
            == "ABIERTO"
        )

        detectado = clasificar_fallo(
            red_responde
        )

        fallos = min(
            fallos_previos + 1,
            999
        )

        mantener_histeresis = (
            conectado_previo
            and fallos
                < UMBRAL_FALLOS
        )

        if mantener_histeresis:
            operativo = (
                ESTADO_TRANSITORIO
            )

            conectado_legacy = 1

            detalle = (
                f"Fallo transitorio "
                f"{fallos}/"
                f"{UMBRAL_FALLOS}; "
                f"detectado: "
                f"{texto_estado(detectado)}"
            )

        else:
            operativo = detectado

            conectado_legacy = 0

            detalle = texto_estado(
                operativo
            )

        try:
            con.execute(
                "BEGIN IMMEDIATE"
            )

            con.execute("""
                UPDATE ps3_estado
                SET
                    conectado=?,
                    host=?,
                    puerto=?,

                    estado_operativo=?,
                    estado_detectado=?,

                    red_responde=?,
                    ftp_disponible=?,
                    http_disponible=?,

                    fallos_consecutivos=?,
                    detalle_estado=?,

                    ultima_consulta_utc=?,

                    ultima_red_ok_utc =
                        CASE
                            WHEN ?=1
                                THEN ?
                            ELSE ultima_red_ok_utc
                        END,

                    ultimo_http_ok_utc =
                        CASE
                            WHEN ?=1
                                THEN ?
                            ELSE ultimo_http_ok_utc
                        END,

                    ultimo_error=?,
                    duracion_consulta_ms=?

                WHERE id=1
            """, (
                conectado_legacy,
                host,
                puerto,

                operativo,
                detectado,

                1
                    if red_responde
                    else 0,

                1
                    if ftp_ok
                    else 0,

                1
                    if http_ok
                    else 0,

                fallos,
                detalle,

                ahora,

                1
                    if red_responde
                    else 0,

                ahora,

                1
                    if http_ok
                    else 0,

                ahora,

                mensaje,
                duracion_ms,
            ))

            if (
                operativo
                == ESTADO_TRANSITORIO
                and operativo_previo
                    != ESTADO_TRANSITORIO
            ):
                registrar_evento(
                    con,
                    "AVISO",
                    "PS3_INCIDENCIA_TRANSITORIA",
                    (
                        "Incidencia transitoria "
                        "al consultar la PS3"
                    ),
                    {
                        "host":
                            host,

                        "fallos":
                            fallos,

                        "umbral":
                            UMBRAL_FALLOS,

                        "detectado":
                            detectado,

                        "error":
                            mensaje,
                    }
                )

            elif (
                operativo
                != ESTADO_TRANSITORIO
                and operativo
                    != operativo_previo
            ):

                if (
                    operativo
                    == ESTADO_SIN_WEBMAN
                ):
                    tipo = (
                        "PS3_ENCENDIDA_SIN_WEBMAN"
                    )

                    evento_mensaje = (
                        "PS3 accesible, pero "
                        "HEN/webMAN/FTP "
                        "no está disponible"
                    )

                else:
                    tipo = (
                        "PS3_NO_DISPONIBLE"
                    )

                    evento_mensaje = (
                        "PS3 no disponible "
                        "en la red supervisada"
                    )

                registrar_evento(
                    con,
                    "AVISO",
                    tipo,
                    evento_mensaje,
                    {
                        "host":
                            host,

                        "ftp":
                            ftp_estado,

                        "http":
                            http_estado,

                        "fallos":
                            fallos,

                        "error":
                            mensaje,
                    }
                )

            con.commit()

        except Exception:
            con.rollback()
            raise

        print(
            "PS3             :",
            operativo
        )

        print(
            "Estado detectado:",
            detectado
        )

        print(
            "Red             :",
            (
                "RESPONDE"
                if red_responde
                else "SIN RESPUESTA"
            )
        )

        print(
            "FTP 21          :",
            ftp_estado
        )

        print(
            "HTTP 80         :",
            http_estado
        )

        print(
            "Fallos seguidos :",
            f"{fallos}/{UMBRAL_FALLOS}"
        )

        print(
            "Error           :",
            mensaje
        )

        print(
            "Duración        :",
            f"{duracion_ms} ms"
        )

        return 0

    finally:
        try:
            ftp.quit()

        except Exception:
            try:
                ftp.close()

            except Exception:
                pass

        con.close()


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
