<main class="contenedor">

<section class="vista-cabecera">
    <div>
        <span class="subtitulo">
            BIBLIOTECA INSTALADA
        </span>

        <h2>
            Juegos
        </h2>

        <p>
            Juegos detectados en la PS3 y agrupados
            por título lógico, independientemente de
            sus componentes físicos.
        </p>
    </div>

    <div
        id="juegosEstadoInventario"
        class="estado estado--neutro"
    >
        Consultando inventario…
    </div>
</section>


<section class="metricas">

    <article class="metrica">
        <span class="metrica__etiqueta">
            Juegos
        </span>

        <strong
            id="juegosMetricaTotal"
            class="metrica__valor"
        >
            —
        </strong>

        <span class="metrica__detalle">
            títulos detectados
        </span>
    </article>


    <article class="metrica">
        <span class="metrica__etiqueta">
            Disponibles
        </span>

        <strong
            id="juegosMetricaDisponibles"
            class="metrica__valor"
        >
            —
        </strong>

        <span class="metrica__detalle">
            presentes actualmente
        </span>
    </article>


    <article class="metrica">
        <span class="metrica__etiqueta">
            Componentes
        </span>

        <strong
            id="juegosMetricaComponentes"
            class="metrica__valor"
        >
            —
        </strong>

        <span class="metrica__detalle">
            rutas físicas asociadas
        </span>
    </article>


    <article class="metrica">
        <span class="metrica__etiqueta">
            Inventario
        </span>

        <strong
            id="juegosMetricaInventario"
            class="metrica__valor"
        >
            —
        </strong>

        <span
            id="juegosMetricaInventarioDetalle"
            class="metrica__detalle"
        >
            última actualización
        </span>
    </article>

</section>


<section class="panel">

    <div class="panel__cabecera">

        <div>
            <span class="subtitulo">
                CATÁLOGO DE JUEGOS
            </span>

            <h2>
                Contenido jugable
            </h2>

            <p>
                Un registro por juego lógico.
                Los datos, cachés y demás componentes
                asociados se muestran dentro del mismo título.
            </p>
        </div>

        <span
            id="juegosResumen"
            class="seleccion"
        >
            Consultando…
        </span>

    </div>


    <div class="juegos-controles">

        <label class="juegos-buscador">
            <span class="juegos-buscador__etiqueta">
                Buscar
            </span>

            <input
                id="juegosBuscar"
                type="search"
                placeholder="Nombre o Title ID"
                autocomplete="off"
            >
        </label>


        <label class="juegos-filtro">
            <span class="juegos-filtro__etiqueta">
                Tipo
            </span>

            <select id="juegosFiltroTipo">
                <option value="">
                    Todos
                </option>

                <option value="JB_FOLDER">
                    JB Folder
                </option>

                <option value="HDD_JUEGO">
                    HDD
                </option>

                <option value="PS3_ISO">
                    PS3 ISO
                </option>
            </select>
        </label>


        <label class="juegos-filtro">
            <span class="juegos-filtro__etiqueta">
                Estado
            </span>

            <select id="juegosFiltroEstado">
                <option value="">
                    Todos
                </option>

                <option value="disponible">
                    Disponible
                </option>

                <option value="no-disponible">
                    No disponible
                </option>
            </select>
        </label>


        <label class="juegos-filtro">
            <span class="juegos-filtro__etiqueta">
                Ordenar
            </span>

            <select id="juegosOrden">
                <option value="nombre-asc">
                    Nombre A-Z
                </option>

                <option value="nombre-desc">
                    Nombre Z-A
                </option>

                <option value="tamano-desc">
                    Tamaño mayor-menor
                </option>

                <option value="tamano-asc">
                    Tamaño menor-mayor
                </option>

                <option value="recientes">
                    Más recientes
                </option>
            </select>
        </label>

    </div>


    <div
        id="juegosLista"
        class="juegos-lista"
        aria-live="polite"
    >
        <div class="cargando">
            Cargando juegos…
        </div>
    </div>

</section>


<dialog
    id="juegosDetalle"
    class="juego-dialogo"
    aria-labelledby="juegosDetalleTitulo"
>
    <div class="juego-dialogo__panel">
        <div class="juego-dialogo__cabecera">
            <div>
                <span class="subtitulo">
                    DETALLE DEL JUEGO
                </span>

                <h2 id="juegosDetalleTitulo">
                    Juego
                </h2>
            </div>

            <button
                type="button"
                class="juego-dialogo__cerrar"
                data-juego-cerrar
                aria-label="Cerrar detalle"
            >
                ×
            </button>
        </div>

        <div
            id="juegosDetalleContenido"
            class="juego-dialogo__contenido"
        ></div>
    </div>
</dialog>


<dialog
    id="juegosEliminar"
    class="juego-dialogo juego-dialogo--peligro"
    aria-labelledby="juegosEliminarTitulo"
>
    <div class="juego-dialogo__panel">
        <div class="juego-dialogo__cabecera">
            <div>
                <span class="subtitulo">
                    OPERACIÓN DESTRUCTIVA
                </span>

                <h2 id="juegosEliminarTitulo">
                    Eliminar juego
                </h2>
            </div>

            <button
                type="button"
                class="juego-dialogo__cerrar"
                data-eliminacion-cerrar
                aria-label="Cerrar eliminación"
            >
                ×
            </button>
        </div>

        <div class="juego-dialogo__contenido">
            <div
                id="juegosEliminarContenido"
                class="juego-eliminar"
            ></div>

            <div class="juego-eliminar__confirmacion">
                <label for="juegosEliminarConfirmacion">
                    Confirmación exacta
                </label>

                <input
                    id="juegosEliminarConfirmacion"
                    type="text"
                    autocomplete="off"
                    spellcheck="false"
                    placeholder="Escribí la confirmación indicada"
                >

                <p
                    id="juegosEliminarEstado"
                    class="juego-eliminar__estado"
                    aria-live="polite"
                ></p>

                <div class="juego-eliminar__acciones">
                    <button
                        type="button"
                        class="juego-eliminar__cancelar"
                        data-eliminacion-cerrar
                    >
                        Cancelar
                    </button>

                    <button
                        id="juegosEliminarEjecutar"
                        type="button"
                        class="juego-eliminar__ejecutar"
                        disabled
                    >
                        Eliminar de la PS3
                    </button>
                </div>
            </div>
        </div>
    </div>
</dialog>

</main>
