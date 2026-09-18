#!/usr/bin/env python3

from __future__ import annotations

import configparser
from io import BytesIO
import ftplib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
from ftplib import FTP
from urllib.parse import quote
from urllib.request import Request, urlopen
import sys
import time
import threading
from datetime import datetime, timezone
from typing import Optional


VERSION = "1.12.0"

CONFIG_PATH = Path(
    "/opt/ctps3/config/config.ini"
)

DB_PATH = Path(
    "/var/lib/ctps3/"
    "transferencias.sqlite3"
)

LOG_DIR = Path(
    "/var/log/ctps3"
)

LOG_FILE = LOG_DIR / "worker.log"

LFTP = Path("/usr/bin/lftp")

DETENER = False


def utc() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def configurar_log() -> logging.Logger:
    logger = logging.getLogger("ctps3")

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    archivo = RotatingFileHandler(
        LOG_FILE,
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )

    archivo.setFormatter(formatter)

    consola = logging.StreamHandler(sys.stdout)
    consola.setFormatter(formatter)

    logger.addHandler(archivo)
    logger.addHandler(consola)

    return logger


LOG = configurar_log()


def manejar_senal(signum, frame) -> None:
    global DETENER

    DETENER = True

    LOG.info(
        "Señal %s recibida; finalización controlada.",
        signum
    )


signal.signal(signal.SIGTERM, manejar_senal)
signal.signal(signal.SIGINT, manejar_senal)


def cargar_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()

    if not CONFIG_PATH.is_file():
        raise RuntimeError(
            f"No existe configuración: {CONFIG_PATH}"
        )

    config.read(CONFIG_PATH)

    return config


CONFIG = cargar_config()

HOST = CONFIG["ps3"]["host"]
PORT = CONFIG.getint("ps3", "port", fallback=21)
USER = CONFIG["ps3"]["usuario"]
PASSWORD = CONFIG["ps3"]["password"]

REMOTE_DIR = CONFIG["ps3"][
    "directorio_remoto"
].rstrip("/")

LOCAL_ROOT = Path(
    CONFIG["local"]["directorio_pkg"]
).resolve()

TIMEOUT = CONFIG.getint(
    "transferencias",
    "timeout_segundos",
    fallback=30
)

NET_RETRIES = CONFIG.getint(
    "transferencias",
    "max_reintentos_red",
    fallback=20
)

RECONNECT_BASE = CONFIG.getint(
    "transferencias",
    "reconexion_base_segundos",
    fallback=5
)

RECONNECT_MAX = CONFIG.getint(
    "transferencias",
    "reconexion_maxima_segundos",
    fallback=30
)

MAX_TRANSFER_RETRIES = CONFIG.getint(
    "transferencias",
    "max_reintentos_transferencia",
    fallback=3
)

QUEUE_INTERVAL = CONFIG.getfloat(
    "worker",
    "intervalo_cola_segundos",
    fallback=1
)

PROGRESS_INTERVAL = CONFIG.getfloat(
    "worker",
    "intervalo_progreso_segundos",
    fallback=1
)

REMOTE_QUERY_INTERVAL = CONFIG.getfloat(
    "worker",
    "consulta_remota_segundos",
    fallback=2
)

HEARTBEAT_INTERVAL = CONFIG.getfloat(
    "worker",
    "heartbeat_segundos",
    fallback=5
)


def conectar_db() -> sqlite3.Connection:
    con = sqlite3.connect(
        DB_PATH,
        timeout=5
    )

    con.row_factory = sqlite3.Row

    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")

    return con


DB = conectar_db()


def actualizar_worker(
    estado: str,
    mensaje: str,
    transferencia_id: Optional[int] = None,
) -> None:
    ahora = utc()

    DB.execute("""
        UPDATE worker_estado
        SET
            estado=?,
            pid=?,
            version=?,
            transferencia_id=?,
            heartbeat_utc=?,
            iniciado_utc=COALESCE(iniciado_utc, ?),
            mensaje=?
        WHERE id=1
    """, (
        estado,
        os.getpid(),
        VERSION,
        transferencia_id,
        ahora,
        ahora,
        mensaje
    ))

    DB.commit()


