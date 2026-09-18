<?php

declare(strict_types=1);

require_once __DIR__ . '/../includes/aplicacion.php';

ctps3_exigir_metodo('POST');
ctps3_exigir_csrf();


function ctps3_datos_asociados_ids(mixed $valor): array
{
    if (!is_array($valor)) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' => 'COMPONENTES_INVALIDOS',
        ], 422);
    }

    if (count($valor) < 1 || count($valor) > 32) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' => 'COMPONENTES_INVALIDOS',
        ], 422);
    }

    $resultado = [];

    foreach ($valor as $id) {
        $entero = filter_var(
            $id,
            FILTER_VALIDATE_INT
        );

        if ($entero === false || $entero < 1) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' => 'COMPONENTES_INVALIDOS',
            ], 422);
        }

        $resultado[(int) $entero] = true;
    }

    $ids = array_keys($resultado);
    sort($ids, SORT_NUMERIC);

    if (count($ids) !== count($valor)) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' => 'COMPONENTES_DUPLICADOS',
        ], 422);
    }

    return $ids;
}


function ctps3_datos_asociados_ruta_segura(
    string $tipo,
    string $ruta
): bool {
    if (!in_array(
        $tipo,
        ['DATOS_GAME', 'CACHE_GAME'],
        true
    )) {
        return false;
    }

    $prefijo = '/dev_hdd0/game/';

    if (
        $ruta === ''
        || !str_starts_with($ruta, $prefijo)
        || str_contains($ruta, "\0")
        || str_contains($ruta, '\\')
        || str_contains($ruta, '*')
        || str_contains($ruta, '?')
        || str_contains($ruta, '#')
        || str_contains($ruta, '%')
    ) {
        return false;
    }

    if (preg_match('/[\x00-\x1F\x7F]/', $ruta) === 1) {
        return false;
    }

    $relativa = substr(
        $ruta,
        strlen($prefijo)
    );

    if (
        $relativa === ''
        || $relativa === '.'
        || $relativa === '..'
        || str_contains($relativa, '/')
        || str_starts_with($relativa, '_INST_')
    ) {
        return false;
    }

    return true;
}


