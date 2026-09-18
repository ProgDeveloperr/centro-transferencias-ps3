from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "1.0.0"

ROOT = "/dev_hdd0/game"

CLASES = (
    "JUEGO_INSTALADO",
    "VINCULADO",
    "STORE_APLICACION",
    "HOMEBREW_UTILIDAD",
    "SOPORTE_PS2",
    "SISTEMA_PROTEGIDO",
    "POSIBLE_HUERFANO",
    "DESCONOCIDO",
)

GAME_ID_RE = re.compile(
    r"^[A-Z]{4}[0-9]{5}$"
)

SAFE_ID_RE = re.compile(
    r"^[A-Z0-9_-]{1,64}$"
)


class PoliticaInvalida(RuntimeError):
    pass


class EntradaInvalida(RuntimeError):
    pass


def _texto(valor):
    if valor is None:
        return ""

    return str(valor).strip()


def _texto_upper(valor):
    return _texto(valor).upper()


def _validar_ruta(ruta):
    ruta = _texto(ruta)

    prefijo = ROOT + "/"

    if not ruta.startswith(prefijo):
        raise EntradaInvalida(
            "Ruta fuera de /dev_hdd0/game"
        )

    relativo = ruta[len(prefijo):]

    if (
        not relativo
        or "/" in relativo
        or "\\" in relativo
        or ".." in relativo
        or "\x00" in relativo
        or "\n" in relativo
        or "\r" in relativo
    ):
        raise EntradaInvalida(
            "Ruta no segura o no inmediata"
        )

    return ruta


def _validar_tamano(valor):
    try:
        numero = int(valor)

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise EntradaInvalida(
            "tamano_bytes inválido"
        ) from exc

    if numero < 0:
        raise EntradaInvalida(
            "tamano_bytes negativo"
        )

    return numero


def cargar_politica(ruta):
    ruta = Path(ruta)

    datos = json.loads(
        ruta.read_text(
            encoding="utf-8"
        )
    )

    if datos.get("version") != "1.0.0":
        raise PoliticaInvalida(
            "Versión de política no soportada"
        )

    if datos.get("root") != ROOT:
        raise PoliticaInvalida(
            "Root de política inesperado"
        )

    registros = datos.get(
        "registros_exactos"
    )

    if not isinstance(
        registros,
        dict,
    ):
        raise PoliticaInvalida(
            "registros_exactos ausente"
        )

    esperadas = {
        "SISTEMA_PROTEGIDO",
        "SOPORTE_PS2",
        "HOMEBREW_UTILIDAD",
        "STORE_APLICACION",
    }

    if set(registros) != esperadas:
        raise PoliticaInvalida(
            "Clases exactas inesperadas"
        )

    vistos = {}

    for clase, ids in registros.items():
        if not isinstance(
            ids,
            list,
        ):
            raise PoliticaInvalida(
                f"Lista inválida para {clase}"
            )

        for valor in ids:
            title_id = _texto_upper(
                valor
            )

            if not SAFE_ID_RE.fullmatch(
                title_id
            ):
                raise PoliticaInvalida(
                    f"TITLE_ID inválido: {valor}"
                )

            anterior = vistos.get(
                title_id
            )

            if anterior is not None:
                raise PoliticaInvalida(
                    f"TITLE_ID duplicado entre "
                    f"{anterior} y {clase}: "
                    f"{title_id}"
                )

            vistos[
                title_id
            ] = clase

    datos[
        "_indice_exactos"
    ] = vistos

    return datos


def _base(
    *,
    ruta,
    title_id,
    title,
    category,
    tamano_bytes,
):
    return {
        "ruta":
            _validar_ruta(
                ruta
            ),

        "title_id":
            _texto_upper(
                title_id
            ),

        "title":
            _texto(
                title
            ),

        "category":
            _texto_upper(
                category
            ),

        "tamano_bytes":
            _validar_tamano(
                tamano_bytes
            ),

        "clase":
            None,

        "subtipo":
            None,

        "confianza":
            None,

        "evidencia":
            [],

        "politica":
            None,

        "posible_huerfano":
            False,

        "eliminacion_automatica_permitida":
            False,
    }


