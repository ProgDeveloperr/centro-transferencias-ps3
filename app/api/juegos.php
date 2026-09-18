<?php

declare(strict_types=1);

require_once __DIR__ . '/../includes/aplicacion.php';

ctps3_exigir_metodo('GET');

try {
    $pdo = ctps3_bd();

    /*
     * =====================================================
     * Metadatos del inventario
     * =====================================================
     */

    $consultaMeta = $pdo->query("
        SELECT
            clave,
            valor
        FROM meta
        WHERE clave LIKE 'inventario_juegos_%'
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
     * Juegos lógicos
     * =====================================================
     */

    $consultaJuegos = $pdo->query("
        SELECT
            id,
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

        FROM juegos_ps3

        ORDER BY
            disponible DESC,
            nombre COLLATE NOCASE ASC,
            id ASC
    ");

    /*
     * =====================================================
     * Componentes físicos
     * =====================================================
     */

    $consultaComponentes = $pdo->query("
        SELECT
            id,
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

        FROM juegos_ps3_componentes

        ORDER BY
            juego_id ASC,
            disponible DESC,
            tipo ASC,
            ruta_remota COLLATE NOCASE ASC
    ");

    $componentesPorJuego = [];

    foreach (
        $consultaComponentes
        as $fila
    ) {
        $juegoId =
            (int) $fila['juego_id'];

        $componente = [
            'id' =>
                (int) $fila['id'],

            'juego_id' =>
                $juegoId,

            'tipo' =>
                (string) $fila['tipo'],

            'ruta_remota' =>
                (string) $fila[
                    'ruta_remota'
                ],

            'title_id_sfo' =>
                $fila['title_id_sfo']
                    !== null
                        ? (string) $fila[
                            'title_id_sfo'
                        ]
                        : null,

            'nombre_sfo' =>
                $fila['nombre_sfo']
                    !== null
                        ? (string) $fila[
                            'nombre_sfo'
                        ]
                        : null,

            'categoria_sfo' =>
                $fila['categoria_sfo']
                    !== null
                        ? (string) $fila[
                            'categoria_sfo'
                        ]
                        : null,

            'bootable' =>
                $fila['bootable']
                    !== null
                        ? (bool) $fila[
                            'bootable'
                        ]
                        : null,

            'app_ver' =>
                $fila['app_ver']
                    !== null
                        ? (string) $fila[
                            'app_ver'
                        ]
                        : null,

            'version' =>
                $fila['version']
                    !== null
                        ? (string) $fila[
                            'version'
                        ]
                        : null,

            'tamano_bytes' =>
                $fila['tamano_bytes']
                    !== null
                        ? (int) $fila[
                            'tamano_bytes'
                        ]
                        : null,

            'disponible' =>
                (bool) $fila[
                    'disponible'
                ],

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

        $componentesPorJuego[
            $juegoId
        ][] = $componente;
    }

    /*
     * =====================================================
     * Modelo lógico final
     * =====================================================
     */

    $juegos = [];

    $disponibles = 0;
    $inventariosCompletos = 0;

    $componentesTotales = 0;
    $componentesDisponibles = 0;

    $porTipo = [];

    foreach (
        $consultaJuegos
        as $fila
    ) {
        $id =
            (int) $fila['id'];

        $disponible =
            (bool) $fila[
                'disponible'
            ];

        $inventarioCompleto =
            (bool) $fila[
                'inventario_completo'
            ];

        $componentes =
            $componentesPorJuego[
                $id
            ] ?? [];

        if ($disponible) {
            $disponibles++;
        }

        if ($inventarioCompleto) {
            $inventariosCompletos++;
        }

        foreach (
            $componentes
            as $componente
        ) {
            $componentesTotales++;

            if (
                $componente[
                    'disponible'
                ]
            ) {
                $componentesDisponibles++;
            }
        }

        $tipo =
            (string) $fila[
                'tipo_principal'
            ];

        if (!isset($porTipo[$tipo])) {
            $porTipo[$tipo] = 0;
        }

        $porTipo[$tipo]++;

        $tamano =
            $fila['tamano_total_bytes']
                !== null
                    ? (int) $fila[
                        'tamano_total_bytes'
                    ]
                    : null;

        $juegos[] = [
            'id' =>
                $id,

            'clave_logica' =>
                (string) $fila[
                    'clave_logica'
                ],

            'title_id' =>
                $fila['title_id']
                    !== null
                        ? (string) $fila[
                            'title_id'
                        ]
                        : null,

            'nombre' =>
                (string) $fila[
                    'nombre'
                ],

            'tipo_principal' =>
                $tipo,

            'tamano_total_bytes' =>
                $tamano,

            'tamano_conocido' =>
                $tamano !== null,

            'disponible' =>
                $disponible,

            'inventario_completo' =>
                $inventarioCompleto,

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

            'cantidad_componentes' =>
                count($componentes),

            'componentes' =>
                $componentes,
        ];
    }

    ksort($porTipo);

    $ultimoError =
        trim(
            $meta[
                'inventario_juegos_ultimo_error'
            ] ?? ''
        );

    ctps3_respuesta_json([
        'ok' => true,

        'version' => '1.0.0',

        'inventario' => [
            'version' =>
                $meta[
                    'inventario_juegos_version'
                ] ?? null,

            'automatizacion_version' =>
                $meta[
                    'inventario_juegos_automatizacion_version'
                ] ?? null,

            'ultima_ok_utc' =>
                $meta[
                    'inventario_juegos_ultima_ok_utc'
                ] ?? null,

            'ultimo_intento_utc' =>
                $meta[
                    'inventario_juegos_ultimo_intento_utc'
                ] ?? null,

            'duracion_ms' =>
                isset(
                    $meta[
                        'inventario_juegos_duracion_ms'
                    ]
                )
                    ? (int) $meta[
                        'inventario_juegos_duracion_ms'
                    ]
                    : null,

            'ultimo_error' =>
                $ultimoError !== ''
                    ? $ultimoError
                    : null,
        ],

        'resumen' => [
            'juegos' =>
                count($juegos),

            'juegos_disponibles' =>
                $disponibles,

            'juegos_no_disponibles' =>
                count($juegos)
                - $disponibles,

            'inventarios_completos' =>
                $inventariosCompletos,

            'componentes' =>
                $componentesTotales,

            'componentes_disponibles' =>
                $componentesDisponibles,

            'componentes_no_disponibles' =>
                $componentesTotales
                - $componentesDisponibles,

            'por_tipo' =>
                $porTipo,
        ],

        'juegos' =>
            $juegos,
    ]);

} catch (Throwable $e) {
    error_log(
        'CTPS3 api/juegos.php: '
        . get_class($e)
        . ': '
        . $e->getMessage()
    );

    http_response_code(500);

    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'ERROR_INTERNO',
    ]);
}
