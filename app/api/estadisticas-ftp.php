<?php

declare(strict_types=1);

require_once __DIR__ . '/../includes/aplicacion.php';

ctps3_exigir_metodo('GET');

try {
    $pdo = ctps3_bd();


    $version =
        $pdo->query("
            SELECT valor
            FROM meta
            WHERE clave='telemetria_ftp_version'
            LIMIT 1
        ")->fetchColumn();


    $desde =
        $pdo->query("
            SELECT valor
            FROM meta
            WHERE clave='telemetria_ftp_desde_utc'
            LIMIT 1
        ")->fetchColumn();


    if (
        $version === false
        || $version === null
        || (string) $version !== '1.0.0'
        || $desde === false
        || $desde === null
        || trim((string) $desde) === ''
    ) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' => 'TELEMETRIA_NO_DISPONIBLE',
        ], 503);
    }


    $desde = (string) $desde;


    /*
     * =====================================================
     * SESIONES FTP REALES
     * =====================================================
     */

    $sesionesResumen =
        $pdo->query("
            SELECT
                COUNT(*) AS sesiones,

                COALESCE(
                    SUM(bytes_ftp),
                    0
                ) AS bytes_ftp,

                COALESCE(
                    SUM(duracion_segundos),
                    0
                ) AS duracion_segundos,

                COALESCE(
                    SUM(bytes_ftp)
                    /
                    NULLIF(
                        SUM(duracion_segundos),
                        0
                    ),
                    0
                ) AS velocidad_media_bps,

                COALESCE(
                    SUM(
                        CASE
                            WHEN reanudacion=1
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS sesiones_reanudadas,

                COALESCE(
                    SUM(
                        CASE
                            WHEN resultado='COMPLETADO'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS sesiones_completadas,

                COALESCE(
                    SUM(
                        CASE
                            WHEN resultado='INCOMPLETO'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS sesiones_incompletas,

                COALESCE(
                    SUM(
                        CASE
                            WHEN resultado='ERROR'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS sesiones_error,

                COALESCE(
                    SUM(
                        CASE
                            WHEN resultado='CANCELADO'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS sesiones_canceladas,

                COALESCE(
                    SUM(
                        CASE
                            WHEN resultado='PAUSADO'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS sesiones_pausadas

            FROM transferencia_intentos
        ")->fetch();


    /*
     * =====================================================
     * TRANSFERENCIAS EN EL PERIODO DE TELEMETRIA
     *
     * Una transferencia pertenece al periodo si:
     * - fue creada después del inicio de 8B; o
     * - finalizó después del inicio de 8B; o
     * - posee al menos una sesión FTP registrada.
     * =====================================================
     */

    $consultaResumen =
        $pdo->prepare("
            WITH sesiones AS (
                SELECT
                    transferencia_id,

                    COUNT(*) AS sesiones,

                    COALESCE(
                        SUM(bytes_ftp),
                        0
                    ) AS bytes_ftp,

                    COALESCE(
                        SUM(duracion_segundos),
                        0
                    ) AS duracion_ftp,

                    COALESCE(
                        SUM(
                            CASE
                                WHEN reanudacion=1
                                THEN 1
                                ELSE 0
                            END
                        ),
                        0
                    ) AS sesiones_reanudadas

                FROM transferencia_intentos

                GROUP BY transferencia_id
            )

            SELECT
                COUNT(*) AS transferencias_periodo,

                COALESCE(
                    SUM(
                        CASE
                            WHEN t.estado='COMPLETADO'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS completadas,

                COALESCE(
                    SUM(
                        CASE
                            WHEN t.estado='YA_EXISTE'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS ya_existe,

                COALESCE(
                    SUM(
                        CASE
                            WHEN t.estado='ERROR'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS errores,

                COALESCE(
                    SUM(
                        CASE
                            WHEN t.estado='CANCELADO'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS canceladas,

                COALESCE(
                    SUM(
                        CASE
                            WHEN t.estado='CONFLICTO'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS conflictos,

                COALESCE(
                    SUM(
                        CASE
                            WHEN t.estado IN (
                                'COMPLETADO',
                                'YA_EXISTE'
                            )
                            THEN t.tamano_total
                            ELSE 0
                        END
                    ),
                    0
                ) AS bytes_validados,

                COALESCE(
                    SUM(
                        CASE
                            WHEN t.estado IN (
                                'COMPLETADO',
                                'YA_EXISTE'
                            )
                            THEN
                                COALESCE(
                                    s.bytes_ftp,
                                    0
                                )
                            ELSE 0
                        END
                    ),
                    0
                ) AS bytes_ftp_en_validadas,

                COALESCE(
                    SUM(
                        CASE
                            WHEN t.estado='YA_EXISTE'
                            THEN t.tamano_total
                            ELSE 0
                        END
                    ),
                    0
                ) AS bytes_ya_existian

            FROM transferencias t

            LEFT JOIN sesiones s
                ON s.transferencia_id=t.id

            WHERE
                t.creada_utc >= :desde_creada

                OR COALESCE(
                    t.finalizada_utc,
                    ''
                ) >= :desde_finalizada

                OR COALESCE(
                    s.sesiones,
                    0
                ) > 0
        ");


    $consultaResumen->execute([
        ':desde_creada' =>
            $desde,

        ':desde_finalizada' =>
            $desde,
    ]);


    $resumenTransferencias =
        $consultaResumen->fetch();


    $bytesFtp =
        (int) (
            $sesionesResumen[
                'bytes_ftp'
            ]
            ?? 0
        );


    $bytesValidados =
        (int) (
            $resumenTransferencias[
                'bytes_validados'
            ]
            ?? 0
        );


    $bytesFtpValidadas =
        (int) (
            $resumenTransferencias[
                'bytes_ftp_en_validadas'
            ]
            ?? 0
        );


    $bytesReutilizados =
        max(
            0,
            $bytesValidados
            - $bytesFtpValidadas
        );


    $bytesFtpNoValidados =
        max(
            0,
            $bytesFtp
            - $bytesFtpValidadas
        );


    $porcentajeReutilizado =
        $bytesValidados > 0
            ? round(
                (
                    $bytesReutilizados
                    / $bytesValidados
                ) * 100,
                1
            )
            : null;


    /*
     * =====================================================
     * HISTORIAL DE TRANSFERENCIAS DEL PERIODO
     * =====================================================
     */

    $consultaTransferencias =
        $pdo->prepare("
            WITH sesiones AS (
                SELECT
                    transferencia_id,

                    COUNT(*) AS sesiones_ftp,

                    COALESCE(
                        SUM(bytes_ftp),
                        0
                    ) AS bytes_ftp,

                    COALESCE(
                        SUM(duracion_segundos),
                        0
                    ) AS duracion_ftp_segundos,

                    COALESCE(
                        SUM(
                            CASE
                                WHEN reanudacion=1
                                THEN 1
                                ELSE 0
                            END
                        ),
                        0
                    ) AS sesiones_reanudadas

                FROM transferencia_intentos

                GROUP BY transferencia_id
            )

            SELECT
                t.id,
                t.nombre_snapshot,
                t.estado,
                t.tamano_total,

                t.creada_utc,
                t.iniciada_utc,
                t.finalizada_utc,
                t.actualizada_utc,

                t.error_codigo,

                COALESCE(
                    s.sesiones_ftp,
                    0
                ) AS sesiones_ftp,

                COALESCE(
                    s.bytes_ftp,
                    0
                ) AS bytes_ftp,

                COALESCE(
                    s.duracion_ftp_segundos,
                    0
                ) AS duracion_ftp_segundos,

                COALESCE(
                    s.sesiones_reanudadas,
                    0
                ) AS sesiones_reanudadas,

                CASE
                    WHEN t.estado IN (
                        'COMPLETADO',
                        'YA_EXISTE'
                    )
                    THEN MAX(
                        t.tamano_total
                        - COALESCE(
                            s.bytes_ftp,
                            0
                        ),
                        0
                    )
                    ELSE 0
                END AS bytes_reutilizados

            FROM transferencias t

            LEFT JOIN sesiones s
                ON s.transferencia_id=t.id

            WHERE
                t.creada_utc >= :desde_creada

                OR COALESCE(
                    t.finalizada_utc,
                    ''
                ) >= :desde_finalizada

                OR COALESCE(
                    s.sesiones_ftp,
                    0
                ) > 0

            ORDER BY
                COALESCE(
                    t.finalizada_utc,
                    t.actualizada_utc,
                    t.creada_utc
                ) DESC,
                t.id DESC

            LIMIT 30
        ");


    $consultaTransferencias->execute([
        ':desde_creada' =>
            $desde,

        ':desde_finalizada' =>
            $desde,
    ]);


    $transferencias = [];

    foreach (
        $consultaTransferencias
        as $fila
    ) {
        foreach ([
            'id',
            'tamano_total',
            'sesiones_ftp',
            'bytes_ftp',
            'sesiones_reanudadas',
            'bytes_reutilizados',
        ] as $campo) {
            $fila[$campo] =
                (int) $fila[$campo];
        }

        $fila[
            'duracion_ftp_segundos'
        ] =
            (float) $fila[
                'duracion_ftp_segundos'
            ];

        $transferencias[] =
            $fila;
    }


    /*
     * =====================================================
     * HISTORIAL DE SESIONES FTP
     * =====================================================
     */

    $consultaSesiones =
        $pdo->query("
            SELECT
                ti.id,
                ti.transferencia_id,
                ti.numero_sesion,
                ti.intento_worker,

                ti.pid,
                ti.reanudacion,

                ti.bytes_remotos_inicio,
                ti.bytes_remotos_fin,
                ti.bytes_ftp,

                ti.duracion_segundos,
                ti.velocidad_media_bps,

                ti.resultado,
                ti.codigo_lftp,

                ti.error_codigo,

                ti.iniciada_utc,
                ti.finalizada_utc,

                t.nombre_snapshot

            FROM transferencia_intentos ti

            INNER JOIN transferencias t
                ON t.id=ti.transferencia_id

            ORDER BY
                ti.id DESC

            LIMIT 30
        ");


    $sesiones = [];

    foreach (
        $consultaSesiones
        as $fila
    ) {
        foreach ([
            'id',
            'transferencia_id',
            'numero_sesion',
            'intento_worker',
            'bytes_remotos_inicio',
            'bytes_remotos_fin',
            'bytes_ftp',
        ] as $campo) {
            $fila[$campo] =
                $fila[$campo] !== null
                    ? (int) $fila[$campo]
                    : null;
        }

        $fila['pid'] =
            $fila['pid'] !== null
                ? (int) $fila['pid']
                : null;

        $fila['codigo_lftp'] =
            $fila['codigo_lftp'] !== null
                ? (int) $fila['codigo_lftp']
                : null;

        $fila['reanudacion'] =
            (bool) $fila['reanudacion'];

        $fila['duracion_segundos'] =
            (float) (
                $fila[
                    'duracion_segundos'
                ]
                ?? 0
            );

        $fila['velocidad_media_bps'] =
            (float) (
                $fila[
                    'velocidad_media_bps'
                ]
                ?? 0
            );

        $sesiones[] =
            $fila;
    }


    /*
     * =====================================================
     * RESULTADOS DE SESIONES
     * =====================================================
     */

    $resultados = [];

    $consultaResultados =
        $pdo->query("
            SELECT
                resultado,
                COUNT(*) AS cantidad

            FROM transferencia_intentos

            GROUP BY resultado

            ORDER BY
                cantidad DESC,
                resultado ASC
        ");


    foreach (
        $consultaResultados
        as $fila
    ) {
        $resultados[
            $fila['resultado']
        ] =
            (int) $fila['cantidad'];
    }


    ctps3_respuesta_json([
        'ok' => true,

        'version' =>
            '1.0.0',

        'telemetria_version' =>
            (string) $version,

        'desde_utc' =>
            $desde,

        'resumen' => [
            'transferencias_periodo' =>
                (int) (
                    $resumenTransferencias[
                        'transferencias_periodo'
                    ]
                    ?? 0
                ),

            'completadas' =>
                (int) (
                    $resumenTransferencias[
                        'completadas'
                    ]
                    ?? 0
                ),

            'ya_existe' =>
                (int) (
                    $resumenTransferencias[
                        'ya_existe'
                    ]
                    ?? 0
                ),

            'errores' =>
                (int) (
                    $resumenTransferencias[
                        'errores'
                    ]
                    ?? 0
                ),

            'canceladas' =>
                (int) (
                    $resumenTransferencias[
                        'canceladas'
                    ]
                    ?? 0
                ),

            'conflictos' =>
                (int) (
                    $resumenTransferencias[
                        'conflictos'
                    ]
                    ?? 0
                ),

            'sesiones_ftp' =>
                (int) (
                    $sesionesResumen[
                        'sesiones'
                    ]
                    ?? 0
                ),

            'sesiones_reanudadas' =>
                (int) (
                    $sesionesResumen[
                        'sesiones_reanudadas'
                    ]
                    ?? 0
                ),

            'sesiones_completadas' =>
                (int) (
                    $sesionesResumen[
                        'sesiones_completadas'
                    ]
                    ?? 0
                ),

            'sesiones_incompletas' =>
                (int) (
                    $sesionesResumen[
                        'sesiones_incompletas'
                    ]
                    ?? 0
                ),

            'sesiones_error' =>
                (int) (
                    $sesionesResumen[
                        'sesiones_error'
                    ]
                    ?? 0
                ),

            'sesiones_canceladas' =>
                (int) (
                    $sesionesResumen[
                        'sesiones_canceladas'
                    ]
                    ?? 0
                ),

            'sesiones_pausadas' =>
                (int) (
                    $sesionesResumen[
                        'sesiones_pausadas'
                    ]
                    ?? 0
                ),

            'bytes_ftp' =>
                $bytesFtp,

            'bytes_ftp_en_validadas' =>
                $bytesFtpValidadas,

            'bytes_ftp_no_validados' =>
                $bytesFtpNoValidados,

            'bytes_validados' =>
                $bytesValidados,

            'bytes_reutilizados' =>
                $bytesReutilizados,

            'bytes_ya_existian' =>
                (int) (
                    $resumenTransferencias[
                        'bytes_ya_existian'
                    ]
                    ?? 0
                ),

            'porcentaje_reutilizado' =>
                $porcentajeReutilizado,

            'duracion_ftp_segundos' =>
                (float) (
                    $sesionesResumen[
                        'duracion_segundos'
                    ]
                    ?? 0
                ),

            'velocidad_media_bps' =>
                (float) (
                    $sesionesResumen[
                        'velocidad_media_bps'
                    ]
                    ?? 0
                ),
        ],

        'resultados_sesiones' =>
            $resultados,

        'transferencias' =>
            $transferencias,

        'sesiones' =>
            $sesiones,
    ]);

} catch (Throwable $e) {

    error_log(
        '[CTPS3][estadisticas-ftp] '
        . $e->getMessage()
    );

    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'ERROR_INTERNO',
    ], 500);
}
