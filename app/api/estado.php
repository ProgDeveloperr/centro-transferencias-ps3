<?php

declare(strict_types=1);

require_once __DIR__ . '/../includes/aplicacion.php';

ctps3_exigir_metodo('GET');

try {
    $pdo = ctps3_bd();

    $worker = $pdo->query("
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

    $estados = [];

    foreach ($pdo->query("
        SELECT
            estado,
            COUNT(*) AS cantidad
        FROM transferencias
        GROUP BY estado
    ") as $fila) {
        $estados[$fila['estado']] =
            (int) $fila['cantidad'];
    }

    $catalogo = $pdo->query("
        SELECT
            COUNT(*) AS archivos,
            COALESCE(SUM(tamano_bytes), 0) AS bytes
        FROM archivos_locales
        WHERE disponible=1
    ")->fetch();

    ctps3_respuesta_json([
        'ok' => true,

        'worker' => [
            'estado' =>
                $worker['estado'],

            'pid' =>
                $worker['pid'] !== null
                    ? (int) $worker['pid']
                    : null,

            'version' =>
                $worker['version'],

            'transferencia_id' =>
                $worker['transferencia_id'] !== null
                    ? (int) $worker['transferencia_id']
                    : null,

            'heartbeat_utc' =>
                $worker['heartbeat_utc'],

            'iniciado_utc' =>
                $worker['iniciado_utc'],

            'mensaje' =>
                $worker['mensaje'],
        ],

        'cola' => $estados,

        'catalogo' => [
            'archivos' =>
                (int) $catalogo['archivos'],

            'tamano_total_bytes' =>
                (int) $catalogo['bytes'],
        ],
    ]);

} catch (Throwable $e) {
    error_log(
        '[CTPS3][estado] ' .
        $e->getMessage()
    );

    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'ERROR_INTERNO',
    ], 500);
}
