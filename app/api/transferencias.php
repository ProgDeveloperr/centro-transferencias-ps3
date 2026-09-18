<?php

declare(strict_types=1);

require_once __DIR__ . '/../includes/aplicacion.php';

ctps3_exigir_metodo('GET');

try {
    $pdo = ctps3_bd();

    $telemetriaDesdeValor =
        $pdo->query("
            SELECT valor
            FROM meta
            WHERE clave='telemetria_ftp_desde_utc'
            LIMIT 1
        ")->fetchColumn();

    $telemetriaDesde =
        $telemetriaDesdeValor !== false
        && $telemetriaDesdeValor !== null
            ? (string) $telemetriaDesdeValor
            : null;

    $ahora =
        new DateTimeImmutable(
            'now',
            new DateTimeZone('UTC')
        );

    $segundosEntre =
        static function (
            ?string $desde,
            ?string $hasta = null
        ) use ($ahora): ?int {
            if (!$desde) {
                return null;
            }

            try {
                $inicio =
                    new DateTimeImmutable(
                        $desde
                    );

                $fin =
                    $hasta
                        ? new DateTimeImmutable(
                            $hasta
                        )
                        : $ahora;

                return max(
                    0,
                    $fin->getTimestamp()
                    - $inicio->getTimestamp()
                );

            } catch (Throwable) {
                return null;
            }
        };

    $consulta = $pdo->query("
        SELECT
            t.id,
            t.archivo_id,
            t.nombre_snapshot,
            t.ruta_relativa_snapshot,
            t.nombre_remoto,
            t.tamano_total,
            t.bytes_transferidos,
            t.bytes_remotos,
            t.estado,
            t.prioridad,
            t.posicion_cola,
            t.intentos,
            t.pid,
            t.velocidad_bps,
            t.velocidad_promedio_bps,
            t.eta_segundos,
            t.reanudada,
            t.mensaje,
            t.error_codigo,
            t.error_detalle,
            t.creada_utc,
            t.iniciada_utc,
            t.actualizada_utc,
            t.finalizada_utc,

            (
                SELECT COUNT(*)
                FROM transferencia_intentos ti
                WHERE ti.transferencia_id=t.id
            ) AS sesiones_ftp,

            (
                SELECT COALESCE(
                    SUM(ti.bytes_ftp),
                    0
                )
                FROM transferencia_intentos ti
                WHERE ti.transferencia_id=t.id
            ) AS bytes_ftp,

            (
                SELECT COALESCE(
                    SUM(ti.duracion_segundos),
                    0
                )
                FROM transferencia_intentos ti
                WHERE ti.transferencia_id=t.id
            ) AS tiempo_ftp_segundos,

            (
                SELECT COALESCE(
                    SUM(ti.bytes_ftp)
                    /
                    NULLIF(
                        SUM(ti.duracion_segundos),
                        0
                    ),
                    0
                )
                FROM transferencia_intentos ti
                WHERE ti.transferencia_id=t.id
            ) AS velocidad_ftp_media_bps,

            a.titulo_juego,
            a.codigo_juego,
            a.parte_numero

        FROM transferencias t

        LEFT JOIN archivos_locales a
            ON a.id=t.archivo_id

        ORDER BY
            CASE
                WHEN t.estado IN (
                    'TRANSFIRIENDO',
                    'COMPROBANDO',
                    'PREPARANDO',
                    'VERIFICANDO'
                )
                    THEN 0

                WHEN t.estado='EN_COLA'
                    THEN 1

                WHEN t.estado='PAUSADO'
                    THEN 2

                WHEN t.estado='REINTENTANDO'
                    THEN 3

                ELSE 4
            END ASC,

            CASE
                WHEN t.estado='EN_COLA'
                    THEN t.prioridad
                ELSE 0
            END ASC,

            CASE
                WHEN t.estado='EN_COLA'
                    THEN t.posicion_cola
                ELSE 0
            END ASC,

            CASE
                WHEN t.estado IN (
                    'EN_COLA',
                    'TRANSFIRIENDO',
                    'COMPROBANDO',
                    'PREPARANDO',
                    'VERIFICANDO',
                    'PAUSADO',
                    'REINTENTANDO'
                )
                    THEN t.creada_utc
                ELSE NULL
            END ASC,

            t.id DESC

        LIMIT 150
    ");

    $transferencias = [];

    $pendientesBytes = 0;
    $cantidadActivas = 0;
    $cantidadEnCola = 0;
    $cantidadPausadas = 0;

    $velocidadActual = 0.0;

    $duracionesHistoricas = [];

    foreach ($consulta as $fila) {
        foreach ([
            'id',
            'archivo_id',
            'tamano_total',
            'bytes_transferidos',
            'bytes_remotos',
            'prioridad',
            'posicion_cola',
            'intentos',
            'sesiones_ftp',
            'bytes_ftp',
        ] as $campo) {
            $fila[$campo] =
                (int) $fila[$campo];
        }

        foreach ([
            'pid',
            'eta_segundos',
            'parte_numero',
        ] as $campo) {
            $fila[$campo] =
                $fila[$campo] !== null
                    ? (int) $fila[$campo]
                    : null;
        }

        foreach ([
            'velocidad_bps',
            'velocidad_promedio_bps',
            'tiempo_ftp_segundos',
            'velocidad_ftp_media_bps',
        ] as $campo) {
            $fila[$campo] =
                $fila[$campo] !== null
                    ? (float) $fila[$campo]
                    : null;
        }

        $fila['reanudada'] =
            (bool) $fila['reanudada'];

        $fila['telemetria_ftp_disponible'] =
            $telemetriaDesde !== null
            && strcmp(
                (string) $fila['actualizada_utc'],
                $telemetriaDesde
            ) >= 0;

        $fila['activa'] =
            ctps3_estado_activo(
                $fila['estado']
            );

        $total =
            max(
                1,
                $fila['tamano_total']
            );

        $fila['porcentaje'] =
            min(
                100,
                round(
                    (
                        $fila[
                            'bytes_transferidos'
                        ]
                        / $total
                    ) * 100,
                    2
                )
            );

        $fila['bytes_pendientes'] =
            max(
                0,
                $fila['tamano_total']
                - $fila[
                    'bytes_transferidos'
                ]
            );

        $fila['prioridad_nombre'] =
            $fila['prioridad'] <= 10
                ? 'ALTA'
                : (
                    $fila['prioridad'] >= 200
                        ? 'BAJA'
                        : 'NORMAL'
                );

        $fila['duracion_segundos'] =
            $fila['iniciada_utc']
                ? $segundosEntre(
                    $fila['iniciada_utc'],
                    $fila['finalizada_utc']
                )
                : null;

        $hastaEspera =
            $fila['iniciada_utc']
            ?? $fila['finalizada_utc'];

        $fila['espera_segundos'] =
            $segundosEntre(
                $fila['creada_utc'],
                $hastaEspera
            );

        if ($fila['activa']) {
            $cantidadActivas++;

            $pendientesBytes +=
                $fila[
                    'bytes_pendientes'
                ];
        }

        if (
            $fila['estado']
            === 'EN_COLA'
        ) {
            $cantidadEnCola++;
        }

        if (
            $fila['estado']
            === 'PAUSADO'
        ) {
            $cantidadPausadas++;
        }

        if (
            $fila['estado']
            === 'TRANSFIRIENDO'
            && (
                $fila['velocidad_bps']
                ?? 0
            ) > 0
        ) {
            $velocidadActual =
                (float) $fila[
                    'velocidad_bps'
                ];
        }

        if (
            $fila['estado']
                === 'COMPLETADO'
            && $fila[
                'duracion_segundos'
            ] !== null
            && $fila[
                'duracion_segundos'
            ] > 0
        ) {
            $duracionesHistoricas[] =
                $fila[
                    'duracion_segundos'
                ];
        }

        $transferencias[] =
            $fila;
    }

    $historica =
        $pdo->query("
            SELECT AVG(
                velocidad_promedio_bps
            )
            FROM (
                SELECT
                    velocidad_promedio_bps
                FROM transferencias
                WHERE
                    estado='COMPLETADO'
                    AND velocidad_promedio_bps > 0
                ORDER BY
                    finalizada_utc DESC
                LIMIT 10
            )
        ")->fetchColumn();

    $velocidadHistorica =
        $historica !== false
        && $historica !== null
            ? (float) $historica
            : 0.0;

    $velocidadReferencia =
        $velocidadActual > 0
            ? $velocidadActual
            : $velocidadHistorica;

    $etaCola =
        $velocidadReferencia > 0
            ? (int) ceil(
                $pendientesBytes
                / $velocidadReferencia
            )
            : null;

    $valorColaPausada =
        $pdo->query("
            SELECT valor
            FROM meta
            WHERE clave='cola_pausada'
            LIMIT 1
        ")->fetchColumn();

    $colaPausada =
        (string) $valorColaPausada
        === '1';

    $proxima =
        $pdo->query("
            SELECT id
            FROM transferencias
            WHERE estado='EN_COLA'
            ORDER BY
                prioridad ASC,
                posicion_cola ASC,
                creada_utc ASC,
                id ASC
            LIMIT 1
        ")->fetchColumn();

    $duracionMedia =
        $duracionesHistoricas
            ? (int) round(
                array_sum(
                    $duracionesHistoricas
                )
                / count(
                    $duracionesHistoricas
                )
            )
            : null;

    ctps3_respuesta_json([
        'ok' => true,

        'resumen' => [
            'activas' =>
                $cantidadActivas,

            'en_cola' =>
                $cantidadEnCola,

            'pausadas' =>
                $cantidadPausadas,

            'pendientes_bytes' =>
                $pendientesBytes,

            'velocidad_actual_bps' =>
                $velocidadActual,

            'velocidad_historica_bps' =>
                $velocidadHistorica,

            'velocidad_referencia_bps' =>
                $velocidadReferencia,

            'eta_cola_segundos' =>
                $etaCola,

            'cola_pausada' =>
                $colaPausada,

            'proxima_transferencia_id' =>
                $proxima !== false
                    ? (int) $proxima
                    : null,

            'duracion_media_segundos' =>
                $duracionMedia,

            'telemetria_ftp_desde_utc' =>
                $telemetriaDesde,
        ],

        'transferencias' =>
            $transferencias,
    ]);

} catch (Throwable $e) {
    error_log(
        '[CTPS3][transferencias] ' .
        $e->getMessage()
    );

    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'ERROR_INTERNO',
    ], 500);
}
