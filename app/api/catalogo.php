<?php

declare(strict_types=1);

require_once __DIR__ . '/../includes/aplicacion.php';

ctps3_exigir_metodo('GET');

try {
    $pdo = ctps3_bd();

    $consulta = $pdo->query("
        SELECT
            a.id,
            a.nombre,
            a.ruta_relativa,
            a.tamano_bytes,
            a.titulo_juego,
            a.codigo_juego,
            a.etiqueta_origen,
            a.parte_numero,
            a.es_fragmentado,
            a.extension,
            a.formato,
            a.sha256,
            a.sha256_estado,
            a.disponible,
            a.detectado_utc,
            a.visto_utc,
            a.actualizado_utc,

            COALESCE(
                r_pkg.id,
                r_iso.id,
                r_ps2.id
            ) AS remoto_id,

            COALESCE(
                r_pkg.tamano_bytes,
                r_iso.tamano_bytes,
                r_ps2.tamano_bytes
            ) AS remoto_tamano_bytes,

            COALESCE(
                r_pkg.fecha_modificacion_ftp,
                r_iso.fecha_modificacion_ftp,
                r_ps2.fecha_modificacion_ftp
            ) AS remoto_fecha_modificacion_ftp,

            CASE
                WHEN
                    COALESCE(
                        r_pkg.id,
                        r_iso.id,
                        r_ps2.id
                    ) IS NULL
                    THEN 'AUSENTE'

                WHEN
                    COALESCE(
                        r_pkg.tamano_bytes,
                        r_iso.tamano_bytes,
                        r_ps2.tamano_bytes
                    ) = a.tamano_bytes
                    THEN 'COMPLETO'

                WHEN
                    COALESCE(
                        r_pkg.tamano_bytes,
                        r_iso.tamano_bytes,
                        r_ps2.tamano_bytes
                    ) < a.tamano_bytes
                    THEN 'PARCIAL'

                ELSE 'CONFLICTO'
            END AS estado_ps3

        FROM archivos_locales a

        LEFT JOIN archivos_remotos r_pkg
            ON
                a.formato='PKG'
                AND r_pkg.nombre=a.nombre
                AND r_pkg.disponible=1

        LEFT JOIN archivos_remotos_iso r_iso
            ON
                a.formato='PS3ISO'
                AND r_iso.ruta_remota=
                    '/dev_hdd0/PS3ISO/'
                    || a.nombre
                AND r_iso.disponible=1

        LEFT JOIN archivos_remotos_ps2iso r_ps2
            ON
                a.formato='PS2ISO'
                AND r_ps2.ruta_remota=
                    '/dev_hdd0/PS2ISO/'
                    || a.nombre
                AND r_ps2.disponible=1

        WHERE a.disponible=1

        ORDER BY
            COALESCE(
                a.titulo_juego,
                a.nombre
            ),
            COALESCE(
                a.parte_numero,
                0
            ),
            a.nombre
    ");

    $archivos = [];
    $totalBytes = 0;

    $resumenEstados = [
        'COMPLETO' => 0,
        'PARCIAL' => 0,
        'AUSENTE' => 0,
        'CONFLICTO' => 0,
    ];

    foreach ($consulta as $fila) {

        $fila['id'] =
            (int) $fila['id'];

        $fila['tamano_bytes'] =
            (int) $fila['tamano_bytes'];

        $fila['parte_numero'] =
            $fila['parte_numero'] !== null
                ? (int) $fila['parte_numero']
                : null;

        $fila['es_fragmentado'] =
            (bool) $fila['es_fragmentado'];

        $fila['disponible'] =
            (bool) $fila['disponible'];

        $fila['remoto_id'] =
            $fila['remoto_id'] !== null
                ? (int) $fila['remoto_id']
                : null;

        $fila['remoto_tamano_bytes'] =
            $fila[
                'remoto_tamano_bytes'
            ] !== null
                ? (int) $fila[
                    'remoto_tamano_bytes'
                ]
                : null;

        $totalBytes +=
            $fila['tamano_bytes'];

        $estado =
            $fila['estado_ps3'];

        if (
            isset(
                $resumenEstados[$estado]
            )
        ) {
            $resumenEstados[$estado]++;
        }

        $archivos[] = $fila;
    }

    $juegos = [];

    foreach ($archivos as $archivo) {
        $clave =
            $archivo['formato']
            . '::'
            . (
                $archivo['codigo_juego']
                ?? $archivo['titulo_juego']
                ?? $archivo['nombre']
            );

        $juegos[$clave] = true;
    }

    ctps3_respuesta_json([
        'ok' => true,

        'resumen' => [
            'archivos' =>
                count($archivos),

            'juegos' =>
                count($juegos),

            'tamano_total_bytes' =>
                $totalBytes,

            'ps3' =>
                $resumenEstados,
        ],

        'archivos' =>
            $archivos,
    ]);

} catch (Throwable $e) {
    error_log(
        '[CTPS3][catalogo] ' .
        $e->getMessage()
    );

    ctps3_respuesta_json([
        'ok' => false,
        'error' => 'ERROR_INTERNO',
    ], 500);
}
