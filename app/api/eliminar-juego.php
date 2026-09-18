<?php

declare(strict_types=1);

require_once __DIR__ . '/../includes/aplicacion.php';

ctps3_exigir_metodo('POST');
ctps3_exigir_csrf();


function ctps3_juego_eliminacion_ruta_segura(
    string $tipo,
    string $ruta
): bool {
    $reglas = [
        'HDD_JUEGO' => [
            'prefijo' =>
                '/dev_hdd0/game/',
            'iso' =>
                false,
        ],

        'DATOS_GAME' => [
            'prefijo' =>
                '/dev_hdd0/game/',
            'iso' =>
                false,
        ],

        'CACHE_GAME' => [
            'prefijo' =>
                '/dev_hdd0/game/',
            'iso' =>
                false,
        ],

        'JB_FOLDER' => [
            'prefijo' =>
                '/dev_hdd0/GAMES/',
            'iso' =>
                false,
        ],

        'PS3_ISO' => [
            'prefijo' =>
                '/dev_hdd0/PS3ISO/',
            'iso' =>
                true,
        ],
    ];

    if (!isset($reglas[$tipo])) {
        return false;
    }

    if (
        $ruta === ''
        || str_contains($ruta, "\0")
        || str_contains($ruta, '\\')
        || str_contains($ruta, '*')
        || str_contains($ruta, '?')
        || str_contains($ruta, '#')
        || str_contains($ruta, '%')
    ) {
        return false;
    }

    if (
        preg_match(
            '/[\x00-\x1F\x7F]/',
            $ruta
        ) === 1
    ) {
        return false;
    }

    $regla =
        $reglas[$tipo];

    $prefijo =
        (string) $regla['prefijo'];

    if (!str_starts_with(
        $ruta,
        $prefijo
    )) {
        return false;
    }

    $relativa =
        substr(
            $ruta,
            strlen($prefijo)
        );

    if (
        $relativa === ''
        || $relativa === '.'
        || $relativa === '..'
        || str_contains(
            $relativa,
            '/'
        )
        || str_starts_with(
            $relativa,
            '_INST_'
        )
    ) {
        return false;
    }

    if (
        (bool) $regla['iso']
        && !str_ends_with(
            strtolower($relativa),
            '.iso'
        )
    ) {
        return false;
    }

    return true;
}


function ctps3_juego_eliminacion_preview(
    PDO $pdo,
    int $juegoId
): array {
    $consultaJuego =
        $pdo->prepare("
            SELECT
                id,
                title_id,
                nombre,
                tipo_principal,
                tamano_total_bytes,
                disponible,
                inventario_completo

            FROM juegos_ps3

            WHERE id=?

            LIMIT 1
        ");

    $consultaJuego->execute([
        $juegoId,
    ]);

    $juego =
        $consultaJuego->fetch();

    if (!$juego) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' =>
                'JUEGO_NO_EXISTE',
        ], 404);
    }

    if (!(bool) $juego['disponible']) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' =>
                'JUEGO_NO_DISPONIBLE',
        ], 409);
    }

    if (!(bool) $juego['inventario_completo']) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' =>
                'INVENTARIO_INCOMPLETO',
        ], 409);
    }

    $consultaComponentes =
        $pdo->prepare("
            SELECT
                id,
                tipo,
                ruta_remota,
                tamano_bytes,
                disponible

            FROM juegos_ps3_componentes

            WHERE
                juego_id=?
                AND disponible=1

            ORDER BY
                CASE tipo
                    WHEN 'HDD_JUEGO' THEN 1
                    WHEN 'JB_FOLDER' THEN 2
                    WHEN 'PS3_ISO' THEN 3
                    WHEN 'DATOS_GAME' THEN 4
                    WHEN 'CACHE_GAME' THEN 5
                    ELSE 99
                END,
                ruta_remota COLLATE NOCASE ASC,
                id ASC
        ");

    $consultaComponentes->execute([
        $juegoId,
    ]);

    $componentes = [];
    $rutas = [];

    $tamano = 0;
    $tamanoCompleto = true;

    foreach (
        $consultaComponentes
        as $componente
    ) {
        $tipo =
            (string) $componente['tipo'];

        $ruta =
            (string) $componente[
                'ruta_remota'
            ];

        if (
            !ctps3_juego_eliminacion_ruta_segura(
                $tipo,
                $ruta
            )
        ) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'COMPONENTE_RUTA_NO_PERMITIDA',

                'componente_id' =>
                    (int) $componente['id'],

                'tipo' =>
                    $tipo,
            ], 403);
        }

        if (isset($rutas[$ruta])) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'COMPONENTES_DUPLICADOS',
            ], 409);
        }

        $rutas[$ruta] = true;

        $tamanoComponente =
            $componente['tamano_bytes']
                !== null
                    ? (int) $componente[
                        'tamano_bytes'
                    ]
                    : null;

        if ($tamanoComponente === null) {
            $tamanoCompleto = false;

        } else {
            $tamano +=
                $tamanoComponente;
        }

        $componentes[] = [
            'id' =>
                (int) $componente['id'],

            'tipo' =>
                $tipo,

            'ruta_remota' =>
                $ruta,

            'tamano_bytes' =>
                $tamanoComponente,
        ];
    }

    if (!$componentes) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' =>
                'SIN_COMPONENTES_ELIMINABLES',
        ], 409);
    }

    $titleId =
        $juego['title_id']
            !== null
                ? trim(
                    (string) $juego[
                        'title_id'
                    ]
                )
                : '';

    $nombre =
        trim(
            (string) $juego['nombre']
        );

    $confirmacionBase =
        $titleId !== ''
            ? $titleId
            : $nombre;

    $confirmacion =
        'ELIMINAR '
        . $confirmacionBase;

    return [
        'juego_id' =>
            (int) $juego['id'],

        'title_id' =>
            $titleId !== ''
                ? $titleId
                : null,

        'nombre' =>
            $nombre,

        'tipo_principal' =>
            (string) $juego[
                'tipo_principal'
            ],

        'tamano_total_bytes' =>
            $juego['tamano_total_bytes']
                !== null
                    ? (int) $juego[
                        'tamano_total_bytes'
                    ]
                    : null,

        'tamano_liberable_bytes' =>
            $tamano,

        'tamano_completo' =>
            $tamanoCompleto,

        'cantidad_componentes' =>
            count($componentes),

        'componentes' =>
            $componentes,

        'confirmacion_esperada' =>
            $confirmacion,
    ];
}


