-- CTPS3 public schema
-- Schema only. No production data included.

-- table: almacenamiento_ps3_elementos
CREATE TABLE almacenamiento_ps3_elementos (
                id INTEGER PRIMARY KEY,

                ruta_remota TEXT NOT NULL UNIQUE,

                nombre_directorio TEXT NOT NULL,

                title_id_sfo TEXT,
                nombre_sfo TEXT,
                categoria_sfo TEXT,

                tamano_bytes INTEGER NOT NULL
                    CHECK (tamano_bytes >= 0),

                origen TEXT NOT NULL
                    CHECK (
                        origen IN ('J3','ESP_SUPLEMENTARIO')
                    ),

                juego_id INTEGER,
                juego_componente_id INTEGER,

                clase TEXT NOT NULL
                    CHECK (
                        clase IN ('JUEGO_INSTALADO','VINCULADO','STORE_APLICACION','HOMEBREW_UTILIDAD','SOPORTE_PS2','SISTEMA_PROTEGIDO','POSIBLE_HUERFANO','DESCONOCIDO')
                    ),

                subtipo TEXT,

                confianza TEXT NOT NULL
                    CHECK (
                        confianza IN ('ALTA','MEDIA','BAJA')
                    ),

                politica TEXT NOT NULL,

                evidencia_json TEXT NOT NULL
                    DEFAULT '[]',

                posible_huerfano INTEGER NOT NULL
                    DEFAULT 0
                    CHECK (
                        posible_huerfano IN (0, 1)
                    ),

                eliminacion_automatica_permitida
                    INTEGER NOT NULL
                    DEFAULT 0
                    CHECK (
                        eliminacion_automatica_permitida = 0
                    ),

                disponible INTEGER NOT NULL
                    DEFAULT 1
                    CHECK (
                        disponible IN (0, 1)
                    ),

                detectado_utc TEXT NOT NULL
                    DEFAULT (
                        strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        )
                    ),

                visto_utc TEXT NOT NULL
                    DEFAULT (
                        strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        )
                    ),

                actualizado_utc TEXT NOT NULL
                    DEFAULT (
                        strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        )
                    ),

                FOREIGN KEY (juego_id)
                    REFERENCES juegos_ps3(id)
                    ON DELETE SET NULL,

                FOREIGN KEY (juego_componente_id)
                    REFERENCES juegos_ps3_componentes(id)
                    ON DELETE SET NULL,

                CHECK (
                    substr(ruta_remota, 1, 15)
                        = '/dev_hdd0/game/'
                ),

                CHECK (
                    length(
                        substr(ruta_remota, 16)
                    ) >= 1
                ),

                CHECK (
                    instr(
                        substr(ruta_remota, 16),
                        '/'
                    ) = 0
                ),

                CHECK (
                    instr(
                        substr(ruta_remota, 16),
                        char(92)
                    ) = 0
                ),

                CHECK (
                    instr(
                        substr(ruta_remota, 16),
                        '..'
                    ) = 0
                )
            );

-- table: archivos_locales
CREATE TABLE "archivos_locales" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    nombre TEXT NOT NULL,
    ruta_relativa TEXT NOT NULL UNIQUE,

    tamano_bytes INTEGER NOT NULL
        CHECK (tamano_bytes >= 0),

    mtime_ns INTEGER NOT NULL,

    sha256 TEXT,

    sha256_estado TEXT NOT NULL DEFAULT 'PENDIENTE'
        CHECK (
            sha256_estado IN (
                'PENDIENTE',
                'CALCULANDO',
                'CALCULADO',
                'ERROR'
            )
        ),

    disponible INTEGER NOT NULL DEFAULT 1
        CHECK (disponible IN (0,1)),

    detectado_utc TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),

    visto_utc TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),

    actualizado_utc TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
