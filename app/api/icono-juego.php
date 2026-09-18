<?php

declare(strict_types=1);

require_once __DIR__
    . '/../includes/aplicacion.php';


const CTPS3_ICONO_JUEGO_API_VERSION =
    '1.0.2';

const CTPS3_ICONOS_DIRECTORIO =
    '/var/www/datos-transferencias-ps3/'
    . 'iconos-juegos';

const CTPS3_ICONOS_MANIFIESTO =
    CTPS3_ICONOS_DIRECTORIO
    . '/manifiesto.tsv';


/**
 * Devuelve un error JSON y termina.
 */
function ctps3_icono_error(
    int $codigoHttp,
    string $codigo,
    string $mensaje
): never {

    ctps3_respuesta_json([
        'ok' => false,

        'error' => [
            'codigo' =>
                $codigo,

            'mensaje' =>
                $mensaje,
        ],

        'api_version' =>
            CTPS3_ICONO_JUEGO_API_VERSION,
    ], $codigoHttp);
}


/**
 * Obtiene y valida ?id=N.
 */
function ctps3_icono_obtener_id(): int
{
    $valor = $_GET['id']
        ?? null;

    if (
        !is_string($valor)
        && !is_int($valor)
    ) {
        ctps3_icono_error(
            400,
            'ID_REQUERIDO',
            'Se requiere un juego_id.'
        );
    }

    $texto = trim(
        (string) $valor
    );

    if (
        $texto === ''
        || preg_match(
            '/^[1-9][0-9]*$/D',
            $texto
        ) !== 1
    ) {
        ctps3_icono_error(
            400,
            'ID_INVALIDO',
            'El juego_id no es válido.'
        );
    }

    $id = (int) $texto;

    if (
        $id < 1
        || $id > 2147483647
    ) {
        ctps3_icono_error(
            400,
            'ID_INVALIDO',
            'El juego_id está fuera de rango.'
        );
    }

    return $id;
}


/**
 * Confirma que el juego exista en CTPS3.
 */
function ctps3_icono_validar_juego(
    PDO $bd,
    int $juegoId
): void {

    $consulta = $bd->prepare(
        '
        SELECT id
        FROM juegos_ps3
        WHERE id = :id
        LIMIT 1
        '
    );

    $consulta->execute([
        ':id' =>
            $juegoId,
    ]);

    if (
        $consulta->fetchColumn()
        === false
    ) {
        ctps3_icono_error(
            404,
            'JUEGO_NO_EXISTE',
            'El juego solicitado no existe.'
        );
    }
}


/**
 * Lee una única fila del manifiesto
 * correspondiente al juego.
 */
function ctps3_icono_buscar_manifiesto(
    int $juegoId
): array {

    $ruta =
        CTPS3_ICONOS_MANIFIESTO;

    if (
        !is_file($ruta)
        || !is_readable($ruta)
    ) {
        ctps3_icono_error(
            503,
            'CACHE_NO_DISPONIBLE',
            'La caché visual no está disponible.'
        );
    }

    $fh = fopen(
        $ruta,
        'rb'
    );

    if ($fh === false) {
        ctps3_icono_error(
            503,
            'MANIFIESTO_NO_LEGIBLE',
            'No se pudo abrir el manifiesto.'
        );
    }

    try {

        $cabecera = fgetcsv(
            $fh,
            0,
            "\t"
        );

        if (
            !is_array($cabecera)
            || $cabecera === []
        ) {
            ctps3_icono_error(
                503,
                'MANIFIESTO_INVALIDO',
                'El manifiesto de imágenes es inválido.'
            );
        }

        $requeridos = [
            'juego_id',
            'archivo_cache',
            'bytes',
            'ancho',
            'alto',
            'sha256',
        ];

        foreach (
            $requeridos
            as $campo
        ) {
            if (
                !in_array(
                    $campo,
                    $cabecera,
                    true
                )
            ) {
                ctps3_icono_error(
                    503,
                    'MANIFIESTO_INVALIDO',
                    'El manifiesto está incompleto.'
                );
            }
        }

        while (
            (
                $fila = fgetcsv(
                    $fh,
                    0,
                    "\t"
                )
            ) !== false
        ) {

            if (
                count($fila)
                !== count($cabecera)
            ) {
                continue;
            }

            $datos = array_combine(
                $cabecera,
                $fila
            );

            if (
                !is_array($datos)
            ) {
                continue;
            }

            if (
                (int) (
                    $datos['juego_id']
                    ?? 0
                )
                !== $juegoId
            ) {
                continue;
            }

            return $datos;
        }

    } finally {
        fclose($fh);
    }

    ctps3_icono_error(
        404,
        'ICONO_NO_EXISTE',
        'No existe una imagen cacheada para este juego.'
    );
}


/**
 * Valida el archivo indicado por el
 * manifiesto sin aceptar rutas externas.
 */
