'use strict';


const filtrosHistorialV4 = {
    texto: '',
    estado: 'TODOS',
    juego: 'TODOS',
    reanudada: 'TODAS',
};


function normalizarHistorialV4(valor) {
    return String(
        valor ?? ''
    )
        .normalize('NFD')
        .replace(
            /[\u0300-\u036f]/g,
            ''
        )
        .toLowerCase()
        .trim();
}


function asegurarHistorialProfesionalV4() {
    let bloque =
        $('historialProfesionalV4');

    if (bloque) {
        return bloque;
    }

    const historial =
        $('historial');

    const panel =
        historial?.closest(
            '.panel'
        );

    const cabecera =
        panel?.querySelector(
            '.panel__cabecera'
        );

    if (!panel || !cabecera) {
        return null;
    }

    bloque =
        document.createElement(
            'div'
        );

    bloque.id =
        'historialProfesionalV4';

    bloque.className =
        'historial-profesional-v4';

    bloque.innerHTML = `
        <div
            id="estadisticasHistorialV4"
            class="historial-stats-v4"
        ></div>

        <div class="historial-filtros-v4">

            <div class="historial-busqueda-v4">
                <span>Buscar</span>

                <input
                    id="historialBuscarV4"
                    type="search"
                    autocomplete="off"
                    placeholder="Archivo, juego, código o estado…"
                >
            </div>

            <label>
                <span>Estado</span>

                <select id="historialEstadoV4">
                    <option value="TODOS">
                        Todos
                    </option>

                    <option value="CORRECTAS">
                        Correctas
                    </option>

                    <option value="COMPLETADO">
                        Completado
                    </option>

                    <option value="YA_EXISTE">
                        Ya existe
                    </option>

                    <option value="ERROR">
                        Error
                    </option>

                    <option value="CANCELADO">
                        Cancelado
                    </option>

                    <option value="CONFLICTO">
                        Conflicto
                    </option>
                </select>
            </label>

            <label>
                <span>Juego</span>

                <select id="historialJuegoV4">
                    <option value="TODOS">
                        Todos
                    </option>
                </select>
            </label>

            <label>
                <span>Reanudación</span>

                <select id="historialReanudadaV4">
                    <option value="TODAS">
                        Todas
                    </option>

                    <option value="SI">
                        Reanudadas
                    </option>

                    <option value="NO">
                        Sin reanudar
                    </option>
                </select>
            </label>

            <button
                id="historialLimpiarV4"
                class="
                    boton
                    boton--mini
                    boton--secundario
                "
                type="button"
            >
                Limpiar
            </button>

        </div>

        <div class="historial-filtros-v4__pie">

            <span id="historialResultadosV4">
                —
            </span>

            <span>
                Filtros sobre el historial reciente cargado
            </span>

        </div>

        <div
            id="historialJuegosV4"
            class="historial-juegos-v4"
        ></div>
    `;

    cabecera.insertAdjacentElement(
        'afterend',
        bloque
    );


    $('historialBuscarV4')
        ?.addEventListener(
            'input',
            (evento) => {
                filtrosHistorialV4.texto =
                    evento.target.value;

                aplicarFiltrosHistorialV4();
            }
        );


    $('historialEstadoV4')
        ?.addEventListener(
            'change',
            (evento) => {
                filtrosHistorialV4.estado =
                    evento.target.value;

                aplicarFiltrosHistorialV4();
            }
        );


    $('historialJuegoV4')
        ?.addEventListener(
            'change',
            (evento) => {
                filtrosHistorialV4.juego =
                    evento.target.value;

                aplicarFiltrosHistorialV4();
            }
        );


    $('historialReanudadaV4')
        ?.addEventListener(
            'change',
            (evento) => {
                filtrosHistorialV4.reanudada =
                    evento.target.value;

                aplicarFiltrosHistorialV4();
            }
        );


    $('historialLimpiarV4')
        ?.addEventListener(
            'click',
            () => {
                filtrosHistorialV4.texto =
                    '';

                filtrosHistorialV4.estado =
                    'TODOS';

                filtrosHistorialV4.juego =
                    'TODOS';

                filtrosHistorialV4.reanudada =
                    'TODAS';

                $('historialBuscarV4').value =
                    '';

                $('historialEstadoV4').value =
                    'TODOS';

                $('historialJuegoV4').value =
                    'TODOS';

                $('historialReanudadaV4').value =
                    'TODAS';

                aplicarFiltrosHistorialV4();
            }
        );


    return bloque;
}