, titulo_juego TEXT, codigo_juego TEXT, etiqueta_origen TEXT, parte_numero INTEGER, es_fragmentado INTEGER NOT NULL DEFAULT 0
        CHECK (es_fragmentado IN (0,1)), extension TEXT NOT NULL DEFAULT 'pkg', formato TEXT
                NOT NULL
                DEFAULT 'PKG'
                CHECK (
                    formato IN (
                        'PKG',
                        'PS3ISO',
                        'PS2ISO'
                    )
                ));

-- table: archivos_remotos
CREATE TABLE archivos_remotos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    nombre TEXT NOT NULL UNIQUE,

    ruta_remota TEXT NOT NULL UNIQUE,

    tamano_bytes INTEGER NOT NULL
        CHECK (tamano_bytes >= 0),

    fecha_modificacion_ftp TEXT,

    unix_mode TEXT,
    unix_uid TEXT,
    unix_gid TEXT,

    disponible INTEGER NOT NULL DEFAULT 1
        CHECK (disponible IN (0,1)),

    detectado_utc TEXT NOT NULL
        DEFAULT (
            strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        ),

    visto_utc TEXT NOT NULL
        DEFAULT (
            strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        ),

    actualizado_utc TEXT NOT NULL
        DEFAULT (
            strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        )
);

-- table: archivos_remotos_iso
CREATE TABLE archivos_remotos_iso (
                id INTEGER
                    PRIMARY KEY AUTOINCREMENT,

                nombre TEXT
                    NOT NULL,

                ruta_remota TEXT
                    NOT NULL UNIQUE,

                tamano_bytes INTEGER
                    NOT NULL
                    CHECK (
                        tamano_bytes >= 0
                    ),

                fecha_modificacion_ftp TEXT,

                unix_mode TEXT,
                unix_uid TEXT,
                unix_gid TEXT,

                disponible INTEGER
                    NOT NULL
                    DEFAULT 1
                    CHECK (
                        disponible IN (0,1)
                    ),

                detectado_utc TEXT
                    NOT NULL
                    DEFAULT (
                        strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        )
                    ),

                visto_utc TEXT
                    NOT NULL
                    DEFAULT (
                        strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        )
                    ),

                actualizado_utc TEXT
                    NOT NULL
                    DEFAULT (
                        strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        )
                    ),

                CHECK (
                    LOWER(
                        substr(
                            nombre,
                            -4
                        )
                    ) = '.iso'
                ),

                CHECK (
                    ruta_remota
                    LIKE '/dev_hdd0/PS3ISO/%'
                )
            );

-- table: archivos_remotos_ps2iso
CREATE TABLE archivos_remotos_ps2iso (
            id INTEGER
                PRIMARY KEY AUTOINCREMENT,

            nombre TEXT
                NOT NULL,

            ruta_remota TEXT
                NOT NULL UNIQUE,

            tamano_bytes INTEGER
                NOT NULL
                CHECK (
                    tamano_bytes >= 0
                ),

            fecha_modificacion_ftp TEXT,

            unix_mode TEXT,
            unix_uid TEXT,
            unix_gid TEXT,

            disponible INTEGER
                NOT NULL
                DEFAULT 1
                CHECK (
                    disponible IN (0,1)
                ),

            detectado_utc TEXT
                NOT NULL
                DEFAULT (
                    strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                ),

            visto_utc TEXT
                NOT NULL
                DEFAULT (
                    strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                ),

            actualizado_utc TEXT
                NOT NULL
                DEFAULT (
                    strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                ),

            CHECK (
                substr(
                    nombre,
                    -8
                ) = '.BIN.ENC'
            ),

            CHECK (
                ruta_remota
                LIKE '/dev_hdd0/PS2ISO/%'
            )
        );