function ctps3_icono_validar_archivo(
    array $entrada
): array {

    $archivo = (
        $entrada['archivo_cache']
        ?? ''
    );

    if (
        !is_string($archivo)
        || preg_match(
            '/^[0-9]{3,10}_'
            . '[A-Z0-9_-]+'
            . '_ICON0\.png$/D',
            $archivo
        ) !== 1
    ) {
        ctps3_icono_error(
            503,
            'CACHE_INVALIDA',
            'El nombre cacheado no es válido.'
        );
    }

    if (
        basename($archivo)
        !== $archivo
    ) {
        ctps3_icono_error(
            503,
            'CACHE_INVALIDA',
            'La referencia del archivo no es segura.'
        );
    }

    $base = realpath(
        CTPS3_ICONOS_DIRECTORIO
    );

    if (
        $base === false
        || !is_dir($base)
    ) {
        ctps3_icono_error(
            503,
            'CACHE_NO_DISPONIBLE',
            'El directorio visual no está disponible.'
        );
    }

    $ruta = realpath(
        $base
        . DIRECTORY_SEPARATOR
        . $archivo
    );

    if ($ruta === false) {
        ctps3_icono_error(
            404,
            'ICONO_NO_EXISTE',
            'La imagen cacheada no existe.'
        );
    }

    $prefijo =
        $base
        . DIRECTORY_SEPARATOR;

    if (
        !str_starts_with(
            $ruta,
            $prefijo
        )
    ) {
        ctps3_icono_error(
            503,
            'CACHE_INVALIDA',
            'La ruta resuelta no pertenece a la caché.'
        );
    }

    if (
        !is_file($ruta)
        || !is_readable($ruta)
    ) {
        ctps3_icono_error(
            404,
            'ICONO_NO_LEGIBLE',
            'La imagen cacheada no es legible.'
        );
    }

    $esperadoBytes = (
        $entrada['bytes']
        ?? ''
    );

    if (
        !is_string($esperadoBytes)
        || preg_match(
            '/^[0-9]+$/D',
            $esperadoBytes
        ) !== 1
    ) {
        ctps3_icono_error(
            503,
            'MANIFIESTO_INVALIDO',
            'El tamaño registrado no es válido.'
        );
    }

    $bytes = filesize(
        $ruta
    );

    if (
        $bytes === false
        || $bytes !== (int) $esperadoBytes
    ) {
        ctps3_icono_error(
            503,
            'CACHE_CORRUPTA',
            'El tamaño de la imagen no coincide.'
        );
    }

    $fh = fopen(
        $ruta,
        'rb'
    );

    if ($fh === false) {
        ctps3_icono_error(
            503,
            'CACHE_NO_LEGIBLE',
            'No se pudo leer la imagen.'
        );
    }

    $firma = fread(
        $fh,
        8
    );

    fclose(
        $fh
    );

    if (
        $firma !==
        "\x89PNG\r\n\x1a\n"
    ) {
        ctps3_icono_error(
            503,
            'CACHE_CORRUPTA',
            'La firma PNG es inválida.'
        );
    }

    $shaEsperado = strtolower(
        trim(
            (string) (
                $entrada['sha256']
                ?? ''
            )
        )
    );

    if (
        preg_match(
            '/^[a-f0-9]{64}$/D',
            $shaEsperado
        ) !== 1
    ) {
        ctps3_icono_error(
            503,
            'MANIFIESTO_INVALIDO',
            'El SHA-256 registrado no es válido.'
        );
    }

    $shaReal = hash_file(
        'sha256',
        $ruta
    );

    if (
        !is_string($shaReal)
        || !hash_equals(
            $shaEsperado,
            strtolower($shaReal)
        )
    ) {
        ctps3_icono_error(
            503,
            'CACHE_CORRUPTA',
            'La imagen no coincide con el manifiesto.'
        );
    }

    return [
        'ruta' =>
            $ruta,

        'bytes' =>
            $bytes,

        'sha256' =>
            $shaEsperado,

        'ancho' =>
            (int) (
                $entrada['ancho']
                ?? 0
            ),

        'alto' =>
            (int) (
                $entrada['alto']
                ?? 0
            ),
    ];
}


/**
 * Responde el PNG usando ETag.
 */
function ctps3_icono_responder(
    array $archivo
): never {

    $etag =
        '"'
        . $archivo['sha256']
        . '"';

    $ifNoneMatch = (
        $_SERVER[
            'HTTP_IF_NONE_MATCH'
        ]
        ?? ''
    );

    if (
        is_string($ifNoneMatch)
        && trim($ifNoneMatch)
            === $etag
    ) {
        http_response_code(
            304
        );

        header(
            'ETag: ' . $etag
        );

        header(
            'Cache-Control: '
            . 'public, max-age=3600'
        );

        exit;
    }

    header(
        'Content-Type: image/png'
    );

    header(
        'Content-Length: '
        . (string) $archivo['bytes']
    );

    header(
        'X-Content-Type-Options: nosniff'
    );

    header(
        'Cache-Control: '
        . 'public, max-age=3600'
    );

    header(
        'ETag: ' . $etag
    );

    $resultado = readfile(
        $archivo['ruta']
    );

    if ($resultado === false) {
        exit;
    }

    exit;
}


ctps3_exigir_metodo(
    'GET'
);

try {

    $juegoId =
        ctps3_icono_obtener_id();

    $bd =
        ctps3_bd();

    ctps3_icono_validar_juego(
        $bd,
        $juegoId
    );

    $entrada =
        ctps3_icono_buscar_manifiesto(
            $juegoId
        );

    $archivo =
        ctps3_icono_validar_archivo(
            $entrada
        );

    ctps3_icono_responder(
        $archivo
    );

} catch (Throwable $error) {

    ctps3_icono_error(
        500,
        'ERROR_INTERNO',
        'No se pudo obtener la imagen del juego.'
    );
}