def clasificar(
    registro,
    politica,
):
    if not isinstance(
        registro,
        dict,
    ):
        raise EntradaInvalida(
            "Registro no es dict"
        )

    item = _base(
        ruta=registro.get(
            "ruta"
        ),
        title_id=registro.get(
            "title_id"
        ),
        title=registro.get(
            "title"
        ),
        category=registro.get(
            "category"
        ),
        tamano_bytes=registro.get(
            "tamano_bytes"
        ),
    )

    tipo_j3 = _texto_upper(
        registro.get(
            "tipo_j3"
        )
    )

    correlacion_j3 = (
        registro.get(
            "correlacion_j3"
        )
        is True
    )

    origen = _texto_upper(
        registro.get(
            "origen"
        )
    )

    if (
        correlacion_j3
        and tipo_j3 in {
            "DATOS_GAME",
            "CACHE_GAME",
        }
    ):
        item["clase"] = (
            "VINCULADO"
        )
        item["subtipo"] = (
            tipo_j3
        )
        item["confianza"] = (
            "ALTA"
        )
        item["politica"] = (
            "NO_LIMPIEZA_AUTOMATICA;"
            "GESTIONAR_COMO_DATO_ASOCIADO"
        )
        item["evidencia"].extend([
            "COMPONENTE_J3_DISPONIBLE",
            "TITLE_ID_CORRELACIONADO_J3",
            tipo_j3 + "_J3",
        ])

        return item

    if (
        correlacion_j3
        and tipo_j3 == "HDD_JUEGO"
    ):
        item["clase"] = (
            "JUEGO_INSTALADO"
        )
        item["subtipo"] = (
            "HDD_JUEGO"
        )
        item["confianza"] = (
            "ALTA"
        )
        item["politica"] = (
            "NO_LIMPIEZA_AUTOMATICA;"
            "GESTIONAR_DESDE_JUEGOS"
        )
        item["evidencia"].extend([
            "COMPONENTE_J3_DISPONIBLE",
            "TITLE_ID_CORRELACIONADO_J3",
            "HDD_JUEGO_J3",
        ])

        return item

    exacta = politica[
        "_indice_exactos"
    ].get(
        item["title_id"]
    )

    if exacta is not None:
        item["clase"] = exacta
        item["confianza"] = "ALTA"
        item["evidencia"].append(
            "TITLE_ID_EXACTO_"
            + exacta
        )

        if exacta == "SISTEMA_PROTEGIDO":
            item["subtipo"] = "PS3HEN"
            item["politica"] = (
                "BLOQUEO_PERMANENTE_ESP;"
                "NO_PROPONER_COMO_LIMPIEZA"
            )

        elif exacta == "SOPORTE_PS2":
            item["subtipo"] = "PS2_CLASSICS"
            item["politica"] = (
                "BLOQUEADO_POR_DEFECTO;"
                "NO_CONSIDERAR_HUERFANO"
            )

        elif exacta == "HOMEBREW_UTILIDAD":
            item["subtipo"] = (
                "APLICACION_UTILIDAD"
            )
            item["politica"] = (
                "NO_LIMPIEZA_AUTOMATICA;"
                "GESTION_EXPLICITA_DE_APLICACION"
            )

        elif exacta == "STORE_APLICACION":
            item["subtipo"] = "STORE"
            item["politica"] = (
                "NO_LIMPIEZA_AUTOMATICA;"
                "GESTION_EXPLICITA_DE_APLICACION"
            )

        return item

    if (
        item["category"] == "GD"
        and GAME_ID_RE.fullmatch(
            item["title_id"]
        )
    ):
        item["clase"] = (
            "POSIBLE_HUERFANO"
        )
        item["subtipo"] = (
            "GAME_DATA_NO_CORRELACIONADO"
        )
        item["confianza"] = (
            "MEDIA"
        )
        item["politica"] = (
            "BLOQUEADO;"
            "REQUIERE_CORRELACION_ADICIONAL_Y_CONFIRMACION"
        )
        item["posible_huerfano"] = True
        item["evidencia"].extend([
            "PARAM_SFO_LEGIBLE"
            if origen == "ESP"
            else "METADATOS_DISPONIBLES",
            "GD_CON_TITLE_ID_DE_JUEGO_NO_CORRELACIONADO",
        ])

        return item

    item["clase"] = (
        "DESCONOCIDO"
    )
    item["subtipo"] = (
        "NO_CLASIFICADO"
    )
    item["confianza"] = (
        "BAJA"
    )
    item["politica"] = (
        "BLOQUEADO;"
        "REVISION_MANUAL"
    )
    item["evidencia"].append(
        "SIN_REGLA_SEGURA"
    )

    return item


def clasificar_lote(
    registros,
    politica,
):
    if not isinstance(
        registros,
        list,
    ):
        raise EntradaInvalida(
            "registros debe ser lista"
        )

    resultados = []
    rutas = set()

    for registro in registros:
        item = clasificar(
            registro,
            politica,
        )

        ruta = item["ruta"]

        if ruta in rutas:
            raise EntradaInvalida(
                "Ruta duplicada: "
                + ruta
            )

        rutas.add(
            ruta
        )

        resultados.append(
            item
        )

    conteo = Counter(
        item["clase"]
        for item in resultados
    )

    bytes_por_clase = defaultdict(int)

    for item in resultados:
        bytes_por_clase[
            item["clase"]
        ] += item[
            "tamano_bytes"
        ]

    auto = [
        item
        for item in resultados
        if item[
            "eliminacion_automatica_permitida"
        ]
    ]

    if auto:
        raise RuntimeError(
            "Contrato violado: apareció borrado automático"
        )

    return {
        "version":
            VERSION,

        "rutas":
            len(resultados),

        "bytes_total":
            sum(
                item[
                    "tamano_bytes"
                ]
                for item in resultados
            ),

        "conteo_por_clase":
            dict(
                conteo
            ),

        "bytes_por_clase":
            dict(
                bytes_por_clase
            ),

        "posibles_huerfanos":
            sum(
                1
                for item in resultados
                if item[
                    "posible_huerfano"
                ]
            ),

        "desconocidos":
            conteo.get(
                "DESCONOCIDO",
                0,
            ),

        "eliminacion_automatica_permitida":
            0,

        "elementos":
            resultados,
    }