-- table: eliminaciones_juegos
CREATE TABLE eliminaciones_juegos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    juego_id INTEGER NOT NULL
        REFERENCES juegos_ps3(id)
        ON DELETE RESTRICT,

    nombre TEXT NOT NULL,
    title_id TEXT,
    tipo_principal TEXT NOT NULL,

    estado TEXT NOT NULL
        CHECK (
            estado IN (
                'PENDIENTE',
                'PROCESANDO',
                'COMPLETADO',
                'ERROR'
            )
        ),

    componentes_total INTEGER NOT NULL
        CHECK (componentes_total >= 1),

    componentes_eliminados INTEGER NOT NULL
        DEFAULT 0
        CHECK (
            componentes_eliminados >= 0
            AND componentes_eliminados
                <= componentes_total
        ),

    tamano_objetivo_bytes INTEGER,
    tamano_completo INTEGER NOT NULL
        DEFAULT 0
        CHECK (tamano_completo IN (0, 1)),

    creada_utc TEXT NOT NULL
        DEFAULT (
            strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        ),

    iniciada_utc TEXT,

    actualizada_utc TEXT NOT NULL
        DEFAULT (
            strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        ),

    finalizada_utc TEXT,
    mensaje TEXT,
    error_detalle TEXT
, alcance TEXT NOT NULL
                DEFAULT 'JUEGO_COMPLETO'
                CHECK (
                    alcance IN (
                        'JUEGO_COMPLETO',
                        'DATOS_ASOCIADOS'
                    )
                ));

-- table: eliminaciones_juegos_componentes
CREATE TABLE eliminaciones_juegos_componentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    eliminacion_id INTEGER NOT NULL
        REFERENCES eliminaciones_juegos(id)
        ON DELETE CASCADE,

    juego_componente_id INTEGER NOT NULL
        REFERENCES juegos_ps3_componentes(id)
        ON DELETE RESTRICT,

    tipo TEXT NOT NULL,
    ruta_remota TEXT NOT NULL,
    tamano_bytes INTEGER,

    estado TEXT NOT NULL
        DEFAULT 'PENDIENTE'
        CHECK (
            estado IN (
                'PENDIENTE',
                'PROCESANDO',
                'ELIMINADO',
                'ERROR'
            )
        ),

    mensaje TEXT,
    http_codigo INTEGER,
    respuesta_bytes INTEGER,

    creado_utc TEXT NOT NULL
        DEFAULT (
            strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        ),

    actualizado_utc TEXT NOT NULL
        DEFAULT (
            strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        ),

    UNIQUE (
        eliminacion_id,
        juego_componente_id
    ),

    UNIQUE (
        eliminacion_id,
        ruta_remota
    )
);

-- table: eventos
CREATE TABLE eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    transferencia_id INTEGER,

    nivel TEXT NOT NULL DEFAULT 'INFO'
        CHECK (
            nivel IN (
                'DEBUG',
                'INFO',
                'AVISO',
                'ERROR',
                'CRITICO'
            )
        ),

    tipo TEXT NOT NULL,
    mensaje TEXT NOT NULL,

    datos_json TEXT,

    creado_utc TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),

    FOREIGN KEY (transferencia_id)
        REFERENCES transferencias(id)
        ON DELETE SET NULL
);

-- table: juegos_ps3
CREATE TABLE juegos_ps3 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            clave_logica TEXT NOT NULL UNIQUE,

            title_id TEXT,

            nombre TEXT NOT NULL,

            tipo_principal TEXT NOT NULL
                CHECK (
                    tipo_principal IN (
                        'JB_FOLDER',
                        'HDD_JUEGO',
                        'PS3_ISO',
                        'DESCONOCIDO'
                    )
                ),

            tamano_total_bytes INTEGER
                CHECK (
                    tamano_total_bytes IS NULL
                    OR tamano_total_bytes >= 0
                ),

            disponible INTEGER NOT NULL
                DEFAULT 1
                CHECK (
                    disponible IN (0,1)
                ),

            inventario_completo INTEGER NOT NULL
                DEFAULT 1
                CHECK (
                    inventario_completo IN (0,1)
                ),

            detectado_utc TEXT NOT NULL
                DEFAULT (
                    strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                ),

            visto_utc TEXT NOT NULL
                DEFAULT (
                    strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                ),

            actualizado_utc TEXT NOT NULL
                DEFAULT (
                    strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                )
        );

