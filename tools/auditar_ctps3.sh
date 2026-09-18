#!/usr/bin/env bash
set -uo pipefail

VERSION="1.3.0"

ADMIN="/opt/ctps3/admin"
PROY="/opt/ctps3/app"
DB="/var/lib/ctps3/transferencias.sqlite3"

RELEASE_DIR="/opt/ctps3/admin/releases/CTPS3-1.0-RC3-20260825-162522"
BACKUP_ARCHIVE="$ADMIN/backups/consolidacion/CTPS3-1.0-RC1-20260815-153957.tar.gz"
BACKUP_ARCHIVE_SUM="$BACKUP_ARCHIVE.sha256"
BACKUP_JSON="/opt/ctps3/admin/backups/consolidacion/CTPS3-1.0-RC1-20260815-153957/BACKUP.json"
OPS_ESTADO_JSON="${CTPS3_OPS_ESTADO_JSON:-/var/lib/ctps3/ops-estado.json}"
OPS_HISTORIAL_JSON="${CTPS3_OPS_HISTORIAL_JSON:-/var/lib/ctps3/ops-historial.json}"
HIST_AUD_DIR="${CTPS3_HIST_AUD_DIR:-$ADMIN/auditorias}"

AUD_DIR="${CTPS3_AUD_DIR:-$ADMIN/auditorias}"
MARCA="$(date '+%Y%m%d-%H%M%S')"
REPORT="$AUD_DIR/ctps3-auditoria-$MARCA.txt"
LATEST="$AUD_DIR/ultima.txt"

EXPECTED_RELEASE="$(basename "$RELEASE_DIR" | sed -E 's/-[0-9]{8}-[0-9]{6}$//')"

mkdir -p "$AUD_DIR"

PASS=0
WARN=0
FAIL=0

pass() {
    PASS=$((PASS + 1))
    printf '[PASS] %s\n' "$*"
}

warn() {
    WARN=$((WARN + 1))
    printf '[WARN] %s\n' "$*"
}

fail() {
    FAIL=$((FAIL + 1))
    printf '[FAIL] %s\n' "$*"
}

seccion() {
    printf '\n=== %s ===\n' "$*"
}

hash_archivo() {
    sha256sum "$1" 2>/dev/null | awk '{print $1}'
}

auditar_archivo() {
    local archivo="$1"
    local esperado="$2"
    local etiqueta="$3"
    local actual

    if [ ! -f "$archivo" ]; then
        fail "$etiqueta: falta $archivo"
        return
    fi

    actual="$(hash_archivo "$archivo")"

    if [ "$actual" = "$esperado" ]; then
        pass "$etiqueta: SHA256 coincide"
    else
        fail "$etiqueta: drift SHA256"
        printf '       esperado=%s\n' "$esperado"
        printf '       actual=%s\n' "$actual"
        printf '       archivo=%s\n' "$archivo"
    fi
}

