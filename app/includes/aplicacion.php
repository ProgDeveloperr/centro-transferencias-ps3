<?php

declare(strict_types=1);

const CTPS3_BD =
    '/var/www/datos-transferencias-ps3/transferencias.sqlite3';

const CTPS3_BIBLIOTECA =
    '/var/www/biblioteca-ps3';

if (session_status() !== PHP_SESSION_ACTIVE) {
    ini_set('session.use_strict_mode', '1');
    ini_set('session.cookie_httponly', '1');
    ini_set('session.cookie_samesite', 'Strict');

    session_start();
}

function ctps3_respuesta_json(
    array $datos,
    int $codigo = 200
): never {
    http_response_code($codigo);

    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store, max-age=0');
    header('Pragma: no-cache');
    header('X-Content-Type-Options: nosniff');

    echo json_encode(
        $datos,
        JSON_UNESCAPED_UNICODE
        | JSON_UNESCAPED_SLASHES
        | JSON_INVALID_UTF8_SUBSTITUTE
    );

    exit;
}

function ctps3_exigir_metodo(string $metodo): void
{
    if ($_SERVER['REQUEST_METHOD'] !== $metodo) {
        header('Allow: ' . $metodo);

        ctps3_respuesta_json([
            'ok' => false,
            'error' => 'METODO_NO_PERMITIDO',
        ], 405);
    }
}

function ctps3_bd(): PDO
{
    $pdo = new PDO(
        'sqlite:' . CTPS3_BD,
        null,
        null,
        [
            PDO::ATTR_ERRMODE =>
                PDO::ERRMODE_EXCEPTION,

            PDO::ATTR_DEFAULT_FETCH_MODE =>
                PDO::FETCH_ASSOC,

            PDO::ATTR_EMULATE_PREPARES =>
                false,
        ]
    );

    $pdo->exec('PRAGMA foreign_keys=ON');
    $pdo->exec('PRAGMA busy_timeout=5000');

    return $pdo;
}

function ctps3_csrf_token(): string
{
    if (
        !isset($_SESSION['ctps3_csrf'])
        || !is_string($_SESSION['ctps3_csrf'])
    ) {
        $_SESSION['ctps3_csrf'] =
            bin2hex(random_bytes(32));
    }

    return $_SESSION['ctps3_csrf'];
}

function ctps3_exigir_csrf(): void
{
    $recibido =
        $_SERVER['HTTP_X_CSRF_TOKEN']
        ?? '';

    $esperado =
        $_SESSION['ctps3_csrf']
        ?? '';

    if (
        !is_string($recibido)
        || !is_string($esperado)
        || $recibido === ''
        || !hash_equals($esperado, $recibido)
    ) {
        ctps3_respuesta_json([
            'ok' => false,
            'error' => 'CSRF_INVALIDO',
        ], 403);
    }
}

function ctps3_json(): array
{
    $contenido = file_get_contents('php://input');

    if ($contenido === false || trim($contenido) === '') {
        return [];
    }

    $datos = json_decode(
        $contenido,
        true,
        512,
        JSON_THROW_ON_ERROR
    );

    if (!is_array($datos)) {
        throw new RuntimeException(
            'El cuerpo JSON debe ser un objeto'
        );
    }

    return $datos;
}

function ctps3_estado_activo(string $estado): bool
{
    return in_array(
        $estado,
        [
            'EN_COLA',
            'COMPROBANDO',
            'PREPARANDO',
            'TRANSFIRIENDO',
            'PAUSANDO',
            'PAUSADO',
            'CANCELANDO',
            'VERIFICANDO',
            'REINTENTANDO',
        ],
        true
    );
}