-- table: juegos_ps3_componentes
CREATE TABLE juegos_ps3_componentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            juego_id INTEGER NOT NULL,

            tipo TEXT NOT NULL
                CHECK (
                    tipo IN (
                        'JB_FOLDER',
                        'HDD_JUEGO',
                        'DATOS_GAME',
                        'CACHE_GAME',
                        'PS3_ISO',
                        'OTRO'
                    )
                ),

            ruta_remota TEXT NOT NULL UNIQUE,

            title_id_sfo TEXT,

            nombre_sfo TEXT,

            categoria_sfo TEXT,

            bootable INTEGER
                CHECK (
                    bootable IS NULL
                    OR bootable IN (0,1)
                ),

            app_ver TEXT,

            version TEXT,

            tamano_bytes INTEGER
                CHECK (
                    tamano_bytes IS NULL
                    OR tamano_bytes >= 0
                ),

            disponible INTEGER NOT NULL
                DEFAULT 1
                CHECK (
                    disponible IN (0,1)
                ),

            detectado_utc TEXT NOT NULL
                DEFAULT (
                    strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                ),

            visto_utc TEXT NOT NULL
                DEFAULT (
                    strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                ),

            actualizado_utc TEXT NOT NULL
                DEFAULT (
                    strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                ),

            FOREIGN KEY (
                juego_id
            )
                REFERENCES juegos_ps3(id)
                ON DELETE CASCADE
        );

-- table: lote_pkg_ordenes
CREATE TABLE lote_pkg_ordenes (
    lote_id INTEGER NOT NULL,

    orden_id INTEGER NOT NULL,

    posicion INTEGER NOT NULL
        CHECK (posicion >= 1),

    PRIMARY KEY (
        lote_id,
        posicion
    ),

    UNIQUE (
        orden_id
    ),

    FOREIGN KEY (
        lote_id
    )
        REFERENCES lotes_pkg(id)
        ON DELETE CASCADE,

    FOREIGN KEY (
        orden_id
    )
        REFERENCES ordenes(id)
        ON DELETE CASCADE
);

-- table: lotes_pkg
CREATE TABLE lotes_pkg (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    titulo TEXT NOT NULL,

    estado TEXT NOT NULL
        DEFAULT 'PENDIENTE'
        CHECK (
            estado IN (
                'PENDIENTE',
                'PROCESANDO',
                'EJECUTADO',
                'ERROR'
            )
        ),

    creada_utc TEXT NOT NULL
        DEFAULT (
            strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        ),

    procesada_utc TEXT,

    mensaje TEXT
);

-- table: meta
CREATE TABLE meta (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

-- table: ordenes
CREATE TABLE "ordenes" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            transferencia_id INTEGER,

            archivo_remoto_id INTEGER,

            accion TEXT NOT NULL
                CHECK (
                    accion IN (
                        'PAUSAR',
                        'REANUDAR',
                        'CANCELAR',
                        'REINTENTAR',
                        'INSTALAR_PKG',
                        'ELIMINAR_PKG'
                    )
                ),

            estado TEXT NOT NULL
                DEFAULT 'PENDIENTE'
                CHECK (
                    estado IN (
                        'PENDIENTE',
                        'PROCESANDO',
                        'EJECUTADA',
                        'RECHAZADA',
                        'ERROR'
                    )
                ),

            creada_utc TEXT NOT NULL
                DEFAULT (
                    strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                ),

            procesada_utc TEXT,

            mensaje TEXT,


            CHECK (
                (
                    accion IN (
                        'PAUSAR',
                        'REANUDAR',
                        'CANCELAR',
                        'REINTENTAR'
                    )

                    AND transferencia_id
                        IS NOT NULL

                    AND archivo_remoto_id
                        IS NULL
                )

                OR

                (
                    accion IN (
                        'INSTALAR_PKG',
                        'ELIMINAR_PKG'
                    )

                    AND transferencia_id
                        IS NULL

                    AND archivo_remoto_id
                        IS NOT NULL
                )
            ),


            FOREIGN KEY (
                transferencia_id
            )
                REFERENCES transferencias(id)
                ON DELETE CASCADE,


            FOREIGN KEY (
                archivo_remoto_id
            )
                REFERENCES archivos_remotos(id)
                ON DELETE RESTRICT
        );

