<main class="contenedor">

<?php
require __DIR__
    . '/../includes/interfaz/aviso-worker.php';
?>

<section class="vista-cabecera">
    <div>
        <span class="subtitulo">
            CONTENIDO
        </span>

        <h2>
            Biblioteca
        </h2>

        <p>
            PKG, PS3ISO y PS2 disponibles en el servidor y contenido detectado en la PS3.
        </p>
    </div>
</section>

<section class="panel">

        <div class="panel__cabecera">

            <div>
                <span class="subtitulo">
                    BIBLIOTECA LOCAL
                </span>

                <h2>
                    Juegos disponibles
                </h2>

                <p>
                    PKG, PS3ISO y PS2 detectados automáticamente
                    en el servidor.
                </p>
            </div>

            <div class="acciones-biblioteca">

                <span
                    id="seleccionContador"
                    class="seleccion"
                >
                    0 seleccionados
                </span>

                <span
                    id="seleccionCapacidad"
                    class="seleccion"
                    aria-live="polite"
                >
                    Capacidad: sin selección
                </span>

                <button
                    id="botonEncolar"
                    class="boton boton--primario"
                    type="button"
                    disabled
                >
                    Agregar a la cola
                </button>

            </div>

        </div>

        <div
            id="bibliotecaControles"
            class="biblioteca-controles"
        >
            <label class="biblioteca-control biblioteca-control--buscar">
                <span>Buscar</span>
                <input
                    id="bibliotecaBuscar"
                    type="search"
                    placeholder="Juego, código o archivo"
                    autocomplete="off"
                >
            </label>

            <label class="biblioteca-control">
                <span>Formato</span>
                <select id="bibliotecaFiltroFormato">
                    <option value="">Todos</option>
                    <option value="PKG">PKG</option>
                    <option value="PS3ISO">PS3 ISO</option>
                    <option value="PS2ISO">PS2 BIN.ENC</option>
                </select>
            </label>

            <label class="biblioteca-control">
                <span>Presencia en PS3</span>
                <select id="bibliotecaFiltroPs3">
                    <option value="">Todos</option>
                    <option value="COMPLETO">Completo</option>
                    <option value="PARCIAL">Parcial</option>
                    <option value="AUSENTE">Ausente</option>
                    <option value="CONFLICTO">Conflicto</option>
                    <option value="MIXTO">Mixto</option>
                </select>
            </label>

            <label class="biblioteca-control">
                <span>Ordenar</span>
                <select id="bibliotecaOrden">
                    <option value="nombre-asc">Nombre A-Z</option>
                    <option value="nombre-desc">Nombre Z-A</option>
                    <option value="tamano-desc">Tamaño mayor-menor</option>
                    <option value="tamano-asc">Tamaño menor-mayor</option>
                </select>
            </label>

            <div
                id="bibliotecaResumenVisible"
                class="biblioteca-resumen-visible"
                aria-live="polite"
            >
                Calculando…
            </div>
        </div>

        <div
            id="biblioteca"
            class="biblioteca"
        >
            <div class="cargando">
                Cargando biblioteca…
            </div>
        </div>

    </section>

<section class="panel">

        <div class="panel__cabecera">

            <div>
                <span class="subtitulo">
                    INVENTARIO REMOTO
                </span>

                <h2>
                    PKG solo en la PS3
                </h2>

                <p>
                    PKG detectados en
                    /dev_hdd0/packages que no forman
                    parte de la biblioteca local.
                </p>
            </div>

            <span
                id="inventarioPs3Resumen"
                class="seleccion"
            >
                Consultando…
            </span>

        </div>

        <div
            id="inventarioPs3"
            class="inventario-ps3"
        >
            <div class="cargando">
                Consultando inventario remoto…
            </div>
        </div>

    </section>

</main>
