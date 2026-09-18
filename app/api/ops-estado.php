<?php

declare(strict_types=1);

const CTPS3_OPS_ESTADO_API_VERSION = '1.0.0';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, max-age=0');

$metodo =
    $_SERVER['REQUEST_METHOD']
    ?? 'GET';

if ($metodo !== 'GET') {
    http_response_code(405);
    header('Allow: GET');

    echo json_encode(
        [
            'ok' => false,
            'version' =>
                CTPS3_OPS_ESTADO_API_VERSION,
            'error' => 'METODO_NO_PERMITIDO',
        ],
        JSON_UNESCAPED_UNICODE
        | JSON_UNESCAPED_SLASHES
    );

    return;
}

$rutaEstado =
    getenv('CTPS3_OPS_ESTADO_JSON')
    ?: '/var/www/datos-transferencias-ps3/ops-estado.json';

if (
    !is_file($rutaEstado)
    || !is_readable($rutaEstado)
) {
    http_response_code(503);

    echo json_encode(
        [
            'ok' => false,
            'version' =>
                CTPS3_OPS_ESTADO_API_VERSION,
            'error' =>
                'ESTADO_CONSOLIDADO_NO_DISPONIBLE',
        ],
        JSON_UNESCAPED_UNICODE
        | JSON_UNESCAPED_SLASHES
    );

    return;
}

$contenido =
    file_get_contents(
        $rutaEstado
    );

if ($contenido === false) {
    http_response_code(503);

    echo json_encode(
        [
            'ok' => false,
            'version' =>
                CTPS3_OPS_ESTADO_API_VERSION,
            'error' =>
                'ESTADO_CONSOLIDADO_NO_LEIBLE',
        ],
        JSON_UNESCAPED_UNICODE
        | JSON_UNESCAPED_SLASHES
    );

    return;
}

try {
    $estado =
        json_decode(
            $contenido,
            true,
            64,
            JSON_THROW_ON_ERROR
        );
} catch (Throwable $e) {
    http_response_code(500);

    echo json_encode(
        [
            'ok' => false,
            'version' =>
                CTPS3_OPS_ESTADO_API_VERSION,
            'error' =>
                'ESTADO_CONSOLIDADO_INVALIDO',
        ],
        JSON_UNESCAPED_UNICODE
        | JSON_UNESCAPED_SLASHES
    );

    return;
}

if (
    !is_array($estado)
    || !isset(
        $estado['auditoria'],
        $estado['release'],
        $estado['backup'],
        $estado['timers'],
        $estado['ps3']
    )
) {
    http_response_code(500);

    echo json_encode(
        [
            'ok' => false,
            'version' =>
                CTPS3_OPS_ESTADO_API_VERSION,
            'error' =>
                'CONTRATO_ESTADO_INCOMPLETO',
        ],
        JSON_UNESCAPED_UNICODE
        | JSON_UNESCAPED_SLASHES
    );

    return;
}

$auditoria =
    $estado['auditoria'];

$release =
    $estado['release'];

$backup =
    $estado['backup'];

$timers =
    $estado['timers'];

$ps3 =
    $estado['ps3'];

$respuesta = [
    'ok' => true,
    'version' =>
        CTPS3_OPS_ESTADO_API_VERSION,
    'generado_utc' =>
        $estado['generado_utc']
        ?? null,
    'auditoria' => [
        'auditor_version' =>
            $auditoria['auditor_version']
            ?? null,
        'auditor_sha256' =>
            $auditoria['auditor_sha256']
            ?? null,
        'fecha' =>
            $auditoria['fecha']
            ?? null,
        'pass' =>
            (int) (
                $auditoria['pass']
                ?? 0
            ),
        'warn' =>
            (int) (
                $auditoria['warn']
                ?? 0
            ),
        'fail' =>
            (int) (
                $auditoria['fail']
                ?? 0
            ),
        'estado_general' =>
            (string) (
                $auditoria['estado_general']
                ?? 'DESCONOCIDO'
            ),
    ],
    'release' => [
        'nombre' =>
            $release['nombre']
            ?? null,
        'fecha_utc' =>
            $release['fecha_utc']
            ?? null,
        'schema_version' =>
            $release['schema_version']
            ?? null,
        'integrity_check' =>
            $release['integrity_check']
            ?? null,
        'foreign_key_check' =>
            $release['foreign_key_check']
            ?? null,
        'eliminaciones_activas' =>
            $release['eliminaciones_activas']
            ?? null,
        'estado_funcional' =>
            $release['estado_funcional']
            ?? [],
    ],
    'backup' => [
        'release' =>
            $backup['release']
            ?? null,
        'fecha_utc' =>
            $backup['fecha_utc']
            ?? null,
        'archivos_payload' =>
            $backup['archivos_payload']
            ?? null,
        'bytes_payload' =>
            $backup['bytes_payload']
            ?? null,
        'snapshot_sha256' =>
            $backup['snapshot_sha256']
            ?? null,
        'snapshot_schema' =>
            $backup['snapshot_schema']
            ?? null,
    ],
    'timers' => $timers,
    'ps3' => [
        'requerida_para_auditoria' =>
            (bool) (
                $ps3['requerida_para_auditoria']
                ?? false
            ),
        'eliminacion_real_e2e' =>
            $ps3['eliminacion_real_e2e']
            ?? 'NO_EJECUTADA',
    ],
];

echo json_encode(
    $respuesta,
    JSON_UNESCAPED_UNICODE
    | JSON_UNESCAPED_SLASHES
);
