<?php

declare(strict_types=1);

const CTPS3_OPS_HISTORIAL_API_VERSION = '1.0.0';

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
                CTPS3_OPS_HISTORIAL_API_VERSION,
            'error' =>
                'METODO_NO_PERMITIDO',
        ],
        JSON_UNESCAPED_UNICODE
        | JSON_UNESCAPED_SLASHES
    );

    return;
}

$ruta =
    '/var/www/datos-transferencias-ps3/ops-historial.json';

if (
    !is_file($ruta)
    || !is_readable($ruta)
) {
    http_response_code(503);

    echo json_encode(
        [
            'ok' => false,
            'version' =>
                CTPS3_OPS_HISTORIAL_API_VERSION,
            'error' =>
                'HISTORIAL_NO_DISPONIBLE',
        ],
        JSON_UNESCAPED_UNICODE
        | JSON_UNESCAPED_SLASHES
    );

    return;
}

$contenido =
    file_get_contents($ruta);

if ($contenido === false) {
    http_response_code(503);

    echo json_encode(
        [
            'ok' => false,
            'version' =>
                CTPS3_OPS_HISTORIAL_API_VERSION,
            'error' =>
                'HISTORIAL_NO_LEIBLE',
        ],
        JSON_UNESCAPED_UNICODE
        | JSON_UNESCAPED_SLASHES
    );

    return;
}

try {
    $datos =
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
                CTPS3_OPS_HISTORIAL_API_VERSION,
            'error' =>
                'HISTORIAL_INVALIDO',
        ],
        JSON_UNESCAPED_UNICODE
        | JSON_UNESCAPED_SLASHES
    );

    return;
}

if (
    !is_array($datos)
    || !isset(
        $datos['resumen'],
        $datos['auditorias']
    )
    || !is_array($datos['auditorias'])
) {
    http_response_code(500);

    echo json_encode(
        [
            'ok' => false,
            'version' =>
                CTPS3_OPS_HISTORIAL_API_VERSION,
            'error' =>
                'CONTRATO_HISTORIAL_INVALIDO',
        ],
        JSON_UNESCAPED_UNICODE
        | JSON_UNESCAPED_SLASHES
    );

    return;
}

echo json_encode(
    [
        'ok' => true,
        'version' =>
            CTPS3_OPS_HISTORIAL_API_VERSION,
        'generado_utc' =>
            $datos['generado_utc']
            ?? null,
        'resumen' =>
            $datos['resumen'],
        'auditorias' =>
            array_slice(
                $datos['auditorias'],
                0,
                50
            ),
    ],
    JSON_UNESCAPED_UNICODE
    | JSON_UNESCAPED_SLASHES
);