function ctps3_datos_asociados_activa(
    PDO $pdo,
    int $juegoId
): ?array {
    $consulta = $pdo->prepare("
        SELECT
            id,
            alcance,
            estado,
            creada_utc,
            mensaje
        FROM eliminaciones_juegos
        WHERE
            juego_id=?
            AND estado IN ('PENDIENTE', 'PROCESANDO')
        ORDER BY id ASC
        LIMIT 1
    ");

    $consulta->execute([$juegoId]);
    $fila = $consulta->fetch();

    if (!$fila) {
        return null;
    }

    return [
        'id' => (int) $fila['id'],
        'alcance' => (string) $fila['alcance'],
        'estado' => (string) $fila['estado'],
        'creada_utc' => (string) $fila['creada_utc'],
        'mensaje' => $fila['mensaje'] !== null
            ? (string) $fila['mensaje']
            : null,
    ];
}


function ctps3_datos_asociados_reconciliacion_pendiente(
    PDO $pdo,
    array $ids
): ?array {
    if (!$ids) {
        return null;
    }

    $marcas = implode(
        ', ',
        array_fill(0, count($ids), '?')
    );

    $consulta = $pdo->prepare("
        SELECT
            e.id AS eliminacion_id,
            e.estado AS eliminacion_estado,
            e.finalizada_utc,
            ec.juego_componente_id,
            ec.estado AS componente_estado,
            c.visto_utc AS j3_visto_utc,
            a.visto_utc AS almacenamiento_visto_utc
        FROM eliminaciones_juegos e
        JOIN eliminaciones_juegos_componentes ec
          ON ec.eliminacion_id=e.id
        JOIN juegos_ps3_componentes c
          ON c.id=ec.juego_componente_id
        LEFT JOIN almacenamiento_ps3_elementos a
          ON a.juego_componente_id=ec.juego_componente_id
        WHERE
            e.alcance='DATOS_ASOCIADOS'
            AND e.estado IN ('COMPLETADO', 'ERROR')
            AND e.finalizada_utc IS NOT NULL
            AND (
                (
                    e.estado='COMPLETADO'
                    AND ec.estado='ELIMINADO'
                )
                OR e.estado='ERROR'
            )
            AND ec.juego_componente_id IN ($marcas)
            AND (
                julianday(c.visto_utc)
                    <= julianday(e.finalizada_utc)
                OR (
                    a.juego_componente_id IS NOT NULL
                    AND julianday(a.visto_utc)
                        <= julianday(e.finalizada_utc)
                )
            )
        ORDER BY
            julianday(e.finalizada_utc) DESC,
            e.id DESC,
            ec.id DESC
        LIMIT 1
    ");

    $consulta->execute($ids);
    $fila = $consulta->fetch();

    if (!$fila) {
        return null;
    }

    return [
        'eliminacion_id' =>
            (int) $fila['eliminacion_id'],

        'eliminacion_estado' =>
            (string) $fila['eliminacion_estado'],

        'juego_componente_id' =>
            (int) $fila['juego_componente_id'],

        'componente_estado' =>
            (string) $fila['componente_estado'],

        'finalizada_utc' =>
            (string) $fila['finalizada_utc'],

        'j3_visto_utc' =>
            (string) $fila['j3_visto_utc'],

        'almacenamiento_visto_utc' =>
            $fila['almacenamiento_visto_utc'] !== null
                ? (string) $fila['almacenamiento_visto_utc']
                : null,
    ];
}


function ctps3_datos_asociados_preview(
    PDO $pdo,
    int $juegoId,
    array $ids
): array {
    $consultaJuego = $pdo->prepare("
        SELECT
            id,
            title_id,
            nombre,
            tipo_principal,
            disponible,
            inventario_completo
        FROM juegos_ps3
        WHERE id=?
        LIMIT 1
    ");

    $consultaJuego->execute([$juegoId]);
    $juego = $consultaJuego->fetch();

    if (!$juego) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' => 'JUEGO_NO_EXISTE',
        ], 404);
    }

    if (!(bool) $juego['disponible']) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' => 'JUEGO_NO_DISPONIBLE',
        ], 409);
    }

    if (!(bool) $juego['inventario_completo']) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' => 'INVENTARIO_INCOMPLETO',
        ], 409);
    }

    $marcas = implode(
        ', ',
        array_fill(0, count($ids), '?')
    );

    $sql = "
        SELECT
            a.id AS almacenamiento_id,
            a.juego_componente_id,
            a.subtipo AS tipo,
            a.ruta_remota,
            a.tamano_bytes,
            a.confianza,
            a.politica,
            a.evidencia_json
        FROM almacenamiento_ps3_elementos a
        JOIN juegos_ps3_componentes c
          ON c.id=a.juego_componente_id
        WHERE
            a.disponible=1
            AND a.juego_id=?
            AND a.clase='VINCULADO'
            AND a.confianza='ALTA'
            AND a.posible_huerfano=0
            AND a.eliminacion_automatica_permitida=0
            AND a.politica=(
                'NO_LIMPIEZA_AUTOMATICA;'
                || 'GESTIONAR_COMO_DATO_ASOCIADO'
            )
            AND a.subtipo IN ('DATOS_GAME', 'CACHE_GAME')
            AND a.juego_componente_id IN ($marcas)
            AND c.disponible=1
            AND c.juego_id=a.juego_id
            AND c.tipo=a.subtipo
            AND c.ruta_remota=a.ruta_remota
            AND c.tamano_bytes=a.tamano_bytes
        ORDER BY
            CASE a.subtipo
                WHEN 'DATOS_GAME' THEN 1
                WHEN 'CACHE_GAME' THEN 2
                ELSE 99
            END,
            a.ruta_remota COLLATE NOCASE ASC,
            a.juego_componente_id ASC
    ";

    $consulta = $pdo->prepare($sql);
    $consulta->execute([
        $juegoId,
        ...$ids,
    ]);

    $componentes = [];
    $rutas = [];
    $encontrados = [];
    $tamano = 0;

    foreach ($consulta as $fila) {
        $componenteId = (int) $fila['juego_componente_id'];
        $tipo = (string) $fila['tipo'];
        $ruta = (string) $fila['ruta_remota'];
        $tamanoBytes = (int) $fila['tamano_bytes'];

        if (!ctps3_datos_asociados_ruta_segura(
            $tipo,
            $ruta
        )) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' => 'COMPONENTE_RUTA_NO_PERMITIDA',
                'componente_id' => $componenteId,
            ], 403);
        }

        if (isset($rutas[$ruta])) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' => 'COMPONENTES_DUPLICADOS',
            ], 409);
        }

        $rutas[$ruta] = true;
        $encontrados[$componenteId] = true;
        $tamano += $tamanoBytes;

        $evidencia = [];

        try {
            $decodificada = json_decode(
                (string) $fila['evidencia_json'],
                true,
                512,
                JSON_THROW_ON_ERROR
            );

            if (is_array($decodificada)) {
                foreach ($decodificada as $valor) {
                    if (is_string($valor)) {
                        $evidencia[] = $valor;
                    }
                }
            }
        } catch (JsonException) {
            $evidencia = [];
        }

        $componentes[] = [
            'juego_componente_id' => $componenteId,
            'almacenamiento_id' => (int) $fila['almacenamiento_id'],
            'tipo' => $tipo,
            'ruta_remota' => $ruta,
            'tamano_bytes' => $tamanoBytes,
            'confianza' => (string) $fila['confianza'],
            'politica' => (string) $fila['politica'],
            'evidencia' => $evidencia,
        ];
    }

    if (count($encontrados) !== count($ids)) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' => 'COMPONENTE_NO_ELEGIBLE',
        ], 409);
    }

    foreach ($ids as $id) {
        if (!isset($encontrados[$id])) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' => 'COMPONENTE_NO_ELEGIBLE',
                'componente_id' => $id,
            ], 409);
        }
    }

    $reconciliacionPendiente =
        ctps3_datos_asociados_reconciliacion_pendiente(
            $pdo,
            $ids
        );

    if ($reconciliacionPendiente !== null) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' => 'RECONCILIACION_PENDIENTE',
            'mensaje' =>
                'El borrado anterior ya fue confirmado, '
                . 'pero J3/Almacenamiento aún no reflejan '
                . 'un inventario posterior.',
            'reconciliacion' =>
                $reconciliacionPendiente,
        ], 409);
    }

    $titleId = $juego['title_id'] !== null
        ? trim((string) $juego['title_id'])
        : '';

    $nombre = trim((string) $juego['nombre']);
    $confirmacionBase = $titleId !== ''
        ? $titleId
        : $nombre;

    return [
        'alcance' => 'DATOS_ASOCIADOS',
        'juego_id' => (int) $juego['id'],
        'title_id' => $titleId !== '' ? $titleId : null,
        'nombre' => $nombre,
        'tipo_principal' => (string) $juego['tipo_principal'],
        'cantidad_componentes' => count($componentes),
        'tamano_liberable_bytes' => $tamano,
        'tamano_completo' => true,
        'componentes' => $componentes,
        'confirmacion_esperada' =>
            'ELIMINAR DATOS ' . $confirmacionBase,
    ];
}


