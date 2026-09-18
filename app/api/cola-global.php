<?php

declare(strict_types=1);

require_once __DIR__ . '/../includes/aplicacion.php';

ctps3_exigir_metodo('POST');
ctps3_exigir_csrf();

try {
    $datos = ctps3_json();

    $accion = strtoupper(
        trim(
            (string) (
                $datos['accion']
                ?? ''
            )
        )
    );

    if (
        !in_array(
            $accion,
            [
                'PAUSAR_COLA',
                'REANUDAR_COLA',
            ],
            true
        )
    ) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' =>
                'ACCION_INVALIDA',
        ], 422);
    }

    $pausada =
        $accion === 'PAUSAR_COLA';

    $pdo = ctps3_bd();

    $pdo->beginTransaction();

    $consulta = $pdo->prepare("
        SELECT valor
        FROM meta
        WHERE clave='cola_pausada'
    ");

    $consulta->execute();

    $valorPrevio =
        $consulta->fetchColumn();

    $previa =
        (string) $valorPrevio === '1';

    $actualizar = $pdo->prepare("
        INSERT INTO meta(
            clave,
            valor
        )
        VALUES(
            'cola_pausada',
            ?
        )
        ON CONFLICT(clave)
        DO UPDATE SET
            valor=excluded.valor
    ");

    $actualizar->execute([
        $pausada ? '1' : '0',
    ]);

    $actual = $pdo->query("
        SELECT
            id,
            estado,
            nombre_snapshot
        FROM transferencias
        WHERE estado IN (
            'COMPROBANDO',
            'PREPARANDO',
            'TRANSFIRIENDO',
            'PAUSANDO',
            'CANCELANDO',
            'VERIFICANDO',
            'REINTENTANDO'
        )
        ORDER BY id DESC
        LIMIT 1
    ")->fetch();

    $pendientes =
        (int) $pdo->query("
            SELECT COUNT(*)
            FROM transferencias
            WHERE estado='EN_COLA'
        ")->fetchColumn();

    if ($previa !== $pausada) {
        $evento = $pdo->prepare("
            INSERT INTO eventos (
                nivel,
                tipo,
                mensaje
            )
            VALUES (
                'INFO',
                ?,
                ?
            )
        ");

        if ($pausada) {
            $evento->execute([
                'COLA_GLOBAL_PAUSADA',
                (
                    $actual
                    ? 'Cola pausada; la transferencia actual continuará'
                    : 'Cola pausada'
                ),
            ]);
        } else {
            $evento->execute([
                'COLA_GLOBAL_REANUDADA',
                'Cola reanudada',
            ]);
        }
    }

    $pdo->commit();

    ctps3_respuesta_json([
        'ok' => true,

        'cola_pausada' =>
            $pausada,

        'sin_cambio' =>
            $previa === $pausada,

        'pendientes' =>
            $pendientes,

        'transferencia_actual' =>
            $actual
                ? [
                    'id' =>
                        (int) $actual['id'],

                    'estado' =>
                        $actual['estado'],

                    'nombre' =>
                        $actual[
                            'nombre_snapshot'
                        ],
                ]
                : null,
    ]);

} catch (JsonException $e) {
    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'JSON_INVALIDO',
    ], 400);

} catch (Throwable $e) {
    if (
        isset($pdo)
        && $pdo instanceof PDO
        && $pdo->inTransaction()
    ) {
        $pdo->rollBack();
    }

    error_log(
        '[CTPS3][cola-global] ' .
        $e->getMessage()
    );

    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'ERROR_INTERNO',
    ], 500);
}