main() {
    echo "============================================================"
    echo " CTPS3 — AUDITOR GENERAL READ-ONLY"
    echo " version=$VERSION"
    echo " fecha=$(date --iso-8601=seconds)"
    echo " hostname=$(hostname)"
    echo " referencia=$EXPECTED_RELEASE"
    echo "============================================================"

    seccion "1. RELEASE CONSOLIDADA"

    if [ -d "$RELEASE_DIR" ]; then
        pass "release dir presente"
    else
        fail "release dir ausente: $RELEASE_DIR"
    fi

    if [ -f "$RELEASE_DIR/SHA256SUMS" ]; then
        if (
            cd "$RELEASE_DIR"
            sha256sum -c SHA256SUMS >/dev/null 2>&1
        ); then
            pass "release SHA256SUMS completa"
        else
            fail "release SHA256SUMS no verifica"
        fi
    else
        fail "release sin SHA256SUMS"
    fi

    if [ -f "$RELEASE_DIR/RELEASE.json" ]; then
        if python3 - "$RELEASE_DIR/RELEASE.json" "$EXPECTED_RELEASE" <<'PY'
import json
import sys

with open(
    sys.argv[1],
    "r",
    encoding="utf-8",
) as fh:
    d = json.load(fh)

assert d["release"] == sys.argv[2]
assert str(d["sqlite"]["schema_version"]) == "13"
assert d["sqlite"]["integrity_check"] == "ok"
assert int(d["sqlite"]["foreign_key_check"]) == 0

print("release_json_semantica=OK")
PY
        then
            pass "RELEASE.json semánticamente válido"
        else
            fail "RELEASE.json inválido"
        fi
    else
        fail "falta RELEASE.json"
    fi

    seccion "2. DRIFT DE ARCHIVOS CONTRA RELEASE"

    if [ -f "$RELEASE_DIR/archivos.json" ]; then
        while IFS=$'\t' read -r ruta esperado; do
            [ -n "$ruta" ] || continue
            auditar_archivo \
                "$ruta" \
                "$esperado" \
                "release $(basename "$ruta")"
        done < <(
            python3 - "$RELEASE_DIR/archivos.json" <<'PY'
import json
import sys

with open(
    sys.argv[1],
    "r",
    encoding="utf-8",
) as fh:
    items = json.load(fh)

for item in items:
    if (
        item.get("existe") is True
        and item.get("sha256")
    ):
        print(
            item["ruta"],
            item["sha256"],
            sep="\t",
        )
PY
        )
    else
        fail "falta archivos.json de release"
    fi

    seccion "3. SQLITE"

    if [ ! -f "$DB" ]; then
        fail "no existe DB: $DB"
    else
        SQLITE_OUT="$(
            python3 - "$DB" 2>&1 <<'PY'
import json
import sqlite3
import sys

con = sqlite3.connect(
    f"file:{sys.argv[1]}?mode=ro",
    uri=True,
)

integrity = con.execute(
    "PRAGMA integrity_check"
).fetchone()[0]

fk = len(
    con.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()
)

schema_row = con.execute(
    """
    SELECT valor
    FROM meta
    WHERE clave='schema_version'
    """
).fetchone()

schema = (
    None
    if schema_row is None
    else str(schema_row[0])
)

datos = {
    "integrity": integrity,
    "fk": fk,
    "schema": schema,
    "eliminaciones_total": con.execute(
        "SELECT COUNT(*) FROM eliminaciones_juegos"
    ).fetchone()[0],
    "eliminaciones_activas": con.execute(
        """
        SELECT COUNT(*)
        FROM eliminaciones_juegos
        WHERE estado IN ('PENDIENTE','PROCESANDO')
        """
    ).fetchone()[0],
    "componentes_eliminacion": con.execute(
        "SELECT COUNT(*) FROM eliminaciones_juegos_componentes"
    ).fetchone()[0],
}

print(
    json.dumps(
        datos,
        sort_keys=True,
        separators=(",", ":"),
    )
)

con.close()
PY
        )"

        if [ $? -ne 0 ]; then
            fail "no se pudo leer SQLite"
            printf '%s\n' "$SQLITE_OUT"
        else
            printf 'sqlite=%s\n' "$SQLITE_OUT"

            if python3 - "$SQLITE_OUT" <<'PY'
import json
import sys

d = json.loads(sys.argv[1])

raise SystemExit(
    0
    if (
        d["integrity"] == "ok"
        and d["fk"] == 0
        and d["schema"] == "13"
    )
    else 1
)
PY
            then
                pass "SQLite integrity ok / FK 0 / schema 13"
            else
                fail "SQLite no cumple integridad/FK/schema"
            fi

            ACTIVAS="$(
                python3 - "$SQLITE_OUT" <<'PY'