def evento(
    tipo: str,
    mensaje: str,
    transferencia_id: Optional[int] = None,
    nivel: str = "INFO",
    datos: Optional[dict] = None,
) -> None:
    DB.execute("""
        INSERT INTO eventos (
            transferencia_id,
            nivel,
            tipo,
            mensaje,
            datos_json
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        transferencia_id,
        nivel,
        tipo,
        mensaje,
        json.dumps(
            datos,
            ensure_ascii=False
        ) if datos is not None else None
    ))

    DB.commit()


CAMPOS_TRANSFERENCIA = {
    "estado",
    "bytes_transferidos",
    "bytes_remotos",
    "prioridad",
    "intentos",
    "pid",
    "velocidad_bps",
    "velocidad_promedio_bps",
    "eta_segundos",
    "reanudada",
    "mensaje",
    "error_codigo",
    "error_detalle",
    "iniciada_utc",
    "actualizada_utc",
    "finalizada_utc",
}


def actualizar_transferencia(
    transferencia_id: int,
    **campos
) -> None:
    desconocidos = (
        set(campos) - CAMPOS_TRANSFERENCIA
    )

    if desconocidos:
        raise RuntimeError(
            "Campos de transferencia inválidos: "
            + ", ".join(sorted(desconocidos))
        )

    if "actualizada_utc" not in campos:
        campos["actualizada_utc"] = utc()

    asignaciones = ", ".join(
        f"{campo}=?"
        for campo in campos
    )

    valores = list(campos.values())
    valores.append(transferencia_id)

    DB.execute(
        f"""
        UPDATE transferencias
        SET {asignaciones}
        WHERE id=?
        """,
        valores
    )

    DB.commit()


def recuperar_transferencias_interrumpidas() -> int:
    estados = (
        "COMPROBANDO",
        "PREPARANDO",
        "TRANSFIRIENDO",
        "PAUSANDO",
        "CANCELANDO",
        "VERIFICANDO",
        "REINTENTANDO",
    )

    placeholders = ",".join(
        "?" for _ in estados
    )

    ahora = utc()

    detalle_sesion = (
        "Sesión FTP encontrada EN_CURSO "
        "al iniciar el worker; se conserva "
        "el último progreso observado y se "
        "reconciliará con el tamaño remoto "
        "cuando la PS3 vuelva a estar disponible"
    )

    mensaje_transferencia = (
        "Recuperada después de reiniciar "
        "el worker; se conservará el parcial remoto"
    )

    try:
        sesiones = DB.execute("""
            SELECT
                id,
                transferencia_id,
                pid,

                bytes_remotos_inicio,
                bytes_remotos_fin,
                bytes_ftp,

                duracion_segundos

            FROM transferencia_intentos

            WHERE resultado='EN_CURSO'

            ORDER BY id
        """).fetchall()


        transferencias = DB.execute(
            f"""
            SELECT
                id,
                estado,
                pid,
                bytes_remotos

            FROM transferencias

            WHERE estado IN ({placeholders})

            ORDER BY id
            """,
            estados
        ).fetchall()


        for sesion in sesiones:

            sesion_id = int(
                sesion["id"]
            )

            transferencia_id = int(
                sesion[
                    "transferencia_id"
                ]
            )

            remoto_inicio = max(
                0,
                int(
                    sesion[
                        "bytes_remotos_inicio"
                    ]
                    or 0
                )
            )

            remoto_fin = max(
                remoto_inicio,
                int(
                    sesion[
                        "bytes_remotos_fin"
                    ]
                    or remoto_inicio
                )
            )

            bytes_previos = max(
                0,
                int(
                    sesion[
                        "bytes_ftp"
                    ]
                    or 0
                )
            )

            bytes_sesion = max(
                bytes_previos,
                remoto_fin
                - remoto_inicio
            )

            duracion = max(
                0.0,
                float(
                    sesion[
                        "duracion_segundos"
                    ]
                    or 0
                )
            )

            velocidad = (
                bytes_sesion
                / duracion

                if duracion > 0

                else 0.0
            )


            DB.execute("""
                UPDATE transferencia_intentos

                SET
                    bytes_remotos_fin=?,
                    bytes_ftp=?,
                    velocidad_media_bps=?,

                    resultado='INTERRUMPIDO',

                    error_codigo=?,
                    error_detalle=?,

                    finalizada_utc=
                        COALESCE(
                            finalizada_utc,
                            ?
                        ),

                    actualizada_utc=?

                WHERE
                    id=?
                    AND resultado='EN_CURSO'
            """, (
                remoto_fin,
                bytes_sesion,
                velocidad,

                "WORKER_REINICIADO",
                detalle_sesion,

                ahora,
                ahora,

                sesion_id,
            ))


            DB.execute("""
                INSERT INTO recuperaciones_worker (
                    tipo,
                    transferencia_id,
                    sesion_id,

                    estado_anterior,
                    estado_nuevo,

                    pid_anterior,

                    bytes_observados,
                    bytes_reconciliados,

                    detalle,

                    creada_utc,
                    resuelta_utc
                )
                VALUES (
                    'SESION_HUERFANA',
                    ?,
                    ?,

                    'EN_CURSO',
                    'INTERRUMPIDO',

                    ?,

                    ?,
                    NULL,

                    ?,

                    ?,
                    NULL
                )
            """, (
                transferencia_id,
                sesion_id,

                sesion["pid"],

                remoto_fin,

                (
                    "Sesión FTP recuperada "
                    "después de un reinicio inesperado "
                    "del worker"
                ),

                ahora,
            ))


        for transferencia in transferencias:

            DB.execute("""
                INSERT INTO recuperaciones_worker (
                    tipo,
                    transferencia_id,
                    sesion_id,

                    estado_anterior,
                    estado_nuevo,

                    pid_anterior,

                    bytes_observados,
                    bytes_reconciliados,

                    detalle,

                    creada_utc,
                    resuelta_utc
                )
                VALUES (
                    'TRANSFERENCIA_RECUPERADA',
                    ?,
                    NULL,

                    ?,
                    'EN_COLA',

                    ?,

                    ?,
                    ?,

                    ?,

                    ?,
                    ?
                )
            """, (
                int(
                    transferencia[
                        "id"
                    ]
                ),

                transferencia[
                    "estado"
                ],

                transferencia[
                    "pid"
                ],

                int(
                    transferencia[
                        "bytes_remotos"
                    ]
                    or 0
                ),

                int(
                    transferencia[
                        "bytes_remotos"
                    ]
                    or 0
                ),

                (
                    "Transferencia devuelta "
                    "a EN_COLA al iniciar "
                    "el worker"
                ),

                ahora,
                ahora,
            ))


        parametros = (
            mensaje_transferencia,
            ahora,
            *estados,
        )


        cursor = DB.execute(
            f"""
            UPDATE transferencias

            SET
                estado='EN_COLA',

                pid=NULL,

                velocidad_bps=NULL,

                eta_segundos=NULL,

                mensaje=?,

                error_codigo=NULL,
                error_detalle=NULL,

                finalizada_utc=NULL,

                actualizada_utc=?

            WHERE estado IN ({placeholders})
            """,
            parametros
        )


        DB.commit()


        if sesiones:

            LOG.warning(
                (
                    "Resiliencia: %s sesión(es) FTP "
                    "huérfana(s) cerrada(s) "
                    "como INTERRUMPIDO"
                ),
                len(sesiones),
            )


        return cursor.rowcount


    except Exception:

        DB.rollback()

        raise


def reconciliar_sesion_interrumpida(
    transferencia_id: int,
    remoto_actual: int
) -> None:

    try:
        recuperacion = DB.execute("""
            SELECT
                rw.id,
                rw.sesion_id,
                rw.bytes_observados

            FROM recuperaciones_worker rw

            INNER JOIN transferencia_intentos ti
                ON ti.id=rw.sesion_id

            WHERE
                rw.tipo='SESION_HUERFANA'

                AND rw.transferencia_id=?

                AND rw.resuelta_utc IS NULL

                AND ti.resultado='INTERRUMPIDO'

            ORDER BY rw.id DESC

            LIMIT 1
        """, (
            transferencia_id,
        )).fetchone()


        if recuperacion is None:
            return


        sesion_id = int(
            recuperacion[
                "sesion_id"
            ]
        )


        sesion = DB.execute("""
            SELECT
                bytes_remotos_inicio,
                bytes_remotos_fin,
                bytes_ftp,
                duracion_segundos

            FROM transferencia_intentos

            WHERE id=?
        """, (
            sesion_id,
        )).fetchone()


        if sesion is None:
            return


        remoto_inicio = max(
            0,
            int(
                sesion[
                    "bytes_remotos_inicio"
                ]
                or 0
            )
        )


        remoto_previo = max(
            remoto_inicio,
            int(
                sesion[
                    "bytes_remotos_fin"
                ]
                or remoto_inicio
            )
        )


        remoto_actual = max(
            0,
            int(
                remoto_actual
            )
        )


        remoto_reconciliado = max(
            remoto_previo,
            remoto_actual
        )


        bytes_previos = max(
            0,
            int(
                sesion[
                    "bytes_ftp"
                ]
                or 0
            )
        )


        bytes_reconciliados = max(
            bytes_previos,
            remoto_reconciliado
            - remoto_inicio
        )


        duracion = max(
            0.0,
            float(
                sesion[
                    "duracion_segundos"
                ]
                or 0
            )
        )


        velocidad = (
            bytes_reconciliados
            / duracion

            if duracion > 0

            else 0.0
        )


        ahora = utc()


        DB.execute("""
            UPDATE transferencia_intentos

            SET
                bytes_remotos_fin=?,

                bytes_ftp=?,

                velocidad_media_bps=?,

                actualizada_utc=?

            WHERE id=?
        """, (
            remoto_reconciliado,
            bytes_reconciliados,
            velocidad,
            ahora,
            sesion_id,
        ))


        diferencia = max(
            0,
            remoto_actual
            - remoto_previo
        )


        DB.execute("""
            UPDATE recuperaciones_worker

            SET
                bytes_reconciliados=?,

                detalle_reconciliacion=?,

                resuelta_utc=?

            WHERE id=?
        """, (
            remoto_actual,

            (
                "Reconciliación remota completada; "
                f"crecimiento adicional observado: "
                f"{diferencia} bytes"
            ),

            ahora,

            int(
                recuperacion[
                    "id"
                ]
            ),
        ))


        DB.commit()


        LOG.info(
            (
                "Resiliencia: sesión %s "
                "reconciliada para transferencia #%s; "
                "remoto=%s bytes"
            ),
            sesion_id,
            transferencia_id,
            remoto_actual,
        )


    except Exception as exc:

        try:
            DB.rollback()
        except Exception:
            pass


        LOG.warning(
            (
                "Resiliencia: no se pudo reconciliar "
                "telemetría de transferencia #%s: %s"
            ),
            transferencia_id,
            exc,
        )




def procesos_lftp_externos(
    ignorar_pid: Optional[int] = None
) -> list[int]:
    encontrados = []

    proc = Path("/proc")

    for entrada in proc.iterdir():
        if not entrada.name.isdigit():
            continue

        pid = int(entrada.name)

        if ignorar_pid is not None and pid == ignorar_pid:
            continue

        try:
            cmdline = (
                entrada / "cmdline"
            ).read_bytes()

            if not cmdline:
                continue

            primer_argumento = (
                cmdline.split(b"\0", 1)[0]
                .decode(errors="ignore")
            )

            if Path(primer_argumento).name == "lftp":
                encontrados.append(pid)

        except (
            FileNotFoundError,
            PermissionError,
            ProcessLookupError,
            OSError,
        ):
            continue

    return sorted(encontrados)


def ruta_local_segura(
    ruta_relativa: str
) -> Path:
    relativa = Path(ruta_relativa)

    if relativa.is_absolute():
        raise RuntimeError(
            "La ruta relativa no puede ser absoluta"
        )

    candidata = (
        LOCAL_ROOT / relativa
    ).resolve()

    try:
        candidata.relative_to(LOCAL_ROOT)
    except ValueError as exc:
        raise RuntimeError(
            "La ruta sale de la biblioteca permitida"
        ) from exc

    if candidata.suffix.lower() != ".pkg":
        raise RuntimeError(
            "Solo se permiten archivos .pkg"
        )

    if not candidata.is_file():
        raise RuntimeError(
            f"Archivo local inexistente: {candidata}"
        )

    return candidata


def nombre_remoto_seguro(nombre: str) -> str:
    if (
        "/" in nombre
        or "\\" in nombre
        or "\x00" in nombre
        or "\n" in nombre
        or "\r" in nombre
    ):
        raise RuntimeError(
            "Nombre remoto inválido"
        )

    if not nombre.lower().endswith(".pkg"):
        raise RuntimeError(
            "El archivo remoto debe ser .pkg"
        )

    return nombre


def lftp_quote(valor: str) -> str:
    valor = valor.replace("\\", "\\\\")
    valor = valor.replace('"', '\\"')
    valor = valor.replace("$", "\\$")
    valor = valor.replace("`", "\\`")

    return f'"{valor}"'


class FTPTemporalError(RuntimeError):
    """Fallo temporal al consultar el FTP de la PS3."""
    pass


class InspectorFTP:

    def __init__(self) -> None:
        self.ftp: Optional[ftplib.FTP] = None

    def cerrar(self) -> None:
        if self.ftp is None:
            return

        try:
            self.ftp.quit()
        except Exception:
            try:
                self.ftp.close()
            except Exception:
                pass

        self.ftp = None

    def conectar(self) -> None:
        self.cerrar()

        ftp = ftplib.FTP()

        # webMAN MOD puede devolver nombres de LIST
        # con bytes que no forman UTF-8 válido.
        ftp.encoding = "latin-1"

        ftp.connect(
            HOST,
            PORT,
            timeout=TIMEOUT
        )

        ftp.login(
            USER,
            PASSWORD
        )

        ftp.voidcmd("TYPE I")

        self.ftp = ftp

    def _size_directo(
        self,
        remoto: str
    ) -> Optional[int]:
        assert self.ftp is not None

        try:
            respuesta = self.ftp.sendcmd(
                "SIZE " + remoto
            )

            if respuesta.startswith("213 "):
                return int(
                    respuesta.split(maxsplit=1)[1]
                )

            return None

        except ftplib.error_perm as exc:
            mensaje = str(exc)

            if mensaje.startswith("550"):
                return 0

            if mensaje.startswith(
                ("500", "501", "502", "504")
            ):
                return None

            raise

    def _size_list(
        self,
        remoto: str
    ) -> int:
        assert self.ftp is not None

        lineas: list[str] = []

        try:
            self.ftp.retrlines(
                "LIST " + remoto,
                lineas.append
            )

        except ftplib.error_perm as exc:
            if str(exc).startswith("550"):
                return 0

            raise

        if not lineas:
            return 0

        partes = lineas[0].split(
            maxsplit=8
        )

        if len(partes) < 5:
            raise RuntimeError(
                "No se pudo interpretar LIST remoto"
            )

        try:
            return int(partes[4])

        except ValueError as exc:
            raise RuntimeError(
                "Tamaño remoto inválido en LIST"
            ) from exc

    def size(
        self,
        remoto: str
    ) -> int:
        ultimo_error = None
        max_intentos = 5

        for intento in range(1, max_intentos + 1):
            try:
                if self.ftp is None:
                    self.conectar()

                assert self.ftp is not None

                try:
                    self.ftp.voidcmd("NOOP")
                except Exception:
                    self.conectar()

                directo = self._size_directo(
                    remoto
                )

                if directo is not None:
                    return directo

                return self._size_list(
                    remoto
                )

            except Exception as exc:
                ultimo_error = exc
                self.cerrar()

                if intento < max_intentos:
                    espera = min(
                        2 ** (intento - 1),
                        5
                    )

                    LOG.warning(
                        "Consulta FTP falló (%s/%s): %s. "
                        "Nuevo intento en %ss.",
                        intento,
                        max_intentos,
                        exc,
                        espera
                    )

                    time.sleep(espera)

        raise FTPTemporalError(
            "No se pudo consultar tamaño remoto "
            f"después de {max_intentos} intentos: "
            f"{ultimo_error}"
        )


def cola_pausada() -> bool:
    fila = DB.execute("""
        SELECT valor
        FROM meta
        WHERE clave='cola_pausada'
        LIMIT 1
    """).fetchone()

    if fila is None:
        return False

    return str(
        fila["valor"]
    ).strip() == "1"


FRESCURA_PS3_SEGUNDOS = 60

# ALM-5 — gate de capacidad antes de lftp.
FRESCURA_HDD_SEGUNDOS = 60
MARGEN_HDD_SEGURIDAD_BYTES = 512 * 1024 * 1024
REVALIDACION_HDD_BLOQUEO_SEGUNDOS = 60
CODIGOS_ESPERA_HDD = {
    "ESPACIO_INSUFICIENTE",
    "ALMACENAMIENTO_NO_VERIFICABLE",
}


def hay_transferencias_en_cola() -> bool:
    return DB.execute("""
        SELECT 1
        FROM transferencias
        WHERE estado='EN_COLA'
        LIMIT 1
    """).fetchone() is not None


def ps3_lista_para_transferir():
    fila = DB.execute("""
        SELECT
            estado_operativo,
            ftp_disponible,
            fallos_consecutivos,
            detalle_estado,
            ultima_consulta_utc,

            (
                julianday('now')
                - julianday(
                    ultima_consulta_utc
                )
            ) * 86400.0
                AS antiguedad_segundos

        FROM ps3_estado
        WHERE id=1
        LIMIT 1
    """).fetchone()

    if fila is None:
        return (
            False,
            "NO_DISPONIBLE",
            (
                "Esperando PS3: "
                "estado operativo no disponible"
            ),
        )

    estado = (
        fila["estado_operativo"]
        or "NO_DISPONIBLE"
    )

    ftp_ok = bool(
        fila["ftp_disponible"]
    )

    fallos = int(
        fila["fallos_consecutivos"]
        or 0
    )

    detalle = (
        fila["detalle_estado"]
        or ""
    ).strip()

    antiguedad = (
        float(
            fila["antiguedad_segundos"]
        )
        if fila[
            "antiguedad_segundos"
        ] is not None
        else None
    )

    fresca = (
        antiguedad is not None
        and antiguedad >= -5
        and antiguedad
            <= FRESCURA_PS3_SEGUNDOS
    )

    if not fresca:
        return (
            False,
            estado,
            (
                "Esperando PS3: "
                "estado del inspector desactualizado"
            ),
        )

    if (
        estado == "LISTA"
        and ftp_ok
    ):
        return (
            True,
            estado,
            "PS3 lista para transferencias",
        )

    if estado == "TRANSITORIO":
        return (
            False,
            estado,
            (
                "Esperando PS3: "
                "verificando estabilidad "
                f"({fallos}/3)"
            ),
        )

    if (
        estado
        == "ENCENDIDA_SIN_WEBMAN"
    ):
        return (
            False,
            estado,
            (
                "Esperando PS3: "
                "consola encendida; "
                "activá HEN/webMAN"
            ),
        )

    if estado == "NO_DISPONIBLE":
        return (
            False,
            estado,
            (
                "Esperando PS3: "
                "consola no disponible"
            ),
        )

    if (
        estado == "LISTA"
        and not ftp_ok
    ):
        return (
            False,
            estado,
            (
                "Esperando PS3: "
                "FTP no disponible"
            ),
        )

    return (
        False,
        estado,
        (
            "Esperando PS3: "
            + (
                detalle
                if detalle
                else estado
            )
        ),
    )


def marcar_siguiente_espera_ps3(
    mensaje: str
) -> None:
    fila = DB.execute("""
        SELECT
            id,
            mensaje
        FROM transferencias
        WHERE estado='EN_COLA'
        ORDER BY
            prioridad ASC,
            posicion_cola ASC,
            creada_utc ASC,
            id ASC
        LIMIT 1
    """).fetchone()

    if fila is None:
        return

    if (
        (fila["mensaje"] or "")
        == mensaje
    ):
        return

    DB.execute("""
        UPDATE transferencias
        SET
            mensaje=?,
            actualizada_utc=?
        WHERE
            id=?
            AND estado='EN_COLA'
    """, (
        mensaje,
        utc(),
        int(fila["id"]),
    ))

    DB.commit()


def estado_espera_worker():
    orden_pkg = siguiente_orden_pkg()

    if orden_pkg is not None:
        (
            lista_pkg,
            _estado_pkg,
            motivo_pkg,
        ) = ps3_lista_para_pkg(
            str(
                orden_pkg["accion"]
            )
        )

        if not lista_pkg:
            return (
                "ESPERANDO",
                motivo_pkg,
            )

        return (
            "ESPERANDO",
            "Operación PKG pendiente",
        )

    if cola_pausada():
        return (
            "ESPERANDO",
            "Cola pausada por el usuario",
        )

    if not hay_transferencias_en_cola():
        return (
            "ESPERANDO",
            "Sin transferencias en cola",
        )

    (
        lista,
        _estado,
        motivo,
    ) = ps3_lista_para_transferir()

    if not lista:
        marcar_siguiente_espera_ps3(
            motivo
        )

        return (
            "ESPERANDO",
            motivo,
        )

    return (
        "ESPERANDO",
        "Esperando próximo ciclo de despacho",
    )


def leer_estado_hdd_transferencia():
    return DB.execute("""
        SELECT
            hdd_libre_bytes_aprox,
            hdd_libre_texto,
            hdd_fuente,
            hdd_ultima_lectura_ok_utc,
            hdd_ultimo_error,

            (
                julianday('now')
                - julianday(
                    hdd_ultima_lectura_ok_utc
                )
            ) * 86400.0
                AS hdd_antiguedad_segundos

        FROM ps3_estado
        WHERE id=1
        LIMIT 1
    """).fetchone()


def evaluar_capacidad_hdd_transferencia(
    tamano_total,
    bytes_remotos,
    estado_hdd,
):
    total = max(
        0,
        int(
            tamano_total
            or 0
        ),
    )

    remoto = max(
        0,
        min(
            int(
                bytes_remotos
                or 0
            ),
            total,
        ),
    )

    requeridos = max(
        0,
        total - remoto,
    )

    datos = {
        "tamano_total": total,
        "bytes_remotos": remoto,
        "bytes_requeridos": requeridos,
        "margen_seguridad_bytes":
            MARGEN_HDD_SEGURIDAD_BYTES,
        "hdd_libre_bytes_aprox": None,
        "capacidad_util_bytes": None,
        "faltante_bytes": None,
        "hdd_antiguedad_segundos": None,
        "hdd_fuente": None,
        "motivo": None,
    }

    if estado_hdd is None:
        datos["motivo"] = (
            "SIN_ESTADO_HDD"
        )

        return (
            False,
            "ALMACENAMIENTO_NO_VERIFICABLE",
            (
                "Esperando PS3: "
                "almacenamiento no verificable"
            ),
            datos,
        )

    libre_raw = estado_hdd[
        "hdd_libre_bytes_aprox"
    ]

    antiguedad_raw = estado_hdd[
        "hdd_antiguedad_segundos"
    ]

    ultimo_error = str(
        estado_hdd[
            "hdd_ultimo_error"
        ]
        or ""
    ).strip()

    libre = (
        max(0, int(libre_raw))
        if libre_raw is not None
        else None
    )

    antiguedad = (
        float(antiguedad_raw)
        if antiguedad_raw is not None
        else None
    )

    datos[
        "hdd_libre_bytes_aprox"
    ] = libre

    datos[
        "hdd_antiguedad_segundos"
    ] = antiguedad

    datos[
        "hdd_fuente"
    ] = estado_hdd[
        "hdd_fuente"
    ]

    if libre is None:
        datos["motivo"] = (
            "SIN_LECTURA_HDD"
        )

        return (
            False,
            "ALMACENAMIENTO_NO_VERIFICABLE",
            (
                "Esperando PS3: "
                "sin lectura de almacenamiento"
            ),
            datos,
        )

    fresca = (
        antiguedad is not None
        and antiguedad >= -5.0
        and antiguedad
            <= FRESCURA_HDD_SEGUNDOS
    )

    if not fresca:
        datos["motivo"] = (
            "LECTURA_HDD_DESACTUALIZADA"
        )

        return (
            False,
            "ALMACENAMIENTO_NO_VERIFICABLE",
            (
                "Esperando PS3: "
                "lectura de almacenamiento "
                "desactualizada"
            ),
            datos,
        )

    if ultimo_error:
        datos["motivo"] = (
            "ULTIMO_INTENTO_HDD_ERROR"
        )

        return (
            False,
            "ALMACENAMIENTO_NO_VERIFICABLE",
            (
                "Esperando PS3: "
                "almacenamiento no verificable"
            ),
            datos,
        )

    capacidad_util = max(
        0,
        libre
        - MARGEN_HDD_SEGURIDAD_BYTES,
    )

    faltante = max(
        0,
        requeridos
        - capacidad_util,
    )

    datos[
        "capacidad_util_bytes"
    ] = capacidad_util

    datos[
        "faltante_bytes"
    ] = faltante

    if faltante > 0:
        datos["motivo"] = (
            "ESPACIO_INSUFICIENTE"
        )

        requeridos_gb = (
            requeridos
            / (1024 ** 3)
        )

        libre_gb = (
            libre
            / (1024 ** 3)
        )

        faltante_gb = (
            faltante
            / (1024 ** 3)
        )

        return (
            False,
            "ESPACIO_INSUFICIENTE",
            (
                "Esperando espacio en PS3: "
                f"requiere {requeridos_gb:.1f} GB; "
                f"libres {libre_gb:.1f} GB; "
                f"faltan aprox. {faltante_gb:.1f} GB"
            ),
            datos,
        )

    datos["motivo"] = "OK"

    return (
        True,
        None,
        "Capacidad HDD verificada",
        datos,
    )


def siguiente_transferencia():
    if cola_pausada():
        return None

    if not hay_transferencias_en_cola():
        return None

    (
        ps3_lista,
        _estado_ps3,
        motivo_ps3,
    ) = ps3_lista_para_transferir()

    if not ps3_lista:
        marcar_siguiente_espera_ps3(
            motivo_ps3
        )

        return None

    transferencia = DB.execute("""
        SELECT
            transferencias.*,

            (
                julianday('now')
                - julianday(
                    transferencias.actualizada_utc
                )
            ) * 86400.0
                AS espera_hdd_segundos

        FROM transferencias

        WHERE estado='EN_COLA'

        ORDER BY
            prioridad ASC,
            posicion_cola ASC,
            creada_utc ASC,
            id ASC

        LIMIT 1
    """).fetchone()

    if transferencia is None:
        return None

    if (
        transferencia["error_codigo"]
        in CODIGOS_ESPERA_HDD
    ):
        (
            capacidad_ok,
            codigo_hdd,
            mensaje_hdd,
            datos_hdd,
        ) = evaluar_capacidad_hdd_transferencia(
            transferencia["tamano_total"],
            transferencia["bytes_remotos"],
            leer_estado_hdd_transferencia(),
        )

        if not capacidad_ok:
            espera_hdd = (
                float(
                    transferencia[
                        "espera_hdd_segundos"
                    ]
                )
                if transferencia[
                    "espera_hdd_segundos"
                ] is not None
                else 0.0
            )

            # Si la telemetria es valida pero
            # sigue faltando espacio, una vez por
            # minuto permitimos volver a entrar en
            # COMPROBANDO para refrescar SIZE.
            #
            # Esto evita un bloqueo permanente si
            # el parcial remoto cambio fuera del
            # worker, sin crear un bucle agresivo.
            if (
                codigo_hdd
                == "ESPACIO_INSUFICIENTE"
                and espera_hdd
                    >= REVALIDACION_HDD_BLOQUEO_SEGUNDOS
            ):
                return transferencia

            detalle_hdd = json.dumps(
                datos_hdd,
                ensure_ascii=False,
                separators=(",", ":"),
            )

            if (
                transferencia["error_codigo"]
                    != codigo_hdd
                or (
                    transferencia["mensaje"]
                    or ""
                ) != mensaje_hdd
            ):
                actualizar_transferencia(
                    int(
                        transferencia["id"]
                    ),
                    estado="EN_COLA",
                    pid=None,
                    velocidad_bps=0,
                    eta_segundos=None,
                    mensaje=mensaje_hdd,
                    error_codigo=codigo_hdd,
                    error_detalle=detalle_hdd,
                    finalizada_utc=None,
                )

            return None

    return transferencia




def ordenes_pendientes(
    transferencia_id: int
):
    return DB.execute("""
        SELECT *
        FROM ordenes
        WHERE
            transferencia_id=?
            AND estado='PENDIENTE'
        ORDER BY creada_utc ASC, id ASC
    """, (
        transferencia_id,
    )).fetchall()


def marcar_orden(
    orden_id: int,
    estado: str,
    mensaje: str
) -> None:
    DB.execute("""
        UPDATE ordenes
        SET
            estado=?,
            procesada_utc=?,
            mensaje=?
        WHERE id=?
    """, (
        estado,
        utc(),
        mensaje,
        orden_id
    ))

    DB.commit()


def procesar_ordenes_inactivas() -> None:
    filas = DB.execute("""
        SELECT
            o.*,
            t.estado AS estado_transferencia
        FROM ordenes o
        JOIN transferencias t
            ON t.id=o.transferencia_id
        WHERE o.estado='PENDIENTE'
        ORDER BY o.creada_utc ASC
        LIMIT 50
    """).fetchall()

    for fila in filas:
        accion = fila["accion"]
        estado = fila["estado_transferencia"]
        tid = int(fila["transferencia_id"])
        oid = int(fila["id"])

        estados_activos = {
            "COMPROBANDO",
            "PREPARANDO",
            "TRANSFIRIENDO",
            "PAUSANDO",
            "CANCELANDO",
            "VERIFICANDO",
            "REINTENTANDO",
        }

        if estado in estados_activos:
            continue

        if accion == "PAUSAR":
            if estado == "EN_COLA":
                actualizar_transferencia(
                    tid,
                    estado="PAUSADO",
                    mensaje="Transferencia pausada antes de iniciar",
                    pid=None
                )

                marcar_orden(
                    oid,
                    "EJECUTADA",
                    "Transferencia pausada"
                )
            else:
                marcar_orden(
                    oid,
                    "RECHAZADA",
                    f"No se puede pausar desde {estado}"
                )

        elif accion == "REANUDAR":
            if estado == "PAUSADO":
                actualizar_transferencia(
                    tid,
                    estado="EN_COLA",
                    mensaje="Transferencia reanudada",
                    pid=None,
                    finalizada_utc=None
                )

                marcar_orden(
                    oid,
                    "EJECUTADA",
                    "Transferencia devuelta a la cola"
                )
            else:
                marcar_orden(
                    oid,
                    "RECHAZADA",
                    f"No se puede reanudar desde {estado}"
                )

        elif accion == "CANCELAR":
            if estado in {
                "EN_COLA",
                "PAUSADO",
                "ERROR",
            }:
                actualizar_transferencia(
                    tid,
                    estado="CANCELADO",
                    mensaje="Transferencia cancelada",
                    pid=None,
                    velocidad_bps=None,
                    eta_segundos=None,
                    finalizada_utc=utc()
                )

                marcar_orden(
                    oid,
                    "EJECUTADA",
                    "Transferencia cancelada"
                )
            else:
                marcar_orden(
                    oid,
                    "RECHAZADA",
                    f"No se puede cancelar desde {estado}"
                )

        elif accion == "REINTENTAR":
            if estado == "ERROR":
                actualizar_transferencia(
                    tid,
                    estado="EN_COLA",
                    mensaje="Reintento solicitado",
                    pid=None,
                    error_codigo=None,
                    error_detalle=None,
                    finalizada_utc=None
                )

                marcar_orden(
                    oid,
                    "EJECUTADA",
                    "Transferencia devuelta a la cola"
                )
            else:
                marcar_orden(
                    oid,
                    "RECHAZADA",
                    f"No se puede reintentar desde {estado}"
                )


def terminar_proceso(
    proceso: subprocess.Popen,
    timeout: float = 10
) -> None:
    if proceso.poll() is not None:
        return

    try:
        os.killpg(
            proceso.pid,
            signal.SIGTERM
        )
    except ProcessLookupError:
        return

    try:
        proceso.wait(timeout=timeout)
        return
    except subprocess.TimeoutExpired:
        pass

    try:
        os.killpg(
            proceso.pid,
            signal.SIGKILL
        )
    except ProcessLookupError:
        return

    try:
        proceso.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def tail_archivo(
    ruta: Path,
    limite: int = 5000
) -> str:
    try:
        with ruta.open("rb") as archivo:
            archivo.seek(
                0,
                os.SEEK_END
            )

            tamano = archivo.tell()

            archivo.seek(
                max(0, tamano - limite)
            )

            return archivo.read().decode(
                errors="replace"
            ).strip()

    except OSError:
        return ""


def crear_sesion_telemetria(
    transferencia_id: int,
    intento_worker: int,
    pid: int,
    bytes_remotos_inicio: int,
    log_archivo: str
):
    try:
        fila = DB.execute("""
            SELECT
                COALESCE(
                    MAX(numero_sesion),
                    0
                ) + 1
            FROM transferencia_intentos
            WHERE transferencia_id=?
        """, (
            transferencia_id,
        )).fetchone()

        numero_sesion = int(
            fila[0]
            if fila is not None
            else 1
        )

        cursor = DB.execute("""
            INSERT INTO transferencia_intentos (
                transferencia_id,
                numero_sesion,
                intento_worker,
                pid,
                reanudacion,
                bytes_remotos_inicio,
                bytes_remotos_fin,
                bytes_ftp,
                duracion_segundos,
                velocidad_media_bps,
                resultado,
                codigo_lftp,
                error_codigo,
                error_detalle,
                log_archivo,
                iniciada_utc,
                actualizada_utc
            )
            VALUES (
                ?, ?, ?, ?, ?,
                ?, ?,
                0,
                0,
                0,
                'EN_CURSO',
                NULL,
                NULL,
                NULL,
                ?,
                ?,
                ?
            )
        """, (
            transferencia_id,
            numero_sesion,
            intento_worker,
            pid,
            (
                1
                if bytes_remotos_inicio > 0
                else 0
            ),
            bytes_remotos_inicio,
            bytes_remotos_inicio,
            log_archivo,
            utc(),
            utc(),
        ))

        DB.commit()

        return int(
            cursor.lastrowid
        )

    except Exception as exc:
        try:
            DB.rollback()
        except Exception:
            pass

        LOG.warning(
            "Telemetría FTP: no se pudo crear sesión #%s: %s",
            transferencia_id,
            exc,
        )

        return None


def actualizar_sesion_telemetria(
    sesion_id,
    bytes_remotos_inicio: int,
    bytes_remotos_actual: int,
    duracion_segundos: float
) -> None:
    if sesion_id is None:
        return

    try:
        enviados = max(
            0,
            int(bytes_remotos_actual)
            - int(bytes_remotos_inicio)
        )

        duracion = max(
            0.0,
            float(duracion_segundos)
        )

        velocidad_media = (
            enviados / duracion
            if duracion > 0
            else 0.0
        )

        DB.execute("""
            UPDATE transferencia_intentos
            SET
                bytes_remotos_fin=?,
                bytes_ftp=?,
                duracion_segundos=?,
                velocidad_media_bps=?,
                actualizada_utc=?
            WHERE
                id=?
                AND resultado='EN_CURSO'
        """, (
            int(bytes_remotos_actual),
            enviados,
            duracion,
            velocidad_media,
            utc(),
            int(sesion_id),
        ))

        DB.commit()

    except Exception as exc:
        try:
            DB.rollback()
        except Exception:
            pass

        LOG.warning(
            "Telemetría FTP: no se pudo actualizar sesión %s: %s",
            sesion_id,
            exc,
        )


def finalizar_sesion_telemetria(
    sesion_id,
    transferencia_id: int,
    codigo_lftp=None
) -> None:
    if sesion_id is None:
        return

    try:
        sesion = DB.execute("""
            SELECT
                id,
                bytes_remotos_inicio,
                iniciada_utc,
                resultado
            FROM transferencia_intentos
            WHERE id=?
        """, (
            int(sesion_id),
        )).fetchone()

        if sesion is None:
            return

        if sesion["resultado"] != "EN_CURSO":
            return


        transferencia = DB.execute("""
            SELECT
                estado,
                bytes_remotos,
                error_codigo,
                error_detalle
            FROM transferencias
            WHERE id=?
        """, (
            transferencia_id,
        )).fetchone()


        if transferencia is None:
            estado = "ERROR"
            remoto_final = int(
                sesion["bytes_remotos_inicio"]
                or 0
            )
            error_codigo = (
                "TRANSFERENCIA_NO_ENCONTRADA"
            )
            error_detalle = (
                "No se encontró transferencia "
                "al cerrar telemetría"
            )

        else:
            estado = (
                transferencia["estado"]
                or "ERROR"
            )

            remoto_final = max(
                0,
                int(
                    transferencia[
                        "bytes_remotos"
                    ]
                    or 0
                )
            )

            error_codigo = (
                transferencia[
                    "error_codigo"
                ]
            )

            error_detalle = (
                transferencia[
                    "error_detalle"
                ]
            )


        mapa = {
            "COMPLETADO":
                "COMPLETADO",

            "PAUSADO":
                "PAUSADO",

            "CANCELADO":
                "CANCELADO",

            "CONFLICTO":
                "CONFLICTO",

            "REINTENTANDO":
                "INCOMPLETO",

            "EN_COLA":
                "INTERRUMPIDO",

            "ERROR":
                "ERROR",
        }

        resultado = mapa.get(
            estado,
            "INTERRUMPIDO"
        )


        remoto_inicial = int(
            sesion[
                "bytes_remotos_inicio"
            ]
            or 0
        )

        enviados = max(
            0,
            remoto_final
            - remoto_inicial
        )


        fin = utc()

        fila = DB.execute("""
            SELECT
                MAX(
                    0.0,
                    (
                        julianday(?)
                        - julianday(iniciada_utc)
                    ) * 86400.0
                )
            FROM transferencia_intentos
            WHERE id=?
        """, (
            fin,
            int(sesion_id),
        )).fetchone()

        duracion = float(
            fila[0]
            if (
                fila is not None
                and fila[0] is not None
            )
            else 0.0
        )

        velocidad_media = (
            enviados / duracion
            if duracion > 0
            else 0.0
        )


        DB.execute("""
            UPDATE transferencia_intentos
            SET
                bytes_remotos_fin=?,
                bytes_ftp=?,
                duracion_segundos=?,
                velocidad_media_bps=?,
                resultado=?,
                codigo_lftp=?,
                error_codigo=?,
                error_detalle=?,
                finalizada_utc=?,
                actualizada_utc=?
            WHERE
                id=?
                AND resultado='EN_CURSO'
        """, (
            remoto_final,
            enviados,
            duracion,
            velocidad_media,
            resultado,
            (
                int(codigo_lftp)
                if codigo_lftp is not None
                else None
            ),
            error_codigo,
            error_detalle,
            fin,
            fin,
            int(sesion_id),
        ))

        DB.commit()

        LOG.info(
            (
                "Telemetría FTP: sesión %s "
                "cerrada, resultado=%s, bytes=%s"
            ),
            sesion_id,
            resultado,
            enviados,
        )

    except Exception as exc:
        try:
            DB.rollback()
        except Exception:
            pass

        LOG.warning(
            "Telemetría FTP: no se pudo cerrar sesión %s: %s",
            sesion_id,
            exc,
        )



# ==========================================================
# Transferencias multiformato
# ==========================================================

LOCAL_ROOT_PS3ISO = Path(
    "/srv/ps3/PS3ISO"
).resolve()

DESTINO_REMOTO_PKG = (
    "/dev_hdd0/packages"
)

DESTINO_REMOTO_PS3ISO = (
    "/dev_hdd0/PS3ISO"
)


LOCAL_ROOT_PS2ISO = Path(
    "/srv/ps3/PS2ISO"
).resolve()

DESTINO_REMOTO_PS2ISO = (
    "/dev_hdd0/PS2ISO"
)


def _campo_transferencia(
    transferencia,
    clave: str,
    predeterminado=None,
):
    try:
        return transferencia[
            clave
        ]

    except (
        KeyError,
        IndexError,
    ):
        return predeterminado


def resolver_transferencia_multiformato(
    transferencia,
):
    formato = str(
        _campo_transferencia(
            transferencia,
            "formato_snapshot",
            "PKG",
        )
        or "PKG"
    ).strip().upper()

    destino = str(
        _campo_transferencia(
            transferencia,
            "destino_remoto_snapshot",
            DESTINO_REMOTO_PKG,
        )
        or ""
    ).strip()

    ruta_relativa = str(
        transferencia[
            "ruta_relativa_snapshot"
        ]
    )

    nombre_remoto = str(
        transferencia[
            "nombre_remoto"
        ]
    )


    if formato == "PKG":

        if (
            REMOTE_DIR
            != DESTINO_REMOTO_PKG
        ):
            raise RuntimeError(
                "Configuración PKG remota "
                "fuera de la allowlist"
            )

        if (
            destino
            != DESTINO_REMOTO_PKG
        ):
            raise RuntimeError(
                "Destino PKG no permitido"
            )

        local = ruta_local_segura(
            ruta_relativa
        )

        nombre = nombre_remoto_seguro(
            nombre_remoto
        )

        remoto = (
            DESTINO_REMOTO_PKG
            + "/"
            + nombre
        )

        return {
            "formato":
                "PKG",

            "local":
                local,

            "nombre":
                nombre,

            "destino":
                DESTINO_REMOTO_PKG,

            "remoto":
                remoto,
        }


    if formato == "PS3ISO":

        if (
            destino
            != DESTINO_REMOTO_PS3ISO
        ):
            raise RuntimeError(
                "Destino PS3ISO no permitido"
            )

        if (
            not ruta_relativa
            or ruta_relativa in (
                ".",
                "..",
            )
            or "/" in ruta_relativa
            or "\\" in ruta_relativa
            or "\x00" in ruta_relativa
            or "\n" in ruta_relativa
            or "\r" in ruta_relativa
        ):
            raise RuntimeError(
                "Ruta relativa PS3ISO inválida"
            )

        relativa = Path(
            ruta_relativa
        )

        if (
            relativa.is_absolute()
            or len(
                relativa.parts
            ) != 1
        ):
            raise RuntimeError(
                "PS3ISO sólo admite "
                "archivos de primer nivel"
            )

        local = (
            LOCAL_ROOT_PS3ISO
            / relativa
        ).resolve()

        try:
            local.relative_to(
                LOCAL_ROOT_PS3ISO
            )

        except ValueError as exc:
            raise RuntimeError(
                "La ruta PS3ISO sale de "
                "la biblioteca permitida"
            ) from exc

        if (
            local.suffix.lower()
            != ".iso"
        ):
            raise RuntimeError(
                "PS3ISO requiere extensión .iso"
            )

        if not local.is_file():
            raise RuntimeError(
                "Archivo ISO local inexistente: "
                + str(local)
            )

        nombre = nombre_remoto

        if (
            not nombre
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
            raise RuntimeError(
                "Nombre remoto PS3ISO inválido"
            )

        if not nombre.lower().endswith(
            ".iso"
        ):
            raise RuntimeError(
                "El archivo remoto PS3ISO "
                "debe terminar en .iso"
            )

        if nombre != relativa.name:
            raise RuntimeError(
                "El nombre remoto PS3ISO "
                "debe coincidir con el local"
            )

        remoto = (
            DESTINO_REMOTO_PS3ISO
            + "/"
            + nombre
        )

        return {
            "formato":
                "PS3ISO",

            "local":
                local,

            "nombre":
                nombre,

            "destino":
                DESTINO_REMOTO_PS3ISO,

            "remoto":
                remoto,
        }


    if formato == "PS2ISO":

        if (
            destino
            != DESTINO_REMOTO_PS2ISO
        ):
            raise RuntimeError(
                "Destino PS2ISO no permitido"
            )

        if (
            not ruta_relativa
            or ruta_relativa in (
                ".",
                "..",
            )
            or "/" in ruta_relativa
            or "\\" in ruta_relativa
            or "\x00" in ruta_relativa
            or "\n" in ruta_relativa
            or "\r" in ruta_relativa
        ):
            raise RuntimeError(
                "Ruta relativa PS2ISO inválida"
            )

        relativa = Path(
            ruta_relativa
        )

        if (
            relativa.is_absolute()
            or len(
                relativa.parts
            ) != 1
        ):
            raise RuntimeError(
                "PS2ISO sólo admite "
                "archivos de primer nivel"
            )

        local = (
            LOCAL_ROOT_PS2ISO
            / relativa
        ).resolve()

        try:
            local.relative_to(
                LOCAL_ROOT_PS2ISO
            )

        except ValueError as exc:
            raise RuntimeError(
                "La ruta PS2ISO sale de "
                "la biblioteca permitida"
            ) from exc

        if not local.name.endswith(
            ".BIN.ENC"
        ):
            raise RuntimeError(
                "PS2ISO requiere extensión "
                ".BIN.ENC"
            )

        if not local.is_file():
            raise RuntimeError(
                "Archivo ISO local inexistente: "
                + str(local)
            )

        nombre = nombre_remoto

        if (
            not nombre
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
            raise RuntimeError(
                "Nombre remoto PS2ISO inválido"
            )

        if not nombre.endswith(
            ".BIN.ENC"
        ):
            raise RuntimeError(
                "El archivo remoto PS2ISO "
                "debe terminar en .BIN.ENC"
            )

        if nombre != relativa.name:
            raise RuntimeError(
                "El nombre remoto PS2ISO "
                "debe coincidir con el local"
            )

        remoto = (
            DESTINO_REMOTO_PS2ISO
            + "/"
            + nombre
        )

        return {
            "formato":
                "PS2ISO",

            "local":
                local,

            "nombre":
                nombre,

            "destino":
                DESTINO_REMOTO_PS2ISO,

            "remoto":
                remoto,
        }


    raise RuntimeError(
        "Formato de transferencia "
        "no permitido: "
        + formato
    )



def ejecutar_transferencia(
    transferencia
) -> None:
    tid = int(
        transferencia["id"]
    )

    inspector = InspectorFTP()
    proceso = None
    log_handle = None

    sesion_telemetria_id = None
    remoto_inicial_telemetria = 0

    try:
        actualizar_worker(
            "OCUPADO",
            f"Procesando transferencia #{tid}",
            tid
        )

        actualizar_transferencia(
            tid,
            estado="COMPROBANDO",
            pid=None,
            mensaje="Validando archivo local y PS3",
            error_codigo=None,
            error_detalle=None
        )

        resolucion = (
            resolver_transferencia_multiformato(
                transferencia
            )
        )

        local = resolucion[
            "local"
        ]

        nombre = resolucion[
            "nombre"
        ]

        remoto = resolucion[
            "remoto"
        ]

        stat = local.stat()

        total = int(
            transferencia["tamano_total"]
        )

        if stat.st_size != total:
            raise RuntimeError(
                "El tamaño del archivo local cambió "
                "desde que fue agregado a la cola"
            )

        try:
            remoto_inicial = inspector.size(
                remoto
            )

            reconciliar_sesion_interrumpida(
                tid,
                remoto_inicial
            )

        except FTPTemporalError as exc:
            intento_previo = (
                int(transferencia["intentos"]) + 1
            )

            detalle = str(exc)

            if intento_previo < MAX_TRANSFER_RETRIES:
                actualizar_transferencia(
                    tid,
                    estado="REINTENTANDO",
                    intentos=intento_previo,
                    pid=None,
                    velocidad_bps=0,
                    eta_segundos=None,
                    mensaje=(
                        "PS3 temporalmente inaccesible; "
                        "se reintentará automáticamente"
                    ),
                    error_codigo="FTP_TEMPORAL",
                    error_detalle=detalle,
                    finalizada_utc=None
                )

                evento(
                    "FTP_TEMPORAL",
                    (
                        "La PS3 no respondió durante "
                        "la comprobación previa"
                    ),
                    tid,
                    "AVISO",
                    {
                        "intento": intento_previo,
                        "detalle": detalle,
                    }
                )

                espera = min(
                    RECONNECT_BASE * intento_previo,
                    RECONNECT_MAX
                )

                inicio_espera = time.monotonic()

                while (
                    not DETENER
                    and (
                        time.monotonic()
                        - inicio_espera
                    ) < espera
                ):
                    actualizar_worker(
                        "OCUPADO",
                        (
                            "Esperando para reintentar "
                            f"#{tid}"
                        ),
                        tid
                    )

                    time.sleep(1)

                if not DETENER:
                    actualizar_transferencia(
                        tid,
                        estado="EN_COLA",
                        pid=None,
                        mensaje=(
                            "Nuevo intento automático "
                            "programado"
                        ),
                        error_codigo=None,
                        error_detalle=None,
                        finalizada_utc=None
                    )

                return

            actualizar_transferencia(
                tid,
                estado="ERROR",
                intentos=intento_previo,
                pid=None,
                velocidad_bps=0,
                eta_segundos=None,
                mensaje=(
                    "La PS3 no respondió después "
                    "de varios intentos"
                ),
                error_codigo="FTP_INACCESIBLE",
                error_detalle=detalle,
                finalizada_utc=utc()
            )

            evento(
                "FTP_INACCESIBLE",
                (
                    "Se agotaron los intentos de "
                    "conexión con la PS3"
                ),
                tid,
                "ERROR",
                {
                    "intentos": intento_previo,
                    "detalle": detalle,
                }
            )

            return

        actualizar_transferencia(
            tid,
            bytes_remotos=remoto_inicial,
            bytes_transferidos=min(
                remoto_inicial,
                total
            ),
            reanudada=(
                1
                if 0 < remoto_inicial < total
                else 0
            )
        )

        if remoto_inicial > total:
            actualizar_transferencia(
                tid,
                estado="CONFLICTO",
                mensaje=(
                    "El archivo remoto es mayor "
                    "que el archivo local"
                ),
                error_codigo="REMOTO_MAYOR",
                error_detalle=(
                    f"Remoto={remoto_inicial}; "
                    f"local={total}"
                ),
                pid=None,
                velocidad_bps=None,
                eta_segundos=None,
                finalizada_utc=utc()
            )

            evento(
                "CONFLICTO_REMOTO",
                "Archivo remoto mayor que el local",
                tid,
                "AVISO",
                {
                    "remoto": remoto_inicial,
                    "local": total,
                }
            )

            return

        if remoto_inicial == total:
            actualizar_transferencia(
                tid,
                estado="YA_EXISTE",
                bytes_transferidos=total,
                bytes_remotos=total,
                mensaje=(
                    "El archivo ya existe completo "
                    "en la PS3"
                ),
                pid=None,
                velocidad_bps=0,
                velocidad_promedio_bps=0,
                eta_segundos=0,
                finalizada_utc=utc()
            )

            evento(
                "ARCHIVO_YA_EXISTE",
                "No fue necesario transferir",
                tid
            )

            return

        (
            capacidad_hdd_ok,
            codigo_hdd,
            mensaje_hdd,
            datos_hdd,
        ) = evaluar_capacidad_hdd_transferencia(
            total,
            remoto_inicial,
            leer_estado_hdd_transferencia(),
        )

        if not capacidad_hdd_ok:
            actualizar_transferencia(
                tid,
                estado="EN_COLA",
                pid=None,
                velocidad_bps=0,
                eta_segundos=None,
                mensaje=mensaje_hdd,
                error_codigo=codigo_hdd,
                error_detalle=json.dumps(
                    datos_hdd,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                finalizada_utc=None,
            )

            evento(
                (
                    "TRANSFERENCIA_ESPERA_ESPACIO"
                    if codigo_hdd
                        == "ESPACIO_INSUFICIENTE"
                    else
                    "ALMACENAMIENTO_NO_VERIFICABLE"
                ),
                mensaje_hdd,
                tid,
                "AVISO",
                datos_hdd,
            )

            return

        intento = int(
            transferencia["intentos"]
        ) + 1

        actualizar_transferencia(
            tid,
            estado="PREPARANDO",
            intentos=intento,
            mensaje=(
                "Preparando transferencia"
                if remoto_inicial == 0
                else
                f"Preparando reanudación desde "
                f"{remoto_inicial} bytes"
            )
        )

        script = "; ".join([
            "set ftp:ssl-allow no",
            "set ftp:passive-mode true",
            f"set net:timeout {TIMEOUT}",
            f"set net:max-retries {NET_RETRIES}",
            (
                "set net:reconnect-interval-base "
                f"{RECONNECT_BASE}"
            ),
            (
                "set net:reconnect-interval-max "
                f"{RECONNECT_MAX}"
            ),
            (
                "put -c "
                f"{lftp_quote(str(local))} "
                "-o "
                f"{lftp_quote(remoto)}"
            ),
            "bye",
        ])

        comando = [
            str(LFTP),
            "-u",
            f"{USER},{PASSWORD}",
            "-e",
            script,
            f"ftp://{HOST}:{PORT}",
        ]

        log_lftp = (
            LOG_DIR
            / f"transferencia-{tid}.lftp.log"
        )

        log_handle = log_lftp.open(
            "ab",
            buffering=0
        )

        proceso = subprocess.Popen(
            comando,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True
        )

        remoto_inicial_telemetria = (
            remoto_inicial
        )

        sesion_telemetria_id = (
            crear_sesion_telemetria(
                tid,
                intento,
                proceso.pid,
                remoto_inicial,
                str(log_lftp)
            )
        )

        ahora = utc()

        DB.execute("""
            UPDATE transferencias
            SET
                estado='TRANSFIRIENDO',
                pid=?,
                mensaje=?,
                iniciada_utc=
                    COALESCE(iniciada_utc, ?),
                actualizada_utc=?
            WHERE id=?
        """, (
            proceso.pid,
            (
                "Reanudando transferencia"
                if remoto_inicial > 0
                else
                "Transfiriendo a PS3"
            ),
            ahora,
            ahora,
            tid
        ))

        DB.commit()

        evento(
            "TRANSFERENCIA_INICIADA",
            (
                "Transferencia iniciada"
                if remoto_inicial == 0
                else
                "Transferencia reanudada"
            ),
            tid,
            datos={
                "pid": proceso.pid,
                "bytes_iniciales": remoto_inicial,
                "intento": intento,
            }
        )

        inicio_monotonic = time.monotonic()
        ultimo_tiempo = inicio_monotonic
        ultimo_remoto = remoto_inicial
        ultima_consulta = 0.0

        while proceso.poll() is None:

            if DETENER:
                terminar_proceso(
                    proceso
                )

                actualizar_transferencia(
                    tid,
                    estado="EN_COLA",
                    pid=None,
                    velocidad_bps=None,
                    eta_segundos=None,
                    mensaje=(
                        "Worker detenido; "
                        "se reanudará automáticamente"
                    )
                )

                evento(
                    "WORKER_INTERRUMPIDO",
                    (
                        "Transferencia devuelta a "
                        "la cola al detener worker"
                    ),
                    tid,
                    "AVISO"
                )

                return

            for orden in ordenes_pendientes(
                tid
            ):
                accion = orden["accion"]
                oid = int(orden["id"])

                if accion == "PAUSAR":
                    actualizar_transferencia(
                        tid,
                        estado="PAUSANDO",
                        mensaje=(
                            "Deteniendo transferencia "
                            "de forma controlada"
                        )
                    )

                    terminar_proceso(
                        proceso
                    )

                    try:
                        remoto_actual = inspector.size(
                            remoto
                        )
                    except Exception:
                        remoto_actual = ultimo_remoto

                    actualizar_transferencia(
                        tid,
                        estado="PAUSADO",
                        pid=None,
                        bytes_transferidos=min(
                            remoto_actual,
                            total
                        ),
                        bytes_remotos=remoto_actual,
                        velocidad_bps=0,
                        eta_segundos=None,
                        mensaje=(
                            "Transferencia pausada; "
                            "el parcial remoto fue conservado"
                        )
                    )

                    marcar_orden(
                        oid,
                        "EJECUTADA",
                        "Transferencia pausada"
                    )

                    evento(
                        "TRANSFERENCIA_PAUSADA",
                        "Transferencia pausada",
                        tid
                    )

                    return

                if accion == "CANCELAR":
                    actualizar_transferencia(
                        tid,
                        estado="CANCELANDO",
                        mensaje=(
                            "Cancelando transferencia"
                        )
                    )

                    terminar_proceso(
                        proceso
                    )

                    try:
                        remoto_actual = inspector.size(
                            remoto
                        )
                    except Exception:
                        remoto_actual = ultimo_remoto

                    actualizar_transferencia(
                        tid,
                        estado="CANCELADO",
                        pid=None,
                        bytes_transferidos=min(
                            remoto_actual,
                            total
                        ),
                        bytes_remotos=remoto_actual,
                        velocidad_bps=0,
                        eta_segundos=None,
                        mensaje=(
                            "Transferencia cancelada; "
                            "se conserva el parcial remoto"
                        ),
                        finalizada_utc=utc()
                    )

                    marcar_orden(
                        oid,
                        "EJECUTADA",
                        "Transferencia cancelada"
                    )

                    evento(
                        "TRANSFERENCIA_CANCELADA",
                        "Transferencia cancelada",
                        tid,
                        "AVISO"
                    )

                    return

                marcar_orden(
                    oid,
                    "RECHAZADA",
                    (
                        f"{accion} no es válida "
                        "durante una transferencia activa"
                    )
                )

            ahora_mono = time.monotonic()

            if (
                ahora_mono - ultima_consulta
                >= REMOTE_QUERY_INTERVAL
            ):
                ultima_consulta = ahora_mono

                try:
                    remoto_actual = inspector.size(
                        remoto
                    )

                    delta_bytes = max(
                        0,
                        remoto_actual - ultimo_remoto
                    )

                    delta_t = max(
                        0.001,
                        ahora_mono - ultimo_tiempo
                    )

                    velocidad = (
                        delta_bytes
                        / delta_t
                    )

                    transcurrido = max(
                        0.001,
                        ahora_mono - inicio_monotonic
                    )

                    transferidos_sesion = max(
                        0,
                        remoto_actual - remoto_inicial
                    )

                    promedio = (
                        transferidos_sesion
                        / transcurrido
                    )

                    restante = max(
                        0,
                        total - remoto_actual
                    )

                    referencia = (
                        promedio
                        if promedio > 0
                        else velocidad
                    )

                    eta = (
                        int(restante / referencia)
                        if referencia > 0
                        else None
                    )

                    actualizar_transferencia(
                        tid,
                        bytes_transferidos=min(
                            remoto_actual,
                            total
                        ),
                        bytes_remotos=remoto_actual,
                        velocidad_bps=velocidad,
                        velocidad_promedio_bps=promedio,
                        eta_segundos=eta,
                        mensaje="Transfiriendo a PS3"
                    )

                    actualizar_sesion_telemetria(
                        sesion_telemetria_id,
                        remoto_inicial_telemetria,
                        remoto_actual,
                        transcurrido
                    )

                    ultimo_remoto = remoto_actual
                    ultimo_tiempo = ahora_mono

                except Exception as exc:
                    LOG.warning(
                        "Transferencia #%s: no se "
                        "pudo consultar progreso: %s",
                        tid,
                        exc
                    )

            actualizar_worker(
                "OCUPADO",
                f"Transfiriendo #{tid}",
                tid
            )

            time.sleep(
                PROGRESS_INTERVAL
            )

        retorno = proceso.returncode

        actualizar_transferencia(
            tid,
            estado="VERIFICANDO",
            pid=None,
            velocidad_bps=0,
            eta_segundos=0,
            mensaje=(
                "Verificando tamaño remoto final"
            )
        )

        inspector.cerrar()

        time.sleep(0.5)

        inspector = InspectorFTP()

        remoto_final = inspector.size(
            remoto
        )

        if remoto_final == total:
            actualizar_transferencia(
                tid,
                estado="COMPLETADO",
                bytes_transferidos=total,
                bytes_remotos=total,
                pid=None,
                velocidad_bps=0,
                eta_segundos=0,
                mensaje=(
                    "Transferencia completada "
                    "y tamaño remoto verificado"
                ),
                error_codigo=None,
                error_detalle=None,
                finalizada_utc=utc()
            )

            evento(
                "TRANSFERENCIA_COMPLETADA",
                "Transferencia completada correctamente",
                tid,
                datos={
                    "tamano_bytes": total,
                    "codigo_lftp": retorno,
                }
            )

            return

        if remoto_final > total:
            actualizar_transferencia(
                tid,
                estado="CONFLICTO",
                bytes_remotos=remoto_final,
                pid=None,
                velocidad_bps=0,
                eta_segundos=None,
                mensaje=(
                    "El archivo remoto terminó "
                    "siendo mayor que el local"
                ),
                error_codigo="REMOTO_MAYOR",
                error_detalle=(
                    f"Remoto={remoto_final}; "
                    f"local={total}"
                ),
                finalizada_utc=utc()
            )

            evento(
                "CONFLICTO_REMOTO",
                "Tamaño remoto final inválido",
                tid,
                "ERROR"
            )

            return

        detalle_lftp = tail_archivo(
            log_lftp
        )

        if intento < MAX_TRANSFER_RETRIES:
            actualizar_transferencia(
                tid,
                estado="REINTENTANDO",
                bytes_transferidos=min(
                    remoto_final,
                    total
                ),
                bytes_remotos=remoto_final,
                pid=None,
                velocidad_bps=0,
                eta_segundos=None,
                mensaje=(
                    f"Intento {intento} incompleto; "
                    "se reanudará automáticamente"
                ),
                error_codigo="LFTP_INCOMPLETO",
                error_detalle=detalle_lftp[-2000:]
            )

            evento(
                "TRANSFERENCIA_REINTENTO",
                (
                    "Transferencia incompleta; "
                    "se programó reanudación"
                ),
                tid,
                "AVISO",
                {
                    "intento": intento,
                    "codigo_lftp": retorno,
                    "bytes_remotos": remoto_final,
                }
            )

            limite = min(
                RECONNECT_BASE * intento,
                RECONNECT_MAX
            )

            inicio_espera = time.monotonic()

            while (
                not DETENER
                and time.monotonic() - inicio_espera
                    < limite
            ):
                actualizar_worker(
                    "OCUPADO",
                    f"Reintentando #{tid}",
                    tid
                )

                time.sleep(1)

            if not DETENER:
                actualizar_transferencia(
                    tid,
                    estado="EN_COLA",
                    pid=None,
                    mensaje=(
                        "Lista para reanudar "
                        "automáticamente"
                    )
                )

            return

        actualizar_transferencia(
            tid,
            estado="ERROR",
            bytes_transferidos=min(
                remoto_final,
                total
            ),
            bytes_remotos=remoto_final,
            pid=None,
            velocidad_bps=0,
            eta_segundos=None,
            mensaje=(
                "La transferencia agotó "
                "los reintentos"
            ),
            error_codigo="LFTP_ERROR",
            error_detalle=detalle_lftp[-4000:],
            finalizada_utc=utc()
        )

        evento(
            "TRANSFERENCIA_ERROR",
            "Transferencia finalizada con error",
            tid,
            "ERROR",
            {
                "codigo_lftp": retorno,
                "intentos": intento,
                "bytes_remotos": remoto_final,
            }
        )

    except Exception as exc:
        LOG.exception(
            "Error procesando transferencia #%s",
            tid
        )

        if proceso is not None:
            terminar_proceso(
                proceso
            )

        actualizar_transferencia(
            tid,
            estado="ERROR",
            pid=None,
            velocidad_bps=0,
            eta_segundos=None,
            mensaje="Error en el worker",
            error_codigo="WORKER_ERROR",
            error_detalle=str(exc),
            finalizada_utc=utc()
        )

        evento(
            "WORKER_ERROR",
            str(exc),
            tid,
            "ERROR"
        )

    finally:
        if sesion_telemetria_id is not None:
            codigo_telemetria = (
                proceso.returncode
                if proceso is not None
                else None
            )

            finalizar_sesion_telemetria(
                sesion_telemetria_id,
                tid,
                codigo_telemetria
            )

        inspector.cerrar()

        if log_handle is not None:
            try:
                log_handle.close()
            except Exception:
                pass

        actualizar_worker(
            "ESPERANDO",
            "Esperando nuevas transferencias",
            None
        )




# ==========================================================
# CTPS3 J3-D3 - ELIMINACION SEGURA DE JUEGOS
# Version 1.0.0
# ==========================================================

TIPOS_ELIMINACION_JUEGO = {
    "HDD_JUEGO": (
        "/dev_hdd0/game/",
        False,
    ),

    "DATOS_GAME": (
        "/dev_hdd0/game/",
        False,
    ),

    "CACHE_GAME": (
        "/dev_hdd0/game/",
        False,
    ),

    "JB_FOLDER": (
        "/dev_hdd0/GAMES/",
        False,
    ),

    "PS3_ISO": (
        "/dev_hdd0/PS3ISO/",
        True,
    ),
}


def registrar_evento_eliminacion_juego(
    tipo: str,
    mensaje: str,
    nivel: str = "INFO",
    datos=None,
) -> None:
    DB.execute("""
        INSERT INTO eventos (
            transferencia_id,
            nivel,
            tipo,
            mensaje,
            datos_json
        )
        VALUES (
            NULL,
            ?,
            ?,
            ?,
            ?
        )
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

    DB.commit()


def siguiente_eliminacion_juego():
    return DB.execute("""
        SELECT
            id,
            juego_id,
            nombre,
            title_id,
            tipo_principal,
            estado,
            componentes_total,
            componentes_eliminados,
            tamano_objetivo_bytes,
            tamano_completo,
            creada_utc,
            mensaje

        FROM eliminaciones_juegos

        WHERE estado='PENDIENTE'

        ORDER BY
            creada_utc ASC,
            id ASC

        LIMIT 1
    """).fetchone()


def validar_ruta_eliminacion_juego(
    tipo: str,
    ruta_remota: str,
) -> tuple[str, str]:
    tipo = str(
        tipo
        or ""
    )

    ruta = str(
        ruta_remota
        or ""
    )


    if tipo not in TIPOS_ELIMINACION_JUEGO:
        raise RuntimeError(
            "Tipo de componente "
            "no permitido para eliminación"
        )


    if (
        not ruta
        or "\x00" in ruta
        or "\\" in ruta
        or "*" in ruta
        or "?" in ruta
        or "#" in ruta
        or "%" in ruta
    ):
        raise RuntimeError(
            "Ruta de eliminación "
            "contiene caracteres no permitidos"
        )


    if any(
        ord(caracter) < 32
        or ord(caracter) == 127
        for caracter in ruta
    ):
        raise RuntimeError(
            "Ruta de eliminación "
            "contiene caracteres de control"
        )


    (
        prefijo,
        requiere_iso,
    ) = TIPOS_ELIMINACION_JUEGO[
        tipo
    ]


    if not ruta.startswith(
        prefijo
    ):
        raise RuntimeError(
            "Ruta fuera del root "
            "permitido para el tipo"
        )


    relativa = ruta[
        len(prefijo):
    ]


    if (
        not relativa
        or relativa in {
            ".",
            "..",
        }
        or "/" in relativa
        or relativa.startswith(
            "_INST_"
        )
    ):
        raise RuntimeError(
            "Ruta relativa de eliminación "
            "no permitida"
        )


    if (
        requiere_iso
        and not relativa
            .lower()
            .endswith(
                ".iso"
            )
    ):
        raise RuntimeError(
            "PS3_ISO requiere archivo .iso"
        )


    return (
        prefijo.rstrip("/"),
        relativa,
    )


def ruta_eliminacion_existe_ftp(
    tipo: str,
    ruta_remota: str,
) -> bool:
    (
        directorio_padre,
        nombre,
    ) = validar_ruta_eliminacion_juego(
        tipo,
        ruta_remota,
    )


    ftp = FTP(
        encoding="latin-1"
    )


    try:
        ftp.connect(
            HOST,
            PORT,
            timeout=30
        )

        ftp.login(
            USER,
            PASSWORD
        )

        ftp.voidcmd(
            "TYPE I"
        )

        ftp.cwd(
            directorio_padre
        )

        listado = ftp.nlst()

        presentes = {
            str(item)
                .rstrip("/")
                .rsplit("/", 1)[-1]
            for item in listado
        }


        try:
            ftp.quit()
        except Exception:
            ftp.close()


        return nombre in presentes


    except Exception:
        try:
            ftp.close()
        except Exception:
            pass

        raise


def eliminar_ruta_juego_webman(
    tipo: str,
    ruta_remota: str,
):
    validar_ruta_eliminacion_juego(
        tipo,
        ruta_remota,
    )


    ruta_url = quote(
        ruta_remota,
        safe="/"
    )


    url = (
        f"http://{HOST}:"
        f"{WEBMAN_HTTP_PORT}"
        f"/delete.ps3"
        f"{ruta_url}"
    )


    solicitud = Request(
        url,
        method="GET",
        headers={
            "User-Agent":
                f"CTPS3/{VERSION}",

            "Connection":
                "close",
        },
    )


    codigo = None
    cuerpo = b""
    error_http = None


    try:
        with urlopen(
            solicitud,
            timeout=120
        ) as respuesta:

            codigo = int(
                respuesta.getcode()
            )

            cuerpo = respuesta.read(
                4096
            )


        if not (
            200 <= codigo < 300
        ):
            error_http = RuntimeError(
                "webMAN devolvió HTTP "
                f"{codigo}"
            )


    except Exception as exc:
        error_http = exc


    presente = True

    for intento in range(15):
        try:
            presente = (
                ruta_eliminacion_existe_ftp(
                    tipo,
                    ruta_remota,
                )
            )

        except Exception:
            if intento >= 14:
                raise

            time.sleep(2)
            continue


        if not presente:
            break


        if intento < 14:
            time.sleep(2)


    if presente:
        if error_http is not None:
            raise RuntimeError(
                "webMAN no confirmó la eliminación "
                "y la ruta continúa presente: "
                f"{error_http}"
            )

        raise RuntimeError(
            "webMAN respondió pero la ruta "
            "continúa presente"
        )


    return (
        codigo,
        len(cuerpo),
        (
            str(error_http)
            if error_http is not None
            else None
        ),
    )


def marcar_eliminacion_juego_procesando(
    eliminacion_id: int,
) -> bool:
    ahora = utc()

    cursor = DB.execute("""
        UPDATE eliminaciones_juegos
        SET
            estado='PROCESANDO',
            iniciada_utc=
                COALESCE(
                    iniciada_utc,
                    ?
                ),
            actualizada_utc=?,
            mensaje='Eliminando componentes',
            error_detalle=NULL
        WHERE
            id=?
            AND estado='PENDIENTE'
    """, (
        ahora,
        ahora,
        eliminacion_id,
    ))

    DB.commit()

    return cursor.rowcount == 1


def recuperar_eliminaciones_juegos_interrumpidas(
) -> int:
    filas = DB.execute("""
        SELECT
            id,
            juego_id,
            nombre
        FROM eliminaciones_juegos
        WHERE estado='PROCESANDO'
        ORDER BY id ASC
    """).fetchall()


    if not filas:
        return 0


    ahora = utc()

    DB.execute(
        "BEGIN IMMEDIATE"
    )


    try:
        DB.execute("""
            UPDATE eliminaciones_juegos_componentes
            SET
                estado='ERROR',
                mensaje=(
                    'Worker reiniciado durante '
                    'una eliminación destructiva; '
                    'no se reintenta automáticamente'
                ),
                actualizado_utc=?
            WHERE
                estado='PROCESANDO'
                AND eliminacion_id IN (
                    SELECT id
                    FROM eliminaciones_juegos
                    WHERE estado='PROCESANDO'
                )
        """, (
            ahora,
        ))


        DB.execute("""
            UPDATE eliminaciones_juegos
            SET
                estado='ERROR',
                actualizada_utc=?,
                finalizada_utc=?,
                mensaje=(
                    'Eliminación interrumpida '
                    'por reinicio del worker'
                ),
                error_detalle=(
                    'Resultado remoto ambiguo; '
                    'se requiere nuevo inventario '
                    'antes de otra solicitud'
                )
            WHERE estado='PROCESANDO'
        """, (
            ahora,
            ahora,
        ))


        DB.commit()


    except Exception:
        DB.rollback()
        raise


    for fila in filas:
        registrar_evento_eliminacion_juego(
            "JUEGO_ELIMINACION_INTERRUMPIDA",
            (
                "Eliminación interrumpida: "
                + str(
                    fila["nombre"]
                )
            ),
            nivel="ERROR",
            datos={
                "eliminacion_id":
                    int(fila["id"]),

                "juego_id":
                    int(fila["juego_id"]),
            },
        )


    return len(filas)


def ejecutar_eliminacion_juego(
    eliminacion,
) -> bool:
    eliminacion_id = int(
        eliminacion["id"]
    )

    juego_id = int(
        eliminacion["juego_id"]
    )

    nombre = str(
        eliminacion["nombre"]
    )


    (
        lista,
        _estado,
        motivo,
    ) = ps3_lista_para_pkg(
        "INSTALAR_PKG"
    )


    if not lista:
        actualizar_worker(
            "ESPERANDO",
            (
                "Eliminación pendiente: "
                + motivo
            ),
            None
        )

        return False


    if not marcar_eliminacion_juego_procesando(
        eliminacion_id
    ):
        return True


    actualizar_worker(
        "OCUPADO",
        (
            "Eliminando juego: "
            + nombre
        ),
        None
    )


    componente_actual_id = None


    try:
        componentes = DB.execute("""
            SELECT
                id,
                juego_componente_id,
                tipo,
                ruta_remota,
                tamano_bytes,
                estado

            FROM eliminaciones_juegos_componentes

            WHERE
                eliminacion_id=?
                AND estado='PENDIENTE'

            ORDER BY id ASC
        """, (
            eliminacion_id,
        )).fetchall()


        if not componentes:
            raise RuntimeError(
                "La eliminación no tiene "
                "componentes pendientes"
            )


        for componente in componentes:
            componente_actual_id = int(
                componente["id"]
            )

            juego_componente_id = int(
                componente[
                    "juego_componente_id"
                ]
            )

            tipo = str(
                componente["tipo"]
            )

            ruta = str(
                componente["ruta_remota"]
            )


            validar_ruta_eliminacion_juego(
                tipo,
                ruta,
            )


            actual = DB.execute("""
                SELECT
                    juego_id,
                    tipo,
                    ruta_remota,
                    disponible
                FROM juegos_ps3_componentes
                WHERE id=?
                LIMIT 1
            """, (
                juego_componente_id,
            )).fetchone()


            if actual is None:
                raise RuntimeError(
                    "Componente lógico ya no existe"
                )


            if (
                int(actual["juego_id"])
                    != juego_id
                or str(actual["tipo"])
                    != tipo
                or str(actual["ruta_remota"])
                    != ruta
            ):
                raise RuntimeError(
                    "Componente cambió desde "
                    "la solicitud; eliminación bloqueada"
                )


            if not bool(
                actual["disponible"]
            ):
                if ruta_eliminacion_existe_ftp(
                    tipo,
                    ruta,
                ):
                    raise RuntimeError(
                        "Inventario marca el componente "
                        "no disponible pero la ruta existe"
                    )


                ahora = utc()

                DB.execute("""
                    UPDATE
                        eliminaciones_juegos_componentes
                    SET
                        estado='ELIMINADO',
                        mensaje=(
                            'La ruta ya estaba ausente '
                            'antes de ejecutar'
                        ),
                        actualizado_utc=?
                    WHERE
                        id=?
                        AND estado='PENDIENTE'
                """, (
                    ahora,
                    componente_actual_id,
                ))

                DB.execute("""
                    UPDATE eliminaciones_juegos
                    SET
                        componentes_eliminados=(
                            SELECT COUNT(*)
                            FROM
                                eliminaciones_juegos_componentes
                            WHERE
                                eliminacion_id=?
                                AND estado='ELIMINADO'
                        ),
                        actualizada_utc=?
                    WHERE id=?
                """, (
                    eliminacion_id,
                    ahora,
                    eliminacion_id,
                ))

                DB.commit()

                continue


            ahora = utc()

            cursor = DB.execute("""
                UPDATE
                    eliminaciones_juegos_componentes
                SET
                    estado='PROCESANDO',
                    mensaje='Eliminando mediante webMAN',
                    actualizado_utc=?
                WHERE
                    id=?
                    AND estado='PENDIENTE'
            """, (
                ahora,
                componente_actual_id,
            ))

            DB.commit()


            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Cambio concurrente en "
                    "componente de eliminación"
                )


            (
                codigo_http,
                bytes_respuesta,
                advertencia_http,
            ) = eliminar_ruta_juego_webman(
                tipo,
                ruta,
            )


            ahora = utc()

            DB.execute("""
                UPDATE
                    eliminaciones_juegos_componentes
                SET
                    estado='ELIMINADO',
                    mensaje=?,
                    http_codigo=?,
                    respuesta_bytes=?,
                    actualizado_utc=?
                WHERE
                    id=?
                    AND estado='PROCESANDO'
            """, (
                (
                    "Ruta eliminada y ausencia "
                    "verificada por FTP"
                    + (
                        " (HTTP con incidencia: "
                        + advertencia_http
                        + ")"
                        if advertencia_http
                        else ""
                    )
                ),
                codigo_http,
                bytes_respuesta,
                ahora,
                componente_actual_id,
            ))


            DB.execute("""
                UPDATE eliminaciones_juegos
                SET
                    componentes_eliminados=(
                        SELECT COUNT(*)
                        FROM
                            eliminaciones_juegos_componentes
                        WHERE
                            eliminacion_id=?
                            AND estado='ELIMINADO'
                    ),
                    actualizada_utc=?,
                    mensaje='Eliminando componentes'
                WHERE id=?
            """, (
                eliminacion_id,
                ahora,
                eliminacion_id,
            ))

            DB.commit()


            registrar_evento_eliminacion_juego(
                "JUEGO_COMPONENTE_ELIMINADO",
                (
                    "Componente eliminado: "
                    + ruta
                ),
                nivel="INFO",
                datos={
                    "eliminacion_id":
                        eliminacion_id,

                    "juego_id":
                        juego_id,

                    "juego_componente_id":
                        juego_componente_id,

                    "tipo":
                        tipo,

                    "ruta_remota":
                        ruta,

                    "http_codigo":
                        codigo_http,
                },
            )


        resumen = DB.execute("""
            SELECT
                componentes_total,
                componentes_eliminados
            FROM eliminaciones_juegos
            WHERE id=?
            LIMIT 1
        """, (
            eliminacion_id,
        )).fetchone()


        if (
            resumen is None
            or int(
                resumen[
                    "componentes_eliminados"
                ]
            )
            != int(
                resumen[
                    "componentes_total"
                ]
            )
        ):
            raise RuntimeError(
                "No todos los componentes "
                "quedaron verificados como eliminados"
            )


        ahora = utc()

        DB.execute("""
            UPDATE eliminaciones_juegos
            SET
                estado='COMPLETADO',
                actualizada_utc=?,
                finalizada_utc=?,
                mensaje=(
                    'Todos los componentes fueron '
                    'eliminados y verificados'
                ),
                error_detalle=NULL
            WHERE
                id=?
                AND estado='PROCESANDO'
        """, (
            ahora,
            ahora,
            eliminacion_id,
        ))

        DB.commit()


        registrar_evento_eliminacion_juego(
            "JUEGO_ELIMINADO",
            (
                "Juego eliminado: "
                + nombre
            ),
            nivel="INFO",
            datos={
                "eliminacion_id":
                    eliminacion_id,

                "juego_id":
                    juego_id,

                "componentes":
                    int(
                        resumen[
                            "componentes_total"
                        ]
                    ),

                "tamano_bytes":
                    int(
                        eliminacion[
                            "tamano_objetivo_bytes"
                        ]
                        or 0
                    ),
            },
        )


        return True


    except Exception as exc:
        LOG.exception(
            "Error eliminando juego #%s (%s)",
            juego_id,
            eliminacion_id
        )


        ahora = utc()


        if componente_actual_id is not None:
            DB.execute("""
                UPDATE
                    eliminaciones_juegos_componentes
                SET
                    estado='ERROR',
                    mensaje=?,
                    actualizado_utc=?
                WHERE
                    id=?
                    AND estado='PROCESANDO'
            """, (
                str(exc),
                ahora,
                componente_actual_id,
            ))


        DB.execute("""
            UPDATE eliminaciones_juegos
            SET
                estado='ERROR',
                actualizada_utc=?,
                finalizada_utc=?,
                mensaje='Eliminación detenida por error',
                error_detalle=?
            WHERE
                id=?
                AND estado='PROCESANDO'
        """, (
            ahora,
            ahora,
            str(exc),
            eliminacion_id,
        ))

        DB.commit()


        registrar_evento_eliminacion_juego(
            "JUEGO_ELIMINACION_ERROR",
            (
                "Error eliminando juego: "
                + nombre
            ),
            nivel="ERROR",
            datos={
                "eliminacion_id":
                    eliminacion_id,

                "juego_id":
                    juego_id,

                "error":
                    str(exc),
            },
        )


        return True


    finally:
        actualizar_worker(
            "ESPERANDO",
            "Esperando nuevas transferencias",
            None
        )



