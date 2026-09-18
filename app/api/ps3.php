<?php

declare(strict_types=1);

require_once __DIR__ . '/../includes/aplicacion.php';

ctps3_exigir_metodo('GET');

try {
    $pdo = ctps3_bd();

    $estado = $pdo->query("
        SELECT
            conectado,
            host,
            puerto,
            banner,
            ruta_packages,
            paquetes_remotos,

            estado_operativo,
            estado_detectado,

            red_responde,
            ftp_disponible,
            http_disponible,

            fallos_consecutivos,
            detalle_estado,

            ultima_consulta_utc,
            ultima_conexion_ok_utc,
            ultima_red_ok_utc,
            ultimo_ftp_ok_utc,
            ultimo_http_ok_utc,

            ultimo_error,
            duracion_consulta_ms,

            hdd_libre_bytes_aprox,
            hdd_libre_texto,
            hdd_fuente,
            hdd_ultimo_intento_utc,
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
    ")->fetch();

    if (!$estado) {
        throw new RuntimeException(
            'No existe ps3_estado id=1'
        );
    }

    $consulta = $pdo->query("
        SELECT
            id,
            nombre,
            ruta_remota,
            tamano_bytes,
            fecha_modificacion_ftp,
            unix_mode,
            disponible,
            visto_utc,
            actualizado_utc,

            (
                SELECT o.accion
                FROM ordenes o

                WHERE
                    o.archivo_remoto_id
                        = archivos_remotos.id

                    AND o.estado IN (
                        'PENDIENTE',
                        'PROCESANDO'
                    )

                    AND o.accion IN (
                        'INSTALAR_PKG',
                        'ELIMINAR_PKG'
                    )

                ORDER BY o.id DESC

                LIMIT 1

            ) AS operacion_pkg,

            (
                SELECT o.estado
                FROM ordenes o

                WHERE
                    o.archivo_remoto_id
                        = archivos_remotos.id

                    AND o.estado IN (
                        'PENDIENTE',
                        'PROCESANDO'
                    )

                    AND o.accion IN (
                        'INSTALAR_PKG',
                        'ELIMINAR_PKG'
                    )

                ORDER BY o.id DESC

                LIMIT 1

            ) AS operacion_pkg_estado,

            (
                SELECT
                    lpo.lote_id

                FROM ordenes o

                JOIN lote_pkg_ordenes lpo
                    ON lpo.orden_id=o.id

                WHERE
                    o.archivo_remoto_id
                        = archivos_remotos.id

                    AND o.estado IN (
                        'PENDIENTE',
                        'PROCESANDO'
                    )

                    AND o.accion='INSTALAR_PKG'

                ORDER BY o.id DESC

                LIMIT 1

            ) AS lote_pkg_id

        FROM archivos_remotos

        WHERE disponible=1

        ORDER BY
            nombre COLLATE NOCASE ASC
    ");

    $archivos = [];

    foreach ($consulta as $fila) {
        $fila['id'] =
            (int) $fila['id'];

        $fila['tamano_bytes'] =
            (int) $fila[
                'tamano_bytes'
            ];

        $fila['disponible'] =
            (bool) $fila[
                'disponible'
            ];

        $fila['lote_pkg_id'] =
            $fila['lote_pkg_id'] !== null
                ? (int) $fila[
                    'lote_pkg_id'
                ]
                : null;

        $fila['controlada_por_lote'] =
            $fila['lote_pkg_id'] !== null;

        $archivos[] = $fila;
    }

    $operativo =
        $estado[
            'estado_operativo'
        ]
        ?: (
            (bool) $estado['conectado']
                ? 'LISTA'
                : 'NO_DISPONIBLE'
        );

    $detectado =
        $estado[
            'estado_detectado'
        ]
        ?: $operativo;

    $lista =
        $operativo === 'LISTA';

    ctps3_respuesta_json([
        'ok' => true,

        'ps3' => [
            /*
             * Compatibilidad con la API V1.
             */
            'conectado' =>
                (bool) $estado[
                    'conectado'
                ],

            /*
             * Estado inteligente V2.
             */
            'estado_operativo' =>
                $operativo,

            'estado_detectado' =>
                $detectado,

            'listo_transferencias' =>
                $lista,

            'transitorio' =>
                $operativo
                === 'TRANSITORIO',

            'red_responde' =>
                (bool) $estado[
                    'red_responde'
                ],

            'ftp_disponible' =>
                (bool) $estado[
                    'ftp_disponible'
                ],

            'http_disponible' =>
                (bool) $estado[
                    'http_disponible'
                ],

            'fallos_consecutivos' =>
                (int) $estado[
                    'fallos_consecutivos'
                ],

            'umbral_fallos' =>
                3,

            'detalle_estado' =>
                $estado[
                    'detalle_estado'
                ],

            /*
             * Datos tradicionales.
             */
            'host' =>
                $estado['host'],

            'puerto' =>
                (int) $estado[
                    'puerto'
                ],

            'banner' =>
                $estado['banner'],

            'ruta_packages' =>
                $estado[
                    'ruta_packages'
                ],

            'paquetes_remotos' =>
                (int) $estado[
                    'paquetes_remotos'
                ],

            'ultima_consulta_utc' =>
                $estado[
                    'ultima_consulta_utc'
                ],

            'ultima_conexion_ok_utc' =>
                $estado[
                    'ultima_conexion_ok_utc'
                ],

            'ultima_red_ok_utc' =>
                $estado[
                    'ultima_red_ok_utc'
                ],

            'ultimo_ftp_ok_utc' =>
                $estado[
                    'ultimo_ftp_ok_utc'
                ],

            'ultimo_http_ok_utc' =>
                $estado[
                    'ultimo_http_ok_utc'
                ],

            'ultimo_error' =>
                $estado[
                    'ultimo_error'
                ],

            'duracion_consulta_ms' =>
                $estado[
                    'duracion_consulta_ms'
                ] !== null
                    ? (int) $estado[
                        'duracion_consulta_ms'
                    ]
                    : null,

            /*
             * ALM-PS3 1.0.0
             *
             * webMAN publica una cifra redondeada.
             * Por eso el valor se expone como
             * bytes aproximados.
             */
            'almacenamiento' => [
                'disponible' =>
                    $estado[
                        'hdd_libre_bytes_aprox'
                    ] !== null,

                'libre_bytes_aprox' =>
                    $estado[
                        'hdd_libre_bytes_aprox'
                    ] !== null
                        ? (int) $estado[
                            'hdd_libre_bytes_aprox'
                        ]
                        : null,

                'libre_texto' =>
                    $estado[
                        'hdd_libre_texto'
                    ],

                'fuente' =>
                    $estado[
                        'hdd_fuente'
                    ],

                'ultimo_intento_utc' =>
                    $estado[
                        'hdd_ultimo_intento_utc'
                    ],

                'ultima_lectura_ok_utc' =>
                    $estado[
                        'hdd_ultima_lectura_ok_utc'
                    ],

                'ultimo_error' =>
                    $estado[
                        'hdd_ultimo_error'
                    ],

                'antiguedad_segundos' =>
                    $estado[
                        'hdd_antiguedad_segundos'
                    ] !== null
                        ? round(
                            (float) $estado[
                                'hdd_antiguedad_segundos'
                            ],
                            3
                        )
                        : null,

                'fresca' =>
                    $estado[
                        'hdd_antiguedad_segundos'
                    ] !== null
                    && (float) $estado[
                        'hdd_antiguedad_segundos'
                    ] >= -5.0
                    && (float) $estado[
                        'hdd_antiguedad_segundos'
                    ] <= 60.0
                    && (
                        $estado[
                            'hdd_ultimo_error'
                        ] === null
                        || $estado[
                            'hdd_ultimo_error'
                        ] === ''
                    ),
            ],

            /*
             * El inventario se considera actual
             * únicamente cuando el chequeo FTP
             * completo fue exitoso.
             */
            'inventario_actual' =>
                $lista,
        ],

        'archivos' =>
            $archivos,
    ]);

} catch (Throwable $e) {
    error_log(
        '[CTPS3][ps3-v2] '
        . $e->getMessage()
    );

    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'ERROR_INTERNO',
    ], 500);
}