import json
import sys
print(
    json.loads(
        sys.argv[1]
    )["eliminaciones_activas"]
)
PY
            )"

            if [ "$ACTIVAS" -eq 0 ]; then
                pass "sin eliminaciones activas"
            else
                warn "hay $ACTIVAS eliminaciones activas"
            fi
        fi
    fi

    seccion "4. SYSTEMD"

    if systemctl is-enabled \
        ctps3-inventory.timer \
        >/dev/null 2>&1
    then
        pass "ctps3-inventory.timer enabled"
    else
        fail "ctps3-inventory.timer no está enabled"
    fi

    if systemctl is-active \
        ctps3-inventory.timer \
        >/dev/null 2>&1
    then
        pass "ctps3-inventory.timer active"
    else
        fail "ctps3-inventory.timer no está active"
    fi

    if systemctl is-enabled ctps3-catalog.timer >/dev/null 2>&1; then
        pass "ctps3-catalog.timer enabled"
    else
        fail "ctps3-catalog.timer no está enabled"
    fi

    if systemctl is-active ctps3-catalog.timer >/dev/null 2>&1; then
        pass "ctps3-catalog.timer active"
    else
        fail "ctps3-catalog.timer no está active"
    fi

    CATALOGO_RESULT="$(systemctl show ctps3-catalog.service -p Result --value 2>/dev/null || true)"

    if [ "$CATALOGO_RESULT" = "success" ]; then
        pass "ctps3-catalog.service Result=success"
    else
        fail "ctps3-catalog.service Result=$CATALOGO_RESULT"
    fi

    CATALOGO_STATUS="$(systemctl show ctps3-catalog.service -p ExecMainStatus --value 2>/dev/null || true)"

    if [ "$CATALOGO_STATUS" = "0" ]; then
        pass "ctps3-catalog.service ExecMainStatus=0"
    else
        fail "ctps3-catalog.service ExecMainStatus=$CATALOGO_STATUS"
    fi

    CATALOGO_HASH="$(hash_archivo /opt/ctps3/admin/herramientas/catalogar-pkg.py)"

    if [ "$CATALOGO_HASH" = "bc9718ce2c9d3da0a146b47b71767bf4880a90266de64dda92c1b6ea3017591b" ]; then
        pass "catalogar-pkg.py HF1 hash correcto"
    else
        fail "catalogar-pkg.py no coincide con HF1"
    fi

    if journalctl -u ctps3-catalog.service --since "3 minutes ago" --no-pager -o cat 2>/dev/null | grep -Fq "Catalogador multiformato 1.1.0"; then
        pass "ctps3-catalog.service ejecución reciente"
    else
        fail "ctps3-catalog.service sin ejecución reciente"
    fi

    TIMER_SHOW="$(
        systemctl show \
            ctps3-inventory.timer \
            -p ActiveState \
            -p UnitFileState \
            -p LastTriggerUSec \
            -p NextElapseUSecRealtime \
            2>/dev/null \
        || true
    )"

    printf '%s\n' "$TIMER_SHOW"

    echo
    echo "Unidades relacionadas detectadas:"

    systemctl list-unit-files \
        --type=service \
        --type=timer \
        --no-pager \
        --no-legend \
        2>/dev/null \
    | grep -Ei 'ps3|transfer|ctps3' \
    || true

    seccion "5. DOCKER / FRONTEND"

    if systemctl is-active docker >/dev/null 2>&1; then
        pass "docker.service active"
    else
        fail "docker.service no está active"
    fi

    if docker inspect \
        --format '{{.State.Running}}' \
        apache-php \
        2>/dev/null \
        | grep -qx true
    then
        pass "contenedor apache-php running"
    else
        fail "contenedor apache-php no está running"
    fi

    BASE_URL=""

    for candidata in \
        "http://127.0.0.1:8083/centro-transferencias-ps3" \
        "http://127.0.0.1:8080"
    do
        if curl \
            --silent \
            --show-error \
            --fail \
            --max-time 5 \
            "$candidata/?vista=resumen&auditor=$MARCA" \
            >/dev/null 2>&1
        then
            BASE_URL="$candidata"
            break
        fi
    done

    if [ -z "$BASE_URL" ]; then
        fail "frontend HTTP no accesible"
    else
        pass "frontend HTTP accesible: $BASE_URL"

        for vista in \
            resumen \
            biblioteca \
            transferencias \
            historial \
            sistema \
            juegos \
            almacenamiento
        do
            codigo="$(
                curl \
                    --silent \
                    --show-error \
                    --max-time 8 \
                    --output /dev/null \
                    --write-out '%{http_code}' \
                    "$BASE_URL/?vista=$vista&auditor=$MARCA" \
                2>/dev/null \
                || printf '000'
            )"

            if [ "$codigo" = "200" ]; then
                pass "vista $vista HTTP 200"
            else
                fail "vista $vista HTTP $codigo"
            fi
        done

        TMPDIR_AUD="$(
            mktemp -d /tmp/ctps3-auditor.XXXXXX
        )"

        HTTP_JS="$TMPDIR_AUD/preview.js"
        HTTP_CSS="$TMPDIR_AUD/preview.css"
        HTTP_MAIN_JS="$TMPDIR_AUD/almacenamiento.js"

        curl \
            --silent \
            --show-error \
            --fail \
            --max-time 8 \
            "$BASE_URL/recursos/js/almacenamiento-gestion-preview.js?auditor=$MARCA" \
            > "$HTTP_JS" \
        2>/dev/null \
        || true

        curl \
            --silent \
            --show-error \
            --fail \
            --max-time 8 \
            "$BASE_URL/recursos/css/almacenamiento-gestion-preview.css?auditor=$MARCA" \
            > "$HTTP_CSS" \
        2>/dev/null \
        || true

        curl \
            --silent \
            --show-error \
            --fail \
            --max-time 8 \
            "$BASE_URL/recursos/js/almacenamiento.js?auditor=$MARCA" \
            > "$HTTP_MAIN_JS" \
        2>/dev/null \
        || true

        auditar_archivo \
            "$HTTP_JS" \
            "dbaf359fc76f6f8e178d15568067b1818fc276168d29e78e87ddcaea3a57822e" \
            "asset HTTP preview JS"

        auditar_archivo \
            "$HTTP_CSS" \
            "8c263445341927d6da559aa5bc8a8de24a8570b14dfbe64b7085d6f2b2d67066" \
            "asset HTTP preview CSS"

        auditar_archivo \
            "$HTTP_MAIN_JS" \
            "52a92b2804a66021a1f5e749ba8cb9df1c88fe2f9359ef138d2883c3e6e953d1" \
            "asset HTTP almacenamiento JS"

        rm -rf -- "$TMPDIR_AUD"

        ALM_RESP="$(
            curl \
                --silent \
                --show-error \
                --max-time 8 \
                "$BASE_URL/api/almacenamiento.php?auditor=$MARCA" \
            2>/dev/null \
            || true
        )"

        if python3 - "$ALM_RESP" <<'PY'
