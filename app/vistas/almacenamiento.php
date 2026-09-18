<link
    rel="stylesheet"
    href="recursos/css/ops-frescura.css?v=1.0.0"
>

<link
    rel="stylesheet"
    href="recursos/css/almacenamiento-ops-resumen.css?v=1.0.0"
>

<main class="contenedor almacenamiento-vista">

<?php
require __DIR__
    . '/../includes/interfaz/aviso-worker.php';
?>

<section class="vista-cabecera almacenamiento-vista__cabecera">
    <div>
        <span class="subtitulo">
            MAPA DE ESPACIO PS3
        </span>

        <h2>
            Almacenamiento
        </h2>

        <p>
            Inventario físico clasificado de
            <code>/dev_hdd0/game</code>,
            separado de la telemetría aproximada
            de espacio libre de webMAN.
        </p>
    </div>

    <div
        id="almEstado"
        class="alm-estado alm-estado--cargando"
    >
        CONSULTANDO
    </div>
</section>

<section class="alm-aviso-seguridad">
    <strong>
        Gestión controlada · previsualización
    </strong>

    <span>
        Los datos vinculados pueden revisarse por juego
        y componente. Esta etapa sólo previsualiza:
        no encola ni ejecuta borrados.
    </span>
</section>

<section class="alm-metricas">
    <article class="alm-metrica">
        <span>
            Espacio libre PS3
        </span>

        <strong id="almLibre">
            —
        </strong>

        <small id="almLibreDetalle">
            telemetría webMAN
        </small>
    </article>

    <article class="alm-metrica">
        <span>
            Inventariado en /game
        </span>

        <strong id="almInventariado">
            —
        </strong>

        <small>
            no equivale al uso total del HDD
        </small>
    </article>

    <article class="alm-metrica">
        <span>
            Elementos actuales
        </span>

        <strong id="almElementos">
            —
        </strong>

        <small id="almOrigenDetalle">
            J3 + suplementarios
        </small>
    </article>

    <article class="alm-metrica">
        <span>
            Posibles huérfanos
        </span>

        <strong id="almHuerfanos">
            —
        </strong>

        <small>
            nunca habilitan borrado automático
        </small>
    </article>
</section>

<section class="panel alm-panel">
    <div class="alm-panel__cabecera">
        <div>
            <span class="subtitulo">
                CLASIFICACIÓN
            </span>

            <h3>
                Distribución del inventario
            </h3>

            <p>
                Tamaño y cantidad por clase
                persistida por el backend.
            </p>
        </div>

        <span id="almActualizado" class="alm-actualizado">
            —
        </span>
    </div>

    <div
        id="almResumenOperativo"
        class="alm-ops-resumen"
    >
        <div class="alm-ops-resumen__intro">
            <strong>Lectura operativa</strong>
            <span>
                Agrupación del mismo inventario clasificado.
            </span>
        </div>

        <p
            class="alm-ops-resumen__mensaje"
            data-alm-ops="cargando"
        >
            Calculando resumen…
        </p>

        <p
            class="alm-ops-resumen__mensaje alm-ops-resumen__error"
            data-alm-ops="error"
            hidden
        ></p>

        <div
            class="alm-ops-resumen__grid"
            data-alm-ops="contenido"
            hidden
        >
            <article class="alm-ops-resumen__card">
                <h4>Juegos instalados</h4>
                <div class="alm-ops-resumen__dato">
                    <span>Elementos</span>
                    <strong data-alm-ops="principal-cantidad">—</strong>
                </div>
                <div class="alm-ops-resumen__dato">
                    <span>Tamaño</span>
                    <strong data-alm-ops="principal-bytes">—</strong>
                </div>
                <div class="alm-ops-resumen__dato">
                    <span>Del inventario</span>
                    <strong data-alm-ops="principal-porcentaje">—</strong>
                </div>
            </article>

            <article class="alm-ops-resumen__card">
                <h4>Datos asociados</h4>
                <div class="alm-ops-resumen__dato">
                    <span>Elementos</span>
                    <strong data-alm-ops="asociados-cantidad">—</strong>
                </div>
                <div class="alm-ops-resumen__dato">
                    <span>Tamaño</span>
                    <strong data-alm-ops="asociados-bytes">—</strong>
                </div>
                <div class="alm-ops-resumen__dato">
                    <span>Del inventario</span>
                    <strong data-alm-ops="asociados-porcentaje">—</strong>
                </div>
            </article>

            <article class="alm-ops-resumen__card">
                <h4>Apps, utilidades y soporte</h4>
                <div class="alm-ops-resumen__dato">
                    <span>Elementos</span>
                    <strong data-alm-ops="sistema-cantidad">—</strong>
                </div>
                <div class="alm-ops-resumen__dato">
                    <span>Tamaño</span>
                    <strong data-alm-ops="sistema-bytes">—</strong>
                </div>
                <div class="alm-ops-resumen__dato">
                    <span>Del inventario</span>
                    <strong data-alm-ops="sistema-porcentaje">—</strong>
                </div>
            </article>

            <article class="alm-ops-resumen__card">
                <h4>Revisión requerida</h4>
                <div class="alm-ops-resumen__dato">
                    <span>Huérfanos / desconocidos</span>
                    <strong data-alm-ops="revision-cantidad">—</strong>
                </div>
                <div class="alm-ops-resumen__dato">
                    <span>Tamaño</span>
                    <strong data-alm-ops="revision-bytes">—</strong>
                </div>
                <div class="alm-ops-resumen__dato">
                    <span>Borrado automático</span>
                    <strong data-alm-ops="auto-borrado">—</strong>
                </div>
                <div class="alm-ops-resumen__dato">
                    <span>Estado</span>
                    <strong
                        class="alm-ops-resumen__estado"
                        data-alm-ops="revision-estado"
                    >
                        —
                    </strong>
                </div>
            </article>
        </div>
    </div>

    <div id="almClases" class="alm-clases">
        <div class="alm-cargando">
            Consultando clases…
        </div>
    </div>