try {
    $datos = ctps3_json();

    $accion = strtoupper(trim(
        (string) ($datos['accion'] ?? '')
    ));

    $pdo = ctps3_bd();

    if ($accion === 'PREVISUALIZAR') {
        $juegoId = filter_var(
            $datos['juego_id'] ?? null,
            FILTER_VALIDATE_INT
        );

        if ($juegoId === false || $juegoId < 1) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' => 'JUEGO_INVALIDO',
            ], 422);
        }

        $ids = ctps3_datos_asociados_ids(
            $datos['componentes_ids'] ?? null
        );

        $preview = ctps3_datos_asociados_preview(
            $pdo,
            (int) $juegoId,
            $ids
        );

        ctps3_respuesta_json([
            'ok' => true,
            'version' => '1.2.0',
            'preview' => $preview,
            'eliminacion_activa' =>
                ctps3_datos_asociados_activa(
                    $pdo,
                    (int) $juegoId
                ),
        ]);
    }

    if ($accion === 'SOLICITAR') {
        $juegoId = filter_var(
            $datos['juego_id'] ?? null,
            FILTER_VALIDATE_INT
        );

        if ($juegoId === false || $juegoId < 1) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' => 'JUEGO_INVALIDO',
            ], 422);
        }

        $ids = ctps3_datos_asociados_ids(
            $datos['componentes_ids'] ?? null
        );

        $confirmacion = trim(
            (string) ($datos['confirmacion'] ?? '')
        );

        try {
            $pdo->exec('BEGIN IMMEDIATE');

            $activa = ctps3_datos_asociados_activa(
                $pdo,
                (int) $juegoId
            );

            if ($activa !== null) {
                $pdo->rollBack();

                ctps3_respuesta_json([
                    'ok' => false,
                    'error' => 'ELIMINACION_YA_ACTIVA',
                    'eliminacion_id' => $activa['id'],
                    'alcance' => $activa['alcance'],
                    'estado' => $activa['estado'],
                ], 409);
            }

            $preview = ctps3_datos_asociados_preview(
                $pdo,
                (int) $juegoId,
                $ids
            );

            if (
                $confirmacion === ''
                || !hash_equals(
                    $preview['confirmacion_esperada'],
                    $confirmacion
                )
            ) {
                $pdo->rollBack();

                ctps3_respuesta_json([
                    'ok' => false,
                    'error' => 'CONFIRMACION_INVALIDA',
                ], 422);
            }

            $insertar = $pdo->prepare("
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
                    mensaje,
                    alcance
                )
                VALUES (
                    ?, ?, ?, ?,
                    'PENDIENTE',
                    ?, 0, ?, 1,
                    'Esperando worker · datos asociados',
                    'DATOS_ASOCIADOS'
                )
            ");

            $insertar->execute([
                $preview['juego_id'],
                $preview['nombre'],
                $preview['title_id'],
                $preview['tipo_principal'],
                $preview['cantidad_componentes'],
                $preview['tamano_liberable_bytes'],
            ]);

            $eliminacionId = (int) $pdo->lastInsertId();

            $insertarComponente = $pdo->prepare("
                INSERT INTO eliminaciones_juegos_componentes (
                    eliminacion_id,
                    juego_componente_id,
                    tipo,
                    ruta_remota,
                    tamano_bytes,
                    estado,
                    mensaje
                )
                VALUES (
                    ?, ?, ?, ?, ?,
                    'PENDIENTE',
                    'Esperando eliminación de dato asociado'
                )
            ");

            foreach ($preview['componentes'] as $componente) {
                $insertarComponente->execute([
                    $eliminacionId,
                    $componente['juego_componente_id'],
                    $componente['tipo'],
                    $componente['ruta_remota'],
                    $componente['tamano_bytes'],
                ]);
            }

            $evento = $pdo->prepare("
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
                    'JUEGO_DATOS_ASOCIADOS_ELIMINACION_SOLICITADA',
                    ?,
                    ?
                )
            ");

            $evento->execute([
                'Eliminación de datos asociados solicitada: '
                    . $preview['nombre'],
                json_encode([
                    'eliminacion_id' => $eliminacionId,
                    'alcance' => 'DATOS_ASOCIADOS',
                    'juego_id' => $preview['juego_id'],
                    'title_id' => $preview['title_id'],
                    'componentes' => $preview['cantidad_componentes'],
                    'tamano_bytes' => $preview['tamano_liberable_bytes'],
                ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES),
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
            'version' => '1.2.0',
            'alcance' => 'DATOS_ASOCIADOS',
            'eliminacion_id' => $eliminacionId,
            'estado' => 'PENDIENTE',
            'mensaje' => 'Eliminación de datos asociados encolada',
        ], 202);
    }

    if ($accion === 'ESTADO') {
        $eliminacionId = filter_var(
            $datos['eliminacion_id'] ?? null,
            FILTER_VALIDATE_INT
        );

        if (
            $eliminacionId === false
            || $eliminacionId < 1
        ) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' => 'ELIMINACION_INVALIDA',
            ], 422);
        }

        $consulta = $pdo->prepare("
            SELECT
                id,
                juego_id,
                nombre,
                title_id,
                tipo_principal,
                alcance,
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
            WHERE
                id=?
                AND alcance='DATOS_ASOCIADOS'
            LIMIT 1
        ");

        $consulta->execute([(int) $eliminacionId]);
        $fila = $consulta->fetch();

        if (!$fila) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' => 'ELIMINACION_NO_EXISTE',
            ], 404);
        }

        $consultaComponentes = $pdo->prepare("
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
            FROM eliminaciones_juegos_componentes
            WHERE eliminacion_id=?
            ORDER BY id ASC
        ");

        $consultaComponentes->execute([
            (int) $eliminacionId,
        ]);

        $componentes = [];

        foreach ($consultaComponentes as $componente) {
            $componentes[] = [
                'id' => (int) $componente['id'],
                'juego_componente_id' =>
                    (int) $componente['juego_componente_id'],
                'tipo' => (string) $componente['tipo'],
                'ruta_remota' => (string) $componente['ruta_remota'],
                'tamano_bytes' => $componente['tamano_bytes'] !== null
                    ? (int) $componente['tamano_bytes']
                    : null,
                'estado' => (string) $componente['estado'],
                'mensaje' => $componente['mensaje'] !== null
                    ? (string) $componente['mensaje']
                    : null,
                'http_codigo' => $componente['http_codigo'] !== null
                    ? (int) $componente['http_codigo']
                    : null,
                'respuesta_bytes' =>
                    $componente['respuesta_bytes'] !== null
                        ? (int) $componente['respuesta_bytes']
                        : null,
                'creado_utc' => (string) $componente['creado_utc'],
                'actualizado_utc' =>
                    (string) $componente['actualizado_utc'],
            ];
        }

        ctps3_respuesta_json([
            'ok' => true,
            'version' => '1.2.0',
            'eliminacion' => [
                'id' => (int) $fila['id'],
                'juego_id' => (int) $fila['juego_id'],
                'nombre' => (string) $fila['nombre'],
                'title_id' => $fila['title_id'] !== null
                    ? (string) $fila['title_id']
                    : null,
                'tipo_principal' => (string) $fila['tipo_principal'],
                'alcance' => (string) $fila['alcance'],
                'estado' => (string) $fila['estado'],
                'componentes_total' => (int) $fila['componentes_total'],
                'componentes_eliminados' =>
                    (int) $fila['componentes_eliminados'],
                'tamano_objetivo_bytes' =>
                    $fila['tamano_objetivo_bytes'] !== null
                        ? (int) $fila['tamano_objetivo_bytes']
                        : null,
                'tamano_completo' => (bool) $fila['tamano_completo'],
                'creada_utc' => (string) $fila['creada_utc'],
                'iniciada_utc' => $fila['iniciada_utc'] !== null
                    ? (string) $fila['iniciada_utc']
                    : null,
                'actualizada_utc' => (string) $fila['actualizada_utc'],
                'finalizada_utc' => $fila['finalizada_utc'] !== null
                    ? (string) $fila['finalizada_utc']
                    : null,
                'mensaje' => $fila['mensaje'] !== null
                    ? (string) $fila['mensaje']
                    : null,
                'error_detalle' => $fila['error_detalle'] !== null
                    ? (string) $fila['error_detalle']
                    : null,
                'componentes' => $componentes,
            ],
        ]);
    }

    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'ACCION_NO_SOPORTADA',
    ], 422);

} catch (JsonException $e) {
    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'JSON_INVALIDO',
    ], 400);

} catch (Throwable $e) {
    error_log(
        'CTPS3 api/eliminar-datos-asociados.php: '
        . get_class($e)
        . ': '
        . $e->getMessage()
    );

    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'ERROR_INTERNO',
    ], 500);
}
