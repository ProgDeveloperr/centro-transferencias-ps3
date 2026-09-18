<main class="contenedor">

<?php
require __DIR__
    . '/../includes/interfaz/aviso-worker.php';
?>

<section class="vista-cabecera">
    <div>
        <span class="subtitulo">
            AUDITORÍA
        </span>

        <h2>
            Historial
        </h2>

        <p>
            Transferencias anteriores, estadísticas y actividad registrada.
        </p>
    </div>
</section>

<section class="panel">

        <div class="panel__cabecera">

            <div>
                <span class="subtitulo">
                    REGISTRO
                </span>

                <h2>
                    Historial reciente
                </h2>

                <p>
                    Transferencias terminadas,
                    canceladas o con errores.
                </p>
            </div>

        </div>

        <div
            id="historial"
            class="lista-transferencias"
        >
            <div class="cargando">
                Consultando historial…
            </div>
        </div>

    </section>

<section class="panel panel--eventos">

        <div class="panel__cabecera">

            <div>
                <span class="subtitulo">
                    AUDITORÍA
                </span>

                <h2>
                    Actividad
                </h2>
            </div>

        </div>

        <div
            id="eventos"
            class="eventos"
        ></div>

    </section>

</main>