</section>

<section class="panel alm-panel">
    <div class="alm-panel__cabecera alm-panel__cabecera--lista">
        <div>
            <span class="subtitulo">
                ELEMENTOS FÍSICOS
            </span>

            <h3>
                Contenido de /dev_hdd0/game
            </h3>

            <p>
                Rutas exactas detectadas,
                tamaño, origen, clasificación
                y política asociada.
            </p>
        </div>

        <strong id="almConteo" class="alm-conteo">
            —
        </strong>
    </div>

    <div class="alm-controles">
        <label class="alm-control alm-control--buscar">
            <span>Buscar</span>

            <input
                id="almBuscar"
                type="search"
                placeholder="Nombre, Title ID o ruta…"
                autocomplete="off"
            >
        </label>

        <label class="alm-control">
            <span>Clase</span>

            <select id="almFiltroClase">
                <option value="">
                    Todas
                </option>
            </select>
        </label>

        <label class="alm-control">
            <span>Origen</span>

            <select id="almFiltroOrigen">
                <option value="">
                    Todos
                </option>

                <option value="J3">
                    J3
                </option>

                <option value="ESP_SUPLEMENTARIO">
                    ESP suplementario
                </option>
            </select>
        </label>

        <label class="alm-control">
            <span>Orden</span>

            <select id="almOrden">
                <option value="tamano_desc">
                    Mayor tamaño
                </option>

                <option value="tamano_asc">
                    Menor tamaño
                </option>

                <option value="nombre_asc">
                    Nombre A–Z
                </option>

                <option value="clase_asc">
                    Clase A–Z
                </option>
            </select>
        </label>
    </div>

    <div id="almError" class="alm-error" hidden></div>

    <div class="alm-tabla-contenedor">
        <table class="alm-tabla">
            <thead>
                <tr>
                    <th>Elemento</th>
                    <th>Clase</th>
                    <th>Origen</th>
                    <th>Tamaño</th>
                    <th>Confianza</th>
                    <th>Política</th>
                    <th>Gestión</th>
                </tr>
            </thead>

            <tbody id="almLista">
                <tr>
                    <td colspan="7" class="alm-cargando">
                        Consultando inventario…
                    </td>
                </tr>
            </tbody>
        </table>
    </div>

    <div id="almVacio" class="alm-vacio" hidden>
        No hay elementos que coincidan con los filtros.
    </div>
</section>

<dialog
    id="almGestionPreview"
    class="alm-gestion-preview"
    aria-labelledby="almGestionPreviewTitulo"
>
    <div class="alm-gestion-preview__panel">
        <div class="alm-gestion-preview__cabecera">
            <div>
                <span class="subtitulo">DATOS ASOCIADOS</span>
                <h2 id="almGestionPreviewTitulo">Previsualización</h2>
            </div>

            <button
                type="button"
                class="alm-gestion-preview__cerrar"
                data-alm-preview-cerrar
                aria-label="Cerrar"
            >×</button>
        </div>

        <div class="alm-gestion-preview__contenido">
            <p id="almGestionPreviewEstado" class="alm-gestion-preview__estado"></p>
            <div id="almGestionPreviewOpciones" class="alm-gestion-preview__opciones"></div>
            <div id="almGestionPreviewResultado" class="alm-gestion-preview__resultado"></div>

            <section
                id="almGestionAccion"
                class="alm-gestion-accion"
                hidden
                aria-labelledby="almGestionAccionTitulo"
            >
                <div class="alm-gestion-accion__aviso">
                    <strong id="almGestionAccionTitulo">
                        Eliminar datos asociados seleccionados
                    </strong>
                    <p>
                        Esta acción elimina únicamente los componentes seleccionados
                        de datos asociados. No elimina el juego principal.
                    </p>
                </div>

                <label class="alm-gestion-accion__confirmacion">
                    <span>
                        Escribí exactamente
                        <code id="almGestionConfirmacionEsperada">—</code>
                    </span>

                    <input
                        id="almGestionConfirmacion"
                        type="text"
                        autocomplete="off"
                        autocapitalize="off"
                        spellcheck="false"
                        placeholder="Frase de confirmación"
                    >
                </label>

                <div class="alm-gestion-accion__ejecucion">
                    <p
                        id="almGestionSolicitarEstado"
                        class="alm-gestion-accion__estado"
                        aria-live="polite"
                    ></p>

                    <button
                        id="almGestionSolicitar"
                        type="button"
                        class="alm-gestion-accion__eliminar"
                        disabled
                    >
                        Eliminar datos seleccionados
                    </button>
                </div>
            </section>

            <div class="alm-gestion-preview__pie">
                <span>
                    La eliminación sólo se habilita con la frase exacta
                    validada por el backend.
                </span>
                <button type="button" data-alm-preview-cerrar>Cerrar</button>
            </div>
        </div>
    </div>
</dialog>

</main>

<script
    src="recursos/js/almacenamiento-ops-resumen.js?v=1.0.0"
    defer
></script>

<script
    src="recursos/js/ops-frescura.js?v=1.0.0"
    defer
></script>
