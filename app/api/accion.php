<?php

declare(strict_types=1);

require_once __DIR__ . '/../includes/aplicacion.php';

ctps3_exigir_metodo('POST');
ctps3_exigir_csrf();


const CTPS3_PKG_FRESCURA_HDD_SEGUNDOS = 60;
const CTPS3_PKG_MARGEN_HDD_SEGURIDAD_BYTES =
    512 * 1024 * 1024;


function ctps3_preflight_instalacion_pkg(
    PDO $pdo,
    array $tamanos,
    bool $multipart
): array {
    $normalizados = [];

    foreach ($tamanos as $valor) {
        $tamano = (int) $valor;

        if ($tamano <= 0) {
            return [
                'verificado' => false,
                'estado' => 'NO_VERIFICABLE',
                'motivo' =>
                    'TAMANO_PKG_NO_VERIFICABLE',
                'multipart' => $multipart,
                'metodo_estimacion' =>
                    $multipart
                        ? 'SUMA_PKG_MAS_TEMPORAL_MAXIMO'
                        : 'TAMANO_PKG',
                'pkg_total_bytes' => null,
                'temporal_maximo_bytes' => null,
                'requerido_total_bytes' => null,
                'margen_seguridad_bytes' =>
                    CTPS3_PKG_MARGEN_HDD_SEGURIDAD_BYTES,
                'hdd_libre_bytes_aprox' => null,
                'hdd_libre_texto' => null,
                'hdd_fuente' => null,
                'hdd_antiguedad_segundos' => null,
                'capacidad_util_bytes' => null,
                'faltante_bytes' => null,
            ];
        }

        $normalizados[] = $tamano;
    }

    $pkgTotal =
        array_sum(
            $normalizados
        );

    $temporalMaximo =
        $multipart
            ? max($normalizados)
            : 0;

    $requeridoTotal =
        $pkgTotal
        + $temporalMaximo;

    $fila = $pdo->query("
        SELECT
            hdd_libre_bytes_aprox,
            hdd_libre_texto,
            hdd_fuente,
            hdd_ultimo_error,

            (
                julianday('now')
                - julianday(
                    hdd_ultima_lectura_ok_utc
                )
            ) * 86400.0
                AS hdd_antiguedad_segundos

        FROM ps3_estado
        WHERE id=1
        LIMIT 1
    ")->fetch();

    $resultado = [
        'verificado' => false,
        'estado' => 'NO_VERIFICABLE',
        'motivo' => null,
        'multipart' => $multipart,
        'metodo_estimacion' =>
            $multipart
                ? 'SUMA_PKG_MAS_TEMPORAL_MAXIMO'
                : 'TAMANO_PKG',
        'pkg_total_bytes' => $pkgTotal,
        'temporal_maximo_bytes' =>
            $temporalMaximo,
        'requerido_total_bytes' =>
            $requeridoTotal,
        'margen_seguridad_bytes' =>
            CTPS3_PKG_MARGEN_HDD_SEGURIDAD_BYTES,
        'hdd_libre_bytes_aprox' => null,
        'hdd_libre_texto' => null,
        'hdd_fuente' => null,
        'hdd_antiguedad_segundos' => null,
        'capacidad_util_bytes' => null,
        'faltante_bytes' => null,
    ];

    if (!$fila) {
        $resultado['motivo'] =
            'SIN_ESTADO_HDD';

        return $resultado;
    }

    $libre =
        $fila['hdd_libre_bytes_aprox']
            !== null
                ? max(
                    0,
                    (int) $fila[
                        'hdd_libre_bytes_aprox'
                    ]
                )
                : null;

    $antiguedad =
        $fila['hdd_antiguedad_segundos']
            !== null
                ? (float) $fila[
                    'hdd_antiguedad_segundos'
                ]
                : null;

    $ultimoError =
        trim(
            (string) (
                $fila['hdd_ultimo_error']
                ?? ''
            )
        );

    $resultado['hdd_libre_bytes_aprox'] =
        $libre;

    $resultado['hdd_libre_texto'] =
        $fila['hdd_libre_texto'];

    $resultado['hdd_fuente'] =
        $fila['hdd_fuente'];

    $resultado['hdd_antiguedad_segundos'] =
        $antiguedad;

    if ($libre === null) {
        $resultado['motivo'] =
            'SIN_LECTURA_HDD';

        return $resultado;
    }

    $fresca =
        $antiguedad !== null
        && $antiguedad >= -5.0
        && $antiguedad
            <= CTPS3_PKG_FRESCURA_HDD_SEGUNDOS;

    if (!$fresca) {
        $resultado['motivo'] =
            'LECTURA_HDD_DESACTUALIZADA';

        return $resultado;
    }

    if ($ultimoError !== '') {
        $resultado['motivo'] =
            'ULTIMO_INTENTO_HDD_ERROR';

        return $resultado;
    }

    $capacidadUtil = max(
        0,
        $libre
        - CTPS3_PKG_MARGEN_HDD_SEGURIDAD_BYTES
    );

    $faltante = max(
        0,
        $requeridoTotal
        - $capacidadUtil
    );

    $resultado['verificado'] = true;

    $resultado['capacidad_util_bytes'] =
        $capacidadUtil;

    $resultado['faltante_bytes'] =
        $faltante;

    if ($faltante > 0) {
        $resultado['estado'] =
            'INSUFICIENTE';

        $resultado['motivo'] =
            'ESPACIO_INSUFICIENTE';

        return $resultado;
    }

    $resultado['estado'] = 'OK';
    $resultado['motivo'] = 'OK';

    return $resultado;
}


function ctps3_responder_preflight_pkg(
    array $preflight
): void {
    ctps3_respuesta_json([
        'ok' => true,
        'modo' =>
            'PREFLIGHT_INSTALACION_PKG',
        'preflight' => $preflight,
    ]);
}


function ctps3_bloquear_pkg_si_insuficiente(
    array $preflight
): void {
    if (
        ($preflight['verificado'] ?? false)
            !== true
        || ($preflight['estado'] ?? '')
            !== 'INSUFICIENTE'
    ) {
        return;
    }

    ctps3_respuesta_json([
        'ok' => false,
        'error' =>
            'ESPACIO_INSUFICIENTE_INSTALACION_PKG',
        'preflight' => $preflight,
    ], 409);
}


try {
    $datos = ctps3_json();

    $soloPreflight =
        ($datos['preflight'] ?? false)
        === true;

    $accion = strtoupper(
        trim(
            (string) (
                $datos['accion']
                ?? ''
            )
        )
    );


    $accionesTransferencia = [
        'PAUSAR',
        'REANUDAR',
        'CANCELAR',
        'REINTENTAR',
    ];


    $accionesPkg = [
        'INSTALAR_PKG',
        'ELIMINAR_PKG',
    ];


    /*
     * =====================================================
     * ACCIONES TRADICIONALES DE TRANSFERENCIA
     * =====================================================
     */
    if (
        in_array(
            $accion,
            $accionesTransferencia,
            true
        )
    ) {
        $id = filter_var(
            $datos['transferencia_id']
            ?? null,
            FILTER_VALIDATE_INT
        );

        if (!$id || $id < 1) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'TRANSFERENCIA_INVALIDA',
            ], 422);
        }

        $pdo = ctps3_bd();

        $consulta = $pdo->prepare("
            SELECT estado
            FROM transferencias
            WHERE id=?
        ");

        $consulta->execute([$id]);

        $fila = $consulta->fetch();

        if (!$fila) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'TRANSFERENCIA_NO_EXISTE',
            ], 404);
        }

        $estado =
            (string) $fila['estado'];


        $estadosPermitidos = [
            'PAUSAR' => [
                'EN_COLA',
                'COMPROBANDO',
                'PREPARANDO',
                'TRANSFIRIENDO',
                'REINTENTANDO',
            ],

            'REANUDAR' => [
                'PAUSADO',
            ],

            'CANCELAR' => [
                'EN_COLA',
                'COMPROBANDO',
                'PREPARANDO',
                'TRANSFIRIENDO',
                'PAUSANDO',
                'PAUSADO',
                'REINTENTANDO',
                'ERROR',
            ],

            'REINTENTAR' => [
                'ERROR',
            ],
        ];


        if (
            !in_array(
                $estado,
                $estadosPermitidos[$accion],
                true
            )
        ) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'TRANSICION_INVALIDA',
                'estado' => $estado,
                'accion' => $accion,
            ], 409);
        }


        $pendiente = $pdo->prepare("
            SELECT id
            FROM ordenes
            WHERE
                transferencia_id=?
                AND archivo_remoto_id IS NULL
                AND accion=?
                AND estado IN (
                    'PENDIENTE',
                    'PROCESANDO'
                )
            LIMIT 1
        ");

        $pendiente->execute([
            $id,
            $accion,
        ]);


        if ($pendiente->fetch()) {
            ctps3_respuesta_json([
                'ok' => true,
                'duplicada' => true,
                'mensaje' =>
                    'La orden ya estaba pendiente',
            ]);
        }


        $pdo->beginTransaction();


        $insertar = $pdo->prepare("
            INSERT INTO ordenes (
                transferencia_id,
                archivo_remoto_id,
                accion
            )
            VALUES (
                ?,
                NULL,
                ?
            )
        ");

        $insertar->execute([
            $id,
            $accion,
        ]);


        $ordenId =
            (int) $pdo->lastInsertId();


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
                'ORDEN_SOLICITADA',
                ?
            )
        ");

        $evento->execute([
            $id,
            "Orden solicitada: {$accion}",
        ]);


        $pdo->commit();


        ctps3_respuesta_json([
            'ok' => true,
            'orden_id' => $ordenId,
            'accion' => $accion,
        ]);
    }


    /*
     * =====================================================
     * INSTALACION MULTIPARTE
     * =====================================================
     *
     * INSTALAR_LOTE_PKG existe solamente como acción API.
     * En ordenes se siguen guardando INSTALAR_PKG normales.
     */
    if ($accion === 'INSTALAR_LOTE_PKG') {

        $entrada =
            $datos['archivos_remotos_ids']
            ?? null;

        if (
            !is_array($entrada)
            || count($entrada) < 2
        ) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'LOTE_PKG_ARCHIVOS_INVALIDOS',
            ], 422);
        }


        $ids = [];

        foreach ($entrada as $valor) {
            $id = filter_var(
                $valor,
                FILTER_VALIDATE_INT
            );

            if (!$id || $id < 1) {
                ctps3_respuesta_json([
                    'ok' => false,
                    'error' =>
                        'LOTE_PKG_ARCHIVO_INVALIDO',
                ], 422);
            }

            $ids[] = (int) $id;
        }


        if (
            count(array_unique($ids))
            !== count($ids)
        ) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'LOTE_PKG_ARCHIVOS_DUPLICADOS',
            ], 422);
        }


        $pdo = ctps3_bd();


        /*
         * Ningún lote puede comenzar mientras
         * exista otra operación PKG activa.
         */
        $operacionActiva =
            $pdo->query("
                SELECT id
                FROM ordenes
                WHERE
                    accion IN (
                        'INSTALAR_PKG',
                        'ELIMINAR_PKG'
                    )
                    AND estado IN (
                        'PENDIENTE',
                        'PROCESANDO'
                    )
                LIMIT 1
            ")->fetch();

        if ($operacionActiva) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'PKG_OPERACION_ACTIVA',
            ], 409);
        }


        $loteActivo =
            $pdo->query("
                SELECT id
                FROM lotes_pkg
                WHERE estado IN (
                    'PENDIENTE',
                    'PROCESANDO'
                )
                LIMIT 1
            ")->fetch();

        if ($loteActivo) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'PKG_LOTE_ACTIVO',
                'lote_id' =>
                    (int) $loteActivo['id'],
            ], 409);
        }


        $marcas = implode(
            ',',
            array_fill(
                0,
                count($ids),
                '?'
            )
        );

        $consulta =
            $pdo->prepare("
                SELECT
                    id,
                    nombre,
                    ruta_remota,
                    tamano_bytes,
                    disponible
                FROM archivos_remotos
                WHERE id IN ($marcas)
            ");

        $consulta->execute($ids);

        $archivos =
            $consulta->fetchAll();


        if (
            count($archivos)
            !== count($ids)
        ) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'LOTE_PKG_ARCHIVO_NO_EXISTE',
            ], 404);
        }


        $partes = [];
        $tituloBase = null;


        foreach ($archivos as $archivo) {

            if (!(bool) $archivo['disponible']) {
                ctps3_respuesta_json([
                    'ok' => false,
                    'error' =>
                        'LOTE_PKG_ARCHIVO_NO_DISPONIBLE',
                    'archivo_remoto_id' =>
                        (int) $archivo['id'],
                ], 409);
            }


            $nombre =
                (string) $archivo['nombre'];

            $ruta =
                (string) $archivo['ruta_remota'];


            $nombreSeguro =
                $nombre !== ''
                && !str_contains($nombre, '/')
                && !str_contains($nombre, '\\')
                && $nombre !== '.'
                && $nombre !== '..'
                && str_ends_with(
                    strtolower($nombre),
                    '.pkg'
                );


            $rutaSegura =
                $ruta
                === (
                    '/dev_hdd0/packages/'
                    . $nombre
                );


            $archivoPrueba =
                str_starts_with(
                    $nombre,
                    '__NO_INSTALAR__CTPS3_'
                );


            if (
                !$nombreSeguro
                || !$rutaSegura
                || $archivoPrueba
            ) {
                ctps3_respuesta_json([
                    'ok' => false,
                    'error' =>
                        'LOTE_PKG_RUTA_NO_PERMITIDA',
                    'archivo_remoto_id' =>
                        (int) $archivo['id'],
                ], 403);
            }


            $coincide = preg_match(
                '/^(.*?)[\s_-]+(?:Pt|Part)\s*(\d+)\.pkg$/iu',
                $nombre,
                $m
            );


            if ($coincide !== 1) {
                ctps3_respuesta_json([
                    'ok' => false,
                    'error' =>
                        'LOTE_PKG_NOMBRE_NO_MULTIPARTE',
                    'nombre' =>
                        $nombre,
                ], 422);
            }


            $base =
                trim((string) $m[1]);

            $numero =
                (int) $m[2];


            if (
                $base === ''
                || $numero < 1
            ) {
                ctps3_respuesta_json([
                    'ok' => false,
                    'error' =>
                        'LOTE_PKG_PARTE_INVALIDA',
                ], 422);
            }


            if ($tituloBase === null) {
                $tituloBase = $base;
            } elseif (
                strcasecmp(
                    $tituloBase,
                    $base
                ) !== 0
            ) {
                ctps3_respuesta_json([
                    'ok' => false,
                    'error' =>
                        'LOTE_PKG_TITULOS_DISTINTOS',
                ], 422);
            }


            if (isset($partes[$numero])) {
                ctps3_respuesta_json([
                    'ok' => false,
                    'error' =>
                        'LOTE_PKG_PARTE_DUPLICADA',
                    'parte' =>
                        $numero,
                ], 422);
            }


            $partes[$numero] = [
                'archivo_remoto_id' =>
                    (int) $archivo['id'],

                'nombre' =>
                    $nombre,

                'parte' =>
                    $numero,
            ];
        }


        ksort(
            $partes,
            SORT_NUMERIC
        );


        $esperadas =
            range(
                1,
                count($partes)
            );


        if (
            array_keys($partes)
            !== $esperadas
        ) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'LOTE_PKG_SECUENCIA_INCOMPLETA',
                'partes_detectadas' =>
                    array_keys($partes),
                'partes_esperadas' =>
                    $esperadas,
            ], 422);
        }


        $preflightInstalacion =
            ctps3_preflight_instalacion_pkg(
                $pdo,
                array_map(
                    static fn (array $archivo): int =>
                        (int) $archivo[
                            'tamano_bytes'
                        ],
                    $archivos
                ),
                true
            );


        if ($soloPreflight) {
            ctps3_responder_preflight_pkg(
                $preflightInstalacion
            );
        }


        ctps3_bloquear_pkg_si_insuficiente(
            $preflightInstalacion
        );


        $pdo->beginTransaction();


        try {

            $crearLote =
                $pdo->prepare("
                    INSERT INTO lotes_pkg (
                        titulo,
                        estado,
                        mensaje
                    )
                    VALUES (
                        ?,
                        'PENDIENTE',
                        ?
                    )
                ");

            $crearLote->execute([
                $tituloBase,
                (
                    'Lote preparado con '
                    . count($partes)
                    . ' partes'
                ),
            ]);


            $loteId =
                (int) $pdo->lastInsertId();


            $crearOrden =
                $pdo->prepare("
                    INSERT INTO ordenes (
                        transferencia_id,
                        archivo_remoto_id,
                        accion,
                        estado
                    )
                    VALUES (
                        NULL,
                        ?,
                        'INSTALAR_PKG',
                        'PENDIENTE'
                    )
                ");


            $relacionar =
                $pdo->prepare("
                    INSERT INTO lote_pkg_ordenes (
                        lote_id,
                        orden_id,
                        posicion
                    )
                    VALUES (
                        ?,
                        ?,
                        ?
                    )
                ");


            $ordenesCreadas = [];


            foreach (
                $partes
                as $numero => $parte
            ) {
                $crearOrden->execute([
                    $parte[
                        'archivo_remoto_id'
                    ],
                ]);


                $ordenId =
                    (int) $pdo->lastInsertId();


                $relacionar->execute([
                    $loteId,
                    $ordenId,
                    $numero,
                ]);


                $ordenesCreadas[] = [
                    'orden_id' =>
                        $ordenId,

                    'archivo_remoto_id' =>
                        $parte[
                            'archivo_remoto_id'
                        ],

                    'parte' =>
                        $numero,

                    'nombre' =>
                        $parte['nombre'],
                ];
            }


            $evento =
                $pdo->prepare("
                    INSERT INTO eventos (
                        transferencia_id,
                        nivel,
                        tipo,
                        mensaje,
                        datos_json
                    )
                    VALUES (
                        NULL,
                        'INFO',
                        'PKG_LOTE_SOLICITADO',
                        ?,
                        ?
                    )
                ");


            $evento->execute([
                (
                    'Lote PKG solicitado: '
                    . $tituloBase
                    . ' ('
                    . count($partes)
                    . ' partes)'
                ),

                json_encode(
                    [
                        'lote_id' =>
                            $loteId,

                        'titulo' =>
                            $tituloBase,

                        'total_partes' =>
                            count($partes),

                        'ordenes' =>
                            $ordenesCreadas,
                    ],
                    JSON_UNESCAPED_UNICODE
                    | JSON_UNESCAPED_SLASHES
                    | JSON_INVALID_UTF8_SUBSTITUTE
                ),
            ]);


            $pdo->commit();


        } catch (Throwable $exc) {

            if ($pdo->inTransaction()) {
                $pdo->rollBack();
            }

            throw $exc;
        }


        ctps3_respuesta_json([
            'ok' => true,

            'lote_id' =>
                $loteId,

            'titulo' =>
                $tituloBase,

            'total_partes' =>
                count($partes),

            'ordenes' =>
                $ordenesCreadas,

            'estado' =>
                'PENDIENTE',
        ]);
    }


    /*
     * =====================================================
     * OPERACIONES SOBRE PKG REMOTOS
     * =====================================================
     */
    if (
        in_array(
            $accion,
            $accionesPkg,
            true
        )
    ) {
        $archivoId = filter_var(
            $datos['archivo_remoto_id']
            ?? null,
            FILTER_VALIDATE_INT
        );


        if (
            !$archivoId
            || $archivoId < 1
        ) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'ARCHIVO_REMOTO_INVALIDO',
            ], 422);
        }


        $pdo = ctps3_bd();


        $consulta = $pdo->prepare("
            SELECT
                id,
                nombre,
                ruta_remota,
                tamano_bytes,
                disponible
            FROM archivos_remotos
            WHERE id=?
            LIMIT 1
        ");

        $consulta->execute([
            $archivoId,
        ]);


        $archivo = $consulta->fetch();


        if (!$archivo) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'ARCHIVO_REMOTO_NO_EXISTE',
            ], 404);
        }


        if (!(bool) $archivo['disponible']) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'PKG_NO_DISPONIBLE',
            ], 409);
        }


        $nombre =
            (string) $archivo['nombre'];

        $ruta =
            (string) $archivo['ruta_remota'];


        /*
         * La ruta NUNCA viene del navegador.
         *
         * Se acepta únicamente la combinación
         * ya inventariada en SQLite:
         *
         * /dev_hdd0/packages/<nombre exacto>.pkg
         */
        $rutaEsperada =
            '/dev_hdd0/packages/'
            . $nombre;


        $nombreSeguro =
            $nombre !== ''
            && !str_contains(
                $nombre,
                '/'
            )
            && !str_contains(
                $nombre,
                '\\'
            )
            && $nombre !== '.'
            && $nombre !== '..'
            && str_ends_with(
                strtolower($nombre),
                '.pkg'
            );


        $rutaSegura =
            str_starts_with(
                $ruta,
                '/dev_hdd0/packages/'
            )
            && $ruta === $rutaEsperada;


        $archivoPrueba =
            str_starts_with(
                $nombre,
                '__NO_INSTALAR__CTPS3_'
            );


        if (
            !$nombreSeguro
            || !$rutaSegura
            || $archivoPrueba
        ) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'PKG_RUTA_NO_PERMITIDA',
            ], 403);
        }


        /*
         * Una sola operación PKG simultánea
         * por archivo.
         *
         * Evita, por ejemplo:
         * INSTALAR_PKG + ELIMINAR_PKG
         * pendientes al mismo tiempo.
         */
        $pendiente = $pdo->prepare("
            SELECT
                id,
                accion,
                estado
            FROM ordenes
            WHERE
                archivo_remoto_id=?
                AND estado IN (
                    'PENDIENTE',
                    'PROCESANDO'
                )
            ORDER BY id ASC
            LIMIT 1
        ");

        $pendiente->execute([
            $archivoId,
        ]);


        $ordenExistente =
            $pendiente->fetch();


        /*
         * Resolver una instalación ya enviada
         * a webMAN sin crear una orden nueva.
         */
        $resolucion =
            strtoupper(
                trim(
                    (string) (
                        $datos['resolucion']
                        ?? ''
                    )
                )
            );


        if ($resolucion !== '') {

            if (
                $accion !== 'INSTALAR_PKG'
                || !in_array(
                    $resolucion,
                    [
                        'CONFIRMAR_FINALIZADA',
                        'MARCAR_FALLO',
                    ],
                    true
                )
            ) {
                ctps3_respuesta_json([
                    'ok' => false,
                    'error' =>
                        'RESOLUCION_PKG_INVALIDA',
                ], 422);
            }


            if (
                !$ordenExistente
                || $ordenExistente['accion']
                    !== 'INSTALAR_PKG'
                || $ordenExistente['estado']
                    !== 'PROCESANDO'
            ) {
                ctps3_respuesta_json([
                    'ok' => false,
                    'error' =>
                        'INSTALACION_PKG_NO_ACTIVA',
                ], 409);
            }


            /*
             * Una instalación controlada por un lote
             * multipart no puede resolverse manualmente.
             *
             * El estado de sus órdenes pertenece al
             * ejecutor automático del lote.
             */
            $consultaLoteOrden =
                $pdo->prepare("
                    SELECT
                        lpo.lote_id,
                        lp.estado AS lote_estado
                    FROM lote_pkg_ordenes lpo
                    JOIN lotes_pkg lp
                        ON lp.id=lpo.lote_id
                    WHERE lpo.orden_id=?
                    LIMIT 1
                ");

            $consultaLoteOrden->execute([
                (int) $ordenExistente['id'],
            ]);

            $loteDeOrden =
                $consultaLoteOrden->fetch();


            if ($loteDeOrden) {
                ctps3_respuesta_json([
                    'ok' => false,
                    'error' =>
                        'PKG_LOTE_RESOLUCION_MANUAL_NO_PERMITIDA',

                    'lote_id' =>
                        (int) $loteDeOrden[
                            'lote_id'
                        ],

                    'estado_lote' =>
                        (string) $loteDeOrden[
                            'lote_estado'
                        ],
                ], 409);
            }


            $correcta =
                $resolucion
                === 'CONFIRMAR_FINALIZADA';

            $estadoFinal =
                $correcta
                    ? 'EJECUTADA'
                    : 'ERROR';

            $mensajeFinal =
                $correcta
                    ? (
                        'Instalación finalizada '
                        . 'confirmada desde CTPS3'
                    )
                    : (
                        'Instalación marcada como '
                        . 'fallida desde CTPS3'
                    );

            $tipoEvento =
                $correcta
                    ? 'PKG_INSTALACION_CONFIRMADA'
                    : 'PKG_INSTALACION_FALLIDA';

            $nivel =
                $correcta
                    ? 'INFO'
                    : 'ERROR';


            if ($accion === 'INSTALAR_PKG') {
            $preflightInstalacion =
                ctps3_preflight_instalacion_pkg(
                    $pdo,
                    [
                        (int) $archivo[
                            'tamano_bytes'
                        ],
                    ],
                    false
                );


            if ($soloPreflight) {
                ctps3_responder_preflight_pkg(
                    $preflightInstalacion
                );
            }


            ctps3_bloquear_pkg_si_insuficiente(
                $preflightInstalacion
            );

        } elseif ($soloPreflight) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'PREFLIGHT_SOLO_INSTALACION_PKG',
            ], 422);
        }


        $pdo->beginTransaction();

            $actualizar =
                $pdo->prepare("
                    UPDATE ordenes
                    SET
                        estado=?,
                        procesada_utc=
                            strftime(
                                '%Y-%m-%dT%H:%M:%fZ',
                                'now'
                            ),
                        mensaje=?
                    WHERE
                        id=?
                        AND accion='INSTALAR_PKG'
                        AND estado='PROCESANDO'
                ");

            $actualizar->execute([
                $estadoFinal,
                $mensajeFinal,
                (int) $ordenExistente['id'],
            ]);


            if ($actualizar->rowCount() !== 1) {
                $pdo->rollBack();

                ctps3_respuesta_json([
                    'ok' => false,
                    'error' =>
                        'INSTALACION_PKG_CAMBIO_CONCURRENTE',
                ], 409);
            }


            $evento =
                $pdo->prepare("
                    INSERT INTO eventos (
                        transferencia_id,
                        nivel,
                        tipo,
                        mensaje,
                        datos_json
                    )
                    VALUES (
                        NULL,
                        ?,
                        ?,
                        ?,
                        ?
                    )
                ");

            $evento->execute([
                $nivel,
                $tipoEvento,
                $mensajeFinal . ': ' . $nombre,
                json_encode(
                    [
                        'orden_id' =>
                            (int) $ordenExistente['id'],
                        'archivo_remoto_id' =>
                            (int) $archivoId,
                        'nombre' =>
                            $nombre,
                        'resolucion' =>
                            $resolucion,
                    ],
                    JSON_UNESCAPED_UNICODE
                    | JSON_UNESCAPED_SLASHES
                ),
            ]);

            $pdo->commit();


            ctps3_respuesta_json([
                'ok' => true,
                'orden_id' =>
                    (int) $ordenExistente['id'],
                'estado' =>
                    $estadoFinal,
                'mensaje' =>
                    $mensajeFinal,
            ]);
        }


        /*
         * Exclusión mutua:
         *
         * mientras exista un lote multipart pendiente
         * o procesando, no se aceptan nuevas operaciones
         * PKG individuales.
         */
        $loteActivoIndividual =
            $pdo->query("
                SELECT
                    id,
                    estado
                FROM lotes_pkg
                WHERE estado IN (
                    'PENDIENTE',
                    'PROCESANDO'
                )
                ORDER BY id ASC
                LIMIT 1
            ")->fetch();


        if ($loteActivoIndividual) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'PKG_LOTE_ACTIVO',

                'lote_id' =>
                    (int) $loteActivoIndividual[
                        'id'
                    ],

                'estado_lote' =>
                    (string) $loteActivoIndividual[
                        'estado'
                    ],
            ], 409);
        }


        /*
         * Mientras la PS3 instala un PKG,
         * no aceptar otra operación PKG.
         */
        $instalacionActiva =
            $pdo->query("
                SELECT id
                FROM ordenes
                WHERE
                    accion='INSTALAR_PKG'
                    AND estado='PROCESANDO'
                ORDER BY id ASC
                LIMIT 1
            ")->fetch();


        if ($instalacionActiva) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'PKG_INSTALACION_ACTIVA',
            ], 409);
        }


        if ($ordenExistente) {
            ctps3_respuesta_json([
                'ok' => false,
                'error' =>
                    'PKG_OPERACION_PENDIENTE',

                'orden_id' =>
                    (int) $ordenExistente[
                        'id'
                    ],

                'accion_actual' =>
                    $ordenExistente[
                        'accion'
                    ],

                'estado_actual' =>
                    $ordenExistente[
                        'estado'
                    ],
            ], 409);
        }


        $pdo->beginTransaction();


        $insertar = $pdo->prepare("
            INSERT INTO ordenes (
                transferencia_id,
                archivo_remoto_id,
                accion
            )
            VALUES (
                NULL,
                ?,
                ?
            )
        ");

        $insertar->execute([
            $archivoId,
            $accion,
        ]);


        $ordenId =
            (int) $pdo->lastInsertId();


        $datosEvento = json_encode(
            [
                'orden_id' =>
                    $ordenId,

                'archivo_remoto_id' =>
                    (int) $archivoId,

                'accion' =>
                    $accion,

                'nombre' =>
                    $nombre,

                'ruta_remota' =>
                    $ruta,

                'tamano_bytes' =>
                    (int) $archivo[
                        'tamano_bytes'
                    ],
            ],
            JSON_UNESCAPED_UNICODE
            | JSON_UNESCAPED_SLASHES
            | JSON_INVALID_UTF8_SUBSTITUTE
        );


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
                'INFO',
                'PKG_ORDEN_SOLICITADA',
                ?,
                ?
            )
        ");

        $evento->execute([
            (
                $accion
                . ': '
                . $nombre
            ),
            $datosEvento,
        ]);


        $pdo->commit();


        ctps3_respuesta_json([
            'ok' => true,

            'orden_id' =>
                $ordenId,

            'accion' =>
                $accion,

            'archivo' => [
                'id' =>
                    (int) $archivoId,

                'nombre' =>
                    $nombre,

                'ruta_remota' =>
                    $ruta,

                'tamano_bytes' =>
                    (int) $archivo[
                        'tamano_bytes'
                    ],
            ],
        ]);
    }


    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'ACCION_INVALIDA',
    ], 422);


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
        '[CTPS3][accion-v2] '
        . $e->getMessage()
    );


    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'ERROR_INTERNO',
    ], 500);
}