-- table: ps3_estado
CREATE TABLE ps3_estado (
    id INTEGER PRIMARY KEY
        CHECK (id = 1),

    conectado INTEGER NOT NULL DEFAULT 0
        CHECK (conectado IN (0,1)),

    host TEXT NOT NULL,
    puerto INTEGER NOT NULL DEFAULT 21,

    banner TEXT,

    ruta_packages TEXT NOT NULL
        DEFAULT '/dev_hdd0/packages',

    paquetes_remotos INTEGER NOT NULL DEFAULT 0
        CHECK (paquetes_remotos >= 0),

    ultima_consulta_utc TEXT,

    ultima_conexion_ok_utc TEXT,

    ultimo_error TEXT,

    duracion_consulta_ms INTEGER
, estado_operativo TEXT NOT NULL DEFAULT 'NO_DISPONIBLE', estado_detectado TEXT NOT NULL DEFAULT 'NO_DISPONIBLE', red_responde INTEGER NOT NULL DEFAULT 0, ftp_disponible INTEGER NOT NULL DEFAULT 0, http_disponible INTEGER NOT NULL DEFAULT 0, fallos_consecutivos INTEGER NOT NULL DEFAULT 0, detalle_estado TEXT, ultima_red_ok_utc TEXT, ultimo_ftp_ok_utc TEXT, ultimo_http_ok_utc TEXT, hdd_libre_bytes_aprox INTEGER, hdd_libre_texto TEXT, hdd_fuente TEXT, hdd_ultimo_intento_utc TEXT, hdd_ultima_lectura_ok_utc TEXT, hdd_ultimo_error TEXT);

-- table: recuperaciones_worker
CREATE TABLE recuperaciones_worker (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            tipo TEXT NOT NULL
                CHECK (
                    tipo IN (
                        'SESION_HUERFANA',
                        'TRANSFERENCIA_RECUPERADA'
                    )
                ),

            transferencia_id INTEGER,

            sesion_id INTEGER,

            estado_anterior TEXT,

            estado_nuevo TEXT,

            pid_anterior INTEGER,

            bytes_observados INTEGER
                CHECK (
                    bytes_observados IS NULL
                    OR bytes_observados >= 0
                ),

            bytes_reconciliados INTEGER
                CHECK (
                    bytes_reconciliados IS NULL
                    OR bytes_reconciliados >= 0
                ),

            detalle TEXT,

            detalle_reconciliacion TEXT,

            creada_utc TEXT NOT NULL
                DEFAULT (
                    strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                ),

            resuelta_utc TEXT,

            FOREIGN KEY(transferencia_id)
                REFERENCES transferencias(id)
                ON DELETE SET NULL,

            FOREIGN KEY(sesion_id)
                REFERENCES transferencia_intentos(id)
                ON DELETE SET NULL
        );

