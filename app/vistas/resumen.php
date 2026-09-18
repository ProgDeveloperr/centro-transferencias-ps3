<link
    rel="stylesheet"
    href="recursos/css/ops-frescura.css?v=1.0.0"
>

<main class="contenedor">

<?php
require __DIR__
    . '/../includes/interfaz/aviso-worker.php';
?>

<section class="vista-cabecera">
    <div>
        <span class="subtitulo">
            CENTRO DE OPERACIONES
        </span>

        <h2>
            Resumen
        </h2>

        <p>
            Estado general de la consola, biblioteca y motor de transferencias.
        </p>
    </div>
</section>

<section class="ps3-resumen">

        <div class="ps3-resumen__principal">

            <div
                id="ps3Pulso"
                class="ps3-pulso ps3-pulso--neutro"
            ></div>

            <div>
                <span class="subtitulo">
                    CONSOLA REMOTA
                </span>

                <div class="ps3-resumen__titulo">

                    <strong id="ps3Conexion">
                        Consultando PS3…
                    </strong>

                    <span id="ps3Host">
                        —
                    </span>

                </div>
            </div>

        </div>


        <div class="ps3-resumen__datos">

            <div>
                <span>Servidor FTP</span>
                <strong id="ps3Banner">—</strong>
            </div>

            <div>
                <span>Destino PKG</span>
                <strong id="ps3Ruta">—</strong>
            </div>

            <div>
                <span>Último inventario</span>
                <strong id="ps3Ultima">—</strong>
            </div>

        </div>


        <div
            id="ps3Error"
            class="
                ps3-resumen__error
                ps3-resumen__error--oculto
            "
        ></div>

    </section>

<section class="metricas">

        <article class="metrica">
            <span class="metrica__etiqueta">
                Biblioteca
            </span>

            <strong
                id="metricaArchivos"
                class="metrica__valor"
            >
                —
            </strong>

            <span class="metrica__detalle">
                archivos locales
            </span>
        </article>


        <article class="metrica">
            <span class="metrica__etiqueta">
                Almacenados
            </span>

            <strong
                id="metricaTamano"
                class="metrica__valor"
            >
                —
            </strong>

            <span class="metrica__detalle">
                disponibles
            </span>
        </article>


        <article class="metrica">
            <span class="metrica__etiqueta">
                Espacio libre PS3
            </span>

            <strong
                id="metricaHddPs3"
                class="metrica__valor"
            >
                —
            </strong>

            <span
                id="metricaHddPs3Detalle"
                class="metrica__detalle"
            >
                consultando almacenamiento
            </span>
        </article>


        <article class="metrica">

            <span class="metrica__etiqueta">
                En PS3
            </span>

            <strong
                id="metricaEnPs3"
                class="metrica__valor"
            >
                —
            </strong>

            <span
                id="metricaEnPs3Detalle"
                class="metrica__detalle"
            >
                de la biblioteca local
            </span>

        </article>


        <article class="metrica">

            <span class="metrica__etiqueta">
                PKG remotos
            </span>

            <strong
                id="metricaRemotos"
                class="metrica__valor"
            >
                —
            </strong>

            <span class="metrica__detalle">
                detectados en la consola
            </span>

        </article>


        <article class="metrica">
            <span class="metrica__etiqueta">
                Cola
            </span>

            <strong
                id="metricaCola"
                class="metrica__valor"
            >
                —
            </strong>

            <span class="metrica__detalle">
                pendientes / activas
            </span>
        </article>


        <article class="metrica">
            <span class="metrica__etiqueta">
                Transferencia
            </span>

            <strong
                id="metricaVelocidad"
                class="metrica__valor"
            >
                —
            </strong>

            <span class="metrica__detalle">
                velocidad actual
            </span>
        </article>

    </section>

</main>

<script
    src="recursos/js/ops-frescura.js?v=1.0.0"
    defer
></script>