function ctps3_juego_eliminacion_activa(
    PDO $pdo,
    int $juegoId
): ?array {
    $consulta =
        $pdo->prepare("
            SELECT
                id,
                estado,
                creada_utc,
                mensaje

            FROM eliminaciones_juegos

            WHERE
                juego_id=?
                AND estado IN (
                    'PENDIENTE',
                    'PROCESANDO'
                )

            ORDER BY id ASC

            LIMIT 1
        ");

    $consulta->execute([
        $juegoId,
    ]);

    $fila =
        $consulta->fetch();

    if (!$fila) {
        return null;
    }

    return [
        'id' =>
            (int) $fila['id'],

        'estado' =>
            (string) $fila['estado'],

        'creada_utc' =>
            (string) $fila[
                'creada_utc'
            ],

        'mensaje' =>
            $fila['mensaje']
                !== null
                    ? (string) $fila[
                        'mensaje'
                    ]
                    : null,
    ];
}


try {
    $datos =
        ctps3_json();

    $accion =
        strtoupper(
            trim(
                (string) (
                    $datos['accion']
                    ?? ''
                )
            )
        );

    $pdo =
        ctps3_bd();


    if ($accion === 'PREVISUALIZAR') {
        $juegoId =
            filter_var(
                $datos['juego_id']
                    ?? null,
                FILTER_VALIDATE_INT
            );

        if (!$juegoId || $juegoId < 1) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'JUEGO_INVALIDO',
            ], 422);
        }

        $preview =
            ctps3_juego_eliminacion_preview(
                $pdo,
                (int) $juegoId
            );

        ctps3_respuesta_json([
            'ok' => true,
            'version' => '1.0.0',

            'preview' =>
                $preview,

            'eliminacion_activa' =>
                ctps3_juego_eliminacion_activa(
                    $pdo,
                    (int) $juegoId
                ),
        ]);
    }


    if ($accion === 'SOLICITAR') {
        $juegoId =
            filter_var(
                $datos['juego_id']
                    ?? null,
                FILTER_VALIDATE_INT
            );

        if (!$juegoId || $juegoId < 1) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'JUEGO_INVALIDO',
            ], 422);
        }

        $confirmacion =
            trim(
                (string) (
                    $datos[
                        'confirmacion'
                    ]
                    ?? ''
                )
            );

        $preview =
            ctps3_juego_eliminacion_preview(
                $pdo,
                (int) $juegoId
            );

        if (
            $confirmacion === ''
            || !hash_equals(
                $preview[
                    'confirmacion_esperada'
                ],
                $confirmacion
            )
        ) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'CONFIRMACION_INVALIDA',
            ], 422);
        }

        try {
            $pdo->exec(
                'BEGIN IMMEDIATE'
            );

            $activa =
                ctps3_juego_eliminacion_activa(
                    $pdo,
                    (int) $juegoId
                );

            if ($activa !== null) {
                $pdo->rollBack();

                ctps3_respuesta_json([
                    'ok' => false,
                    'error' =>
                        'ELIMINACION_YA_ACTIVA',

                    'eliminacion_id' =>
                        $activa['id'],

                    'estado' =>
                        $activa['estado'],
                ], 409);
            }

            $insertar =
                $pdo->prepare("
                    INSERT INTO eliminaciones_juegos (
                        juego_id,
                        nombre,
                        title_id,
                        tipo_principal,
                        estado,
                        componentes_total,
                        componentes_eliminados,
                        tamano_objetivo_bytes,
                        tamano_completo,
                        mensaje
                    )
                    VALUES (
                        ?,
                        ?,
                        ?,
                        ?,
                        'PENDIENTE',
                        ?,
                        0,
                        ?,
                        ?,
                        ?
                    )
                ");

            $insertar->execute([
                $preview['juego_id'],
                $preview['nombre'],
                $preview['title_id'],
                $preview['tipo_principal'],
                $preview[
                    'cantidad_componentes'
                ],
                $preview[
                    'tamano_liberable_bytes'
                ],
                $preview['tamano_completo']
                    ? 1
                    : 0,
                'Esperando worker',
            ]);

            $eliminacionId =
                (int) $pdo
                    ->lastInsertId();

            $insertarComponente =
                $pdo->prepare("
                    INSERT INTO
                        eliminaciones_juegos_componentes (
                            eliminacion_id,
                            juego_componente_id,
                            tipo,
                            ruta_remota,
                            tamano_bytes,
                            estado,
                            mensaje
                        )
                    VALUES (
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        'PENDIENTE',
                        'Esperando eliminación'
                    )
                ");

            foreach (
                $preview['componentes']
                as $componente
            ) {
                $insertarComponente
                    ->execute([
                        $eliminacionId,
                        $componente['id'],
                        $componente['tipo'],
                        $componente[
                            'ruta_remota'
                        ],
                        $componente[
                            'tamano_bytes'
                        ],
                    ]);
            }

            $evento =
                $pdo->prepare("
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
                        'JUEGO_ELIMINACION_SOLICITADA',
                        ?,
                        ?
                    )
                ");

            $evento->execute([
                (
                    'Eliminación solicitada: '
                    . $preview['nombre']
                ),

                json_encode(
                    [
                        'eliminacion_id' =>
                            $eliminacionId,

                        'juego_id' =>
                            $preview[
                                'juego_id'
                            ],

                        'title_id' =>
                            $preview[
                                'title_id'
                            ],

                        'componentes' =>
                            $preview[
                                'cantidad_componentes'
                            ],

                        'tamano_bytes' =>
                            $preview[
                                'tamano_liberable_bytes'
                            ],
                    ],
                    JSON_UNESCAPED_UNICODE
                    | JSON_UNESCAPED_SLASHES
                ),
            ]);

            $pdo->commit();

        } catch (Throwable $e) {
            if ($pdo->inTransaction()) {
                $pdo->rollBack();
            }

            throw $e;
        }

        ctps3_respuesta_json([
            'ok' => true,
            'version' => '1.0.0',

            'eliminacion_id' =>
                $eliminacionId,

            'estado' =>
                'PENDIENTE',

            'mensaje' =>
                'Eliminación encolada',
        ], 202);
    }


    if ($accion === 'ESTADO') {
        $eliminacionId =
            filter_var(
                $datos['eliminacion_id']
                    ?? null,
                FILTER_VALIDATE_INT
            );

        if (
            !$eliminacionId
            || $eliminacionId < 1
        ) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'ELIMINACION_INVALIDA',
            ], 422);
        }

        $consulta =
            $pdo->prepare("
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
                    iniciada_utc,
                    actualizada_utc,
                    finalizada_utc,
                    mensaje,
                    error_detalle

                FROM eliminaciones_juegos

                WHERE id=?

                LIMIT 1
            ");

        $consulta->execute([
            (int) $eliminacionId,
        ]);

        $fila =
            $consulta->fetch();

        if (!$fila) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'ELIMINACION_NO_EXISTE',
            ], 404);
        }

        $consultaComponentes =
            $pdo->prepare("
                SELECT
                    id,
                    juego_componente_id,
                    tipo,
                    ruta_remota,
                    tamano_bytes,
                    estado,
                    mensaje,
                    http_codigo,
                    respuesta_bytes,
                    creado_utc,
                    actualizado_utc

                FROM
                    eliminaciones_juegos_componentes

                WHERE eliminacion_id=?

                ORDER BY id ASC
            ");

        $consultaComponentes
            ->execute([
                (int) $eliminacionId,
            ]);

        $componentes = [];

        foreach (
            $consultaComponentes
            as $componente
        ) {
            $componentes[] = [
                'id' =>
                    (int) $componente['id'],

                'juego_componente_id' =>
                    (int) $componente[
                        'juego_componente_id'
                    ],

                'tipo' =>
                    (string) $componente[
                        'tipo'
                    ],

                'ruta_remota' =>
                    (string) $componente[
                        'ruta_remota'
                    ],

                'tamano_bytes' =>
                    $componente[
                        'tamano_bytes'
                    ] !== null
                        ? (int) $componente[
                            'tamano_bytes'
                        ]
                        : null,

                'estado' =>
                    (string) $componente[
                        'estado'
                    ],

                'mensaje' =>
                    $componente['mensaje']
                        !== null
                            ? (string) $componente[
                                'mensaje'
                            ]
                            : null,

                'http_codigo' =>
                    $componente[
                        'http_codigo'
                    ] !== null
                        ? (int) $componente[
                            'http_codigo'
                        ]
                        : null,

                'respuesta_bytes' =>
                    $componente[
                        'respuesta_bytes'
                    ] !== null
                        ? (int) $componente[
                            'respuesta_bytes'
                        ]
                        : null,

                'creado_utc' =>
                    (string) $componente[
                        'creado_utc'
                    ],

                'actualizado_utc' =>
                    (string) $componente[
                        'actualizado_utc'
                    ],
            ];
        }

        ctps3_respuesta_json([
            'ok' => true,
            'version' => '1.0.0',

            'eliminacion' => [
                'id' =>
                    (int) $fila['id'],

                'juego_id' =>
                    (int) $fila[
                        'juego_id'
                    ],

                'nombre' =>
                    (string) $fila[
                        'nombre'
                    ],

                'title_id' =>
                    $fila['title_id']
                        !== null
                            ? (string) $fila[
                                'title_id'
                            ]
                            : null,

                'tipo_principal' =>
                    (string) $fila[
                        'tipo_principal'
                    ],

                'estado' =>
                    (string) $fila[
                        'estado'
                    ],

                'componentes_total' =>
                    (int) $fila[
                        'componentes_total'
                    ],

                'componentes_eliminados' =>
                    (int) $fila[
                        'componentes_eliminados'
                    ],

                'tamano_objetivo_bytes' =>
                    $fila[
                        'tamano_objetivo_bytes'
                    ] !== null
                        ? (int) $fila[
                            'tamano_objetivo_bytes'
                        ]
                        : null,

                'tamano_completo' =>
                    (bool) $fila[
                        'tamano_completo'
                    ],

                'creada_utc' =>
                    (string) $fila[
                        'creada_utc'
                    ],

                'iniciada_utc' =>
                    $fila['iniciada_utc']
                        !== null
                            ? (string) $fila[
                                'iniciada_utc'
                            ]
                            : null,

                'actualizada_utc' =>
                    (string) $fila[
                        'actualizada_utc'
                    ],

                'finalizada_utc' =>
                    $fila['finalizada_utc']
                        !== null
                            ? (string) $fila[
                                'finalizada_utc'
                            ]
                            : null,

                'mensaje' =>
                    $fila['mensaje']
                        !== null
                            ? (string) $fila[
                                'mensaje'
                            ]
                            : null,

                'error_detalle' =>
                    $fila['error_detalle']
                        !== null
                            ? (string) $fila[
                                'error_detalle'
                            ]
                            : null,

                'componentes' =>
                    $componentes,
            ],
        ]);
    }


    ctps3_respuesta_json([
        'ok' => false,
        'error' =>
            'ACCION_NO_SOPORTADA',
    ], 422);

} catch (JsonException $e) {
    ctps3_respuesta_json([
        'ok' => false,
        'error' =>
            'JSON_INVALIDO',
    ], 400);

} catch (Throwable $e) {
    error_log(
        'CTPS3 api/eliminar-juego.php: '
        . get_class($e)
        . ': '
        . $e->getMessage()
    );

    ctps3_respuesta_json([
        'ok' => false,
        'error' =>
            'ERROR_INTERNO',
    ], 500);
}