import json
import sys

try:
    d = json.loads(sys.argv[1])
except Exception:
    raise SystemExit(1)

raise SystemExit(
    0
    if d.get("ok") is True
    else 1
)
PY
        then
            pass "api/almacenamiento.php JSON ok"
        else
            fail "api/almacenamiento.php no devuelve JSON ok"
        fi

        COD_GET_ELIM="$(
            curl \
                --silent \
                --show-error \
                --max-time 8 \
                --output /dev/null \
                --write-out '%{http_code}' \
                "$BASE_URL/api/eliminar-datos-asociados.php" \
            2>/dev/null \
            || printf '000'
        )"

        if [ "$COD_GET_ELIM" = "405" ]; then
            pass "API eliminación mantiene POST-only (GET 405)"
        else
            fail "API eliminación GET=$COD_GET_ELIM; esperado 405"
        fi
    fi

    seccion "6. BACKUP CONSOLIDADO"

    if [ -f "$BACKUP_ARCHIVE" ]; then
        pass "backup tar.gz presente"

        if [ -f "$BACKUP_ARCHIVE_SUM" ]; then
            if sha256sum \
                -c "$BACKUP_ARCHIVE_SUM" \
                >/dev/null 2>&1
            then
                pass "backup tar.gz SHA256 válido"
            else
                fail "backup tar.gz SHA256 inválido"
            fi
        else
            fail "falta archivo .sha256 del backup"
        fi

        if tar \
            --list \
            --gzip \
            --file "$BACKUP_ARCHIVE" \
            >/dev/null 2>&1
        then
            pass "backup tar.gz legible"
        else
            fail "backup tar.gz no se puede listar"
        fi
    else
        fail "backup consolidado ausente"
    fi

    seccion "7. PS3"

    echo "PS3_CHECK=OMITIDO_POR_DISENO"
    echo "El auditor consolidado no requiere PS3 encendida."
    echo "No usa FTP, webMAN ni endpoints remotos de la consola."
    pass "auditor independiente del estado físico de PS3"

    seccion "8. RESUMEN"

    echo "PASS=$PASS"
    echo "WARN=$WARN"
    echo "FAIL=$FAIL"

    if [ "$FAIL" -eq 0 ]; then
        echo
        echo "ESTADO_GENERAL=SALUDABLE"
        echo "CTPS3 coincide con la release consolidada y supera los chequeos read-only."
        return 0
    fi

    echo
    echo "ESTADO_GENERAL=REVISAR"
    echo "Hay chequeos críticos fallidos."
    return 2
}

