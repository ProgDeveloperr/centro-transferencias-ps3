<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <meta
        name="csrf-token"
        content="<?= htmlspecialchars(
            $csrf,
            ENT_QUOTES,
            'UTF-8'
        ) ?>"
    >

    <title><?= htmlspecialchars(
        $definicionVista['titulo']
        . ' · Centro de Transferencias PS3',
        ENT_QUOTES,
        'UTF-8'
    ) ?></title>

    <link
        rel="stylesheet"
        href="recursos/css/estilos.css?v=2"
    >

    <link
        rel="stylesheet"
        href="recursos/css/ps3-inteligente.css?v=7"
    >

    <link
        rel="stylesheet"
        href="recursos/css/cola-profesional.css?v=4"
    >

    <link
        rel="stylesheet"
        href="recursos/css/historial-profesional.css?v=5"
    >
    <link
        rel="stylesheet"
        href="recursos/css/telemetria-ftp.css?v=1"
    >
    <link
        rel="stylesheet"
        href="recursos/css/resiliencia.css?v=1"
    >
    <link
        rel="stylesheet"
        href="recursos/css/navegacion.css?v=3"
    >

    <link
        rel="stylesheet"
        href="recursos/css/juegos.css?v=2"
    >
    <link
        rel="stylesheet"
        href="recursos/css/almacenamiento.css?v=2"
    >
    <link
        rel="stylesheet"
        href="recursos/css/almacenamiento-gestion-preview.css?v=1"
    >
    <link
        rel="stylesheet"
        href="recursos/css/acabado-final.css?v=3"
    >
</head>

<body
    data-vista="<?= htmlspecialchars(
        $vista,
        ENT_QUOTES,
        'UTF-8'
    ) ?>"
>

<div id="toasts" class="toasts"></div>
