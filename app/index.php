<?php

declare(strict_types=1);

require_once __DIR__
    . '/includes/aplicacion.php';


$csrf =
    ctps3_csrf_token();


$vistasCtps3 = [

    'resumen' => [
        'titulo' =>
            'Resumen',

        'descripcion_nav' =>
            'Estado general',
    ],

    'biblioteca' => [
        'titulo' =>
            'Biblioteca',

        'descripcion_nav' =>
            'Local y PS3',
    ],

    'juegos' => [
        'titulo' =>
            'Juegos',

        'descripcion_nav' =>
            'Instalados en PS3',
    ],

    'almacenamiento' => [
        'titulo' =>
            'Almacenamiento',

        'descripcion_nav' =>
            'Mapa de espacio PS3',
    ],

    'transferencias' => [
        'titulo' =>
            'Transferencias',

        'descripcion_nav' =>
            'Cola y progreso',
    ],

    'historial' => [
        'titulo' =>
            'Historial',

        'descripcion_nav' =>
            'Registro y actividad',
    ],

    'sistema' => [
        'titulo' =>
            'Sistema',

        'descripcion_nav' =>
            'Telemetría y salud',
    ],
];


$vistaSolicitada =
    isset($_GET['vista'])
        ? strtolower(
            trim(
                (string) $_GET['vista']
            )
        )
        : 'resumen';


$vista =
    array_key_exists(
        $vistaSolicitada,
        $vistasCtps3
    )
        ? $vistaSolicitada
        : 'resumen';


$definicionVista =
    $vistasCtps3[$vista];


require __DIR__
    . '/includes/interfaz/documento-inicio.php';

require __DIR__
    . '/includes/interfaz/cabecera.php';

require __DIR__
    . '/includes/interfaz/navegacion.php';

require __DIR__
    . '/vistas/'
    . $vista
    . '.php';

require __DIR__
    . '/includes/interfaz/modal-global.php';

require __DIR__
    . '/includes/interfaz/scripts.php';