{
    main
    RC=$?
    echo
    echo "report=$REPORT"
    exit "$RC"
} 2>&1 | tee "$REPORT"

RC=${PIPESTATUS[0]}

ln -sfn \
    "$(basename "$REPORT")" \
    "$LATEST"

python3 \
    - "$REPORT" \
    "$RELEASE_DIR/RELEASE.json" \
    "$BACKUP_JSON" \
    "$OPS_ESTADO_JSON" \
    "$(readlink -f "$0")" <<'PYOPS'
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

report_path = Path(sys.argv[1])
release_path = Path(sys.argv[2])
backup_path = Path(sys.argv[3])
out_path = Path(sys.argv[4])
auditor_path = Path(sys.argv[5])

texto = report_path.read_text(
    encoding="utf-8",
    errors="replace",
)

def valor(clave):
    m = re.search(
        rf"^{re.escape(clave)}=(.+)$",
        texto,
        flags=re.MULTILINE,
    )
    return None if not m else m.group(1).strip()

with release_path.open(
    "r",
    encoding="utf-8",
) as fh:
    release = json.load(fh)

with backup_path.open(
    "r",
    encoding="utf-8",
) as fh:
    backup = json.load(fh)

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for bloque in iter(
            lambda: fh.read(1024 * 1024),
            b"",
        ):
            h.update(bloque)
    return h.hexdigest()

