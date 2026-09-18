<main class="contenedor">

<?php
require __DIR__
    . '/../includes/interfaz/aviso-worker.php';
?>

<section class="vista-cabecera">
    <div>
        <span class="subtitulo">
            OPERACIÓN
        </span>

        <h2>
            Transferencias
        </h2>

        <p>
            Cola, prioridades, controles y progreso del motor.
        </p>
    </div>
</section>

<section class="panel">

        <div class="panel__cabecera">

            <div>
                <span class="subtitulo">
                    MOTOR DE TRANSFERENCIA
                </span>

                <h2>
                    Cola
                </h2>

                <p id="mensajeWorker">
                    Consultando estado…
                </p>
            </div>

        </div>

        <div
            id="cola"
            class="lista-transferencias"
        >
            <div class="cargando">
                Consultando cola…
            </div>
        </div>

    </section>

</main>
