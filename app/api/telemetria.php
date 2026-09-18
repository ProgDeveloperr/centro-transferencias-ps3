<?php

declare(strict_types=1);

require_once __DIR__ . '/../includes/aplicacion.php';

ctps3_exigir_metodo('GET');

try {
    $pdo = ctps3_bd();

    $transferenciaId = null;

    if (isset($_GET['transferencia_id'])) {

        $valor =
            filter_var(
                $_GET['transferencia_id'],
                FILTER_VALIDATE_INT,
                [
                    'options' => [
                        'min_range' => 1,
                    ],
                ]
            );

        if ($valor === false) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' => 'TRANSFERENCIA_INVALIDA',
            ], 400);
        }

        $transferenciaId =
            (int) $valor;
    }


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


    $where = '';
    $parametros = [];

    if ($transferenciaId !== null) {
        $where =
            'WHERE ti.transferencia_id=:transferencia_id';

        $parametros[
            ':transferencia_id'
        ] = $transferenciaId;
    }


    $stmt =
        $pdo->prepare("
            SELECT
                COUNT(*) AS sesiones,

                COALESCE(
                    SUM(ti.bytes_ftp),
                    0
                ) AS bytes_ftp,

                COALESCE(
                    SUM(ti.duracion_segundos),
                    0
                ) AS duracion_segundos,

                COALESCE(
                    SUM(ti.bytes_ftp)
                    /
                    NULLIF(
                        SUM(ti.duracion_segundos),
                        0
                    ),
                    0
                ) AS velocidad_media_bps,

                COALESCE(
                    SUM(
                        CASE
                            WHEN ti.reanudacion=1
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS sesiones_reanudadas

            FROM transferencia_intentos ti

            {$where}
        ");

    $stmt->execute(
        $parametros
    );

    $resumen = $stmt->fetch();


    $stmt =
        $pdo->prepare("
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
                ti.error_detalle,
                ti.log_archivo,

                ti.iniciada_utc,
                ti.actualizada_utc,
                ti.finalizada_utc,

                t.nombre_snapshot,
                t.estado AS estado_transferencia

            FROM transferencia_intentos ti

            INNER JOIN transferencias t
                ON t.id=ti.transferencia_id

            {$where}

            ORDER BY ti.id DESC

            LIMIT 150
        ");

    $stmt->execute(
        $parametros
    );


    $sesiones = [];

    foreach ($stmt as $fila) {

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
            $fila['duracion_segundos'] !== null
                ? (float) $fila['duracion_segundos']
                : null;

        $fila['velocidad_media_bps'] =
            $fila['velocidad_media_bps'] !== null
                ? (float) $fila['velocidad_media_bps']
                : null;

        $sesiones[] = $fila;
    }


    $stmt =
        $pdo->prepare("
            SELECT
                resultado,
                COUNT(*) AS cantidad

            FROM transferencia_intentos ti

            {$where}

            GROUP BY resultado

            ORDER BY
                cantidad DESC,
                resultado ASC
        ");

    $stmt->execute(
        $parametros
    );

    $resultados = [];

    foreach ($stmt as $fila) {
        $resultados[
            $fila['resultado']
        ] = (int) $fila['cantidad'];
    }


    ctps3_respuesta_json([
        'ok' => true,

        'version' =>
            $version !== false
                ? (string) $version
                : null,

        'desde_utc' =>
            $desde !== false
                ? (string) $desde
                : null,

        'transferencia_id' =>
            $transferenciaId,

        'resumen' => [
            'sesiones' =>
                (int) (
                    $resumen['sesiones']
                    ?? 0
                ),

            'bytes_ftp' =>
                (int) (
                    $resumen['bytes_ftp']
                    ?? 0
                ),

            'duracion_segundos' =>
                (float) (
                    $resumen['duracion_segundos']
                    ?? 0
                ),

            'velocidad_media_bps' =>
                (float) (
                    $resumen['velocidad_media_bps']
                    ?? 0
                ),

            'sesiones_reanudadas' =>
                (int) (
                    $resumen['sesiones_reanudadas']
                    ?? 0
                ),
        ],

        'resultados' =>
            $resultados,

        'sesiones' =>
            $sesiones,
    ]);

} catch (Throwable $e) {

    error_log(
        '[CTPS3][telemetria] '
        . $e->getMessage()
    );

    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'ERROR_INTERNO',
    ], 500);
}