def systemctl_estado(unidad):
    def ejecutar(accion):
        r = subprocess.run(
            [
                "systemctl",
                accion,
                unidad,
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        return {
            "ok": r.returncode == 0,
            "texto": (
                r.stdout.strip()
                or r.stderr.strip()
                or "desconocido"
            ),
        }

    return {
        "enabled": ejecutar("is-enabled"),
        "active": ejecutar("is-active"),
    }

fecha_match = re.search(
    r"^ fecha=(.+)$",
    texto,
    flags=re.MULTILINE,
)

if not fecha_match:
    fecha_match = re.search(
        r"^fecha=(.+)$",
        texto,
        flags=re.MULTILINE,
    )

sqlite = release.get(
    "sqlite",
    {},
)

estado_funcional = release.get(
    "estado_funcional",
    {},
)

snapshot = backup.get(
    "sqlite_snapshot",
    {},
)

datos = {
    "version": "1.0.0",
    "generado_utc": dt.datetime.now(
        dt.timezone.utc
    ).isoformat(
        timespec="seconds"
    ).replace(
        "+00:00",
        "Z",
    ),
    "auditoria": {
        "auditor_version": "1.3.0",
        "auditor_sha256": sha256(
            auditor_path
        ),
        "fecha": (
            None
            if not fecha_match
            else fecha_match.group(1).strip()
        ),
        "pass": int(
            valor("PASS") or 0
        ),
        "warn": int(
            valor("WARN") or 0
        ),
        "fail": int(
            valor("FAIL") or 0
        ),
        "estado_general": (
            valor("ESTADO_GENERAL")
            or "DESCONOCIDO"
        ),
        "reporte": report_path.name,
    },
    "release": {
        "nombre": release.get(
            "release"
        ),
        "fecha_utc": release.get(
            "fecha_utc"
        ),
        "schema_version": sqlite.get(
            "schema_version"
        ),
        "integrity_check": sqlite.get(
            "integrity_check"
        ),
        "foreign_key_check": sqlite.get(
            "foreign_key_check"
        ),
        "eliminaciones_activas": sqlite.get(
            "eliminaciones_activas"
        ),
        "estado_funcional": estado_funcional,
    },
    "backup": {
        "release": backup.get(
            "release"
        ),
        "fecha_utc": backup.get(
            "fecha_utc"
        ),
        "archivos_payload": backup.get(
            "archivos_payload"
        ),
        "bytes_payload": backup.get(
            "bytes_payload"
        ),
        "snapshot_sha256": snapshot.get(
            "sha256"
        ),
        "snapshot_schema": snapshot.get(
            "schema_version"
        ),
    },
    "timers": {
        "ctps3-inventory.timer": systemctl_estado(
            "ctps3-inventory.timer"
        ),
        "ctps3-catalog.timer": systemctl_estado(
            "ctps3-catalog.timer"
        ),
    },
    "ps3": {
        "requerida_para_auditoria": False,
        "eliminacion_real_e2e": estado_funcional.get(
            "eliminacion_real_ps3",
            "NO_EJECUTADA",
        ),
    },
}

out_path.parent.mkdir(
    parents=True,
    exist_ok=True,
)

fd, temporal = tempfile.mkstemp(
    prefix=".ops-estado.",
    suffix=".json",
    dir=str(out_path.parent),
)

try:
    with os.fdopen(
        fd,
        "w",
        encoding="utf-8",
    ) as fh:
        json.dump(
            datos,
            fh,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        fh.write("\n")
        fh.flush()
        os.fsync(
            fh.fileno()
        )

    os.chmod(
        temporal,
        0o644,
    )

    os.replace(
        temporal,
        out_path,
    )
finally:
    if os.path.exists(
        temporal
    ):
        os.unlink(
            temporal
        )

print(
    f"ops_estado_json={out_path}"
)
PYOPS

python3 \
    - "$HIST_AUD_DIR" \
    "$OPS_HISTORIAL_JSON" <<'PYHIST'
from pathlib import Path
import datetime as dt
import json
import os
import re
import sys
import tempfile

aud_dir = Path(sys.argv[1])
out_path = Path(sys.argv[2])

def valor(texto, clave):
    m = re.search(
        rf"^{re.escape(clave)}=(.+)$",
        texto,
        flags=re.MULTILINE,
    )
    return None if not m else m.group(1).strip()

filas = []

for ruta in sorted(
    aud_dir.glob("ctps3-auditoria-*.txt")
):
    texto = ruta.read_text(
        encoding="utf-8",
        errors="replace",
    )

    fecha = valor(texto, "fecha")

    if fecha is None:
        m = re.search(
            r"^ fecha=(.+)$",
            texto,
            flags=re.MULTILINE,
        )
        fecha = None if not m else m.group(1).strip()

    version = None
    m = re.search(
        r"^ version=(.+)$",
        texto,
        flags=re.MULTILINE,
    )
    if m:
        version = m.group(1).strip()

    referencia = None
    m = re.search(
        r"^ referencia=(.+)$",
        texto,
        flags=re.MULTILINE,
    )
    if m:
        referencia = m.group(1).strip()

    filas.append({
        "archivo": ruta.name,
        "fecha": fecha,
        "pass": int(valor(texto, "PASS") or 0),
        "warn": int(valor(texto, "WARN") or 0),
        "fail": int(valor(texto, "FAIL") or 0),
        "estado_general": (
            valor(texto, "ESTADO_GENERAL")
            or "DESCONOCIDO"
        ),
        "auditor_version": version,
        "referencia": referencia,
    })

filas.sort(
    key=lambda x: (
        x["fecha"] or "",
        x["archivo"],
    ),
    reverse=True,
)

filas = filas[:50]

datos = {
    "version": "1.0.0",
    "generado_utc": dt.datetime.now(
        dt.timezone.utc
    ).isoformat(
        timespec="seconds"
    ).replace(
        "+00:00",
        "Z",
    ),
    "resumen": {
        "total": len(filas),
        "saludables": sum(
            1
            for f in filas
            if f["estado_general"] == "SALUDABLE"
        ),
        "con_warn": sum(
            1
            for f in filas
            if f["warn"] > 0
        ),
        "con_fail": sum(
            1
            for f in filas
            if f["fail"] > 0
        ),
    },
    "auditorias": filas,
}

out_path.parent.mkdir(
    parents=True,
    exist_ok=True,
)

fd, temporal = tempfile.mkstemp(
    prefix=".ops-historial.",
    suffix=".json",
    dir=str(out_path.parent),
)

try:
    with os.fdopen(
        fd,
        "w",
        encoding="utf-8",
    ) as fh:
        json.dump(
            datos,
            fh,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())

    os.chmod(temporal, 0o644)
    os.replace(temporal, out_path)
finally:
    if os.path.exists(temporal):
        os.unlink(temporal)

print(
    f"ops_historial_json={out_path}"
)
PYHIST

exit "$RC"