-- table: transferencia_intentos
CREATE TABLE transferencia_intentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            transferencia_id INTEGER NOT NULL,

            numero_sesion INTEGER NOT NULL
                CHECK (numero_sesion > 0),

            intento_worker INTEGER NOT NULL
                CHECK (intento_worker > 0),

            pid INTEGER,

            reanudacion INTEGER NOT NULL DEFAULT 0
                CHECK (reanudacion IN (0,1)),

            bytes_remotos_inicio INTEGER NOT NULL DEFAULT 0
                CHECK (bytes_remotos_inicio >= 0),

            bytes_remotos_fin INTEGER
                CHECK (
                    bytes_remotos_fin IS NULL
                    OR bytes_remotos_fin >= 0
                ),

            bytes_ftp INTEGER NOT NULL DEFAULT 0
                CHECK (bytes_ftp >= 0),

            duracion_segundos REAL NOT NULL DEFAULT 0
                CHECK (duracion_segundos >= 0),

            velocidad_media_bps REAL NOT NULL DEFAULT 0
                CHECK (velocidad_media_bps >= 0),

            resultado TEXT NOT NULL DEFAULT 'EN_CURSO'
                CHECK (
                    resultado IN (
                        'EN_CURSO',
                        'COMPLETADO',
                        'PAUSADO',
                        'CANCELADO',
                        'INTERRUMPIDO',
                        'INCOMPLETO',
                        'ERROR',
                        'CONFLICTO'
                    )
                ),

            codigo_lftp INTEGER,

            error_codigo TEXT,
            error_detalle TEXT,

            log_archivo TEXT,

            iniciada_utc TEXT NOT NULL
                DEFAULT (
                    strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                ),

            actualizada_utc TEXT NOT NULL
                DEFAULT (
                    strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                ),

            finalizada_utc TEXT,

            UNIQUE(
                transferencia_id,
                numero_sesion
            ),

            FOREIGN KEY(transferencia_id)
                REFERENCES transferencias(id)
                ON DELETE CASCADE
        );

-- table: transferencias
CREATE TABLE "transferencias" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    archivo_id INTEGER NOT NULL,

    nombre_snapshot TEXT NOT NULL,
    ruta_relativa_snapshot TEXT NOT NULL,

    nombre_remoto TEXT NOT NULL,

    tamano_total INTEGER NOT NULL
        CHECK (tamano_total >= 0),

    bytes_transferidos INTEGER NOT NULL DEFAULT 0
        CHECK (bytes_transferidos >= 0),

    bytes_remotos INTEGER NOT NULL DEFAULT 0
        CHECK (bytes_remotos >= 0),

    estado TEXT NOT NULL DEFAULT 'EN_COLA'
        CHECK (
            estado IN (
                'EN_COLA',
                'COMPROBANDO',
                'YA_EXISTE',
                'PREPARANDO',
                'TRANSFIRIENDO',
                'PAUSANDO',
                'PAUSADO',
                'CANCELANDO',
                'CANCELADO',
                'VERIFICANDO',
                'COMPLETADO',
                'REINTENTANDO',
                'ERROR',
                'CONFLICTO'
            )
        ),

    prioridad INTEGER NOT NULL DEFAULT 100,

    intentos INTEGER NOT NULL DEFAULT 0
        CHECK (intentos >= 0),

    pid INTEGER,

    velocidad_bps REAL,
    velocidad_promedio_bps REAL,

    eta_segundos INTEGER,

    reanudada INTEGER NOT NULL DEFAULT 0
        CHECK (reanudada IN (0,1)),

    mensaje TEXT,

    error_codigo TEXT,
    error_detalle TEXT,

    creada_utc TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),

    iniciada_utc TEXT,

    actualizada_utc TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),

    finalizada_utc TEXT, posicion_cola
        INTEGER NOT NULL DEFAULT 0, formato_snapshot TEXT
                NOT NULL
                DEFAULT 'PKG'
                CHECK (
                    formato_snapshot IN (
                        'PKG',
                        'PS3ISO',
                        'PS2ISO'
                    )
                ), destino_remoto_snapshot TEXT
                NOT NULL
                DEFAULT '/dev_hdd0/packages',

    FOREIGN KEY (archivo_id)
        REFERENCES archivos_locales(id)
        ON DELETE RESTRICT
);

