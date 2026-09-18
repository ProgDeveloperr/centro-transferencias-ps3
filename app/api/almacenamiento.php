<?php

declare(strict_types=1);

require_once __DIR__ . '/../includes/aplicacion.php';

ctps3_exigir_metodo('GET');

try {
    $pdo = ctps3_bd();

    /*
     * =====================================================
     * Metadatos del inventario físico de almacenamiento
     * =====================================================
     */

    $consultaMeta = $pdo->query("
        SELECT
            clave,
            valor
        FROM meta
        WHERE clave LIKE 'almacenamiento_inventario_%'
        ORDER BY clave ASC
    ");

    $meta = [];

    foreach ($consultaMeta as $fila) {
        $meta[
            (string) $fila['clave']
        ] = (string) $fila['valor'];
    }

    /*
     * =====================================================
     * Telemetría de espacio libre
     *
     * webMAN entrega una cifra aproximada/redondeada.
     * No se deriva capacidad total del disco a partir
     * de este valor ni del inventario de /dev_hdd0/game.
     * =====================================================
     */

    $estado = $pdo->query("
        SELECT
            conectado,
            estado_operativo,
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

    /*
     * =====================================================
     * Resumen del snapshot persistido
     * =====================================================
     */

    $resumenFila = $pdo->query("
        SELECT
            COUNT(*) AS elementos,
            COALESCE(
                SUM(tamano_bytes),
                0
            ) AS bytes_inventariados,

            SUM(
                CASE
                    WHEN origen='J3'
                    THEN 1
                    ELSE 0
                END
            ) AS origen_j3,

            SUM(
                CASE
                    WHEN origen='ESP_SUPLEMENTARIO'
                    THEN 1
                    ELSE 0
                END
            ) AS origen_suplementario,

            SUM(
                CASE
                    WHEN posible_huerfano=1
                    THEN 1
                    ELSE 0
                END
            ) AS posibles_huerfanos,

            SUM(
                CASE
                    WHEN clase='DESCONOCIDO'
                    THEN 1
                    ELSE 0
                END
            ) AS desconocidos,

            SUM(
                CASE
                    WHEN eliminacion_automatica_permitida<>0
                    THEN 1
                    ELSE 0
                END
            ) AS borrado_automatico

        FROM almacenamiento_ps3_elementos
        WHERE disponible=1
    ")->fetch();

    if (!$resumenFila) {
        throw new RuntimeException(
            'No se pudo obtener resumen de almacenamiento'
        );
    }

    /*
     * =====================================================
     * Resumen por clase
     * =====================================================
     */

    $consultaClases = $pdo->query("
        SELECT
            clase,
            COUNT(*) AS cantidad,
            COALESCE(
                SUM(tamano_bytes),
                0
            ) AS bytes,

            SUM(
                CASE
                    WHEN posible_huerfano=1
                    THEN 1
                    ELSE 0
                END
            ) AS posibles_huerfanos

        FROM almacenamiento_ps3_elementos
        WHERE disponible=1

        GROUP BY clase

        ORDER BY
            bytes DESC,
            clase ASC
    ");

    $clases = [];

    foreach ($consultaClases as $fila) {
        $clases[] = [
            'clase' =>
                (string) $fila['clase'],

            'cantidad' =>
                (int) $fila['cantidad'],

            'bytes' =>
                (int) $fila['bytes'],

            'posibles_huerfanos' =>
                (int) $fila[
                    'posibles_huerfanos'
                ],
        ];
    }

    /*
     * =====================================================
     * Elementos físicos actuales
     * =====================================================
     */

    $consultaElementos = $pdo->query("
        SELECT
            id,
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
            detectado_utc,
            visto_utc,
            actualizado_utc

        FROM almacenamiento_ps3_elementos

        WHERE disponible=1

        ORDER BY
            tamano_bytes DESC,
            ruta_remota COLLATE NOCASE ASC
    ");

    $elementos = [];

    foreach ($consultaElementos as $fila) {
        $evidencia = [];

        try {
            $decodificada = json_decode(
                (string) $fila['evidencia_json'],
                true,
                512,
                JSON_THROW_ON_ERROR
            );

            if (is_array($decodificada)) {
                foreach ($decodificada as $valor) {
                    if (is_string($valor)) {
                        $evidencia[] = $valor;
                    }
                }
            }
        } catch (JsonException) {
            $evidencia = [];
        }

        $elementos[] = [
            'id' =>
                (int) $fila['id'],

            'ruta_remota' =>
                (string) $fila[
                    'ruta_remota'
                ],

            'nombre_directorio' =>
                (string) $fila[
                    'nombre_directorio'
                ],

            'title_id_sfo' =>
                $fila['title_id_sfo'] !== null
                    ? (string) $fila[
                        'title_id_sfo'
                    ]
                    : null,

            'nombre_sfo' =>
                $fila['nombre_sfo'] !== null
                    ? (string) $fila[
                        'nombre_sfo'
                    ]
                    : null,

            'categoria_sfo' =>
                $fila['categoria_sfo'] !== null
                    ? (string) $fila[
                        'categoria_sfo'
                    ]
                    : null,

            'tamano_bytes' =>
                (int) $fila[
                    'tamano_bytes'
                ],

            'origen' =>
                (string) $fila['origen'],

            'juego_id' =>
                $fila['juego_id'] !== null
                    ? (int) $fila['juego_id']
                    : null,

            'juego_componente_id' =>
                $fila[
                    'juego_componente_id'
                ] !== null
                    ? (int) $fila[
                        'juego_componente_id'
                    ]
                    : null,

            'clase' =>
                (string) $fila['clase'],

            'subtipo' =>
                $fila['subtipo'] !== null
                    ? (string) $fila['subtipo']
                    : null,

            'confianza' =>
                (string) $fila['confianza'],

            'politica' =>
                (string) $fila['politica'],

            'evidencia' =>
                $evidencia,

            'posible_huerfano' =>
                (bool) (
                    (int) $fila[
                        'posible_huerfano'
                    ]
                ),

            'eliminacion_automatica_permitida' =>
                (bool) (
                    (int) $fila[
                        'eliminacion_automatica_permitida'
                    ]
                ),

            'detectado_utc' =>
                (string) $fila[
                    'detectado_utc'
                ],

            'visto_utc' =>
                (string) $fila[
                    'visto_utc'
                ],

            'actualizado_utc' =>
                (string) $fila[
                    'actualizado_utc'
                ],
        ];
    }

    $ultimoError =
        trim(
            $meta[
                'almacenamiento_inventario_ultimo_error'
            ] ?? ''
        );

    $antiguedad =
        $estado[
            'hdd_antiguedad_segundos'
        ] !== null
            ? (float) $estado[
                'hdd_antiguedad_segundos'
            ]
            : null;

    $hddError =
        $estado[
            'hdd_ultimo_error'
        ] !== null
            ? trim(
                (string) $estado[
                    'hdd_ultimo_error'
                ]
            )
            : '';

    ctps3_respuesta_json([
        'ok' => true,

        'version' => '1.0.0',

        'inventario' => [
            'version' =>
                $meta[
                    'almacenamiento_inventario_version'
                ] ?? null,

            'schema_version' =>
                $meta[
                    'almacenamiento_inventario_schema_version'
                ] ?? null,

            'ultima_ok_utc' =>
                $meta[
                    'almacenamiento_inventario_ultima_ok_utc'
                ] ?? null,

            'duracion_ms' =>
                isset(
                    $meta[
                        'almacenamiento_inventario_duracion_ms'
                    ]
                )
                    ? (int) $meta[
                        'almacenamiento_inventario_duracion_ms'
                    ]
                    : null,

            'rutas' =>
                isset(
                    $meta[
                        'almacenamiento_inventario_rutas'
                    ]
                )
                    ? (int) $meta[
                        'almacenamiento_inventario_rutas'
                    ]
                    : null,

            'total_bytes' =>
                isset(
                    $meta[
                        'almacenamiento_inventario_total_bytes'
                    ]
                )
                    ? (int) $meta[
                        'almacenamiento_inventario_total_bytes'
                    ]
                    : null,

            'ultimo_error' =>
                $ultimoError !== ''
                    ? $ultimoError
                    : null,
        ],

        'ps3' => [
            'conectado' =>
                (bool) (
                    (int) $estado['conectado']
                ),

            'estado_operativo' =>
                (string) $estado[
                    'estado_operativo'
                ],

            'espacio_libre' => [
                'disponible' =>
                    $estado[
                        'hdd_libre_bytes_aprox'
                    ] !== null,

                'bytes_aprox' =>
                    $estado[
                        'hdd_libre_bytes_aprox'
                    ] !== null
                        ? (int) $estado[
                            'hdd_libre_bytes_aprox'
                        ]
                        : null,

                'texto' =>
                    $estado[
                        'hdd_libre_texto'
                    ],

                'fuente' =>
                    $estado[
                        'hdd_fuente'
                    ],

                'ultima_lectura_ok_utc' =>
                    $estado[
                        'hdd_ultima_lectura_ok_utc'
                    ],

                'ultimo_intento_utc' =>
                    $estado[
                        'hdd_ultimo_intento_utc'
                    ],

                'ultimo_error' =>
                    $hddError !== ''
                        ? $hddError
                        : null,

                'antiguedad_segundos' =>
                    $antiguedad !== null
                        ? round(
                            $antiguedad,
                            3
                        )
                        : null,

                'fresca' =>
                    $antiguedad !== null
                    && $antiguedad >= -5.0
                    && $antiguedad <= 60.0
                    && $hddError === '',
            ],
        ],

        /*
         * "bytes_inventariados" representa únicamente
         * contenido persistido por ESP en /dev_hdd0/game.
         * No equivale al espacio total usado del HDD.
         */
        'resumen' => [
            'elementos' =>
                (int) $resumenFila[
                    'elementos'
                ],

            'bytes_inventariados' =>
                (int) $resumenFila[
                    'bytes_inventariados'
                ],

            'origen_j3' =>
                (int) (
                    $resumenFila[
                        'origen_j3'
                    ] ?? 0
                ),

            'origen_suplementario' =>
                (int) (
                    $resumenFila[
                        'origen_suplementario'
                    ] ?? 0
                ),

            'posibles_huerfanos' =>
                (int) (
                    $resumenFila[
                        'posibles_huerfanos'
                    ] ?? 0
                ),

            'desconocidos' =>
                (int) (
                    $resumenFila[
                        'desconocidos'
                    ] ?? 0
                ),

            'borrado_automatico' =>
                (int) (
                    $resumenFila[
                        'borrado_automatico'
                    ] ?? 0
                ),
        ],

        'clases' =>
            $clases,

        'elementos' =>
            $elementos,
    ]);

} catch (Throwable $e) {
    error_log(
        'CTPS3 api/almacenamiento.php: '
        . get_class($e)
        . ': '
        . $e->getMessage()
    );

    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'ERROR_INTERNO',
    ], 500);
}
