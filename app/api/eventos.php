<?php

declare(strict_types=1);

require_once __DIR__ . '/../includes/aplicacion.php';

ctps3_exigir_metodo('GET');

try {
    $pdo = ctps3_bd();

    $consulta = $pdo->query("
        SELECT
            e.id,
            e.transferencia_id,
            e.nivel,
            e.tipo,
            e.mensaje,
            e.creado_utc,
            t.nombre_snapshot
        FROM eventos e
        LEFT JOIN transferencias t
            ON t.id=e.transferencia_id
        ORDER BY e.id DESC
        LIMIT 30
    ");

    $eventos = [];

    foreach ($consulta as $fila) {
        $fila['id'] =
            (int) $fila['id'];

        $fila['transferencia_id'] =
            $fila['transferencia_id'] !== null
                ? (int) $fila['transferencia_id']
                : null;

        $eventos[] = $fila;
    }

    ctps3_respuesta_json([
        'ok' => true,
        'eventos' => $eventos,
    ]);

} catch (Throwable $e) {
    error_log(
        '[CTPS3][eventos] ' .
        $e->getMessage()
    );

    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'ERROR_INTERNO',
    ], 500);
}