-- table: worker_estado
CREATE TABLE worker_estado (
    id INTEGER PRIMARY KEY
        CHECK (id = 1),

    estado TEXT NOT NULL
        CHECK (
            estado IN (
                'DETENIDO',
                'INICIANDO',
                'ESPERANDO',
                'OCUPADO',
                'ERROR'
            )
        ),

    pid INTEGER,

    version TEXT NOT NULL,

    transferencia_id INTEGER,

    heartbeat_utc TEXT,
    iniciado_utc TEXT,

    mensaje TEXT,

    FOREIGN KEY (transferencia_id)
        REFERENCES transferencias(id)
        ON DELETE SET NULL
);

-- index: idx_almacenamiento_ps3_clase_disponible
CREATE INDEX idx_almacenamiento_ps3_clase_disponible
            ON almacenamiento_ps3_elementos (
                clase,
                disponible
            )
            ;

-- index: idx_almacenamiento_ps3_juego
CREATE INDEX idx_almacenamiento_ps3_juego
            ON almacenamiento_ps3_elementos (
                juego_id,
                juego_componente_id
            )
            ;

-- index: idx_almacenamiento_ps3_title_id
CREATE INDEX idx_almacenamiento_ps3_title_id
            ON almacenamiento_ps3_elementos (
                title_id_sfo
            )
            ;

-- index: idx_archivos_codigo_juego
CREATE INDEX idx_archivos_codigo_juego
    ON archivos_locales(codigo_juego)
;

-- index: idx_archivos_disponible
CREATE INDEX idx_archivos_disponible
ON archivos_locales(disponible);

-- index: idx_archivos_locales_formato
CREATE INDEX idx_archivos_locales_formato
            ON archivos_locales(
                formato,
                disponible
            )
            ;

-- index: idx_archivos_nombre
CREATE INDEX idx_archivos_nombre
ON archivos_locales(nombre);

-- index: idx_archivos_remotos_disponible
CREATE INDEX idx_archivos_remotos_disponible
ON archivos_remotos(disponible);

-- index: idx_archivos_remotos_iso_disponible
CREATE INDEX idx_archivos_remotos_iso_disponible
            ON archivos_remotos_iso(
                disponible
            )
            ;

-- index: idx_archivos_remotos_iso_nombre
CREATE INDEX idx_archivos_remotos_iso_nombre
            ON archivos_remotos_iso(
                nombre COLLATE NOCASE
            )
            ;

-- index: idx_archivos_remotos_nombre
CREATE INDEX idx_archivos_remotos_nombre
ON archivos_remotos(nombre);

-- index: idx_archivos_remotos_ps2iso_disponible
CREATE INDEX idx_archivos_remotos_ps2iso_disponible
        ON archivos_remotos_ps2iso(
            disponible
        )
    ;

-- index: idx_archivos_remotos_ps2iso_nombre
CREATE INDEX idx_archivos_remotos_ps2iso_nombre
        ON archivos_remotos_ps2iso(
            nombre COLLATE NOCASE
        )
    ;

-- index: idx_archivos_titulo_juego
CREATE INDEX idx_archivos_titulo_juego
    ON archivos_locales(titulo_juego)
;

-- index: idx_eliminaciones_juegos_activa
CREATE UNIQUE INDEX idx_eliminaciones_juegos_activa
ON eliminaciones_juegos(juego_id)
WHERE estado IN (
    'PENDIENTE',
    'PROCESANDO'
);

-- index: idx_eliminaciones_juegos_componentes_estado
CREATE INDEX idx_eliminaciones_juegos_componentes_estado
ON eliminaciones_juegos_componentes(
    eliminacion_id,
    estado,
    id
);

-- index: idx_eliminaciones_juegos_estado
CREATE INDEX idx_eliminaciones_juegos_estado
ON eliminaciones_juegos(
    estado,
    creada_utc,
    id
);

-- index: idx_eventos_fecha
CREATE INDEX idx_eventos_fecha
ON eventos(creado_utc);

