<?php

declare(strict_types=1);

require_once __DIR__ . '/../includes/aplicacion.php';

ctps3_exigir_metodo('GET');


function ctps3_9d_segundos_desde(
    ?string $fecha
): ?int {

    if (
        $fecha === null
        || trim($fecha) === ''
    ) {
        return null;
    }

    $timestamp = strtotime(
        $fecha
    );

    if ($timestamp === false) {
        return null;
    }

    return max(
        0,
        time() - $timestamp
    );
}


function ctps3_9d_comprobacion(
    string $codigo,
    string $estado,
    string $titulo,
    string $detalle
): array {

    return [
        'codigo' =>
            $codigo,

        'estado' =>
            $estado,

        'titulo' =>
            $titulo,

        'detalle' =>
            $detalle,
    ];
}


try {

    $pdo = ctps3_bd();


    /*
     * =====================================================
     * METADATA
     * =====================================================
     */

    $consultaMeta =
        $pdo->query("
            SELECT
                clave,
                valor

            FROM meta

            WHERE clave IN (
                'schema_version',
                'resiliencia_worker_version',
                'prueba_resiliencia_9c_version',
                'panel_resiliencia_version'
            )
        ");


    $meta = [];

    foreach (
        $consultaMeta
        as $fila
    ) {
        $meta[
            (string) $fila['clave']
        ] =
            (string) $fila['valor'];
    }


    /*
     * =====================================================
     * WORKER
     * =====================================================
     */

    $worker =
        $pdo->query("
            SELECT
                estado,
                pid,
                version,
                transferencia_id,

                heartbeat_utc,
                iniciado_utc,

                mensaje

            FROM worker_estado

            WHERE id=1
        ")->fetch();


    if (!$worker) {
        throw new RuntimeException(
            'No existe worker_estado.id=1'
        );
    }


    $worker['pid'] =
        $worker['pid'] !== null
            ? (int) $worker['pid']
            : null;


    $worker['transferencia_id'] =
        $worker['transferencia_id']
            !== null
            ? (int) $worker[
                'transferencia_id'
            ]
            : null;


    $heartbeatSegundos =
        ctps3_9d_segundos_desde(
            $worker['heartbeat_utc']
                ?? null
        );


    $heartbeatOk =
        $heartbeatSegundos !== null
        && $heartbeatSegundos <= 30;


    /*
     * =====================================================
     * CONTADORES OPERATIVOS
     * =====================================================
     */

    $estadosEjecucion = "
        'COMPROBANDO',
        'PREPARANDO',
        'TRANSFIRIENDO',
        'PAUSANDO',
        'CANCELANDO',
        'VERIFICANDO',
        'REINTENTANDO'
    ";


    $transferenciasEjecucion =
        (int) $pdo->query("
            SELECT COUNT(*)

            FROM transferencias

            WHERE estado IN (
                {$estadosEjecucion}
            )
        ")->fetchColumn();


    $transferenciasCola =
        (int) $pdo->query("
            SELECT COUNT(*)

            FROM transferencias

            WHERE estado='EN_COLA'
        ")->fetchColumn();


    $transferenciasPausadas =
        (int) $pdo->query("
            SELECT COUNT(*)

            FROM transferencias

            WHERE estado='PAUSADO'
        ")->fetchColumn();


    $sesionesEnCurso =
        (int) $pdo->query("
            SELECT COUNT(*)

            FROM transferencia_intentos

            WHERE resultado='EN_CURSO'
        ")->fetchColumn();


    $sesionesInconsistentes =
        (int) $pdo->query("
            SELECT COUNT(*)

            FROM transferencia_intentos ti

            LEFT JOIN transferencias t
                ON t.id=ti.transferencia_id

            WHERE
                ti.resultado='EN_CURSO'

                AND (
                    t.id IS NULL
                    OR t.estado!='TRANSFIRIENDO'
                )
        ")->fetchColumn();


    /*
     * =====================================================
     * AUDITORIA DE RECUPERACIONES
     * =====================================================
     */

    $auditoria =
        $pdo->query("
            SELECT
                COUNT(*) AS total,

                COALESCE(
                    SUM(
                        CASE
                            WHEN resuelta_utc IS NULL
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS pendientes,

                COALESCE(
                    SUM(
                        CASE
                            WHEN resuelta_utc IS NOT NULL
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS resueltas,

                COALESCE(
                    SUM(
                        CASE
                            WHEN tipo='SESION_HUERFANA'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS sesiones_huerfanas,

                COALESCE(
                    SUM(
                        CASE
                            WHEN tipo='TRANSFERENCIA_RECUPERADA'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS transferencias_recuperadas,

                MAX(creada_utc)
                    AS ultima_recuperacion_utc

            FROM recuperaciones_worker
        ")->fetch();


    foreach ([
        'total',
        'pendientes',
        'resueltas',
        'sesiones_huerfanas',
        'transferencias_recuperadas',
    ] as $campo) {

        $auditoria[$campo] =
            (int) (
                $auditoria[$campo]
                ?? 0
            );
    }


    /*
     * =====================================================
     * ULTIMAS RECUPERACIONES
     * =====================================================
     */

    $consultaRecuperaciones =
        $pdo->query("
            SELECT
                rw.id,
                rw.tipo,

                rw.transferencia_id,
                rw.sesion_id,

                rw.estado_anterior,
                rw.estado_nuevo,

                rw.pid_anterior,

                rw.bytes_observados,
                rw.bytes_reconciliados,

                rw.detalle,
                rw.detalle_reconciliacion,

                rw.creada_utc,
                rw.resuelta_utc,

                t.nombre_snapshot,

                ti.numero_sesion

            FROM recuperaciones_worker rw

            LEFT JOIN transferencias t
                ON t.id=rw.transferencia_id

            LEFT JOIN transferencia_intentos ti
                ON ti.id=rw.sesion_id

            ORDER BY
                rw.id DESC

            LIMIT 25
        ");


    $recuperaciones = [];


    foreach (
        $consultaRecuperaciones
        as $fila
    ) {

        foreach ([
            'id',
            'transferencia_id',
            'sesion_id',
            'pid_anterior',
            'bytes_observados',
            'bytes_reconciliados',
            'numero_sesion',
        ] as $campo) {

            $fila[$campo] =
                $fila[$campo] !== null
                    ? (int) $fila[$campo]
                    : null;
        }


        $fila['pendiente'] =
            $fila['resuelta_utc'] === null;


        $recuperaciones[] =
            $fila;
    }


    /*
     * =====================================================
     * TRANSFERENCIA ACTUAL DEL WORKER
     * =====================================================
     */

    $transferenciaActual = null;


    if (
        $worker[
            'transferencia_id'
        ] !== null
    ) {

        $consultaActual =
            $pdo->prepare("
                SELECT
                    id,
                    nombre_snapshot,
                    estado,

                    bytes_remotos,
                    tamano_total

                FROM transferencias

                WHERE id=?
            ");


        $consultaActual->execute([
            $worker[
                'transferencia_id'
            ],
        ]);


        $transferenciaActual =
            $consultaActual->fetch();


        if ($transferenciaActual) {

            foreach ([
                'id',
                'bytes_remotos',
                'tamano_total',
            ] as $campo) {

                $transferenciaActual[
                    $campo
                ] =
                    (int) $transferenciaActual[
                        $campo
                    ];
            }
        }
    }


    /*
     * =====================================================
     * COMPROBACIONES AUTOMATICAS
     * =====================================================
     */

    $comprobaciones = [];


    if (
        $heartbeatOk
        && $worker['pid'] !== null
    ) {

        $comprobaciones[] =
            ctps3_9d_comprobacion(
                'WORKER',
                'OK',
                'Worker operativo',
                (
                    'Worker v'
                    . ($worker['version'] ?? '—')
                    . ' con heartbeat '
                    . $heartbeatSegundos
                    . ' s atrás.'
                )
            );

    } else {

        $detalle = [];

        if ($worker['pid'] === null) {
            $detalle[] =
                'PID ausente';
        }

        if (!$heartbeatOk) {
            $detalle[] =
                'heartbeat ausente o atrasado';
        }

        $comprobaciones[] =
            ctps3_9d_comprobacion(
                'WORKER',
                'ERROR',
                'Worker inconsistente',
                implode(
                    ', ',
                    $detalle
                )
            );
    }


    if ($transferenciasEjecucion <= 1) {

        $comprobaciones[] =
            ctps3_9d_comprobacion(
                'CONCURRENCIA',
                'OK',
                'Concurrencia controlada',
                (
                    $transferenciasEjecucion
                    . ' transferencia(s) '
                    . 'en ejecución.'
                )
            );

    } else {

        $comprobaciones[] =
            ctps3_9d_comprobacion(
                'CONCURRENCIA',
                'ERROR',
                'Concurrencia inesperada',
                (
                    $transferenciasEjecucion
                    . ' transferencias aparecen '
                    . 'en ejecución simultánea.'
                )
            );
    }


    if (
        $sesionesEnCurso <= 1
        && $sesionesInconsistentes === 0
    ) {

        $comprobaciones[] =
            ctps3_9d_comprobacion(
                'SESIONES_FTP',
                'OK',
                'Sesiones FTP consistentes',
                (
                    $sesionesEnCurso
                    . ' sesión(es) EN_CURSO '
                    . 'sin inconsistencias.'
                )
            );

    } else {

        $comprobaciones[] =
            ctps3_9d_comprobacion(
                'SESIONES_FTP',
                'ERROR',
                'Sesiones FTP inconsistentes',
                (
                    'EN_CURSO='
                    . $sesionesEnCurso
                    . '; inconsistentes='
                    . $sesionesInconsistentes
                    . '.'
                )
            );
    }


    if (
        $worker[
            'transferencia_id'
        ] === null
        || $transferenciaActual !== null
    ) {

        $comprobaciones[] =
            ctps3_9d_comprobacion(
                'ASIGNACION',
                'OK',
                'Asignación del worker válida',
                (
                    $worker[
                        'transferencia_id'
                    ] === null
                        ? 'El worker no declara una transferencia activa.'
                        : (
                            'La transferencia #'
                            . $worker[
                                'transferencia_id'
                            ]
                            . ' existe en SQLite.'
                        )
                )
            );

    } else {

        $comprobaciones[] =
            ctps3_9d_comprobacion(
                'ASIGNACION',
                'ERROR',
                'Transferencia del worker inexistente',
                (
                    'worker_estado referencia #'
                    . $worker[
                        'transferencia_id'
                    ]
                    . ' pero no existe en transferencias.'
                )
            );
    }


    if (
        $auditoria[
            'pendientes'
        ] === 0
    ) {

        $comprobaciones[] =
            ctps3_9d_comprobacion(
                'RECUPERACIONES',
                'OK',
                'Sin recuperaciones pendientes',
                (
                    $auditoria['resueltas']
                    . ' recuperación(es) '
                    . 'resuelta(s) conservadas.'
                )
            );

    } else {

        $comprobaciones[] =
            ctps3_9d_comprobacion(
                'RECUPERACIONES',
                'ATENCION',
                'Hay reconciliaciones pendientes',
                (
                    $auditoria['pendientes']
                    . ' recuperación(es) esperan '
                    . 'reconciliación remota.'
                )
            );
    }


    $quickCheck =
        (string) $pdo->query(
            "PRAGMA quick_check(1)"
        )->fetchColumn();


    if ($quickCheck === 'ok') {

        $comprobaciones[] =
            ctps3_9d_comprobacion(
                'SQLITE',
                'OK',
                'SQLite consistente',
                'PRAGMA quick_check(1) = ok.'
            );

    } else {

        $comprobaciones[] =
            ctps3_9d_comprobacion(
                'SQLITE',
                'ERROR',
                'SQLite reportó una inconsistencia',
                $quickCheck
            );
    }


    if (
        ($meta[
            'resiliencia_worker_version'
        ] ?? null) === '1.0.0'

        && (
            $meta[
                'prueba_resiliencia_9c_version'
            ] ?? null
        ) === '1.0.0'
    ) {

        $comprobaciones[] =
            ctps3_9d_comprobacion(
                'MOTOR_RESILIENCIA',
                'OK',
                'Motor de resiliencia validado',
                (
                    'Versión 1.0.0 con prueba '
                    . 'funcional real 9C aprobada.'
                )
            );

    } else {

        $comprobaciones[] =
            ctps3_9d_comprobacion(
                'MOTOR_RESILIENCIA',
                'ERROR',
                'Motor de resiliencia no validado',
                'Falta metadata requerida.'
            );
    }


    /*
     * =====================================================
     * SALUD GENERAL
     * =====================================================
     */

    $estadoGeneral =
        'SALUDABLE';


    foreach (
        $comprobaciones
        as $comprobacion
    ) {

        if (
            $comprobacion['estado']
                === 'ERROR'
        ) {
            $estadoGeneral =
                'INCIDENTE';

            break;
        }


        if (
            $comprobacion['estado']
                === 'ATENCION'
            && $estadoGeneral
                === 'SALUDABLE'
        ) {
            $estadoGeneral =
                'ATENCION';
        }
    }


    ctps3_respuesta_json([
        'ok' =>
            true,

        'version' =>
            '1.0.0',

        'estado_general' =>
            $estadoGeneral,

        'worker' => [
            'estado' =>
                $worker['estado'],

            'version' =>
                $worker['version'],

            'pid' =>
                $worker['pid'],

            'transferencia_id' =>
                $worker[
                    'transferencia_id'
                ],

            'heartbeat_utc' =>
                $worker[
                    'heartbeat_utc'
                ],

            'heartbeat_segundos' =>
                $heartbeatSegundos,

            'heartbeat_ok' =>
                $heartbeatOk,

            'iniciado_utc' =>
                $worker[
                    'iniciado_utc'
                ],

            'mensaje' =>
                $worker[
                    'mensaje'
                ],

            'transferencia_actual' =>
                $transferenciaActual,
        ],

        'operacion' => [
            'transferencias_ejecucion' =>
                $transferenciasEjecucion,

            'transferencias_cola' =>
                $transferenciasCola,

            'transferencias_pausadas' =>
                $transferenciasPausadas,

            'sesiones_en_curso' =>
                $sesionesEnCurso,

            'sesiones_inconsistentes' =>
                $sesionesInconsistentes,
        ],

        'auditoria' =>
            $auditoria,

        'comprobaciones' =>
            $comprobaciones,

        'recuperaciones' =>
            $recuperaciones,

        'sqlite' => [
            'quick_check' =>
                $quickCheck,
        ],

        'meta' => [
            'schema_version' =>
                $meta[
                    'schema_version'
                ] ?? null,

            'resiliencia_worker_version' =>
                $meta[
                    'resiliencia_worker_version'
                ] ?? null,

            'prueba_resiliencia_9c_version' =>
                $meta[
                    'prueba_resiliencia_9c_version'
                ] ?? null,

            'panel_resiliencia_version' =>
                $meta[
                    'panel_resiliencia_version'
                ] ?? null,
        ],
    ]);

} catch (Throwable $e) {

    error_log(
        '[CTPS3][resiliencia] '
        . $e->getMessage()
    );


    ctps3_respuesta_json([
        'ok' =>
            false,

        'error' =>
            'ERROR_INTERNO',
    ], 500);
}