function renderStatsHistorialV4(
    datos
) {
    const resumen =
        datos.resumen;

    const contenedor =
        $('estadisticasHistorialV4');

    if (!contenedor) {
        return;
    }

    const tasa =
        resumen.tasa_correctas === null
            ? '—'
            : (
                `${Number(
                    resumen.tasa_correctas
                ).toFixed(1)}%`
            );

    contenedor.innerHTML = `
        <article class="historial-stat-v4">
            <span>Registros</span>

            <strong>
                ${resumen.total}
            </strong>

            <small>
                historial total
            </small>
        </article>


        <article class="historial-stat-v4">
            <span>Correctas</span>

            <strong>
                ${resumen.correctas}
            </strong>

            <small>
                ${tasa} de terminales
            </small>
        </article>


        <article class="historial-stat-v4">
            <span>Completado</span>

            <strong>
                ${bytes(
                    resumen.bytes_completados
                )}
            </strong>

            <small>
                transferido con éxito
            </small>
        </article>


        <article class="historial-stat-v4">
            <span>Velocidad media</span>

            <strong>
                ${velocidad(
                    resumen.velocidad_media_bps
                )}
            </strong>

            <small>
                transferencias completas
            </small>
        </article>


        <article class="historial-stat-v4">
            <span>Tiempo efectivo</span>

            <strong>
                ${tiempo(
                    resumen
                        .tiempo_transferencia_segundos
                )}
            </strong>

            <small>
                sesiones completadas
            </small>
        </article>


        <article class="historial-stat-v4">
            <span>Reanudadas</span>

            <strong>
                ${resumen.reanudadas}
            </strong>

            <small>
                continuaron un parcial
            </small>
        </article>
    `;
}


function actualizarJuegosFiltroV4() {
    const select =
        $('historialJuegoV4');

    if (!select) {
        return;
    }

    const valorActual =
        filtrosHistorialV4.juego;

    const juegos =
        new Map();

    for (
        const item
        of transferencias
    ) {
        if (item.activa) {
            continue;
        }

        const clave =
            item.codigo_juego
            || item.titulo_juego
            || item.nombre_snapshot;

        const etiqueta =
            item.titulo_juego
            || item.nombre_snapshot;

        if (
            !juegos.has(clave)
        ) {
            juegos.set(
                clave,
                {
                    clave,
                    etiqueta,
                    codigo:
                        item.codigo_juego,
                }
            );
        }
    }

    select.innerHTML =
        `
            <option value="TODOS">
                Todos
            </option>
        `
        + [...juegos.values()]
            .sort(
                (a, b) =>
                    a.etiqueta.localeCompare(
                        b.etiqueta,
                        'es'
                    )
            )
            .map(
                (juego) => `
                    <option
                        value="${escapar(
                            juego.clave
                        )}"
                    >
                        ${escapar(
                            juego.etiqueta
                        )}
                        ${
                            juego.codigo
                                ? ` · ${
                                    escapar(
                                        juego.codigo
                                    )
                                }`
                                : ''
                        }
                    </option>
                `
            )
            .join('');

    const existe =
        [...select.options]
            .some(
                (opcion) =>
                    opcion.value
                    === valorActual
            );

    select.value =
        existe
            ? valorActual
            : 'TODOS';

    if (!existe) {
        filtrosHistorialV4.juego =
            'TODOS';
    }
}


function coincideEstadoHistorialV4(
    transferencia
) {
    const filtro =
        filtrosHistorialV4.estado;

    if (filtro === 'TODOS') {
        return true;
    }

    if (filtro === 'CORRECTAS') {
        return [
            'COMPLETADO',
            'YA_EXISTE',
        ].includes(
            transferencia.estado
        );
    }

    return transferencia.estado
        === filtro;
}


function coincideJuegoHistorialV4(
    transferencia
) {
    if (
        filtrosHistorialV4.juego
        === 'TODOS'
    ) {
        return true;
    }

    const clave =
        transferencia.codigo_juego
        || transferencia.titulo_juego
        || transferencia.nombre_snapshot;

    return clave
        === filtrosHistorialV4.juego;
}


