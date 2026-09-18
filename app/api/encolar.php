<?php

declare(strict_types=1);

require_once __DIR__ . '/../includes/aplicacion.php';

ctps3_exigir_metodo('POST');
ctps3_exigir_csrf();

try {
    $datos = ctps3_json();

    $ids = $datos['ids'] ?? null;

    /* ALM-6B: mismo preflight, sin INSERT. */
    $soloPreflight =
        ($datos['preflight'] ?? false)
        === true;

    if (!is_array($ids) || $ids === []) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' => 'SIN_ARCHIVOS',
        ], 422);
    }

    $ids = array_values(
        array_unique(
            array_filter(
                array_map(
                    static fn ($id): int =>
                        filter_var(
                            $id,
                            FILTER_VALIDATE_INT
                        ) ?: 0,
                    $ids
                ),
                static fn (int $id): bool =>
                    $id > 0
            )
        )
    );

    if ($ids === []) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' => 'IDS_INVALIDOS',
        ], 422);
    }

    if (count($ids) > 50) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' => 'DEMASIADOS_ARCHIVOS',
        ], 422);
    }

    $pdo = ctps3_bd();

    /*
     * ALM-PS3 1.0.0
     *
     * Control de admisión conservador.
     *
     * - La lectura HDD debe ser válida y fresca (<= 60 s).
     * - Se reserva un margen fijo de 512 MiB porque webMAN
     *   informa el espacio con precisión redondeada.
     * - Las transferencias activas reservan únicamente los
     *   bytes que aún faltan según su snapshot.
     * - Las nuevas selecciones reservan el tamaño completo.
     *
     * Si la telemetría no es verificable, se conserva el
     * comportamiento histórico: se permite encolar para
     * ejecutar más tarde.
     */
    $margenSeguridadBytes =
        512 * 1024 * 1024;

    $estadosActivos = [
        'EN_COLA',
        'COMPROBANDO',
        'PREPARANDO',
        'TRANSFIRIENDO',
        'PAUSANDO',
        'PAUSADO',
        'CANCELANDO',
        'VERIFICANDO',
        'REINTENTANDO',
    ];

    $destinosPermitidos = [
        'PKG' =>
            '/dev_hdd0/packages',

        'PS3ISO' =>
            '/dev_hdd0/PS3ISO',

        'PS2ISO' =>
            '/dev_hdd0/PS2ISO',
    ];

    $pdo->beginTransaction();

    $marcasIds =
        implode(
            ',',
            array_fill(
                0,
                count($ids),
                '?'
            )
        );

    $consultaSolicitado =
        $pdo->prepare("
            SELECT
                COALESCE(
                    SUM(
                        archivos_locales.tamano_bytes
                    ),
                    0
                )
            FROM archivos_locales
            WHERE
                archivos_locales.id
                    IN ($marcasIds)

                AND archivos_locales.disponible=1

                AND archivos_locales.formato IN (
                    'PKG',
                    'PS3ISO',
                    'PS2ISO'
                )

                AND NOT EXISTS (
                    SELECT 1
                    FROM transferencias
                    WHERE
                        transferencias.archivo_id
                            = archivos_locales.id

                        AND transferencias.estado IN (
                            'EN_COLA',
                            'COMPROBANDO',
                            'PREPARANDO',
                            'TRANSFIRIENDO',
                            'PAUSANDO',
                            'PAUSADO',
                            'CANCELANDO',
                            'VERIFICANDO',
                            'REINTENTANDO'
                        )
                )
        ");

    $consultaSolicitado->execute(
        $ids
    );

    $solicitadoBytes =
        (int) $consultaSolicitado
            ->fetchColumn();

    $reservadoActivoBytes =
        (int) $pdo->query("
            SELECT
                COALESCE(
                    SUM(
                        CASE
                            WHEN tamano_total >
                                MAX(
                                    bytes_transferidos,
                                    bytes_remotos
                                )
                            THEN
                                tamano_total
                                - MAX(
                                    bytes_transferidos,
                                    bytes_remotos
                                )
                            ELSE 0
                        END
                    ),
                    0
                )
            FROM transferencias
            WHERE estado IN (
                'EN_COLA',
                'COMPROBANDO',
                'PREPARANDO',
                'TRANSFIRIENDO',
                'PAUSANDO',
                'PAUSADO',
                'CANCELANDO',
                'VERIFICANDO',
                'REINTENTANDO'
            )
        ")->fetchColumn();

    $estadoHdd =
        $pdo->query("
            SELECT
                hdd_libre_bytes_aprox,
                hdd_libre_texto,
                hdd_fuente,
                hdd_ultima_lectura_ok_utc,
                hdd_ultimo_error,

                (
                    julianday('now')
                    - julianday(
                        hdd_ultima_lectura_ok_utc
                    )
                ) * 86400.0
                    AS antiguedad_segundos

            FROM ps3_estado
            WHERE id=1
            LIMIT 1
        ")->fetch();

    $preflight = [
        'verificado' => false,
        'estado' => 'NO_VERIFICABLE',

        'solicitado_bytes' =>
            $solicitadoBytes,

        'reservado_activo_bytes' =>
            $reservadoActivoBytes,

        'margen_seguridad_bytes' =>
            $margenSeguridadBytes,

        'hdd_libre_bytes_aprox' =>
            null,

        'hdd_libre_texto' =>
            null,

        'capacidad_nueva_bytes' =>
            null,

        'faltante_bytes' =>
            0,

        'lectura_utc' =>
            null,

        'fuente' =>
            null,

        'motivo' =>
            'SIN_LECTURA',
    ];

    if ($estadoHdd) {
        $hddLibreBytes =
            $estadoHdd[
                'hdd_libre_bytes_aprox'
            ] !== null
                ? (int) $estadoHdd[
                    'hdd_libre_bytes_aprox'
                ]
                : null;

        $antiguedad =
            $estadoHdd[
                'antiguedad_segundos'
            ] !== null
                ? (float) $estadoHdd[
                    'antiguedad_segundos'
                ]
                : null;

        $ultimoError =
            trim(
                (string) (
                    $estadoHdd[
                        'hdd_ultimo_error'
                    ]
                    ?? ''
                )
            );

        $lecturaFresca =
            $antiguedad !== null
            && $antiguedad >= -5.0
            && $antiguedad <= 60.0;

        if (
            $hddLibreBytes !== null
            && $hddLibreBytes >= 0
            && $lecturaFresca
            && $ultimoError === ''
        ) {
            $capacidadNuevaBytes =
                max(
                    0,
                    $hddLibreBytes
                    - $margenSeguridadBytes
                    - $reservadoActivoBytes
                );

            $faltanteBytes =
                max(
                    0,
                    $solicitadoBytes
                    - $capacidadNuevaBytes
                );

            $preflight = [
                'verificado' => true,
                'estado' =>
                    $faltanteBytes > 0
                        ? 'INSUFICIENTE'
                        : 'OK',

                'solicitado_bytes' =>
                    $solicitadoBytes,

                'reservado_activo_bytes' =>
                    $reservadoActivoBytes,

                'margen_seguridad_bytes' =>
                    $margenSeguridadBytes,

                'hdd_libre_bytes_aprox' =>
                    $hddLibreBytes,

                'hdd_libre_texto' =>
                    $estadoHdd[
                        'hdd_libre_texto'
                    ],

                'capacidad_nueva_bytes' =>
                    $capacidadNuevaBytes,

                'faltante_bytes' =>
                    $faltanteBytes,

                'lectura_utc' =>
                    $estadoHdd[
                        'hdd_ultima_lectura_ok_utc'
                    ],

                'fuente' =>
                    $estadoHdd[
                        'hdd_fuente'
                    ],

                'motivo' =>
                    null,
            ];

            if (
                $faltanteBytes > 0
                && $soloPreflight
            ) {
                $pdo->rollBack();

                ctps3_respuesta_json([
                    'ok' => true,
                    'modo' => 'PREFLIGHT',
                    'preflight' => $preflight,
                ]);
            }

            if ($faltanteBytes > 0) {
                $pdo->rollBack();

                $gbLibre =
                    number_format(
                        $hddLibreBytes
                            / 1073741824,
                        1,
                        ',',
                        '.'
                    );

                $gbNecesario =
                    number_format(
                        $solicitadoBytes
                            / 1073741824,
                        1,
                        ',',
                        '.'
                    );

                $gbFaltante =
                    number_format(
                        $faltanteBytes
                            / 1073741824,
                        1,
                        ',',
                        '.'
                    );

                ctps3_respuesta_json([
                    'ok' => false,

                    'codigo' =>
                        'ESPACIO_INSUFICIENTE',

                    'error' =>
                        (
                            'No hay espacio suficiente '
                            . 'en la PS3. '
                            . 'Libre aproximado: '
                            . $gbLibre
                            . ' GB; selección: '
                            . $gbNecesario
                            . ' GB; faltan aproximadamente '
                            . $gbFaltante
                            . ' GB considerando la cola '
                            . 'y el margen de seguridad.'
                        ),

                    'preflight' =>
                        $preflight,

                ], 409);
            }

        } else {
            if ($hddLibreBytes === null) {
                $preflight['motivo'] =
                    'SIN_LECTURA';

            } elseif (!$lecturaFresca) {
                $preflight['motivo'] =
                    'LECTURA_DESACTUALIZADA';

            } elseif ($ultimoError !== '') {
                $preflight['motivo'] =
                    'ULTIMO_INTENTO_ERROR';
            }

            $preflight[
                'hdd_libre_bytes_aprox'
            ] = $hddLibreBytes;

            $preflight[
                'hdd_libre_texto'
            ] = $estadoHdd[
                'hdd_libre_texto'
            ];

            $preflight[
                'lectura_utc'
            ] = $estadoHdd[
                'hdd_ultima_lectura_ok_utc'
            ];

            $preflight[
                'fuente'
            ] = $estadoHdd[
                'hdd_fuente'
            ];
        }
    }

    if ($soloPreflight) {
        $pdo->rollBack();

        ctps3_respuesta_json([
            'ok' => true,
            'modo' => 'PREFLIGHT',
            'preflight' => $preflight,
        ]);
    }

    $buscar = $pdo->prepare("
        SELECT
            id,
            nombre,
            ruta_relativa,
            tamano_bytes,
            formato,
            disponible
        FROM archivos_locales
        WHERE id=?
    ");

    $buscarActivo = $pdo->prepare("
        SELECT id
        FROM transferencias
        WHERE
            archivo_id=?
            AND estado IN (
                'EN_COLA',
                'COMPROBANDO',
                'PREPARANDO',
                'TRANSFIRIENDO',
                'PAUSANDO',
                'PAUSADO',
                'CANCELANDO',
                'VERIFICANDO',
                'REINTENTANDO'
            )
        LIMIT 1
    ");

    $insertar = $pdo->prepare("
        INSERT INTO transferencias (
            archivo_id,
            nombre_snapshot,
            ruta_relativa_snapshot,
            nombre_remoto,
            tamano_total,
            formato_snapshot,
            destino_remoto_snapshot,
            posicion_cola,
            estado,
            mensaje
        )
        VALUES (
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            'EN_COLA',
            'Esperando turno'
        )
    ");

    $evento = $pdo->prepare("
        INSERT INTO eventos (
            transferencia_id,
            nivel,
            tipo,
            mensaje
        )
        VALUES (
            ?,
            'INFO',
            'TRANSFERENCIA_ENCOLADA',
            ?
        )
    ");

    $maxPosicion = (int) $pdo->query("
        SELECT COALESCE(
            MAX(posicion_cola),
            0
        )
        FROM transferencias
        WHERE estado IN (
            'EN_COLA',
            'COMPROBANDO',
            'PREPARANDO',
            'TRANSFIRIENDO',
            'PAUSANDO',
            'PAUSADO',
            'CANCELANDO',
            'VERIFICANDO',
            'REINTENTANDO'
        )
    ")->fetchColumn();

    $siguientePos =
        (
            (int) floor(
                $maxPosicion / 100
            )
            + 1
        ) * 100;

    if ($siguientePos < 100) {
        $siguientePos = 100;
    }

    $agregadas = [];
    $omitidas = [];

    foreach ($ids as $id) {
        $buscar->execute([$id]);

        $archivo = $buscar->fetch();

        if (!$archivo) {
            $omitidas[] = [
                'id' => $id,
                'motivo' => 'NO_EXISTE',
            ];

            continue;
        }

        if ((int) $archivo['disponible'] !== 1) {
            $omitidas[] = [
                'id' => $id,
                'motivo' => 'NO_DISPONIBLE',
            ];

            continue;
        }

        $formato =
            (string) $archivo['formato'];

        if (
            !array_key_exists(
                $formato,
                $destinosPermitidos
            )
        ) {
            $omitidas[] = [
                'id' => $id,
                'motivo' =>
                    'FORMATO_NO_SOPORTADO',
            ];

            continue;
        }

        $destinoRemoto =
            $destinosPermitidos[
                $formato
            ];

        $buscarActivo->execute([$id]);

        if ($buscarActivo->fetch()) {
            $omitidas[] = [
                'id' => $id,
                'motivo' => 'YA_ACTIVO',
            ];

            continue;
        }

        try {
            $insertar->execute([
                $id,
                $archivo['nombre'],
                $archivo['ruta_relativa'],
                $archivo['nombre'],
                (int) $archivo['tamano_bytes'],
                $formato,
                $destinoRemoto,
                $siguientePos,
            ]);

            $transferenciaId =
                (int) $pdo->lastInsertId();

            $evento->execute([
                $transferenciaId,
                'Archivo agregado a la cola',
            ]);

            $siguientePos += 100;

            $agregadas[] = [
                'archivo_id' => $id,
                'transferencia_id' =>
                    $transferenciaId,
            ];

        } catch (PDOException $e) {
            if (
                str_contains(
                    $e->getMessage(),
                    'UNIQUE constraint failed'
                )
            ) {
                $omitidas[] = [
                    'id' => $id,
                    'motivo' => 'YA_ACTIVO',
                ];

                continue;
            }

            throw $e;
        }
    }

    $pdo->commit();

    ctps3_respuesta_json([
        'ok' => true,
        'agregadas' => $agregadas,
        'omitidas' => $omitidas,
        'preflight' => $preflight,
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
        '[CTPS3][encolar] ' .
        $e->getMessage()
    );

    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'ERROR_INTERNO',
    ], 500);
}
