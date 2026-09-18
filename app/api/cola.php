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

    $id = filter_var(
        $datos['transferencia_id'] ?? null,
        FILTER_VALIDATE_INT
    );

    if (!$id || $id < 1) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' =>
                'TRANSFERENCIA_INVALIDA',
        ], 422);
    }

    $permitidas = [
        'MOVER_ARRIBA',
        'MOVER_ABAJO',
        'PRIORIDAD',
    ];

    if (
        !in_array(
            $accion,
            $permitidas,
            true
        )
    ) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' =>
                'ACCION_INVALIDA',
        ], 422);
    }

    $pdo = ctps3_bd();

    $pdo->beginTransaction();

    $consulta = $pdo->prepare("
        SELECT
            id,
            estado,
            prioridad,
            posicion_cola
        FROM transferencias
        WHERE id=?
    ");

    $consulta->execute([$id]);

    $actual = $consulta->fetch();

    if (!$actual) {
        $pdo->rollBack();

        ctps3_respuesta_json([
            'ok' => false,
            'error' =>
                'TRANSFERENCIA_NO_EXISTE',
        ], 404);
    }

    if ($actual['estado'] !== 'EN_COLA') {
        $pdo->rollBack();

        ctps3_respuesta_json([
            'ok' => false,
            'error' =>
                'SOLO_TRANSFERENCIAS_EN_COLA',
            'estado' =>
                $actual['estado'],
        ], 409);
    }

    if ($accion === 'PRIORIDAD') {
        $nombre = strtoupper(
            trim(
                (string) (
                    $datos['prioridad']
                    ?? ''
                )
            )
        );

        $mapa = [
            'ALTA' => 10,
            'NORMAL' => 100,
            'BAJA' => 200,
        ];

        if (
            !array_key_exists(
                $nombre,
                $mapa
            )
        ) {
            $pdo->rollBack();

            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'PRIORIDAD_INVALIDA',
            ], 422);
        }

        $actualizar =
            $pdo->prepare("
                UPDATE transferencias
                SET
                    prioridad=?,
                    actualizada_utc=
                        strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        )
                WHERE
                    id=?
                    AND estado='EN_COLA'
            ");

        $actualizar->execute([
            $mapa[$nombre],
            $id,
        ]);

        $evento =
            $pdo->prepare("
                INSERT INTO eventos (
                    transferencia_id,
                    nivel,
                    tipo,
                    mensaje
                )
                VALUES (
                    ?,
                    'INFO',
                    'PRIORIDAD_CAMBIADA',
                    ?
                )
            ");

        $evento->execute([
            $id,
            "Prioridad cambiada a {$nombre}",
        ]);

        $pdo->commit();

        ctps3_respuesta_json([
            'ok' => true,
            'accion' => $accion,
            'prioridad' => $nombre,
            'valor' => $mapa[$nombre],
        ]);
    }

    $prioridad =
        (int) $actual['prioridad'];

    $posicion =
        (int) $actual['posicion_cola'];

    if ($accion === 'MOVER_ARRIBA') {
        $vecino = $pdo->prepare("
            SELECT
                id,
                posicion_cola
            FROM transferencias
            WHERE
                estado='EN_COLA'
                AND prioridad=?
                AND posicion_cola < ?
            ORDER BY
                posicion_cola DESC,
                id DESC
            LIMIT 1
        ");
    } else {
        $vecino = $pdo->prepare("
            SELECT
                id,
                posicion_cola
            FROM transferencias
            WHERE
                estado='EN_COLA'
                AND prioridad=?
                AND posicion_cola > ?
            ORDER BY
                posicion_cola ASC,
                id ASC
            LIMIT 1
        ");
    }

    $vecino->execute([
        $prioridad,
        $posicion,
    ]);

    $otra = $vecino->fetch();

    if (!$otra) {
        $pdo->commit();

        ctps3_respuesta_json([
            'ok' => true,
            'accion' => $accion,
            'sin_cambio' => true,
        ]);
    }

    $otraId =
        (int) $otra['id'];

    $otraPosicion =
        (int) $otra['posicion_cola'];

    $temporal =
        -1 * $id;

    $pdo->prepare("
        UPDATE transferencias
        SET posicion_cola=?
        WHERE id=?
    ")->execute([
        $temporal,
        $id,
    ]);

    $pdo->prepare("
        UPDATE transferencias
        SET posicion_cola=?
        WHERE id=?
    ")->execute([
        $posicion,
        $otraId,
    ]);

    $pdo->prepare("
        UPDATE transferencias
        SET
            posicion_cola=?,
            actualizada_utc=
                strftime(
                    '%Y-%m-%dT%H:%M:%fZ',
                    'now'
                )
        WHERE id=?
    ")->execute([
        $otraPosicion,
        $id,
    ]);

    $evento =
        $pdo->prepare("
            INSERT INTO eventos (
                transferencia_id,
                nivel,
                tipo,
                mensaje
            )
            VALUES (
                ?,
                'INFO',
                'ORDEN_COLA_CAMBIADO',
                ?
            )
        ");

    $mensaje =
        $accion === 'MOVER_ARRIBA'
            ? 'Transferencia subida en la cola'
            : 'Transferencia bajada en la cola';

    $evento->execute([
        $id,
        $mensaje,
    ]);

    $pdo->commit();

    ctps3_respuesta_json([
        'ok' => true,
        'accion' => $accion,
        'intercambio_con' => $otraId,
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
        '[CTPS3][cola] ' .
        $e->getMessage()
    );

    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'ERROR_INTERNO',
    ], 500);
}