function coincideReanudacionHistorialV4(
    transferencia
) {
    const filtro =
        filtrosHistorialV4.reanudada;

    if (filtro === 'TODAS') {
        return true;
    }

    if (filtro === 'SI') {
        return Boolean(
            transferencia.reanudada
        );
    }

    return !transferencia.reanudada;
}


function coincideTextoHistorialV4(
    transferencia
) {
    const texto =
        normalizarHistorialV4(
            filtrosHistorialV4.texto
        );

    if (!texto) {
        return true;
    }

    const contenido =
        normalizarHistorialV4(
            [
                transferencia.nombre_snapshot,
                transferencia.titulo_juego,
                transferencia.codigo_juego,
                transferencia.estado,
                transferencia.mensaje,
                transferencia.error_codigo,
            ]
                .filter(Boolean)
                .join(' ')
        );

    return contenido.includes(
        texto
    );
}


function aplicarFiltrosHistorialV4() {
    const historial =
        transferencias
            .filter(
                (item) =>
                    !item.activa
            )
            .slice(
                0,
                30
            );

    let visibles = 0;

    for (
        const transferencia
        of historial
    ) {
        const tarjeta =
            document.querySelector(
                (
                    '#historial '
                    + '.transferencia'
                    + `[data-transferencia-id="${transferencia.id}"]`
                )
            );

        if (!tarjeta) {
            continue;
        }

        const mostrar =
            coincideEstadoHistorialV4(
                transferencia
            )
            && coincideJuegoHistorialV4(
                transferencia
            )
            && coincideReanudacionHistorialV4(
                transferencia
            )
            && coincideTextoHistorialV4(
                transferencia
            );

        tarjeta.hidden =
            !mostrar;

        if (mostrar) {
            visibles++;
        }
    }

    const contador =
        $('historialResultadosV4');

    if (contador) {
        contador.textContent =
            (
                `${visibles} de `
                + `${historial.length} visibles`
            );
    }
}


function renderJuegosHistorialV4(
    datos
) {
    const contenedor =
        $('historialJuegosV4');

    if (!contenedor) {
        return;
    }

    const juegos =
        datos.juegos
        || [];

    if (!juegos.length) {
        contenedor.innerHTML =
            '';

        return;
    }

    contenedor.innerHTML = `
        <div class="historial-juegos-v4__cabecera">
            <div>
                <span class="subtitulo">
                    RESUMEN HISTÓRICO
                </span>

                <h3>
                    Actividad por juego
                </h3>
            </div>

            <span>
                ${juegos.length}
                ${
                    juegos.length === 1
                        ? 'juego'
                        : 'juegos'
                }
            </span>
        </div>

        <div class="historial-juegos-v4__tabla">

            ${juegos.map(
                (juego) => `
                    <div class="historial-juego-v4">

                        <div
                            class="
                                historial-juego-v4__nombre
                            "
                        >
                            <strong>
                                ${escapar(
                                    juego.juego
                                )}
                            </strong>

                            <span>
                                ${escapar(
                                    juego.codigo
                                    || 'SIN CÓDIGO'
                                )}
                            </span>
                        </div>


                        <div>
                            <span>Registros</span>

                            <strong>
                                ${juego.transferencias}
                            </strong>
                        </div>


                        <div>
                            <span>Correctas</span>

                            <strong>
                                ${
                                    juego.completadas
                                    + juego.ya_existe
                                }
                            </strong>
                        </div>


                        <div>
                            <span>Errores</span>

                            <strong>
                                ${juego.errores}
                            </strong>
                        </div>


                        <div>
                            <span>Completado</span>

                            <strong>
                                ${bytes(
                                    juego.bytes_completados
                                )}
                            </strong>
                        </div>


                        <div>
                            <span>Última actividad</span>

                            <strong>
                                ${fecha(
                                    juego.ultima_actividad_utc
                                )}
                            </strong>
                        </div>

                    </div>
                `
            ).join('')}

        </div>
    `;
}


function renderHistorialProfesional(
    datos
) {
    asegurarHistorialProfesionalV4();

    renderStatsHistorialV4(
        datos
    );

    actualizarJuegosFiltroV4();

    renderJuegosHistorialV4(
        datos
    );

    aplicarFiltrosHistorialV4();
}