# ==========================================================
# CTPS3 11B - MOTOR DE OPERACIONES PKG
# ==========================================================

ACCIONES_PKG = {
    "INSTALAR_PKG",
    "ELIMINAR_PKG",
}

WEBMAN_HTTP_PORT = 80


def registrar_evento_pkg(
    tipo: str,
    mensaje: str,
    nivel: str = "INFO",
    datos=None,
) -> None:
    DB.execute("""
        INSERT INTO eventos (
            transferencia_id,
            nivel,
            tipo,
            mensaje,
            datos_json
        )
        VALUES (
            NULL,
            ?,
            ?,
            ?,
            ?
        )
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

    DB.commit()


def evaluar_capacidad_hdd_instalacion_pkg(
    tamanos_pkg,
    estado_hdd,
    multipart=False,
):
    tamanos = []

    for valor in tamanos_pkg:
        try:
            tamano = int(valor or 0)
        except (TypeError, ValueError):
            tamano = 0

        if tamano <= 0:
            datos = {
                "tipo": "MULTIPART" if multipart else "INDIVIDUAL",
                "metodo_estimacion": (
                    "SUMA_PKG_MAS_TEMPORAL_MAXIMO"
                    if multipart
                    else "TAMANO_PKG"
                ),
                "motivo": "TAMANO_PKG_NO_VERIFICABLE",
                "margen_seguridad_bytes": MARGEN_HDD_SEGURIDAD_BYTES,
                "pkg_total_bytes": None,
                "temporal_maximo_bytes": None,
                "estimacion_instalacion_bytes": None,
                "bytes_requeridos": None,
                "hdd_libre_bytes_aprox": None,
                "capacidad_util_bytes": None,
                "faltante_bytes": None,
            }

            return (
                False,
                "ALMACENAMIENTO_NO_VERIFICABLE",
                "Esperando PS3: tamaño PKG no verificable",
                datos,
            )

        tamanos.append(tamano)

    if not tamanos:
        return (
            False,
            "ALMACENAMIENTO_NO_VERIFICABLE",
            "Esperando PS3: sin PKG para evaluar",
            {
                "motivo": "SIN_PKG",
                "margen_seguridad_bytes": MARGEN_HDD_SEGURIDAD_BYTES,
            },
        )

    pkg_total = sum(tamanos)
    temporal_maximo = max(tamanos) if multipart else 0
    estimacion_instalacion = pkg_total
    requeridos = estimacion_instalacion + temporal_maximo

    datos = {
        "tipo": "MULTIPART" if multipart else "INDIVIDUAL",
        "metodo_estimacion": (
            "SUMA_PKG_MAS_TEMPORAL_MAXIMO"
            if multipart
            else "TAMANO_PKG"
        ),
        "pkg_total_bytes": pkg_total,
        "temporal_maximo_bytes": temporal_maximo,
        "estimacion_instalacion_bytes": estimacion_instalacion,
        "bytes_requeridos": requeridos,
        "margen_seguridad_bytes": MARGEN_HDD_SEGURIDAD_BYTES,
        "hdd_libre_bytes_aprox": None,
        "hdd_antiguedad_segundos": None,
        "hdd_fuente": None,
        "capacidad_util_bytes": None,
        "faltante_bytes": None,
        "motivo": None,
    }

    if estado_hdd is None:
        datos["motivo"] = "SIN_ESTADO_HDD"
        return (
            False,
            "ALMACENAMIENTO_NO_VERIFICABLE",
            "Esperando PS3: almacenamiento no verificable",
            datos,
        )

    libre_raw = estado_hdd["hdd_libre_bytes_aprox"]
    antiguedad_raw = estado_hdd["hdd_antiguedad_segundos"]
    ultimo_error = str(estado_hdd["hdd_ultimo_error"] or "").strip()

    libre = max(0, int(libre_raw)) if libre_raw is not None else None
    antiguedad = float(antiguedad_raw) if antiguedad_raw is not None else None

    datos["hdd_libre_bytes_aprox"] = libre
    datos["hdd_antiguedad_segundos"] = antiguedad
    datos["hdd_fuente"] = estado_hdd["hdd_fuente"]

    if libre is None:
        datos["motivo"] = "SIN_LECTURA_HDD"
        return (
            False,
            "ALMACENAMIENTO_NO_VERIFICABLE",
            "Esperando PS3: sin lectura de almacenamiento",
            datos,
        )

    fresca = (
        antiguedad is not None
        and antiguedad >= -5.0
        and antiguedad <= FRESCURA_HDD_SEGUNDOS
    )

    if not fresca:
        datos["motivo"] = "LECTURA_HDD_DESACTUALIZADA"
        return (
            False,
            "ALMACENAMIENTO_NO_VERIFICABLE",
            "Esperando PS3: lectura de almacenamiento desactualizada",
            datos,
        )

    if ultimo_error:
        datos["motivo"] = "ULTIMO_INTENTO_HDD_ERROR"
        return (
            False,
            "ALMACENAMIENTO_NO_VERIFICABLE",
            "Esperando PS3: almacenamiento no verificable",
            datos,
        )

    capacidad_util = max(0, libre - MARGEN_HDD_SEGURIDAD_BYTES)
    faltante = max(0, requeridos - capacidad_util)

    datos["capacidad_util_bytes"] = capacidad_util
    datos["faltante_bytes"] = faltante

    if faltante > 0:
        datos["motivo"] = "ESPACIO_INSUFICIENTE"
        return (
            False,
            "ESPACIO_INSUFICIENTE_INSTALACION_PKG",
            (
                "Esperando espacio para instalar PKG: "
                f"requiere aprox. {requeridos / (1024 ** 3):.1f} GB; "
                f"libres {libre / (1024 ** 3):.1f} GB; "
                f"faltan aprox. {faltante / (1024 ** 3):.1f} GB"
            ),
            datos,
        )

    datos["motivo"] = "OK"
    return (
        True,
        None,
        "Capacidad estimada para instalación verificada",
        datos,
    )


def siguiente_orden_pkg():
    return DB.execute("""
        SELECT
            o.*,

            ar.nombre AS pkg_nombre,
            ar.ruta_remota AS pkg_ruta,
            ar.tamano_bytes AS pkg_tamano,
            ar.disponible AS pkg_disponible

        FROM ordenes o

        JOIN archivos_remotos ar
            ON ar.id=o.archivo_remoto_id

        WHERE
            o.estado='PENDIENTE'

            AND o.accion IN (
                'INSTALAR_PKG',
                'ELIMINAR_PKG'
            )

            AND NOT EXISTS (
                SELECT 1
                FROM lote_pkg_ordenes lpo
                WHERE lpo.orden_id=o.id
            )

        ORDER BY
            o.creada_utc ASC,
            o.id ASC

        LIMIT 1
    """).fetchone()


def validar_archivo_pkg(
    fila
):
    nombre = str(
        fila["pkg_nombre"]
        or ""
    )

    ruta = str(
        fila["pkg_ruta"]
        or ""
    )

    disponible = bool(
        fila["pkg_disponible"]
    )

    if not disponible:
        raise RuntimeError(
            "PKG ya no disponible "
            "en el inventario"
        )

    if (
        not nombre
        or "/" in nombre
        or "\\" in nombre
        or nombre in {".", ".."}
    ):
        raise RuntimeError(
            "Nombre PKG no permitido"
        )

    if not nombre.lower().endswith(
        ".pkg"
    ):
        raise RuntimeError(
            "El archivo remoto no es PKG"
        )

    if nombre.startswith(
        "__NO_INSTALAR__CTPS3_"
    ):
        raise RuntimeError(
            "Archivo de prueba protegido"
        )

    esperado = (
        REMOTE_DIR.rstrip("/")
        + "/"
        + nombre
    )

    if ruta != esperado:
        raise RuntimeError(
            "Ruta PKG fuera del directorio "
            "permitido"
        )

    return (
        nombre,
        ruta,
    )



# ==========================================================
# CTPS3 11E - MOTOR MULTIPARTE
#
# Etapa 1.7.3:
# - detecta lotes
# - valida sus partes
# - genera el script webMAN
#
# IMPORTANTE:
# todavía NO ejecuta ni sube el script.
# ==========================================================

def siguiente_lote_pkg():
    return DB.execute("""
        SELECT
            id,
            titulo,
            estado,
            creada_utc,
            mensaje
        FROM lotes_pkg
        WHERE estado='PENDIENTE'
        ORDER BY
            creada_utc ASC,
            id ASC
        LIMIT 1
    """).fetchone()


def cargar_partes_lote(
    lote_id: int
):
    filas = DB.execute("""
        SELECT
            lpo.posicion,

            o.id,
            o.archivo_remoto_id,
            o.accion,
            o.estado,

            ar.nombre
                AS pkg_nombre,

            ar.ruta_remota
                AS pkg_ruta,

            ar.tamano_bytes
                AS pkg_tamano,

            ar.disponible
                AS pkg_disponible

        FROM lote_pkg_ordenes lpo

        JOIN ordenes o
            ON o.id=lpo.orden_id

        JOIN archivos_remotos ar
            ON ar.id=o.archivo_remoto_id

        WHERE lpo.lote_id=?

        ORDER BY
            lpo.posicion ASC
    """, (
        lote_id,
    )).fetchall()


    if len(filas) < 2:
        raise RuntimeError(
            "El lote debe contener al menos "
            "dos partes"
        )


    posiciones = [
        int(fila["posicion"])
        for fila in filas
    ]

    esperadas = list(
        range(
            1,
            len(filas) + 1
        )
    )


    if posiciones != esperadas:
        raise RuntimeError(
            "Secuencia de partes inválida: "
            f"{posiciones}; esperaba "
            f"{esperadas}"
        )


    for fila in filas:

        oid = int(
            fila["id"]
        )

        if (
            str(fila["accion"])
            != "INSTALAR_PKG"
        ):
            raise RuntimeError(
                f"Orden #{oid}: "
                "acción no válida para lote"
            )


        if (
            str(fila["estado"])
            != "PENDIENTE"
        ):
            raise RuntimeError(
                f"Orden #{oid}: "
                "estado inesperado "
                f"{fila['estado']}"
            )


        nombre, ruta_remota = (
            validar_archivo_pkg(
                fila
            )
        )


        # validar_archivo_pkg() es la
        # autoridad existente para nombre,
        # disponibilidad y ruta remota.
        _ = nombre, ruta_remota


    return filas


def construir_script_lote(
    lote_id: int,
    partes
):
    if lote_id < 1:
        raise RuntimeError(
            "ID de lote inválido"
        )

    if len(partes) < 2:
        raise RuntimeError(
            "Lote sin suficientes partes"
        )


    tmp_dir = (
        "/dev_hdd0/packages/"
        f"__CTPS3_LOTE_{lote_id}__"
    )

    ruta_script = (
        "/dev_hdd0/tmp/"
        f"ctps3-lote-{lote_id}.bat"
    )

    ruta_log = (
        "/dev_hdd0/tmp/"
        f"ctps3-lote-{lote_id}.log"
    )


    lineas = [
        f"logfile {ruta_log}",
        (
            f"log CTPS3_LOTE_"
            f"{lote_id}_INICIO"
        ),

        # El lote PENDIENTE es siempre
        # un comienzo nuevo, no una
        # recuperación automática.
        f"del {tmp_dir}",
        f"md {tmp_dir}",
    ]


    for fila in partes:

        posicion = int(
            fila["posicion"]
        )

        nombre, ruta_remota = (
            validar_archivo_pkg(
                fila
            )
        )


        # '&' es el separador usado por
        # /copy_ps3 ... &to=...
        #
        # '?' modifica la semántica de
        # comandos HTTP de webMAN.
        #
        # CR/LF nunca pueden entrar al
        # archivo .bat generado.
        caracteres_peligrosos = (
            "&",
            "?",
            "\r",
            "\n",
        )

        if any(
            caracter in ruta_remota
            for caracter
            in caracteres_peligrosos
        ):
            raise RuntimeError(
                "Ruta PKG incompatible "
                "con script webMAN: "
                f"{nombre}"
            )


        temporal = (
            f"{tmp_dir}/"
            f"{posicion:03d}.pkg"
        )


        lineas.extend([
            "",
            (
                f"log CTPS3_LOTE_"
                f"{lote_id}_PARTE_"
                f"{posicion}_COPIA"
            ),

            f"del {temporal}",

            (
                f"/copy_ps3"
                f"{ruta_remota}"
                f"&to={temporal}"
            ),

            (
                "abort if not exist "
                f"{temporal}"
            ),

            (
                f"log CTPS3_LOTE_"
                f"{lote_id}_PARTE_"
                f"{posicion}_INSTALACION"
            ),

            (
                f"/install.ps3"
                f"{temporal}"
            ),

            (
                "abort if exist "
                f"{temporal}"
            ),

            (
                f"log CTPS3_LOTE_"
                f"{lote_id}_PARTE_"
                f"{posicion}_OK"
            ),
        ])


    lineas.extend([
        "",
        (
            f"log CTPS3_LOTE_"
            f"{lote_id}_OK"
        ),
        f"del {tmp_dir}",
    ])


    contenido = (
        "\n".join(lineas)
        + "\n"
    )


    return {
        "contenido":
            contenido,

        "ruta_script":
            ruta_script,

        "ruta_log":
            ruta_log,

        "directorio_temporal":
            tmp_dir,

        "total_partes":
            len(partes),
    }




def subir_script_lote_ftp(
    script
):
    """
    Sube exclusivamente el .bat generado
    para un lote.

    También elimina un script/log anterior
    con el mismo ID para impedir que una
    ejecución nueva lea marcadores viejos.
    """

    contenido = str(
        script["contenido"]
    )

    ruta_script = str(
        script["ruta_script"]
    )

    ruta_log = str(
        script["ruta_log"]
    )


    prefijo_script = (
        "/dev_hdd0/tmp/"
        "ctps3-lote-"
    )

    if (
        not ruta_script.startswith(
            prefijo_script
        )
        or not ruta_script.endswith(
            ".bat"
        )
    ):
        raise RuntimeError(
            "Ruta de script de lote "
            "no permitida"
        )


    prefijo_log = (
        "/dev_hdd0/tmp/"
        "ctps3-lote-"
    )

    if (
        not ruta_log.startswith(
            prefijo_log
        )
        or not ruta_log.endswith(
            ".log"
        )
    ):
        raise RuntimeError(
            "Ruta de log de lote "
            "no permitida"
        )


    if (
        "\x00" in contenido
        or not contenido.endswith("\n")
    ):
        raise RuntimeError(
            "Contenido .bat inválido"
        )


    datos = contenido.encode(
        "utf-8"
    )


    if len(datos) > 256 * 1024:
        raise RuntimeError(
            "Script de lote demasiado grande"
        )


    ftp = FTP(
        encoding="latin-1"
    )

    try:
        ftp.connect(
            HOST,
            PORT,
            timeout=30
        )

        ftp.login(
            USER,
            PASSWORD
        )

        ftp.voidcmd(
            "TYPE I"
        )


        # Una ejecución nueva nunca debe
        # reutilizar el log de otra anterior.
        for ruta in (
            ruta_script,
            ruta_log,
        ):
            try:
                ftp.delete(
                    ruta
                )
            except ftplib.error_perm as exc:
                if not str(exc).startswith(
                    "550"
                ):
                    raise


        ftp.storbinary(
            "STOR " + ruta_script,
            BytesIO(datos)
        )


        tamano_remoto = ftp.size(
            ruta_script
        )


        if tamano_remoto is None:
            raise RuntimeError(
                "FTP no informó tamaño "
                "del script subido"
            )


        if int(tamano_remoto) != len(datos):
            raise RuntimeError(
                "Tamaño remoto del .bat "
                "no coincide con el local"
            )


        try:
            ftp.quit()
        except Exception:
            ftp.close()


    except Exception:
        try:
            ftp.close()
        except Exception:
            pass

        raise


    return {
        "ruta_script":
            ruta_script,

        "ruta_log":
            ruta_log,

        "tamano_bytes":
            len(datos),
    }



def leer_log_lote_ftp(
    ruta_log: str
):
    """
    Devuelve None si el log todavía no existe.
    Si existe, devuelve su contenido textual.
    """

    ruta_log = str(
        ruta_log
    )


    if (
        not ruta_log.startswith(
            "/dev_hdd0/tmp/ctps3-lote-"
        )
        or not ruta_log.endswith(
            ".log"
        )
    ):
        raise RuntimeError(
            "Ruta de log no permitida"
        )


    ftp = FTP(
        encoding="latin-1"
    )

    datos = bytearray()


    try:
        ftp.connect(
            HOST,
            PORT,
            timeout=30
        )

        ftp.login(
            USER,
            PASSWORD
        )

        ftp.voidcmd(
            "TYPE I"
        )


        try:
            ftp.retrbinary(
                "RETR " + ruta_log,
                datos.extend
            )

        except ftplib.error_perm as exc:
            if str(exc).startswith(
                "550"
            ):
                try:
                    ftp.quit()
                except Exception:
                    ftp.close()

                return None

            raise


        try:
            ftp.quit()
        except Exception:
            ftp.close()


    except Exception:
        try:
            ftp.close()
        except Exception:
            pass

        raise


    if len(datos) > 256 * 1024:
        raise RuntimeError(
            "Log de lote demasiado grande"
        )


    return bytes(datos).decode(
        "utf-8",
        errors="replace"
    )



def interpretar_log_lote(
    lote_id: int,
    total_partes: int,
    texto
):
    """
    Interpreta únicamente marcadores CTPS3.

    No cambia SQLite ni consulta la PS3.
    """

    if lote_id < 1:
        raise RuntimeError(
            "ID de lote inválido"
        )

    if total_partes < 2:
        raise RuntimeError(
            "Cantidad de partes inválida"
        )


    if texto is None:
        return {
            "estado":
                "SIN_LOG",

            "finalizado":
                False,

            "partes_ok":
                [],

            "ultima_parte_ok":
                0,

            "parte_actual":
                None,

            "fase":
                "SIN_INICIAR",
        }


    texto = str(
        texto
    )


    prefijo = (
        f"CTPS3_LOTE_{lote_id}_"
    )


    def posicion(
        marcador: str
    ) -> int:
        return texto.find(
            marcador
        )


    inicio = posicion(
        prefijo + "INICIO"
    )


    if inicio < 0:
        return {
            "estado":
                "SIN_INICIO",

            "finalizado":
                False,

            "partes_ok":
                [],

            "ultima_parte_ok":
                0,

            "parte_actual":
                None,

            "fase":
                "SIN_INICIAR",
        }


    anterior = inicio
    partes_ok = []


    for parte in range(
        1,
        total_partes + 1
    ):
        marca_copia = (
            prefijo
            + f"PARTE_{parte}_COPIA"
        )

        marca_instalacion = (
            prefijo
            + f"PARTE_{parte}_INSTALACION"
        )

        marca_ok = (
            prefijo
            + f"PARTE_{parte}_OK"
        )


        pos_copia = posicion(
            marca_copia
        )

        pos_instalacion = posicion(
            marca_instalacion
        )

        pos_ok = posicion(
            marca_ok
        )


        presentes = [
            pos_copia >= 0,
            pos_instalacion >= 0,
            pos_ok >= 0,
        ]


        # Ningún marcador posterior puede
        # existir si falta uno anterior.
        if (
            pos_instalacion >= 0
            and pos_copia < 0
        ):
            raise RuntimeError(
                "Log de lote inconsistente: "
                f"parte {parte} instaló "
                "sin marcador de copia"
            )

        if (
            pos_ok >= 0
            and pos_instalacion < 0
        ):
            raise RuntimeError(
                "Log de lote inconsistente: "
                f"parte {parte} terminó "
                "sin marcador de instalación"
            )


        if all(presentes):
            if not (
                anterior
                < pos_copia
                < pos_instalacion
                < pos_ok
            ):
                raise RuntimeError(
                    "Log de lote fuera de orden "
                    f"en parte {parte}"
                )

            partes_ok.append(
                parte
            )

            anterior = pos_ok

            continue


        # Si esta parte está incompleta,
        # ninguna parte posterior puede
        # aparecer como OK.
        for posterior in range(
            parte + 1,
            total_partes + 1
        ):
            if posicion(
                prefijo
                + f"PARTE_{posterior}_OK"
            ) >= 0:
                raise RuntimeError(
                    "Log de lote no secuencial"
                )


        if pos_instalacion >= 0:
            fase = "INSTALANDO"

        elif pos_copia >= 0:
            fase = "COPIANDO"

        else:
            fase = "PREPARANDO"


        return {
            "estado":
                "EN_PROCESO",

            "finalizado":
                False,

            "partes_ok":
                partes_ok,

            "ultima_parte_ok":
                (
                    partes_ok[-1]
                    if partes_ok
                    else 0
                ),

            "parte_actual":
                parte,

            "fase":
                fase,
        }


    marca_final = (
        prefijo + "OK"
    )

    pos_final = posicion(
        marca_final
    )


    if pos_final < 0:
        return {
            "estado":
                "ESPERANDO_FINAL",

            "finalizado":
                False,

            "partes_ok":
                partes_ok,

            "ultima_parte_ok":
                total_partes,

            "parte_actual":
                None,

            "fase":
                "FINALIZANDO",
        }


    if pos_final <= anterior:
        raise RuntimeError(
            "Marcador final fuera de orden"
        )


    return {
        "estado":
            "FINALIZADO",

        "finalizado":
            True,

        "partes_ok":
            partes_ok,

        "ultima_parte_ok":
            total_partes,

        "parte_actual":
            None,

        "fase":
            "FINALIZADO",
    }




def ejecutar_script_lote_webman(
    ruta_script: str,
    timeout_segundos: float = 60.0,
):
    """
    Ejecuta exclusivamente un .bat CTPS3
    previamente subido a /dev_hdd0/tmp.

    La operación sigue siendo síncrona para
    ejecutar_lote_pkg(), pero la petición HTTP
    vive en un hilo auxiliar para que el hilo
    principal pueda renovar el heartbeat.
    """

    ruta_script = str(
        ruta_script
    )


    prefijo = (
        "/dev_hdd0/tmp/"
        "ctps3-lote-"
    )


    if (
        not ruta_script.startswith(
            prefijo
        )
        or not ruta_script.endswith(
            ".bat"
        )
    ):
        raise RuntimeError(
            "Ruta de script de lote "
            "no permitida"
        )


    identificador = ruta_script[
        len(prefijo):-4
    ]


    if (
        not identificador.isdigit()
        or int(identificador) < 1
    ):
        raise RuntimeError(
            "Identificador de script "
            "de lote inválido"
        )


    lote_id = int(
        identificador
    )


    if timeout_segundos <= 0:
        raise RuntimeError(
            "Timeout webMAN inválido"
        )


    ruta_url = quote(
        ruta_script,
        safe="/"
    )


    url = (
        f"http://{HOST}:"
        f"{WEBMAN_HTTP_PORT}"
        f"/play.ps3"
        f"{ruta_url}"
    )


    solicitud = Request(
        url,
        method="GET",
        headers={
            "User-Agent":
                f"CTPS3/{VERSION}",

            "Connection":
                "close",
        },
    )


    inicio = time.monotonic()

    resultado_hilo = {}


    def ejecutar_http():
        try:
            with urlopen(
                solicitud,
                timeout=timeout_segundos
            ) as respuesta:

                codigo = int(
                    respuesta.getcode()
                )

                cuerpo = respuesta.read(
                    4096
                )


            resultado_hilo[
                "codigo"
            ] = codigo

            resultado_hilo[
                "respuesta_bytes"
            ] = len(cuerpo)


        except Exception as exc:
            resultado_hilo[
                "error"
            ] = exc


    hilo = threading.Thread(
        target=ejecutar_http,
        name=(
            f"ctps3-play-lote-{lote_id}"
        ),
        daemon=True,
    )


    hilo.start()


    # Renovar con una frecuencia inferior al
    # heartbeat normal, pero nunca más espaciada
    # de 10 segundos.
    intervalo_heartbeat = min(
        max(
            float(
                HEARTBEAT_INTERVAL
            ) / 2.0,
            1.0,
        ),
        10.0,
    )


    proximo_heartbeat = (
        time.monotonic()
        + intervalo_heartbeat
    )


    limite = (
        inicio
        + float(timeout_segundos)
    )


    while hilo.is_alive():

        ahora = time.monotonic()


        if DETENER:
            raise RuntimeError(
                "Worker detenido mientras "
                "webMAN podría continuar "
                "ejecutando el lote"
            )


        restante = (
            limite - ahora
        )


        if restante <= 0:
            raise TimeoutError(
                "Tiempo máximo de espera "
                f"de /play.ps3 superado "
                f"({timeout_segundos:.0f}s)"
            )


        if ahora >= proximo_heartbeat:

            actualizar_worker(
                "OCUPADO",
                (
                    f"Lote PKG #{lote_id}: "
                    "webMAN ejecutando "
                    "instalación multipart"
                ),
                None
            )

            proximo_heartbeat = (
                ahora
                + intervalo_heartbeat
            )


        hilo.join(
            timeout=min(
                1.0,
                restante
            )
        )


    # join sin timeout también funciona como
    # barrera de visibilidad para el resultado.
    hilo.join()


    if "error" in resultado_hilo:
        raise resultado_hilo[
            "error"
        ]


    if "codigo" not in resultado_hilo:
        raise RuntimeError(
            "La petición webMAN terminó "
            "sin resultado"
        )


    codigo = int(
        resultado_hilo[
            "codigo"
        ]
    )

    respuesta_bytes = int(
        resultado_hilo[
            "respuesta_bytes"
        ]
    )


    duracion = (
        time.monotonic()
        - inicio
    )


    if not (
        200 <= codigo < 300
    ):
        raise RuntimeError(
            "webMAN devolvió HTTP "
            f"{codigo}"
        )


    # Deja además el heartbeat actualizado
    # exactamente al terminar la operación.
    actualizar_worker(
        "OCUPADO",
        (
            f"Lote PKG #{lote_id}: "
            "/play.ps3 finalizado; "
            "verificando resultado"
        ),
        None
    )


    return {
        "codigo_http":
            codigo,

        "respuesta_bytes":
            respuesta_bytes,

        "duracion_segundos":
            duracion,

        "ruta_script":
            ruta_script,
    }




def resolver_resultado_lote(
    lote_id: int,
    resultado_log: dict,
):
    """
    Resuelve en una sola transacción el padre
    y todas las órdenes hijas de un lote.

    Éxito:
        todas las partes -> EJECUTADA
        lote             -> EJECUTADO

    Fallo conocido:
        partes terminadas -> EJECUTADA
        parte actual      -> ERROR
        posteriores       -> RECHAZADA
        lote              -> ERROR

    Sin evidencia suficiente:
        órdenes restantes -> ERROR
        lote              -> ERROR
    """

    if lote_id < 1:
        raise RuntimeError(
            "ID de lote inválido"
        )

    if not isinstance(
        resultado_log,
        dict
    ):
        raise RuntimeError(
            "Resultado de log inválido"
        )


    lote = DB.execute("""
        SELECT
            id,
            titulo,
            estado
        FROM lotes_pkg
        WHERE id=?
        LIMIT 1
    """, (
        lote_id,
    )).fetchone()


    if lote is None:
        raise RuntimeError(
            f"Lote #{lote_id} inexistente"
        )


    if lote["estado"] != "PROCESANDO":
        raise RuntimeError(
            f"Lote #{lote_id}: "
            f"estado {lote['estado']}, "
            "esperaba PROCESANDO"
        )


    partes = DB.execute("""
        SELECT
            lpo.posicion,
            o.id AS orden_id,
            o.estado AS orden_estado
        FROM lote_pkg_ordenes lpo

        JOIN ordenes o
            ON o.id=lpo.orden_id

        WHERE lpo.lote_id=?

        ORDER BY lpo.posicion ASC
    """, (
        lote_id,
    )).fetchall()


    if len(partes) < 2:
        raise RuntimeError(
            "Lote sin suficientes partes"
        )


    posiciones = [
        int(fila["posicion"])
        for fila in partes
    ]

    esperadas = list(
        range(
            1,
            len(partes) + 1
        )
    )


    if posiciones != esperadas:
        raise RuntimeError(
            "Posiciones del lote inválidas"
        )


    for fila in partes:
        if fila["orden_estado"] != "PROCESANDO":
            raise RuntimeError(
                f"Orden #{fila['orden_id']}: "
                f"estado {fila['orden_estado']}, "
                "esperaba PROCESANDO"
            )


    partes_ok = sorted({
        int(valor)
        for valor in (
            resultado_log.get(
                "partes_ok",
                []
            )
            or []
        )
    })


    if any(
        parte not in esperadas
        for parte in partes_ok
    ):
        raise RuntimeError(
            "partes_ok contiene "
            "posiciones inválidas"
        )


    # Las partes OK deben formar siempre
    # un prefijo secuencial: [1], [1,2], etc.
    if partes_ok != list(
        range(
            1,
            len(partes_ok) + 1
        )
    ):
        raise RuntimeError(
            "partes_ok no es secuencial"
        )


    parte_actual_raw = (
        resultado_log.get(
            "parte_actual"
        )
    )

    parte_actual = (
        int(parte_actual_raw)
        if parte_actual_raw is not None
        else None
    )


    if (
        parte_actual is not None
        and parte_actual not in esperadas
    ):
        raise RuntimeError(
            "parte_actual inválida"
        )


    estado_log = str(
        resultado_log.get(
            "estado",
            ""
        )
    )


    todas_ok = (
        partes_ok == esperadas
    )


    # ESPERANDO_FINAL también prueba que todas
    # las instalaciones terminaron: cada parte
    # alcanzó PARTE_N_OK. Sólo faltó el marcador
    # global posterior.
    exito = (
        todas_ok
        and estado_log in {
            "FINALIZADO",
            "ESPERANDO_FINAL",
        }
    )


    ahora = utc()


    try:
        DB.execute(
            "BEGIN IMMEDIATE"
        )


        if exito:

            for fila in partes:
                posicion = int(
                    fila["posicion"]
                )

                cursor = DB.execute("""
                    UPDATE ordenes
                    SET
                        estado='EJECUTADA',
                        procesada_utc=?,
                        mensaje=?
                    WHERE
                        id=?
                        AND estado='PROCESANDO'
                """, (
                    ahora,
                    (
                        "Parte "
                        f"{posicion}/{len(partes)} "
                        "instalada automáticamente "
                        f"por lote PKG #{lote_id}"
                    ),
                    int(fila["orden_id"]),
                ))

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "Cambio concurrente en "
                        f"orden #{fila['orden_id']}"
                    )


            mensaje_lote = (
                f"Instalación multipart finalizada: "
                f"{len(partes)} partes instaladas"
            )


            cursor = DB.execute("""
                UPDATE lotes_pkg
                SET
                    estado='EJECUTADO',
                    procesada_utc=?,
                    mensaje=?
                WHERE
                    id=?
                    AND estado='PROCESANDO'
            """, (
                ahora,
                mensaje_lote,
                lote_id,
            ))


            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Cambio concurrente "
                    "en el lote"
                )


            DB.execute("""
                INSERT INTO eventos (
                    transferencia_id,
                    nivel,
                    tipo,
                    mensaje,
                    datos_json
                )
                VALUES (
                    NULL,
                    ?,
                    'PKG_LOTE_FINALIZADO',
                    ?,
                    ?
                )
            """, (
                (
                    "INFO"
                    if estado_log == "FINALIZADO"
                    else "AVISO"
                ),
                mensaje_lote,
                json.dumps(
                    {
                        "lote_id":
                            lote_id,

                        "total_partes":
                            len(partes),

                        "partes_ok":
                            partes_ok,

                        "estado_log":
                            estado_log,
                    },
                    ensure_ascii=False
                ),
            ))


            DB.commit()


            return {
                "estado_lote":
                    "EJECUTADO",

                "partes_ok":
                    partes_ok,

                "parte_error":
                    None,

                "partes_omitidas":
                    [],
            }


        # ==================================================
        # FALLO
        # ==================================================

        partes_omitidas = []
        parte_error = None


        for fila in partes:

            posicion = int(
                fila["posicion"]
            )

            orden_id = int(
                fila["orden_id"]
            )


            if posicion in partes_ok:

                estado_orden = (
                    "EJECUTADA"
                )

                mensaje = (
                    f"Parte {posicion}/"
                    f"{len(partes)} instalada "
                    "antes de detenerse "
                    f"el lote #{lote_id}"
                )


            elif (
                parte_actual is not None
                and posicion == parte_actual
            ):

                estado_orden = (
                    "ERROR"
                )

                parte_error = (
                    posicion
                )

                mensaje = (
                    f"Fallo del lote #{lote_id} "
                    f"durante parte {posicion}; "
                    "fase "
                    f"{resultado_log.get('fase')}"
                )


            elif (
                parte_actual is not None
                and posicion > parte_actual
            ):

                estado_orden = (
                    "RECHAZADA"
                )

                partes_omitidas.append(
                    posicion
                )

                mensaje = (
                    "Parte no ejecutada porque "
                    f"el lote #{lote_id} "
                    f"se detuvo en la parte "
                    f"{parte_actual}"
                )


            else:
                # SIN_LOG, SIN_INICIO u otro
                # resultado indeterminado sin
                # una parte actual identificable.
                estado_orden = (
                    "ERROR"
                )

                mensaje = (
                    f"Resultado indeterminado "
                    f"del lote #{lote_id}; "
                    f"estado de log {estado_log}"
                )


            cursor = DB.execute("""
                UPDATE ordenes
                SET
                    estado=?,
                    procesada_utc=?,
                    mensaje=?
                WHERE
                    id=?
                    AND estado='PROCESANDO'
            """, (
                estado_orden,
                ahora,
                mensaje,
                orden_id,
            ))


            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Cambio concurrente en "
                    f"orden #{orden_id}"
                )


        mensaje_lote = (
            f"Instalación multipart detenida; "
            f"estado de log: {estado_log}"
        )


        cursor = DB.execute("""
            UPDATE lotes_pkg
            SET
                estado='ERROR',
                procesada_utc=?,
                mensaje=?
            WHERE
                id=?
                AND estado='PROCESANDO'
        """, (
            ahora,
            mensaje_lote,
            lote_id,
        ))


        if cursor.rowcount != 1:
            raise RuntimeError(
                "Cambio concurrente "
                "en el lote"
            )


        DB.execute("""
            INSERT INTO eventos (
                transferencia_id,
                nivel,
                tipo,
                mensaje,
                datos_json
            )
            VALUES (
                NULL,
                'ERROR',
                'PKG_LOTE_ERROR',
                ?,
                ?
            )
        """, (
            mensaje_lote,
            json.dumps(
                {
                    "lote_id":
                        lote_id,

                    "estado_log":
                        estado_log,

                    "fase":
                        resultado_log.get(
                            "fase"
                        ),

                    "partes_ok":
                        partes_ok,

                    "parte_error":
                        parte_error,

                    "partes_omitidas":
                        partes_omitidas,
                },
                ensure_ascii=False
            ),
        ))


        DB.commit()


        return {
            "estado_lote":
                "ERROR",

            "partes_ok":
                partes_ok,

            "parte_error":
                parte_error,

            "partes_omitidas":
                partes_omitidas,
        }


    except Exception:
        DB.rollback()
        raise




def ejecutar_lote_pkg(
    lote,
    timeout_segundos: float = 21600.0,
) -> bool:
    """
    Ejecuta un lote multipart completo.

    IMPORTANTE:
    esta función no implica que el despacho
    multipart esté conectado a main().

    Retorna:
        False -> lote no consumido
                 (por ejemplo PS3 no lista)

        True  -> lote reservado/consumido,
                 aunque quede en conciliación
                 conservadora.
    """

    if lote is None:
        return False


    lote_id = int(
        lote["id"]
    )

    titulo = str(
        lote["titulo"]
        or f"Lote #{lote_id}"
    )

    estado_lote = str(
        lote["estado"]
    )


    if lote_id < 1:
        raise RuntimeError(
            "ID de lote inválido"
        )


    if estado_lote != "PENDIENTE":
        return False


    if timeout_segundos <= 0:
        raise RuntimeError(
            "Timeout multipart inválido"
        )


    # ======================================================
    # 1. PREFLIGHT COMPLETO ANTES DE RESERVAR
    # ======================================================

    partes = cargar_partes_lote(
        lote_id
    )


    script = construir_script_lote(
        lote_id,
        partes
    )


    total_partes = int(
        script["total_partes"]
    )


    if total_partes != len(partes):
        raise RuntimeError(
            "Cantidad de partes inconsistente"
        )


    (
        ps3_lista,
        estado_ps3,
        motivo_ps3,
    ) = ps3_lista_para_pkg(
        "INSTALAR_PKG"
    )


    if not ps3_lista:
        actualizar_worker(
            "ESPERANDO",
            (
                f"Lote PKG #{lote_id}: "
                f"{motivo_ps3}"
            )
        )

        return False


    (
        capacidad_ok,
        _codigo_hdd,
        mensaje_hdd,
        _datos_hdd,
    ) = evaluar_capacidad_hdd_instalacion_pkg(
        [
            int(parte["pkg_tamano"] or 0)
            for parte in partes
        ],
        leer_estado_hdd_transferencia(),
        multipart=True,
    )

    if not capacidad_ok:
        mensaje_lote = f"Lote PKG #{lote_id}: {mensaje_hdd}"

        DB.execute("""
            UPDATE lotes_pkg
            SET mensaje=?
            WHERE
                id=?
                AND estado='PENDIENTE'
                AND COALESCE(mensaje, '') <> ?
        """, (
            mensaje_lote,
            lote_id,
            mensaje_lote,
        ))
        DB.commit()

        actualizar_worker(
            "ESPERANDO",
            mensaje_lote,
            None
        )

        return False


    # ======================================================
    # 2. RESERVA ATÓMICA
    # ======================================================

    reservado = (
        marcar_lote_pkg_procesando(
            lote_id
        )
    )


    if not reservado:
        return False


    actualizar_worker(
        "OCUPADO",
        (
            f"Instalando lote PKG #{lote_id}: "
            f"{titulo} "
            f"({total_partes} partes)"
        ),
        None
    )


    # ======================================================
    # Helper interno:
    # conserva PROCESANDO cuando la realidad remota
    # no puede determinarse con seguridad.
    # ======================================================

    def conservar_indeterminado(
        etapa: str,
        error,
    ):
        detalle = str(
            error
        )[:700]


        mensaje = (
            f"Lote PKG #{lote_id} "
            "pendiente de conciliación; "
            f"etapa={etapa}; "
            f"detalle={detalle}"
        )


        try:
            DB.execute(
                "BEGIN IMMEDIATE"
            )


            cursor = DB.execute("""
                UPDATE lotes_pkg
                SET mensaje=?
                WHERE
                    id=?
                    AND estado='PROCESANDO'
            """, (
                mensaje,
                lote_id,
            ))


            if cursor.rowcount != 1:
                raise RuntimeError(
                    "El lote dejó de estar "
                    "PROCESANDO durante "
                    "la conciliación"
                )


            DB.execute("""
                UPDATE ordenes
                SET mensaje=?
                WHERE
                    id IN (
                        SELECT orden_id
                        FROM lote_pkg_ordenes
                        WHERE lote_id=?
                    )
                    AND estado='PROCESANDO'
            """, (
                (
                    "Parte controlada por "
                    f"lote PKG #{lote_id}; "
                    "resultado remoto "
                    "pendiente de conciliación"
                ),
                lote_id,
            ))


            DB.execute("""
                INSERT INTO eventos (
                    transferencia_id,
                    nivel,
                    tipo,
                    mensaje,
                    datos_json
                )
                VALUES (
                    NULL,
                    'AVISO',
                    'PKG_LOTE_CONCILIACION_PENDIENTE',
                    ?,
                    ?
                )
            """, (
                mensaje,
                json.dumps(
                    {
                        "lote_id":
                            lote_id,

                        "etapa":
                            etapa,

                        "detalle":
                            detalle,

                        "estado_conservado":
                            "PROCESANDO",

                        "reintento_automatico":
                            False,
                    },
                    ensure_ascii=False
                ),
            ))


            DB.commit()


        except Exception:
            DB.rollback()
            raise


        LOG.warning(
            "Lote PKG #%s queda pendiente "
            "de conciliación: %s",
            lote_id,
            detalle
        )


    # ======================================================
    # 3. SUBIR SCRIPT
    #
    # Si esto falla, /play.ps3 todavía NO fue llamado.
    # Por lo tanto sabemos que el lote no comenzó.
    # ======================================================

    try:
        subir_script_lote_ftp(
            script
        )

    except Exception as exc:

        LOG.exception(
            "Lote PKG #%s: fallo al subir "
            "el script",
            lote_id
        )


        resultado_preinicio = {
            "estado":
                "ERROR_PREPARACION",

            "finalizado":
                False,

            "partes_ok":
                [],

            "ultima_parte_ok":
                0,

            "parte_actual":
                None,

            "fase":
                "SUBIENDO_SCRIPT",
        }


        resolver_resultado_lote(
            lote_id,
            resultado_preinicio
        )

        return True


    # ======================================================
    # 4. EJECUTAR /play.ps3
    #
    # Si la llamada lanza una excepción después de haber
    # sido enviada, NO podemos afirmar que webMAN se haya
    # detenido. Por eso conservamos PROCESANDO.
    # ======================================================

    try:
        resultado_http = (
            ejecutar_script_lote_webman(
                script["ruta_script"],
                timeout_segundos=
                    timeout_segundos,
            )
        )

    except Exception as exc:

        conservar_indeterminado(
            "PLAY_PENDIENTE",
            exc
        )

        return True


    LOG.info(
        "Lote PKG #%s: /play.ps3 terminó "
        "HTTP=%s en %.3fs",
        lote_id,
        resultado_http.get(
            "codigo_http"
        ),
        float(
            resultado_http.get(
                "duracion_segundos",
                0.0
            )
        )
    )


    # ======================================================
    # 5. LEER E INTERPRETAR LOG
    # ======================================================

    try:
        texto_log = (
            leer_log_lote_ftp(
                script["ruta_log"]
            )
        )


        resultado_log = (
            interpretar_log_lote(
                lote_id,
                total_partes,
                texto_log
            )
        )


    except Exception as exc:

        conservar_indeterminado(
            "LECTURA_LOG_POST_PLAY",
            exc
        )

        return True


    # ======================================================
    # 6. RESOLUCIÓN TRANSACCIONAL
    #
    # Si /play.ps3 ya devolvió:
    #
    # FINALIZADO       -> éxito
    # ESPERANDO_FINAL  -> éxito probado por todas partes OK
    # EN_PROCESO       -> script terminó anticipadamente
    # SIN_LOG/INICIO   -> ejecución anormal
    #
    # El resolvedor ya conoce estas reglas.
    # ======================================================

    resultado_final = (
        resolver_resultado_lote(
            lote_id,
            resultado_log
        )
    )


    LOG.info(
        "Lote PKG #%s resuelto: %s",
        lote_id,
        resultado_final
    )


    return True



def ps3_lista_para_pkg(
    accion: str
):
    (
        lista,
        estado,
        motivo,
    ) = ps3_lista_para_transferir()

    if not lista:
        return (
            False,
            estado,
            motivo,
        )

    if accion == "INSTALAR_PKG":
        fila = DB.execute("""
            SELECT
                http_disponible
            FROM ps3_estado
            WHERE id=1
            LIMIT 1
        """).fetchone()

        http_ok = (
            fila is not None
            and bool(
                fila["http_disponible"]
            )
        )

        if not http_ok:
            return (
                False,
                estado,
                (
                    "Esperando PS3: "
                    "webMAN HTTP no disponible"
                ),
            )

    return (
        True,
        estado,
        (
            "PS3 lista para "
            "operación PKG"
        ),
    )


def marcar_orden_pkg_procesando(
    orden_id: int,
    mensaje: str
) -> bool:
    cursor = DB.execute("""
        UPDATE ordenes
        SET
            estado='PROCESANDO',
            procesada_utc=NULL,
            mensaje=?
        WHERE
            id=?
            AND estado='PENDIENTE'
            AND accion IN (
                'INSTALAR_PKG',
                'ELIMINAR_PKG'
            )
    """, (
        mensaje,
        orden_id,
    ))

    DB.commit()

    return cursor.rowcount == 1



def marcar_lote_pkg_procesando(
    lote_id: int
) -> bool:
    """
    Reserva atómicamente un lote y todas
    sus órdenes para procesamiento.
    """

    try:
        DB.execute(
            "BEGIN IMMEDIATE"
        )

        lote = DB.execute("""
            SELECT id, titulo, estado
            FROM lotes_pkg
            WHERE id=?
            LIMIT 1
        """, (
            lote_id,
        )).fetchone()

        if (
            lote is None
            or lote["estado"] != "PENDIENTE"
        ):
            DB.rollback()
            return False


        resumen = DB.execute("""
            SELECT
                COUNT(*) AS total,

                SUM(
                    CASE
                        WHEN
                            o.estado='PENDIENTE'
                            AND o.accion='INSTALAR_PKG'
                        THEN 1
                        ELSE 0
                    END
                ) AS validas

            FROM lote_pkg_ordenes lpo

            JOIN ordenes o
                ON o.id=lpo.orden_id

            WHERE lpo.lote_id=?
        """, (
            lote_id,
        )).fetchone()


        total = int(
            resumen["total"] or 0
        )

        validas = int(
            resumen["validas"] or 0
        )


        if total < 2:
            raise RuntimeError(
                "El lote tiene menos de dos partes"
            )

        if validas != total:
            raise RuntimeError(
                "El lote contiene órdenes "
                "no válidas o no pendientes"
            )


        cursor = DB.execute("""
            UPDATE lotes_pkg
            SET
                estado='PROCESANDO',
                procesada_utc=NULL,
                mensaje=?
            WHERE
                id=?
                AND estado='PENDIENTE'
        """, (
            (
                "Instalación multipart iniciada "
                f"({total} partes)"
            ),
            lote_id,
        ))

        if cursor.rowcount != 1:
            raise RuntimeError(
                "No se pudo reservar el lote"
            )


        cursor = DB.execute("""
            UPDATE ordenes
            SET
                estado='PROCESANDO',
                procesada_utc=NULL,
                mensaje=?
            WHERE
                id IN (
                    SELECT orden_id
                    FROM lote_pkg_ordenes
                    WHERE lote_id=?
                )
                AND estado='PENDIENTE'
                AND accion='INSTALAR_PKG'
        """, (
            (
                "Parte reservada por "
                f"lote PKG #{lote_id}"
            ),
            lote_id,
        ))

        if cursor.rowcount != total:
            raise RuntimeError(
                "No se reservaron todas "
                "las órdenes del lote"
            )


        DB.execute("""
            INSERT INTO eventos (
                transferencia_id,
                nivel,
                tipo,
                mensaje,
                datos_json
            )
            VALUES (
                NULL,
                'INFO',
                'PKG_LOTE_PROCESANDO',
                ?,
                ?
            )
        """, (
            (
                f"Lote PKG #{lote_id} "
                "reservado para procesamiento"
            ),
            json.dumps(
                {
                    "lote_id": lote_id,
                    "total_partes": total,
                },
                ensure_ascii=False
            ),
        ))


        DB.commit()
        return True


    except Exception:
        DB.rollback()
        raise




def conciliar_lotes_pkg_procesando():
    """
    Revisa silenciosamente los lotes que siguen
    PROCESANDO.

    Sólo modifica SQLite cuando el log demuestra
    que todas las partes terminaron.

    Un log parcial, inexistente, inconsistente o
    una PS3 inaccesible conservan PROCESANDO.
    """

    lotes = DB.execute("""
        SELECT
            lp.id,

            COUNT(
                lpo.orden_id
            ) AS total_partes

        FROM lotes_pkg lp

        LEFT JOIN lote_pkg_ordenes lpo
            ON lpo.lote_id=lp.id

        WHERE lp.estado='PROCESANDO'

        GROUP BY lp.id

        ORDER BY lp.id ASC
    """).fetchall()


    resultado = {
        "detectados":
            len(lotes),

        "resueltos":
            0,

        "pendientes":
            0,
    }


    for lote in lotes:

        lote_id = int(
            lote["id"]
        )

        total_partes = int(
            lote["total_partes"]
            or 0
        )


        if total_partes < 2:
            resultado[
                "pendientes"
            ] += 1

            continue


        ruta_log = (
            "/dev_hdd0/tmp/"
            f"ctps3-lote-{lote_id}.log"
        )


        try:
            texto_log = (
                leer_log_lote_ftp(
                    ruta_log
                )
            )

            estado_log = (
                interpretar_log_lote(
                    lote_id,
                    total_partes,
                    texto_log
                )
            )


        except Exception:
            resultado[
                "pendientes"
            ] += 1

            continue


        if estado_log.get(
            "estado"
        ) not in {
            "FINALIZADO",
            "ESPERANDO_FINAL",
        }:
            resultado[
                "pendientes"
            ] += 1

            continue


        try:
            resolver_resultado_lote(
                lote_id,
                estado_log
            )

        except Exception:
            LOG.exception(
                "Lote PKG #%s: fallo "
                "durante conciliación periódica",
                lote_id
            )

            resultado[
                "pendientes"
            ] += 1

            continue


        resultado[
            "resueltos"
        ] += 1


        LOG.warning(
            "Lote PKG #%s conciliado "
            "automáticamente como finalizado",
            lote_id
        )


    return resultado



def recuperar_lotes_pkg_interrumpidos() -> int:
    """
    Reconcilia lotes que quedaron PROCESANDO
    durante un reinicio del worker.

    Regla de seguridad:

    - Si el log demuestra finalización:
      resolver normalmente.

    - Si el resultado sigue siendo parcial,
      la PS3 no responde o el log es dudoso:
      conservar PROCESANDO.

    Nunca se reintenta automáticamente.
    Nunca se marca ERROR sólo por reiniciar.
    """

    lotes = DB.execute("""
        SELECT
            lp.id,
            lp.titulo,

            COUNT(
                lpo.orden_id
            ) AS total_partes

        FROM lotes_pkg lp

        LEFT JOIN lote_pkg_ordenes lpo
            ON lpo.lote_id=lp.id

        WHERE lp.estado='PROCESANDO'

        GROUP BY
            lp.id,
            lp.titulo

        ORDER BY lp.id ASC
    """).fetchall()


    if not lotes:
        return 0


    for lote in lotes:

        lote_id = int(
            lote["id"]
        )

        total_partes = int(
            lote["total_partes"]
            or 0
        )

        ruta_log = (
            "/dev_hdd0/tmp/"
            f"ctps3-lote-{lote_id}.log"
        )


        # Una estructura inválida no se
        # resuelve automáticamente.
        if total_partes < 2:

            mensaje = (
                "Recuperación bloqueada: "
                "estructura multipart inválida"
            )

            DB.execute("""
                UPDATE lotes_pkg
                SET mensaje=?
                WHERE
                    id=?
                    AND estado='PROCESANDO'
            """, (
                mensaje,
                lote_id,
            ))

            DB.execute("""
                INSERT INTO eventos (
                    transferencia_id,
                    nivel,
                    tipo,
                    mensaje,
                    datos_json
                )
                VALUES (
                    NULL,
                    'ERROR',
                    'PKG_LOTE_RECUPERACION_BLOQUEADA',
                    ?,
                    ?
                )
            """, (
                (
                    f"Lote PKG #{lote_id}: "
                    f"{mensaje}"
                ),
                json.dumps(
                    {
                        "lote_id":
                            lote_id,

                        "total_partes":
                            total_partes,
                    },
                    ensure_ascii=False
                ),
            ))

            DB.commit()
            continue


        try:
            texto_log = (
                leer_log_lote_ftp(
                    ruta_log
                )
            )

            resultado = (
                interpretar_log_lote(
                    lote_id,
                    total_partes,
                    texto_log
                )
            )


        except Exception as exc:

            detalle = str(
                exc
            )[:700]

            mensaje = (
                "Recuperación pendiente: "
                "no se pudo conciliar el "
                f"log remoto ({detalle})"
            )

            DB.execute("""
                UPDATE lotes_pkg
                SET mensaje=?
                WHERE
                    id=?
                    AND estado='PROCESANDO'
            """, (
                mensaje,
                lote_id,
            ))

            DB.execute("""
                INSERT INTO eventos (
                    transferencia_id,
                    nivel,
                    tipo,
                    mensaje,
                    datos_json
                )
                VALUES (
                    NULL,
                    'AVISO',
                    'PKG_LOTE_RECUPERACION_PENDIENTE',
                    ?,
                    ?
                )
            """, (
                (
                    f"Lote PKG #{lote_id}: "
                    "recuperación pendiente"
                ),
                json.dumps(
                    {
                        "lote_id":
                            lote_id,

                        "motivo":
                            detalle,

                        "estado_conservado":
                            "PROCESANDO",
                    },
                    ensure_ascii=False
                ),
            ))

            DB.commit()
            continue


        estado_log = str(
            resultado.get(
                "estado",
                ""
            )
        )


        # Las partes completas constituyen
        # evidencia suficiente.
        if estado_log in {
            "FINALIZADO",
            "ESPERANDO_FINAL",
        }:

            resolver_resultado_lote(
                lote_id,
                resultado
            )

            LOG.warning(
                "Lote PKG #%s reconciliado "
                "como finalizado tras reinicio",
                lote_id
            )

            continue


        # SIN_LOG, SIN_INICIO o EN_PROCESO
        # no permiten afirmar ni éxito ni fallo.
        mensaje = (
            "Recuperación pendiente: "
            f"log={estado_log}, "
            f"fase={resultado.get('fase')}, "
            f"última parte OK="
            f"{resultado.get('ultima_parte_ok', 0)}. "
            "El lote permanece bloqueado "
            "hasta obtener evidencia concluyente."
        )


        DB.execute("""
            UPDATE lotes_pkg
            SET mensaje=?
            WHERE
                id=?
                AND estado='PROCESANDO'
        """, (
            mensaje,
            lote_id,
        ))


        DB.execute("""
            INSERT INTO eventos (
                transferencia_id,
                nivel,
                tipo,
                mensaje,
                datos_json
            )
            VALUES (
                NULL,
                'AVISO',
                'PKG_LOTE_RECUPERACION_PENDIENTE',
                ?,
                ?
            )
        """, (
            (
                f"Lote PKG #{lote_id} "
                "permanece en recuperación"
            ),
            json.dumps(
                {
                    "lote_id":
                        lote_id,

                    "estado_log":
                        estado_log,

                    "fase":
                        resultado.get(
                            "fase"
                        ),

                    "partes_ok":
                        resultado.get(
                            "partes_ok",
                            []
                        ),

                    "estado_conservado":
                        "PROCESANDO",

                    "reintento_automatico":
                        False,
                },
                ensure_ascii=False
            ),
        ))


        DB.commit()


    return len(lotes)


def recuperar_ordenes_pkg_interrumpidas() -> int:
    filas = DB.execute("""
        SELECT
            id,
            archivo_remoto_id,
            accion
        FROM ordenes
        WHERE
            estado='PROCESANDO'
            AND accion IN (
                'INSTALAR_PKG',
                'ELIMINAR_PKG'
            )

            AND NOT EXISTS (
                SELECT 1
                FROM lote_pkg_ordenes lpo
                WHERE lpo.orden_id=ordenes.id
            )

        ORDER BY id ASC
    """).fetchall()

    if not filas:
        return 0

    ahora = utc()

    for fila in filas:
        oid = int(
            fila["id"]
        )

        DB.execute("""
            UPDATE ordenes
            SET
                estado='ERROR',
                procesada_utc=?,
                mensaje=?
            WHERE id=?
        """, (
            ahora,
            (
                "Worker reiniciado durante "
                "operación PKG; resultado "
                "indeterminado. "
                "No se reintenta "
                "automáticamente."
            ),
            oid,
        ))

        DB.execute("""
            INSERT INTO eventos (
                transferencia_id,
                nivel,
                tipo,
                mensaje,
                datos_json
            )
            VALUES (
                NULL,
                'AVISO',
                'PKG_OPERACION_INTERRUMPIDA',
                ?,
                ?
            )
        """, (
            (
                "Operación PKG #"
                f"{oid} interrumpida"
            ),
            json.dumps(
                {
                    "orden_id": oid,
                    "archivo_remoto_id":
                        fila[
                            "archivo_remoto_id"
                        ],
                    "accion":
                        fila["accion"],
                },
                ensure_ascii=False
            ),
        ))

    DB.commit()

    return len(filas)


def instalar_pkg_webman(
    ruta_remota: str
):
    ruta_url = quote(
        ruta_remota,
        safe="/"
    )

    url = (
        f"http://{HOST}:"
        f"{WEBMAN_HTTP_PORT}"
        f"/install_ps3"
        f"{ruta_url}"
    )

    solicitud = Request(
        url,
        method="GET",
        headers={
            "User-Agent":
                f"CTPS3/{VERSION}",
            "Connection":
                "close",
        },
    )

    with urlopen(
        solicitud,
        timeout=45
    ) as respuesta:

        codigo = int(
            respuesta.getcode()
        )

        cuerpo = respuesta.read(
            4096
        )

    if not (
        200 <= codigo < 300
    ):
        raise RuntimeError(
            "webMAN devolvió HTTP "
            f"{codigo}"
        )

    return (
        codigo,
        len(cuerpo),
    )


def eliminar_pkg_ftp(
    nombre: str,
    ruta_remota: str
):
    ftp = FTP(
        encoding="latin-1"
    )

    respuesta_delete = None

    try:
        ftp.connect(
            HOST,
            PORT,
            timeout=30
        )

        ftp.login(
            "anonymous",
            "anonymous"
        )

        ftp.voidcmd(
            "TYPE I"
        )

        respuesta_delete = (
            ftp.delete(
                ruta_remota
            )
        )

        # Verificación posterior:
        # listar exactamente packages y
        # comprobar que el nombre ya no exista.

        ftp.cwd(
            REMOTE_DIR
        )

        listado = ftp.nlst()

        presentes = {
            str(item)
                .rstrip("/")
                .rsplit("/", 1)[-1]
            for item in listado
        }

        if nombre in presentes:
            raise RuntimeError(
                "FTP confirmó DELE pero "
                "el PKG sigue listado"
            )

        try:
            ftp.quit()
        except Exception:
            ftp.close()

    except Exception:
        try:
            ftp.close()
        except Exception:
            pass

        raise

    return respuesta_delete


def ejecutar_orden_pkg(
    fila
) -> bool:
    oid = int(
        fila["id"]
    )

    archivo_id = int(
        fila["archivo_remoto_id"]
    )

    accion = str(
        fila["accion"]
    )

    datos_evento = {
        "orden_id":
            oid,

        "archivo_remoto_id":
            archivo_id,

        "accion":
            accion,
    }


    try:
        (
            nombre,
            ruta_remota,
        ) = validar_archivo_pkg(
            fila
        )

    except Exception as exc:
        marcar_orden(
            oid,
            "RECHAZADA",
            str(exc)
        )

        registrar_evento_pkg(
            "PKG_ORDEN_RECHAZADA",
            (
                f"Orden PKG #{oid}: "
                f"{exc}"
            ),
            nivel="AVISO",
            datos=datos_evento,
        )

        return True


    datos_evento.update({
        "nombre":
            nombre,

        "ruta_remota":
            ruta_remota,

        "tamano_bytes":
            int(
                fila["pkg_tamano"]
                or 0
            ),
    })


    (
        lista,
        _estado,
        motivo,
    ) = ps3_lista_para_pkg(
        accion
    )


    if not lista:
        actualizar_worker(
            "ESPERANDO",
            motivo,
            None
        )

        return False


    if accion == "INSTALAR_PKG":
        (
            capacidad_ok,
            _codigo_hdd,
            mensaje_hdd,
            _datos_hdd,
        ) = evaluar_capacidad_hdd_instalacion_pkg(
            [int(fila["pkg_tamano"] or 0)],
            leer_estado_hdd_transferencia(),
            multipart=False,
        )

        if not capacidad_ok:
            mensaje_actual = str(fila["mensaje"] or "")

            if mensaje_actual != mensaje_hdd:
                DB.execute("""
                    UPDATE ordenes
                    SET mensaje=?
                    WHERE id=? AND estado='PENDIENTE'
                """, (
                    mensaje_hdd,
                    oid,
                ))
                DB.commit()

            actualizar_worker(
                "ESPERANDO",
                mensaje_hdd,
                None
            )

            return False


    if not marcar_orden_pkg_procesando(
        oid,
        (
            "Procesando "
            f"{accion}: "
            f"{nombre}"
        )
    ):
        return True


    actualizar_worker(
        "OCUPADO",
        (
            f"{accion}: "
            f"{nombre}"
        ),
        None
    )


    try:
        if accion == "INSTALAR_PKG":

            (
                codigo_http,
                bytes_respuesta,
            ) = instalar_pkg_webman(
                ruta_remota
            )

            mensaje = (
                "Solicitud de instalación "
                "aceptada por webMAN "
                f"(HTTP {codigo_http}). "
                "El PKG se conserva."
            )

            # HTTP 200 significa que webMAN aceptó
            # la instalación, no que ya terminó.
            DB.execute("""
                UPDATE ordenes
                SET mensaje=?
                WHERE
                    id=?
                    AND estado='PROCESANDO'
            """, (
                mensaje,
                oid,
            ))

            DB.commit()

            datos_evento.update({
                "http_codigo":
                    codigo_http,

                "respuesta_bytes":
                    bytes_respuesta,

                "pkg_conservado":
                    True,
            })

            registrar_evento_pkg(
                "PKG_INSTALACION_SOLICITADA",
                (
                    "Instalación solicitada: "
                    f"{nombre}"
                ),
                nivel="INFO",
                datos=datos_evento,
            )


        elif accion == "ELIMINAR_PKG":

            respuesta_ftp = (
                eliminar_pkg_ftp(
                    nombre,
                    ruta_remota
                )
            )

            ahora = utc()

            DB.execute("""
                UPDATE archivos_remotos
                SET
                    disponible=0,
                    actualizado_utc=?
                WHERE
                    id=?
                    AND ruta_remota=?
            """, (
                ahora,
                archivo_id,
                ruta_remota,
            ))

            DB.commit()

            mensaje = (
                "PKG eliminado de "
                "/dev_hdd0/packages"
            )

            marcar_orden(
                oid,
                "EJECUTADA",
                mensaje
            )

            datos_evento.update({
                "respuesta_ftp":
                    respuesta_ftp,

                "disponible":
                    False,
            })

            registrar_evento_pkg(
                "PKG_ELIMINADO",
                (
                    "PKG eliminado: "
                    f"{nombre}"
                ),
                nivel="INFO",
                datos=datos_evento,
            )


        else:
            raise RuntimeError(
                "Acción PKG interna "
                "no soportada"
            )


    except Exception as exc:
        detalle = str(exc)

        marcar_orden(
            oid,
            "ERROR",
            (
                f"{accion}: "
                f"{detalle[:900]}"
            )
        )

        datos_evento.update({
            "error":
                detalle[:2000],
        })

        registrar_evento_pkg(
            "PKG_ERROR",
            (
                f"{accion} falló: "
                f"{nombre}"
            ),
            nivel="ERROR",
            datos=datos_evento,
        )


    finally:
        actualizar_worker(
            "ESPERANDO",
            "Esperando nuevas operaciones",
            None
        )


    return True


def validar_instalacion() -> None:
    if not DB_PATH.is_file():
        raise RuntimeError(
            f"No existe SQLite: {DB_PATH}"
        )

    if not LOCAL_ROOT.is_dir():
        raise RuntimeError(
            "No existe biblioteca PKG: "
            f"{LOCAL_ROOT}"
        )

    if not LOCAL_ROOT_PS3ISO.is_dir():
        raise RuntimeError(
            "No existe biblioteca PS3ISO: "
            f"{LOCAL_ROOT_PS3ISO}"
        )

    if not LOCAL_ROOT_PS2ISO.is_dir():
        raise RuntimeError(
            "No existe biblioteca PS2ISO: "
            f"{LOCAL_ROOT_PS2ISO}"
        )

    if not LFTP.is_file():
        raise RuntimeError(
            f"No existe lftp: {LFTP}"
        )

    if (
        REMOTE_DIR
        != DESTINO_REMOTO_PKG
    ):
        raise RuntimeError(
            "Destino PKG configurado fuera "
            "de la allowlist"
        )

    if (
        DESTINO_REMOTO_PKG
        != "/dev_hdd0/packages"
    ):
        raise RuntimeError(
            "Destino PKG interno inválido"
        )

    if (
        DESTINO_REMOTO_PS3ISO
        != "/dev_hdd0/PS3ISO"
    ):
        raise RuntimeError(
            "Destino PS3ISO interno inválido"
        )

    if (
        DESTINO_REMOTO_PS2ISO
        != "/dev_hdd0/PS2ISO"
    ):
        raise RuntimeError(
            "Destino PS2ISO interno inválido"
        )

    resultado = DB.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]

    if resultado != "ok":
        raise RuntimeError(
            "SQLite integrity_check != ok"
        )

    fila_schema = DB.execute("""
        SELECT valor
        FROM meta
        WHERE clave='schema_version'
    """).fetchone()

    if fila_schema is None:
        raise RuntimeError(
            "No existe meta.schema_version"
        )

    try:
        schema = int(
            fila_schema[0]
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise RuntimeError(
            "schema_version inválido"
        ) from exc

    if schema < 11:
        raise RuntimeError(
            "Worker multiformato requiere "
            "schema >= 11; actual="
            + str(schema)
        )

    columnas_transferencias = {
        fila[1]
        for fila in DB.execute(
            "PRAGMA table_info(transferencias)"
        )
    }

    requeridas_transferencias = {
        "formato_snapshot",
        "destino_remoto_snapshot",
    }

    faltan_transferencias = (
        requeridas_transferencias
        - columnas_transferencias
    )

    if faltan_transferencias:
        raise RuntimeError(
            "Faltan columnas multiformato "
            "en transferencias: "
            + ", ".join(
                sorted(
                    faltan_transferencias
                )
            )
        )

    columnas_locales = {
        fila[1]
        for fila in DB.execute(
            "PRAGMA table_info(archivos_locales)"
        )
    }

    if (
        "formato"
        not in columnas_locales
    ):
        raise RuntimeError(
            "Falta archivos_locales.formato"
        )

    tabla_iso = DB.execute("""
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE
            type='table'
            AND name='archivos_remotos_iso'
    """).fetchone()[0]

    if tabla_iso != 1:
        raise RuntimeError(
            "Falta tabla archivos_remotos_iso"
        )

    tabla_ps2iso = DB.execute("""
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE
            type='table'
            AND name='archivos_remotos_ps2iso'
    """).fetchone()[0]

    if tabla_ps2iso != 1:
        raise RuntimeError(
            "Falta tabla archivos_remotos_ps2iso"
        )

    print("Worker             : OK")
    print("Versión            :", VERSION)
    print("SQLite             : ok")
    print("Schema             :", schema)
    print("Biblioteca PKG     :", LOCAL_ROOT)
    print("Biblioteca PS3ISO  :", LOCAL_ROOT_PS3ISO)
    print("Biblioteca PS2ISO  :", LOCAL_ROOT_PS2ISO)
    print("PS3                :", f"{HOST}:{PORT}")
    print("Destino PKG        :", DESTINO_REMOTO_PKG)
    print(
        "Destino PS3ISO     :",
        DESTINO_REMOTO_PS3ISO
    )
    print(
        "Destino PS2ISO     :",
        DESTINO_REMOTO_PS2ISO
    )
    print(
        "Reintentos worker :",
        MAX_TRANSFER_RETRIES
    )



def main() -> int:
    if "--check" in sys.argv:
        validar_instalacion()
        return 0

    LOG.info(
        "Centro Transferencias PS3 worker %s iniciado",
        VERSION
    )

    recuperadas = (
        recuperar_transferencias_interrumpidas()
    )

    if recuperadas:
        LOG.warning(
            "Se recuperaron %s transferencias "
            "interrumpidas",
            recuperadas
        )

        evento(
            "WORKER_RECUPERACION",
            (
                f"Se recuperaron {recuperadas} "
                "transferencias interrumpidas"
            ),
            nivel="AVISO"
        )

    pkg_interrumpidas = (
        recuperar_ordenes_pkg_interrumpidas()
    )

    if pkg_interrumpidas:
        LOG.warning(
            "Se marcaron %s operaciones PKG "
            "interrumpidas como ERROR",
            pkg_interrumpidas
        )

    juegos_interrumpidos = (
        recuperar_eliminaciones_juegos_interrumpidas()
    )

    if juegos_interrumpidos:
        LOG.warning(
            "Se bloquearon %s eliminaciones de juegos "
            "interrumpidas para revisión",
            juegos_interrumpidos
        )

    lotes_interrumpidos = (
        recuperar_lotes_pkg_interrumpidos()
    )

    if lotes_interrumpidos:
        LOG.warning(
            "Se detectaron %s lotes PKG "
            "en recuperación",
            lotes_interrumpidos
        )

    actualizar_worker(
        "INICIANDO",
        "Inicializando worker"
    )

    ultimo_heartbeat = 0.0
    ultimo_lote_conciliado = time.monotonic()
    intervalo_conciliacion_lotes = 15.0

    try:
        while not DETENER:

            procesar_ordenes_inactivas()

            ahora_lotes = time.monotonic()

            if (
                ahora_lotes
                - ultimo_lote_conciliado
                >= intervalo_conciliacion_lotes
            ):
                ultimo_lote_conciliado = (
                    ahora_lotes
                )

                conciliacion = (
                    conciliar_lotes_pkg_procesando()
                )

                if conciliacion["resueltos"]:
                    LOG.info(
                        "Conciliación multipart: "
                        "%s lote(s) resuelto(s)",
                        conciliacion["resueltos"]
                    )

            instalacion = DB.execute("""
                SELECT
                    o.id,
                    ar.nombre
                FROM ordenes o
                JOIN archivos_remotos ar
                    ON ar.id=o.archivo_remoto_id
                WHERE
                    o.accion='INSTALAR_PKG'
                    AND o.estado='PROCESANDO'
                ORDER BY o.id ASC
                LIMIT 1
            """).fetchone()

            if instalacion is not None:
                actualizar_worker(
                    "OCUPADO",
                    (
                        "Instalación PKG en PS3: "
                        + str(instalacion["nombre"])
                    ),
                    None
                )

                time.sleep(QUEUE_INTERVAL)
                continue

            externos = procesos_lftp_externos()

            if externos:
                mensaje = (
                    "Esperando lftp externo: "
                    + ", ".join(
                        str(pid)
                        for pid in externos
                    )
                )

                actualizar_worker(
                    "ESPERANDO",
                    mensaje
                )

                time.sleep(
                    QUEUE_INTERVAL
                )

                continue

            lote_pkg = (
                siguiente_lote_pkg()
            )

            if lote_pkg is not None:
                consumido_lote = (
                    ejecutar_lote_pkg(
                        lote_pkg
                    )
                )

                if consumido_lote:
                    continue

            eliminacion_juego = (
                siguiente_eliminacion_juego()
            )

            if eliminacion_juego is not None:
                consumida_eliminacion = (
                    ejecutar_eliminacion_juego(
                        eliminacion_juego
                    )
                )

                if consumida_eliminacion:
                    continue

            orden_pkg = (
                siguiente_orden_pkg()
            )

            if orden_pkg is not None:
                consumida = (
                    ejecutar_orden_pkg(
                        orden_pkg
                    )
                )

                if consumida:
                    continue

            transferencia = (
                siguiente_transferencia()
            )

            if transferencia is not None:
                ejecutar_transferencia(
                    transferencia
                )

                continue

            ahora = time.monotonic()

            if (
                ahora - ultimo_heartbeat
                >= HEARTBEAT_INTERVAL
            ):
                ultimo_heartbeat = ahora

                (
                    estado_espera,
                    mensaje_espera,
                ) = estado_espera_worker()

                actualizar_worker(
                    estado_espera,
                    mensaje_espera
                )

            time.sleep(
                QUEUE_INTERVAL
            )

    finally:
        actualizar_worker(
            "DETENIDO",
            "Worker detenido",
            None
        )

        LOG.info(
            "Worker detenido correctamente"
        )

        DB.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