-- index: idx_eventos_transferencia
CREATE INDEX idx_eventos_transferencia
ON eventos(
    transferencia_id,
    creado_utc
);

-- index: idx_juegos_componentes_disponible
CREATE INDEX idx_juegos_componentes_disponible
        ON juegos_ps3_componentes(disponible)
    ;

-- index: idx_juegos_componentes_juego
CREATE INDEX idx_juegos_componentes_juego
        ON juegos_ps3_componentes(juego_id)
    ;

-- index: idx_juegos_componentes_tipo
CREATE INDEX idx_juegos_componentes_tipo
        ON juegos_ps3_componentes(tipo)
    ;

-- index: idx_juegos_ps3_disponible
CREATE INDEX idx_juegos_ps3_disponible
        ON juegos_ps3(disponible)
    ;

-- index: idx_juegos_ps3_tipo
CREATE INDEX idx_juegos_ps3_tipo
        ON juegos_ps3(tipo_principal)
    ;

-- index: idx_juegos_ps3_title_id
CREATE INDEX idx_juegos_ps3_title_id
        ON juegos_ps3(title_id)
    ;

-- index: idx_lote_pkg_orden_posicion
CREATE UNIQUE INDEX idx_lote_pkg_orden_posicion
ON lote_pkg_ordenes (
    lote_id,
    posicion
);

-- index: idx_lotes_pkg_estado
CREATE INDEX idx_lotes_pkg_estado
ON lotes_pkg (
    estado,
    id
);

-- index: idx_ordenes_pkg_estado
CREATE INDEX idx_ordenes_pkg_estado
        ON ordenes (
            archivo_remoto_id,
            estado
        )
    ;

-- index: idx_ordenes_transferencia_estado
CREATE INDEX idx_ordenes_transferencia_estado
        ON ordenes (
            transferencia_id,
            estado
        )
    ;

-- index: idx_recuperaciones_worker_pendientes
CREATE INDEX idx_recuperaciones_worker_pendientes

        ON recuperaciones_worker(
            tipo,
            resuelta_utc
        )
    ;

-- index: idx_recuperaciones_worker_transferencia
CREATE INDEX idx_recuperaciones_worker_transferencia

        ON recuperaciones_worker(
            transferencia_id,
            creada_utc
        )
    ;

-- index: idx_transferencia_archivo_activa
CREATE UNIQUE INDEX idx_transferencia_archivo_activa
ON transferencias(archivo_id)
WHERE estado IN (
    'EN_COLA',
    'COMPROBANDO',
    'PREPARANDO',
    'TRANSFIRIENDO',
    'PAUSANDO',
    'PAUSADO',
    'CANCELANDO',
    'VERIFICANDO',
    'REINTENTANDO'
);

-- index: idx_transferencia_intentos_resultado
CREATE INDEX idx_transferencia_intentos_resultado

        ON transferencia_intentos(
            resultado,
            finalizada_utc
        )
    ;

-- index: idx_transferencia_intentos_transferencia
CREATE INDEX idx_transferencia_intentos_transferencia

        ON transferencia_intentos(
            transferencia_id,
            numero_sesion
        )
    ;

-- index: idx_transferencias_archivo
CREATE INDEX idx_transferencias_archivo
ON transferencias(archivo_id);

-- index: idx_transferencias_cola
CREATE INDEX idx_transferencias_cola
ON transferencias(
    estado,
    prioridad,
    creada_utc
);

-- index: idx_transferencias_despacho
CREATE INDEX idx_transferencias_despacho
    ON transferencias(
        estado,
        prioridad,
        posicion_cola,
        creada_utc,
        id
    )
;

-- index: idx_transferencias_estado
CREATE INDEX idx_transferencias_estado
ON transferencias(estado);

-- index: idx_transferencias_formato
CREATE INDEX idx_transferencias_formato
            ON transferencias(
                formato_snapshot,
                estado
            )
            ;
