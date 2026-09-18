(() => {
    'use strict';

    const API_JUEGOS =
        'api/juegos.php';

    const API_ELIMINAR_JUEGO =
        'api/eliminar-juego.php';

    const CSRF =
        document
            .querySelector(
                'meta[name="csrf-token"]'
            )
            ?.getAttribute('content')
        || '';

    const REFRESCO_MS =
        60_000;

    const estado = {
        datos: null,
        cargando: false,
        detalleJuegoId: null,
        eliminacionPreview: null,
        eliminacionId: null,
        eliminando: false,
        eliminacionTimer: null,
    };


    const elemento = (id) =>
        document.getElementById(id);


    async function postEliminarJuego(
        accion,
        cuerpo = {}
    ) {
        if (!CSRF) {
            throw new Error(
                'CSRF_NO_DISPONIBLE'
            );
        }

        const respuesta =
            await fetch(
                API_ELIMINAR_JUEGO,
                {
                    method: 'POST',
                    cache: 'no-store',

                    headers: {
                        'Content-Type':
                            'application/json',

                        'X-CSRF-Token':
                            CSRF,
                    },

                    body: JSON.stringify({
                        accion,
                        ...cuerpo,
                    }),
                }
            );

        let datos;

        try {
            datos =
                await respuesta.json();
        } catch {
            throw new Error(
                'RESPUESTA_INVALIDA'
            );
        }

        if (
            !respuesta.ok
            || datos.ok !== true
        ) {
            const error =
                new Error(
                    datos.error
                    || `HTTP_${respuesta.status}`
                );

            error.datos =
                datos;

            throw error;
        }

        return datos;
    }


    function textoErrorEliminacion(
        error
    ) {
        const codigo =
            String(
                error?.message
                || ''
            );

        const mensajes = {
            CSRF_NO_DISPONIBLE:
                'No se encontró el token de seguridad.',

            JUEGO_NO_EXISTE:
                'El juego ya no existe en el inventario.',

            JUEGO_NO_DISPONIBLE:
                'El juego ya no figura disponible.',

            INVENTARIO_INCOMPLETO:
                'El inventario del juego no está completo.',

            SIN_COMPONENTES_ELIMINABLES:
                'No hay componentes disponibles para eliminar.',

            COMPONENTE_RUTA_NO_PERMITIDA:
                'El backend rechazó una ruta por seguridad.',

            ELIMINACION_YA_ACTIVA:
                'Ya existe una eliminación activa para este juego.',

            CONFIRMACION_INVALIDA:
                'La confirmación escrita no coincide.',

            ELIMINACION_NO_EXISTE:
                'No existe la operación de eliminación.',

            RESPUESTA_INVALIDA:
                'El servidor devolvió una respuesta inválida.',
        };

        return mensajes[codigo]
            || codigo
            || 'Error desconocido';
    }


    function escapar(valor) {
        return String(
            valor ?? ''
        )
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }


    function formatoBytes(valor) {
        if (
            valor === null
            || valor === undefined
        ) {
            return 'Pendiente';
        }

        let numero =
            Number(valor);

        if (
            !Number.isFinite(numero)
            || numero < 0
        ) {
            return 'Pendiente';
        }

        if (numero < 1024) {
            return `${numero} B`;
        }

        const unidades = [
            'KB',
            'MB',
            'GB',
            'TB',
        ];

        let indice = -1;

        do {
            numero /= 1024;
            indice++;
        } while (
            numero >= 1024
            && indice
                < unidades.length - 1
        );

        return `${
            numero.toFixed(
                numero >= 10
                    ? 1
                    : 2
            )
        } ${unidades[indice]}`;
    }


    function formatoFecha(valor) {
        if (!valor) {
            return 'Sin datos';
        }

        const fecha =
            new Date(valor);

        if (
            Number.isNaN(
                fecha.getTime()
            )
        ) {
            return 'Sin datos';
        }

        return new Intl.DateTimeFormat(
            'es-AR',
            {
                dateStyle: 'short',
                timeStyle: 'short',
            }
        ).format(fecha);
    }


    function etiquetaTipo(tipo) {
        const etiquetas = {
            JB_FOLDER:
                'JB Folder',

            HDD_JUEGO:
                'HDD',

            PS3_ISO:
                'PS3 ISO',

            DATOS_GAME:
                'Datos',

            CACHE_GAME:
                'Caché',

            DESCONOCIDO:
                'Desconocido',
        };

        return etiquetas[tipo]
            || tipo
            || 'Desconocido';
    }


    function renderComponente(
        componente
    ) {
        const categoria =
            componente.categoria_sfo
            || '—';

        const version =
            componente.app_ver
            || componente.version
            || '—';

        return `
            <div class="juego-componente">

                <div
                    class="
                        juego-componente__cabecera
                    "
                >
                    <strong>
                        ${escapar(
                            etiquetaTipo(
                                componente.tipo
                            )
                        )}
                    </strong>

                    <span
                        class="
                            estado
                            ${
                                componente.disponible
                                    ? 'estado--ok'
                                    : 'estado--error'
                            }
                        "
                    >
                        ${
                            componente.disponible
                                ? 'Disponible'
                                : 'No disponible'
                        }
                    </span>
                </div>

                <dl class="juego-componente__datos">

                    <div>
                        <dt>
                            Ruta
                        </dt>

                        <dd>
                            <code>
                                ${escapar(
                                    componente.ruta_remota
                                )}
                            </code>
                        </dd>
                    </div>

                    <div>
                        <dt>
                            CATEGORY
                        </dt>

                        <dd>
                            ${escapar(
                                categoria
                            )}
                        </dd>
                    </div>

                    <div>
                        <dt>
                            Versión
                        </dt>

                        <dd>
                            ${escapar(
                                version
                            )}
                        </dd>
                    </div>

                    <div>
                        <dt>
                            Tamaño
                        </dt>

                        <dd>
                            ${escapar(
                                formatoBytes(
                                    componente.tamano_bytes
                                )
                            )}
                        </dd>
                    </div>

                </dl>

            </div>
        `;
    }


    function renderJuego(juego) {
        const componentes =
            Array.isArray(
                juego.componentes
            )
                ? juego.componentes
                : [];

        const titleId =
            juego.title_id
            || 'Sin Title ID';

        const juegoId =
            Number(
                juego.id
            );

        const iconoUrl =
            Number.isInteger(
                juegoId
            )
            && juegoId > 0
                ? `api/icono-juego.php?id=${juegoId}`
                : '';

        const iconoHtml =
            iconoUrl
                ? `
                    <img
                        class="juego-tarjeta__icono"
                        src="${iconoUrl}"
                        alt=""
                        loading="lazy"
                        decoding="async"
                        width="320"
                        height="176"
                    >
                `
                : '';

        return `
            <article
                class="
                    juego-tarjeta
                    ${
                        juego.disponible
                            ? ''
                            : 'juego-tarjeta--no-disponible'
                    }
                "
            >

                <div
                    class="juego-tarjeta__visual"
                    aria-hidden="true"
                >
                    <div
                        class="
                            juego-tarjeta__visual-fondo
                        "
                    >
                        <span>
                            PS3
                        </span>
                    </div>

                    ${iconoHtml}

                    <span
                        class="
                            juego-tarjeta__visual-tipo
                        "
                    >
                        ${escapar(
                            etiquetaTipo(
                                juego.tipo_principal
                            )
                        )}
                    </span>
                </div>

                <div class="juego-tarjeta__cabecera">

                    <div>
                        <span
                            class="
                                juego-tarjeta__title-id
                            "
                        >
                            ${escapar(titleId)}
                        </span>

                        <h3>
                            ${escapar(
                                juego.nombre
                            )}
                        </h3>
                    </div>

                    <span
                        class="
                            estado
                            ${
                                juego.disponible
                                    ? 'estado--ok'
                                    : 'estado--error'
                            }
                        "
                    >
                        ${
                            juego.disponible
                                ? 'Disponible'
                                : 'No disponible'
                        }
                    </span>

                </div>


                <div class="juego-tarjeta__resumen">

                    <div>
                        <span>
                            Tamaño
                        </span>

                        <strong>
                            ${escapar(
                                formatoBytes(
                                    juego.tamano_total_bytes
                                )
                            )}
                        </strong>
                    </div>

                    <div>
                        <span>
                            Componentes
                        </span>

                        <strong>
                            ${componentes.length}
                        </strong>
                    </div>

                    <div>
                        <span>
                            Inventario
                        </span>

                        <strong>
                            ${
                                juego.inventario_completo
                                    ? 'Completo'
                                    : 'Pendiente'
                            }
                        </strong>
                    </div>

                    <div>
                        <span>
                            Actualizado
                        </span>

                        <strong>
                            ${escapar(
                                formatoFecha(
                                    juego.actualizado_utc
                                )
                            )}
                        </strong>
                    </div>

                </div>


                <div class="juego-tarjeta__acciones">
                    <button
                        type="button"
                        class="juego-tarjeta__detalle"
                        data-juego-detalle="${juegoId}"
                    >
                        Ver detalles
                    </button>
                </div>

            </article>
        `;
    }


    function renderComponenteDetalle(
        componente
    ) {
        const version =
            componente.app_ver
            || componente.version
            || '—';

        const bootable =
            componente.bootable === null
            || componente.bootable === undefined
                ? 'Sin datos'
                : (
                    componente.bootable
                        ? 'Sí'
                        : 'No'
                );

        return `
            <article class="juego-detalle-componente">

                <div
                    class="
                        juego-detalle-componente__cabecera
                    "
                >
                    <strong>
                        ${escapar(
                            etiquetaTipo(
                                componente.tipo
                            )
                        )}
                    </strong>

                    <span
                        class="
                            estado
                            ${
                                componente.disponible
                                    ? 'estado--ok'
                                    : 'estado--error'
                            }
                        "
                    >
                        ${
                            componente.disponible
                                ? 'Disponible'
                                : 'No disponible'
                        }
                    </span>
                </div>

                <dl class="juego-detalle-componente__datos">

                    <div class="juego-detalle-componente__ruta">
                        <dt>Ruta física</dt>
                        <dd>
                            <code>
                                ${escapar(
                                    componente.ruta_remota
                                )}
                            </code>
                        </dd>
                    </div>

                    <div>
                        <dt>Tamaño</dt>
                        <dd>
                            ${escapar(
                                formatoBytes(
                                    componente.tamano_bytes
                                )
                            )}
                        </dd>
                    </div>

                    <div>
                        <dt>Title ID SFO</dt>
                        <dd>
                            ${escapar(
                                componente.title_id_sfo
                                || '—'
                            )}
                        </dd>
                    </div>

                    <div>
                        <dt>Nombre SFO</dt>
                        <dd>
                            ${escapar(
                                componente.nombre_sfo
                                || '—'
                            )}
                        </dd>
                    </div>

                    <div>
                        <dt>CATEGORY</dt>
                        <dd>
                            ${escapar(
                                componente.categoria_sfo
                                || '—'
                            )}
                        </dd>
                    </div>

                    <div>
                        <dt>Versión</dt>
                        <dd>
                            ${escapar(version)}
                        </dd>
                    </div>

                    <div>
                        <dt>Bootable</dt>
                        <dd>
                            ${escapar(bootable)}
                        </dd>
                    </div>

                    <div>
                        <dt>Detectado</dt>
                        <dd>
                            ${escapar(
                                formatoFecha(
                                    componente.detectado_utc
                                )
                            )}
                        </dd>
                    </div>

                    <div>
                        <dt>Actualizado</dt>
                        <dd>
                            ${escapar(
                                formatoFecha(
                                    componente.actualizado_utc
                                )
                            )}
                        </dd>
                    </div>

                </dl>

            </article>
        `;
    }


    function buscarJuegoPorId(id) {
        if (
            !estado.datos
            || !Array.isArray(
                estado.datos.juegos
            )
        ) {
            return null;
        }

        return estado.datos.juegos
            .find(
                (juego) =>
                    Number(juego.id)
                    === Number(id)
            )
            || null;
    }


    function htmlDetalleJuego(juego) {
        const componentes =
            Array.isArray(
                juego.componentes
            )
                ? juego.componentes
                : [];

        return `
            <section class="juego-detalle">

                <div class="juego-detalle__identidad">
                    <div>
                        <span class="juego-detalle__title-id">
                            ${escapar(
                                juego.title_id
                                || 'Sin Title ID'
                            )}
                        </span>

                        <h3>
                            ${escapar(
                                juego.nombre
                            )}
                        </h3>
                    </div>

                    <span
                        class="
                            estado
                            ${
                                juego.disponible
                                    ? 'estado--ok'
                                    : 'estado--error'
                            }
                        "
                    >
                        ${
                            juego.disponible
                                ? 'Disponible'
                                : 'No disponible'
                        }
                    </span>
                </div>


                <dl class="juego-detalle__resumen">

                    <div>
                        <dt>Tipo principal</dt>
                        <dd>
                            ${escapar(
                                etiquetaTipo(
                                    juego.tipo_principal
                                )
                            )}
                        </dd>
                    </div>

                    <div>
                        <dt>Tamaño ocupado</dt>
                        <dd>
                            ${escapar(
                                formatoBytes(
                                    juego.tamano_total_bytes
                                )
                            )}
                        </dd>
                    </div>

                    <div>
                        <dt>Componentes</dt>
                        <dd>
                            ${componentes.length}
                        </dd>
                    </div>

                    <div>
                        <dt>Inventario</dt>
                        <dd>
                            ${
                                juego.inventario_completo
                                    ? 'Completo'
                                    : 'Pendiente'
                            }
                        </dd>
                    </div>

                    <div>
                        <dt>Detectado</dt>
                        <dd>
                            ${escapar(
                                formatoFecha(
                                    juego.detectado_utc
                                )
                            )}
                        </dd>
                    </div>

                    <div>
                        <dt>Última detección</dt>
                        <dd>
                            ${escapar(
                                formatoFecha(
                                    juego.visto_utc
                                )
                            )}
                        </dd>
                    </div>

                    <div>
                        <dt>Actualizado</dt>
                        <dd>
                            ${escapar(
                                formatoFecha(
                                    juego.actualizado_utc
                                )
                            )}
                        </dd>
                    </div>

                </dl>


                <div class="juego-detalle__seccion">
                    <div class="juego-detalle__seccion-cabecera">
                        <div>
                            <span class="subtitulo">
                                COMPONENTES FÍSICOS
                            </span>

                            <h3>
                                Ubicaciones en la PS3
                            </h3>
                        </div>

                        <span class="seleccion">
                            ${componentes.length}
                        </span>
                    </div>

                    <div class="juego-detalle__componentes">
                        ${
                            componentes.length
                                ? componentes
                                    .map(
                                        renderComponenteDetalle
                                    )
                                    .join('')
                                : `
                                    <div class="vacio">
                                        Sin componentes asociados.
                                    </div>
                                `
                        }
                    </div>
                </div>


                ${
                    juego.disponible
                        ? `
                            <div class="juego-detalle__peligro">
                                <div>
                                    <span class="subtitulo">
                                        ADMINISTRACIÓN
                                    </span>

                                    <h3>
                                        Eliminar de la PS3
                                    </h3>

                                    <p>
                                        Borra los componentes físicos
                                        actualmente asociados al juego.
                                        Las partidas guardadas no forman
                                        parte de estas rutas.
                                    </p>
                                </div>

                                <button
                                    type="button"
                                    class="juego-detalle__eliminar"
                                    data-juego-eliminar="${Number(juego.id)}"
                                >
                                    Eliminar juego
                                </button>
                            </div>
                        `
                        : ''
                }

            </section>
        `;
    }


    function htmlPreviewEliminacion(
        preview
    ) {
        const componentes =
            Array.isArray(
                preview.componentes
            )
                ? preview.componentes
                : [];

        const filas =
            componentes
                .map(
                    (componente) => `
                        <article class="juego-eliminar-componente">
                            <div>
                                <strong>
                                    ${escapar(
                                        etiquetaTipo(
                                            componente.tipo
                                        )
                                    )}
                                </strong>

                                <span>
                                    ${escapar(
                                        formatoBytes(
                                            componente.tamano_bytes
                                        )
                                    )}
                                </span>
                            </div>

                            <code>
                                ${escapar(
                                    componente.ruta_remota
                                )}
                            </code>
                        </article>
                    `
                )
                .join('');

        return `
            <div class="juego-eliminar__advertencia">
                <strong>
                    Esta acción no se puede deshacer.
                </strong>

                <p>
                    Se eliminarán únicamente las rutas
                    que el servidor resolvió desde el
                    inventario actual.
                </p>
            </div>

            <dl class="juego-eliminar__resumen">
                <div>
                    <dt>Juego</dt>
                    <dd>
                        ${escapar(preview.nombre)}
                    </dd>
                </div>

                <div>
                    <dt>Title ID</dt>
                    <dd>
                        ${escapar(
                            preview.title_id
                            || 'Sin Title ID'
                        )}
                    </dd>
                </div>

                <div>
                    <dt>Componentes</dt>
                    <dd>
                        ${componentes.length}
                    </dd>
                </div>

                <div>
                    <dt>Espacio recuperable</dt>
                    <dd>
                        ${escapar(
                            formatoBytes(
                                preview.tamano_liberable_bytes
                            )
                        )}
                        ${
                            preview.tamano_completo
                                ? ''
                                : ' (parcial)'
                        }
                    </dd>
                </div>
            </dl>

            <div class="juego-eliminar__componentes">
                ${filas}
            </div>

            <div class="juego-eliminar__frase">
                <span>
                    Para confirmar, escribí exactamente:
                </span>

                <code>
                    ${escapar(
                        preview.confirmacion_esperada
                    )}
                </code>
            </div>
        `;
    }


    function limpiarTimerEliminacion() {
        if (
            estado.eliminacionTimer
            !== null
        ) {
            window.clearTimeout(
                estado.eliminacionTimer
            );

            estado.eliminacionTimer =
                null;
        }
    }


    function cerrarEliminarJuego() {
        limpiarTimerEliminacion();

        const dialogo =
            elemento(
                'juegosEliminar'
            );

        if (
            dialogo?.open
            && typeof dialogo.close
                === 'function'
        ) {
            dialogo.close();

        } else {
            dialogo?.removeAttribute(
                'open'
            );
        }

        estado.eliminacionPreview =
            null;

        estado.eliminacionId =
            null;

        estado.eliminando =
            false;
    }


    async function abrirEliminarJuego(id) {
        const dialogo =
            elemento(
                'juegosEliminar'
            );

        const contenido =
            elemento(
                'juegosEliminarContenido'
            );

        const titulo =
            elemento(
                'juegosEliminarTitulo'
            );

        const confirmacion =
            elemento(
                'juegosEliminarConfirmacion'
            );

        const ejecutar =
            elemento(
                'juegosEliminarEjecutar'
            );

        const estadoTexto =
            elemento(
                'juegosEliminarEstado'
            );

        if (
            !dialogo
            || !contenido
            || !confirmacion
            || !ejecutar
        ) {
            return;
        }

        limpiarTimerEliminacion();

        contenido.innerHTML = `
            <div class="cargando">
                Preparando eliminación segura…
            </div>
        `;

        confirmacion.value = '';
        confirmacion.disabled = true;
        ejecutar.disabled = true;

        if (estadoTexto) {
            estadoTexto.textContent = '';
            estadoTexto.className =
                'juego-eliminar__estado';
        }

        if (titulo) {
            titulo.textContent =
                'Eliminar juego';
        }

        if (!dialogo.open) {
            if (
                typeof dialogo.showModal
                === 'function'
            ) {
                dialogo.showModal();

            } else {
                dialogo.setAttribute(
                    'open',
                    ''
                );
            }
        }

        try {
            const datos =
                await postEliminarJuego(
                    'PREVISUALIZAR',
                    {
                        juego_id:
                            Number(id),
                    }
                );

            estado.eliminacionPreview =
                datos.preview;

            estado.eliminacionId =
                datos.eliminacion_activa
                    ?.id
                ?? null;

            contenido.innerHTML =
                htmlPreviewEliminacion(
                    datos.preview
                );

            if (titulo) {
                titulo.textContent =
                    `Eliminar ${datos.preview.nombre}`;
            }

            if (
                datos.eliminacion_activa
                && estado.eliminacionId
            ) {
                confirmacion.disabled = true;
                ejecutar.disabled = true;

                if (estadoTexto) {
                    estadoTexto.textContent =
                        'Ya existe una eliminación activa. '
                        + 'Consultando estado…';

                    estadoTexto.className =
                        'juego-eliminar__estado '
                        + 'juego-eliminar__estado--aviso';
                }

                consultarEstadoEliminacion();
                return;
            }

            confirmacion.disabled = false;
            confirmacion.focus();

        } catch (error) {
            contenido.innerHTML = `
                <div class="juego-eliminar__advertencia">
                    <strong>
                        No se puede preparar la eliminación.
                    </strong>

                    <p>
                        ${escapar(
                            textoErrorEliminacion(
                                error
                            )
                        )}
                    </p>
                </div>
            `;

            if (estadoTexto) {
                estadoTexto.textContent =
                    textoErrorEliminacion(
                        error
                    );

                estadoTexto.className =
                    'juego-eliminar__estado '
                    + 'juego-eliminar__estado--error';
            }
        }
    }


    function actualizarBotonEliminar() {
        const preview =
            estado.eliminacionPreview;

        const confirmacion =
            elemento(
                'juegosEliminarConfirmacion'
            );

        const ejecutar =
            elemento(
                'juegosEliminarEjecutar'
            );

        if (
            !preview
            || !confirmacion
            || !ejecutar
        ) {
            return;
        }

        ejecutar.disabled =
            estado.eliminando
            || confirmacion.value.trim()
                !== preview
                    .confirmacion_esperada;
    }


    function pintarEstadoEliminacion(
        operacion
    ) {
        const estadoTexto =
            elemento(
                'juegosEliminarEstado'
            );

        if (!estadoTexto) {
            return;
        }

        const estadoOperacion =
            String(
                operacion.estado
                || ''
            );

        const eliminados =
            Number(
                operacion.componentes_eliminados
                || 0
            );

        const total =
            Number(
                operacion.componentes_total
                || 0
            );

        estadoTexto.textContent =
            `${estadoOperacion} · `
            + `${eliminados}/${total} componentes`
            + (
                operacion.mensaje
                    ? ` · ${operacion.mensaje}`
                    : ''
            );

        estadoTexto.className =
            'juego-eliminar__estado '
            + (
                estadoOperacion
                    === 'COMPLETADO'
                    ? 'juego-eliminar__estado--ok'
                    : estadoOperacion
                        === 'ERROR'
                        ? 'juego-eliminar__estado--error'
                        : 'juego-eliminar__estado--aviso'
            );
    }


    async function consultarEstadoEliminacion() {
        const id =
            Number(
                estado.eliminacionId
            );

        if (
            !Number.isInteger(id)
            || id < 1
        ) {
            return;
        }

        try {
            const datos =
                await postEliminarJuego(
                    'ESTADO',
                    {
                        eliminacion_id:
                            id,
                    }
                );

            pintarEstadoEliminacion(
                datos.eliminacion
            );

            const final =
                datos.eliminacion
                    .estado;

            if (
                final === 'COMPLETADO'
                || final === 'ERROR'
            ) {
                estado.eliminando =
                    false;

                const confirmacion =
                    elemento(
                        'juegosEliminarConfirmacion'
                    );

                const ejecutar =
                    elemento(
                        'juegosEliminarEjecutar'
                    );

                if (confirmacion) {
                    confirmacion.disabled =
                        true;
                }

                if (ejecutar) {
                    ejecutar.disabled =
                        true;
                }

                if (final === 'COMPLETADO') {
                    [
                        0,
                        3000,
                        7000,
                        15000,
                    ].forEach(
                        (espera) => {
                            window.setTimeout(
                                () => cargarJuegos(
                                    true
                                ),
                                espera
                            );
                        }
                    );
                }

                return;
            }

            estado.eliminacionTimer =
                window.setTimeout(
                    consultarEstadoEliminacion,
                    1500
                );

        } catch (error) {
            const estadoTexto =
                elemento(
                    'juegosEliminarEstado'
                );

            if (estadoTexto) {
                estadoTexto.textContent =
                    textoErrorEliminacion(
                        error
                    );

                estadoTexto.className =
                    'juego-eliminar__estado '
                    + 'juego-eliminar__estado--error';
            }

            estado.eliminando =
                false;
        }
    }


    async function confirmarEliminarJuego() {
        const preview =
            estado.eliminacionPreview;

        const confirmacion =
            elemento(
                'juegosEliminarConfirmacion'
            );

        const ejecutar =
            elemento(
                'juegosEliminarEjecutar'
            );

        const estadoTexto =
            elemento(
                'juegosEliminarEstado'
            );

        if (
            !preview
            || !confirmacion
            || !ejecutar
            || estado.eliminando
        ) {
            return;
        }

        const texto =
            confirmacion.value.trim();

        if (
            texto
            !== preview.confirmacion_esperada
        ) {
            actualizarBotonEliminar();
            return;
        }

        estado.eliminando = true;
        ejecutar.disabled = true;
        confirmacion.disabled = true;

        if (estadoTexto) {
            estadoTexto.textContent =
                'Encolando eliminación…';

            estadoTexto.className =
                'juego-eliminar__estado '
                + 'juego-eliminar__estado--aviso';
        }

        try {
            const datos =
                await postEliminarJuego(
                    'SOLICITAR',
                    {
                        juego_id:
                            Number(
                                preview.juego_id
                            ),

                        confirmacion:
                            texto,
                    }
                );

            estado.eliminacionId =
                Number(
                    datos.eliminacion_id
                );

            consultarEstadoEliminacion();

        } catch (error) {
            estado.eliminando = false;
            confirmacion.disabled = false;
            actualizarBotonEliminar();

            if (estadoTexto) {
                estadoTexto.textContent =
                    textoErrorEliminacion(
                        error
                    );

                estadoTexto.className =
                    'juego-eliminar__estado '
                    + 'juego-eliminar__estado--error';
            }
        }
    }


    function abrirDetalleJuego(id) {
        const juego =
            buscarJuegoPorId(id);

        const dialogo =
            elemento(
                'juegosDetalle'
            );

        const contenido =
            elemento(
                'juegosDetalleContenido'
            );

        const titulo =
            elemento(
                'juegosDetalleTitulo'
            );

        if (
            !juego
            || !dialogo
            || !contenido
        ) {
            return;
        }

        estado.detalleJuegoId =
            Number(juego.id);

        if (titulo) {
            titulo.textContent =
                juego.nombre;
        }

        contenido.innerHTML =
            htmlDetalleJuego(juego);

        if (!dialogo.open) {
            if (
                typeof dialogo.showModal
                === 'function'
            ) {
                dialogo.showModal();

            } else {
                dialogo.setAttribute(
                    'open',
                    ''
                );
            }
        }
    }


    function cerrarDetalleJuego() {
        const dialogo =
            elemento(
                'juegosDetalle'
            );

        if (!dialogo) {
            return;
        }

        if (
            dialogo.open
            && typeof dialogo.close
                === 'function'
        ) {
            dialogo.close();

        } else {
            dialogo.removeAttribute(
                'open'
            );

            estado.detalleJuegoId =
                null;
        }
    }


    function refrescarDetalleAbierto() {
        if (
            estado.detalleJuegoId
            === null
        ) {
            return;
        }

        const dialogo =
            elemento(
                'juegosDetalle'
            );

        if (
            !dialogo
            || !dialogo.open
        ) {
            return;
        }

        abrirDetalleJuego(
            estado.detalleJuegoId
        );
    }


    function compararNombre(a, b) {
        return String(
            a.nombre
            || ''
        ).localeCompare(
            String(
                b.nombre
                || ''
            ),
            'es-AR',
            {
                sensitivity: 'base',
                numeric: true,
            }
        );
    }


    function ordenarJuegos(
        juegos,
        criterio
    ) {
        const resultado =
            juegos.slice();

        const tamano =
            (juego) => {
                if (
                    juego.tamano_total_bytes
                    === null
                    || juego.tamano_total_bytes
                        === undefined
                ) {
                    return null;
                }

                const valor =
                    Number(
                        juego.tamano_total_bytes
                    );

                return Number.isFinite(
                    valor
                )
                    ? valor
                    : null;
            };

        const compararTamano =
            (
                a,
                b,
                direccion
            ) => {
                const valorA =
                    tamano(a);

                const valorB =
                    tamano(b);

                if (
                    valorA === null
                    && valorB === null
                ) {
                    return compararNombre(
                        a,
                        b
                    );
                }

                if (valorA === null) {
                    return 1;
                }

                if (valorB === null) {
                    return -1;
                }

                const diferencia =
                    (
                        valorA
                        - valorB
                    )
                    * direccion;

                return diferencia
                    || compararNombre(
                        a,
                        b
                    );
            };

        switch (criterio) {
            case 'nombre-desc':
                resultado.sort(
                    (a, b) =>
                        compararNombre(
                            b,
                            a
                        )
                );
                break;

            case 'tamano-desc':
                resultado.sort(
                    (a, b) =>
                        compararTamano(
                            a,
                            b,
                            -1
                        )
                );
                break;

            case 'tamano-asc':
                resultado.sort(
                    (a, b) =>
                        compararTamano(
                            a,
                            b,
                            1
                        )
                );
                break;

            case 'recientes':
                resultado.sort(
                    (a, b) => {
                        const fechaA =
                            Date.parse(
                                a.detectado_utc
                                || ''
                            );

                        const fechaB =
                            Date.parse(
                                b.detectado_utc
                                || ''
                            );

                        const valorA =
                            Number.isFinite(
                                fechaA
                            )
                                ? fechaA
                                : 0;

                        const valorB =
                            Number.isFinite(
                                fechaB
                            )
                                ? fechaB
                                : 0;

                        return (
                            valorB
                            - valorA
                        )
                        || compararNombre(
                            a,
                            b
                        );
                    }
                );
                break;

            case 'nombre-asc':
            default:
                resultado.sort(
                    compararNombre
                );
                break;
        }

        return resultado;
    }

    function obtenerFiltrados() {
        if (
            !estado.datos
            || !Array.isArray(
                estado.datos.juegos
            )
        ) {
            return [];
        }

        const buscar =
            (
                elemento(
                    'juegosBuscar'
                )?.value
                || ''
            )
            .trim()
            .toLocaleLowerCase(
                'es-AR'
            );

        const tipo =
            elemento(
                'juegosFiltroTipo'
            )?.value
            || '';

        const filtroEstado =
            elemento(
                'juegosFiltroEstado'
            )?.value
            || '';

        const orden =
            elemento(
                'juegosOrden'
            )?.value
            || 'nombre-asc';

        const filtrados =
            estado.datos.juegos
                .filter((juego) => {
                    const texto = [
                        juego.nombre,
                        juego.title_id,
                        juego.clave_logica,
                    ]
                        .filter(Boolean)
                        .join(' ')
                        .toLocaleLowerCase(
                            'es-AR'
                        );

                    if (
                        buscar
                        && !texto.includes(
                            buscar
                        )
                    ) {
                        return false;
                    }

                    if (
                        tipo
                        && juego.tipo_principal
                            !== tipo
                    ) {
                        return false;
                    }

                    if (
                        filtroEstado
                        === 'disponible'
                        && !juego.disponible
                    ) {
                        return false;
                    }

                    if (
                        filtroEstado
                        === 'no-disponible'
                        && juego.disponible
                    ) {
                        return false;
                    }

                    return true;
                });

        return ordenarJuegos(
            filtrados,
            orden
        );
    }

    function renderMetricas() {
        if (!estado.datos) {
            return;
        }

        const resumen =
            estado.datos.resumen
            || {};

        const inventario =
            estado.datos.inventario
            || {};

        const total =
            Number(
                resumen.juegos
                || 0
            );

        const disponibles =
            Number(
                resumen.juegos_disponibles
                || 0
            );

        const componentes =
            Number(
                resumen.componentes
                || 0
            );

        if (
            elemento(
                'juegosMetricaTotal'
            )
        ) {
            elemento(
                'juegosMetricaTotal'
            ).textContent =
                String(total);
        }

        if (
            elemento(
                'juegosMetricaDisponibles'
            )
        ) {
            elemento(
                'juegosMetricaDisponibles'
            ).textContent =
                String(disponibles);
        }

        if (
            elemento(
                'juegosMetricaComponentes'
            )
        ) {
            elemento(
                'juegosMetricaComponentes'
            ).textContent =
                String(componentes);
        }

        if (
            elemento(
                'juegosMetricaInventario'
            )
        ) {
            elemento(
                'juegosMetricaInventario'
            ).textContent =
                inventario.version
                || '—';
        }

        if (
            elemento(
                'juegosMetricaInventarioDetalle'
            )
        ) {
            elemento(
                'juegosMetricaInventarioDetalle'
            ).textContent =
                formatoFecha(
                    inventario.ultima_ok_utc
                );
        }

        const indicador =
            elemento(
                'juegosEstadoInventario'
            );

        if (indicador) {
            indicador.className =
                'estado '
                + (
                    inventario.ultimo_error
                        ? 'estado--error'
                        : 'estado--ok'
                );

            indicador.textContent =
                inventario.ultimo_error
                    ? 'Inventario · ERROR'
                    : 'Inventario · ACTUALIZADO';
        }
    }


    function renderLista() {
        const lista =
            elemento(
                'juegosLista'
            );

        if (!lista) {
            return;
        }

        const filtrados =
            obtenerFiltrados();

        const total =
            estado.datos?.juegos
                ?.length
            || 0;

        const resumen =
            elemento(
                'juegosResumen'
            );

        if (resumen) {
            resumen.textContent =
                `${filtrados.length} de ${total} juegos`;
        }

        if (!filtrados.length) {
            lista.innerHTML = `
                <div class="vacio">
                    No hay juegos que coincidan
                    con los filtros actuales.
                </div>
            `;

            return;
        }

        lista.innerHTML =
            filtrados
                .map(renderJuego)
                .join('');
    }


    function render() {
        renderMetricas();
        renderLista();
        refrescarDetalleAbierto();
    }


    function mostrarError(error) {
        const lista =
            elemento(
                'juegosLista'
            );

        if (lista) {
            lista.innerHTML = `
                <div class="vacio">
                    No se pudo cargar el inventario
                    de juegos.
                </div>
            `;
        }

        const indicador =
            elemento(
                'juegosEstadoInventario'
            );

        if (indicador) {
            indicador.className =
                'estado estado--error';

            indicador.textContent =
                'Inventario · ERROR';
        }

        console.error(
            'CTPS3 Juegos:',
            error
        );
    }


    async function cargarJuegos(
        silencioso = false
    ) {
        if (estado.cargando) {
            return;
        }

        estado.cargando = true;

        try {
            const respuesta =
                await fetch(
                    API_JUEGOS,
                    {
                        method: 'GET',
                        cache: 'no-store',
                    }
                );

            const datos =
                await respuesta.json();

            if (
                !respuesta.ok
                || datos.ok !== true
            ) {
                throw new Error(
                    datos.error
                    || `HTTP ${respuesta.status}`
                );
            }

            estado.datos =
                datos;

            render();

        } catch (error) {
            if (
                !silencioso
                || !estado.datos
            ) {
                mostrarError(
                    error
                );
            }

        } finally {
            estado.cargando = false;
        }
    }


    function iniciar() {
        const lista =
            elemento(
                'juegosLista'
            );

        if (!lista) {
            return;
        }

        elemento(
            'juegosBuscar'
        )?.addEventListener(
            'input',
            renderLista
        );

        elemento(
            'juegosFiltroTipo'
        )?.addEventListener(
            'change',
            renderLista
        );

        elemento(
            'juegosFiltroEstado'
        )?.addEventListener(
            'change',
            renderLista
        );

        elemento(
            'juegosOrden'
        )?.addEventListener(
            'change',
            renderLista
        );

        lista.addEventListener(
            'click',
            (evento) => {
                const boton =
                    evento.target
                        .closest(
                            '[data-juego-detalle]'
                        );

                if (
                    !boton
                    || !lista.contains(
                        boton
                    )
                ) {
                    return;
                }

                const id =
                    Number(
                        boton.dataset
                            .juegoDetalle
                    );

                if (
                    Number.isInteger(id)
                    && id > 0
                ) {
                    abrirDetalleJuego(
                        id
                    );
                }
            }
        );

        const dialogo =
            elemento(
                'juegosDetalle'
            );

        dialogo?.addEventListener(
            'click',
            (evento) => {
                if (
                    evento.target
                    === dialogo
                ) {
                    cerrarDetalleJuego();
                    return;
                }

                const eliminar =
                    evento.target
                        .closest(
                            '[data-juego-eliminar]'
                        );

                if (eliminar) {
                    const id =
                        Number(
                            eliminar.dataset
                                .juegoEliminar
                        );

                    if (
                        Number.isInteger(id)
                        && id > 0
                    ) {
                        abrirEliminarJuego(
                            id
                        );
                    }

                    return;
                }

                const cerrar =
                    evento.target
                        .closest(
                            '[data-juego-cerrar]'
                        );

                if (cerrar) {
                    cerrarDetalleJuego();
                }
            }
        );

        dialogo?.addEventListener(
            'close',
            () => {
                estado.detalleJuegoId =
                    null;
            }
        );

        const dialogoEliminar =
            elemento(
                'juegosEliminar'
            );

        dialogoEliminar?.addEventListener(
            'click',
            (evento) => {
                if (
                    evento.target
                    === dialogoEliminar
                ) {
                    cerrarEliminarJuego();
                    return;
                }

                const cerrar =
                    evento.target
                        .closest(
                            '[data-eliminacion-cerrar]'
                        );

                if (cerrar) {
                    cerrarEliminarJuego();
                }
            }
        );

        dialogoEliminar?.addEventListener(
            'close',
            () => {
                limpiarTimerEliminacion();

                estado.eliminacionPreview =
                    null;

                estado.eliminacionId =
                    null;

                estado.eliminando =
                    false;
            }
        );

        elemento(
            'juegosEliminarConfirmacion'
        )?.addEventListener(
            'input',
            actualizarBotonEliminar
        );

        elemento(
            'juegosEliminarEjecutar'
        )?.addEventListener(
            'click',
            confirmarEliminarJuego
        );

        cargarJuegos();

        window.setInterval(
            () => {
                if (
                    !document.hidden
                ) {
                    cargarJuegos(
                        true
                    );
                }
            },
            REFRESCO_MS
        );
    }


    if (
        document.readyState
        === 'loading'
    ) {
        document.addEventListener(
            'DOMContentLoaded',
            iniciar,
            {
                once: true,
            }
        );

    } else {
        iniciar();
    }

})();
