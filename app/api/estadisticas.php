<?php

declare(strict_types=1);

require_once __DIR__ . '/../includes/aplicacion.php';

ctps3_exigir_metodo('GET');

try {
    $pdo = ctps3_bd();

    $resumen = $pdo->query("
        SELECT
            COUNT(*) AS total,

            SUM(
                CASE
                    WHEN estado='COMPLETADO'
                    THEN 1
                    ELSE 0
                END
            ) AS completadas,

            SUM(
                CASE
                    WHEN estado='YA_EXISTE'
                    THEN 1
                    ELSE 0
                END
            ) AS ya_existe,

            SUM(
                CASE
                    WHEN estado='ERROR'
                    THEN 1
                    ELSE 0
                END
            ) AS errores,

            SUM(
                CASE
                    WHEN estado='CANCELADO'
                    THEN 1
                    ELSE 0
                END
            ) AS canceladas,

            SUM(
                CASE
                    WHEN estado='CONFLICTO'
                    THEN 1
                    ELSE 0
                END
            ) AS conflictos,

            SUM(
                CASE
                    WHEN reanudada=1
                    THEN 1
                    ELSE 0
                END
            ) AS reanudadas,

            COALESCE(
                SUM(
                    CASE
                        WHEN estado='COMPLETADO'
                        THEN tamano_total
                        ELSE 0
                    END
                ),
                0
            ) AS bytes_completados,

            COALESCE(
                SUM(
                    CASE
                        WHEN estado IN (
                            'COMPLETADO',
                            'YA_EXISTE'
                        )
                        THEN tamano_total
                        ELSE 0
                    END
                ),
                0
            ) AS bytes_validados,

            COALESCE(
                AVG(
                    CASE
                        WHEN
                            estado='COMPLETADO'
                            AND velocidad_promedio_bps > 0
                        THEN velocidad_promedio_bps
                        ELSE NULL
                    END
                ),
                0
            ) AS velocidad_media_bps,

            COALESCE(
                SUM(
                    CASE
                        WHEN
                            iniciada_utc IS NOT NULL
                            AND finalizada_utc IS NOT NULL
                            AND estado='COMPLETADO'
                        THEN
                            (
                                julianday(finalizada_utc)
                                - julianday(iniciada_utc)
                            ) * 86400.0
                        ELSE 0
                    END
                ),
                0
            ) AS tiempo_transferencia_segundos

        FROM transferencias
    ")->fetch();

    $correctas =
        (int) $resumen['completadas']
        + (int) $resumen['ya_existe'];

    $terminales =
        (int) $resumen['completadas']
        + (int) $resumen['ya_existe']
        + (int) $resumen['errores']
        + (int) $resumen['canceladas']
        + (int) $resumen['conflictos'];

    $tasaCorrectas =
        $terminales > 0
            ? round(
                (
                    $correctas
                    / $terminales
                ) * 100,
                1
            )
            : null;


    $consultaJuegos = $pdo->query("
        SELECT
            COALESCE(
                a.titulo_juego,
                t.nombre_snapshot
            ) AS juego,

            a.codigo_juego AS codigo,

            COUNT(*) AS transferencias,

            SUM(
                CASE
                    WHEN t.estado='COMPLETADO'
                    THEN 1
                    ELSE 0
                END
            ) AS completadas,

            SUM(
                CASE
                    WHEN t.estado='YA_EXISTE'
                    THEN 1
                    ELSE 0
                END
            ) AS ya_existe,

            SUM(
                CASE
                    WHEN t.estado='ERROR'
                    THEN 1
                    ELSE 0
                END
            ) AS errores,

            SUM(
                CASE
                    WHEN t.estado='CANCELADO'
                    THEN 1
                    ELSE 0
                END
            ) AS canceladas,

            SUM(
                CASE
                    WHEN t.reanudada=1
                    THEN 1
                    ELSE 0
                END
            ) AS reanudadas,

            COALESCE(
                SUM(
                    CASE
                        WHEN t.estado='COMPLETADO'
                        THEN t.tamano_total
                        ELSE 0
                    END
                ),
                0
            ) AS bytes_completados,

            MAX(
                COALESCE(
                    t.finalizada_utc,
                    t.actualizada_utc,
                    t.creada_utc
                )
            ) AS ultima_actividad_utc

        FROM transferencias t

        LEFT JOIN archivos_locales a
            ON a.id=t.archivo_id

        GROUP BY
            COALESCE(
                a.codigo_juego,
                a.titulo_juego,
                t.nombre_snapshot
            )

        ORDER BY
            ultima_actividad_utc DESC,
            juego COLLATE NOCASE ASC

        LIMIT 100
    ");

    $juegos = [];

    foreach ($consultaJuegos as $fila) {
        foreach ([
            'transferencias',
            'completadas',
            'ya_existe',
            'errores',
            'canceladas',
            'reanudadas',
            'bytes_completados',
        ] as $campo) {
            $fila[$campo] =
                (int) $fila[$campo];
        }

        $juegos[] = $fila;
    }


    $consultaEstados = $pdo->query("
        SELECT
            estado,
            COUNT(*) AS cantidad
        FROM transferencias
        GROUP BY estado
        ORDER BY cantidad DESC, estado ASC
    ");

    $estados = [];

    foreach ($consultaEstados as $fila) {
        $estados[
            $fila['estado']
        ] = (int) $fila['cantidad'];
    }


    ctps3_respuesta_json([
        'ok' => true,

        'resumen' => [
            'total' =>
                (int) $resumen['total'],

            'completadas' =>
                (int) $resumen['completadas'],

            'ya_existe' =>
                (int) $resumen['ya_existe'],

            'correctas' =>
                $correctas,

            'errores' =>
                (int) $resumen['errores'],

            'canceladas' =>
                (int) $resumen['canceladas'],

            'conflictos' =>
                (int) $resumen['conflictos'],

            'reanudadas' =>
                (int) $resumen['reanudadas'],

            'bytes_completados' =>
                (int) $resumen[
                    'bytes_completados'
                ],

            'bytes_validados' =>
                (int) $resumen[
                    'bytes_validados'
                ],

            'velocidad_media_bps' =>
                (float) $resumen[
                    'velocidad_media_bps'
                ],

            'tiempo_transferencia_segundos' =>
                (int) round(
                    (float) $resumen[
                        'tiempo_transferencia_segundos'
                    ]
                ),

            'tasa_correctas' =>
                $tasaCorrectas,
        ],

        'estados' =>
            $estados,

        'juegos' =>
            $juegos,
    ]);

} catch (Throwable $e) {
    error_log(
        '[CTPS3][estadisticas] '
        . $e->getMessage()
    );

    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'ERROR_INTERNO',
    ], 500);
}
