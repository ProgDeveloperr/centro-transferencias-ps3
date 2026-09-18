'use strict';


function nombrePrioridad(valor) {
    const numero =
        Number(valor);

    if (numero <= 10) {
        return 'ALTA';
    }

    if (numero >= 200) {
        return 'BAJA';
    }

    return 'NORMAL';
}


function clasePrioridad(valor) {
    const nombre =
        nombrePrioridad(valor);

    return (
        'prioridad-v2--'
        + nombre.toLowerCase()
    );
}


async function ejecutarAccionCola(
    transferenciaId,
    accion,
    extra = {}
) {
    try {
        const datos = await post(
            'api/cola.php',
            {
                transferencia_id:
                    transferenciaId,

                accion,

                ...extra,
            }
        );

        if (datos.sin_cambio) {
            toast(
                'La transferencia ya está en ese extremo de la cola.'
            );
        }

        await cargarTodo();

    } catch (error) {
        toast(
            `No se pudo modificar la cola: ${error.message}`,
            'error'
        );
    }
}


function asegurarResumenCola() {
    let elemento =
        $('colaProfesionalResumen');

    if (elemento) {
        return elemento;
    }

    const cola =
        $('cola');

    const panel =
        cola?.closest('.panel');

    if (!panel) {
        return null;
    }

    elemento =
        document.createElement('div');

    elemento.id =
        'colaProfesionalResumen';

    elemento.className =
        'cola-profesional';

    const cabecera =
        panel.querySelector(
            '.panel__cabecera'
        );

    cabecera?.insertAdjacentElement(
        'afterend',
        elemento
    );

    return elemento;
}


function renderResumenCola(resumen) {
    const elemento =
        asegurarResumenCola();

    if (!elemento) {
        return;
    }

    elemento.innerHTML = `
        <div class="cola-profesional__dato">
            <span>Pendiente</span>
            <strong>
                ${bytes(
                    resumen.pendientes_bytes
                )}
            </strong>
        </div>

        <div class="cola-profesional__dato">
            <span>ETA total</span>
            <strong>
                ${tiempo(
                    resumen.eta_cola_segundos
                )}
            </strong>
        </div>

        <div class="cola-profesional__dato">
            <span>Velocidad referencia</span>
            <strong>
                ${velocidad(
                    resumen.velocidad_referencia_bps
                )}
            </strong>
        </div>

        <div class="cola-profesional__dato">
            <span>En cola</span>
            <strong>
                ${resumen.en_cola}
            </strong>
        </div>

        <div class="cola-profesional__dato">
            <span>Pausadas</span>
            <strong>
                ${resumen.pausadas}
            </strong>
        </div>
    `;
}


function decorarTransferenciasCola() {
    for (
        const transferencia
        of transferencias
    ) {
        if (!transferencia.activa) {
            continue;
        }

        const tarjeta =
            document.querySelector(
                (
                    '.transferencia'
                    + `[data-transferencia-id="${transferencia.id}"]`
                )
            );

        if (!tarjeta) {
            continue;
        }

        const superior =
            tarjeta.querySelector(
                '.transferencia__superior'
            );

        if (superior) {
            const prioridad =
                document.createElement(
                    'span'
                );

            prioridad.className =
                (
                    'prioridad-v2 '
                    + clasePrioridad(
                        transferencia.prioridad
                    )
                );

            prioridad.textContent =
                (
                    'PRIORIDAD · '
                    + nombrePrioridad(
                        transferencia.prioridad
                    )
                );

            const detalle =
                tarjeta.querySelector(
                    '.transferencia__detalle'
                );

            detalle
                ?.insertAdjacentElement(
                    'afterend',
                    prioridad
                );
        }

        if (
            transferencia.estado
            !== 'EN_COLA'
        ) {
            continue;
        }

        let acciones =
            tarjeta.querySelector(
                '.transferencia__acciones'
            );

        if (!acciones) {
            acciones =
                document.createElement(
                    'div'
                );

            acciones.className =
                'transferencia__acciones';

            tarjeta.appendChild(
                acciones
            );
        }

        const controles =
            document.createElement(
                'div'
            );

        controles.className =
            'cola-controles-v2';


        const subir =
            document.createElement(
                'button'
            );

        subir.type =
            'button';

        subir.className =
            (
                'boton boton--mini '
                + 'boton--secundario'
            );

        subir.textContent =
            '↑';

        subir.title =
            'Subir en la cola';

        subir.addEventListener(
            'click',
            () => {
                ejecutarAccionCola(
                    transferencia.id,
                    'MOVER_ARRIBA'
                );
            }
        );


        const bajar =
            document.createElement(
                'button'
            );

        bajar.type =
            'button';

        bajar.className =
            (
                'boton boton--mini '
                + 'boton--secundario'
            );

        bajar.textContent =
            '↓';

        bajar.title =
            'Bajar en la cola';

        bajar.addEventListener(
            'click',
            () => {
                ejecutarAccionCola(
                    transferencia.id,
                    'MOVER_ABAJO'
                );
            }
        );


        const selector =
            document.createElement(
                'select'
            );

        selector.className =
            'selector-prioridad-v2';

        for (
            const nombre
            of [
                'ALTA',
                'NORMAL',
                'BAJA',
            ]
        ) {
            const opcion =
                document.createElement(
                    'option'
                );

            opcion.value =
                nombre;

            opcion.textContent =
                nombre;

            selector.appendChild(
                opcion
            );
        }

        selector.value =
            nombrePrioridad(
                transferencia.prioridad
            );

        selector.title =
            'Prioridad de transferencia';

        selector.addEventListener(
            'change',
            () => {
                ejecutarAccionCola(
                    transferencia.id,
                    'PRIORIDAD',
                    {
                        prioridad:
                            selector.value,
                    }
                );
            }
        );


        controles.append(
            subir,
            bajar,
            selector
        );

        acciones.prepend(
            controles
        );
    }
}


function asegurarControlesGlobales() {
    let elemento =
        $('colaGlobalControles');

    if (elemento) {
        return elemento;
    }

    const cola =
        $('cola');

    const panel =
        cola?.closest('.panel');

    const cabecera =
        panel?.querySelector(
            '.panel__cabecera'
        );

    if (!cabecera) {
        return null;
    }

    elemento =
        document.createElement(
            'div'
        );

    elemento.id =
        'colaGlobalControles';

    elemento.className =
        'cola-global-v3';

    cabecera.appendChild(
        elemento
    );

    return elemento;
}


async function ejecutarControlGlobal(
    accion,
    boton
) {
    boton.disabled = true;

    try {
        const datos = await post(
            'api/cola-global.php',
            {
                accion,
            }
        );

        if (datos.sin_cambio) {
            toast(
                'La cola ya estaba en ese estado.'
            );

        } else if (
            accion === 'PAUSAR_COLA'
        ) {
            toast(
                datos.transferencia_actual
                    ? (
                        'Cola pausada. '
                        + 'La transferencia actual '
                        + 'continuará hasta terminar '
                        + 'o hasta que la pauses '
                        + 'individualmente.'
                    )
                    : 'Cola pausada.'
            );

        } else {
            toast(
                'Cola reanudada.'
            );
        }

        await cargarTodo();

    } catch (error) {
        toast(
            (
                'No se pudo cambiar '
                + 'el estado de la cola: '
                + error.message
            ),
            'error'
        );

    } finally {
        boton.disabled = false;
    }
}


function renderControlGlobal(
    resumen
) {
    const elemento =
        asegurarControlesGlobales();

    if (!elemento) {
        return;
    }

    const pausada =
        Boolean(
            resumen.cola_pausada
        );

    elemento.innerHTML = `
        <div class="cola-global-v3__estado">
            <span
                class="
                    cola-global-v3__punto
                    ${
                        pausada
                            ? 'cola-global-v3__punto--pausa'
                            : 'cola-global-v3__punto--activo'
                    }
                "
            ></span>

            <div>
                <strong>
                    ${
                        pausada
                            ? 'COLA PAUSADA'
                            : 'COLA ACTIVA'
                    }
                </strong>

                <span>
                    ${
                        pausada
                            ? 'No se iniciarán nuevos archivos'
                            : 'Despacho automático habilitado'
                    }
                </span>
            </div>
        </div>

        <button
            id="botonEstadoColaGlobal"
            class="
                boton
                boton--mini
                ${
                    pausada
                        ? 'boton--primario'
                        : 'boton--secundario'
                }
            "
            type="button"
        >
            ${
                pausada
                    ? 'Reanudar cola'
                    : 'Pausar cola'
            }
        </button>
    `;

    const boton =
        $('botonEstadoColaGlobal');

    boton?.addEventListener(
        'click',
        () => {
            ejecutarControlGlobal(
                pausada
                    ? 'REANUDAR_COLA'
                    : 'PAUSAR_COLA',
                boton
            );
        }
    );
}


function asegurarModalDetalles() {
    let modal =
        $('modalDetallesTransferencia');

    if (modal) {
        return modal;
    }

    modal =
        document.createElement(
            'div'
        );

    modal.id =
        'modalDetallesTransferencia';

    modal.className =
        'modal modal--oculto';

    modal.setAttribute(
        'role',
        'dialog'
    );

    modal.setAttribute(
        'aria-modal',
        'true'
    );

    modal.innerHTML = `
        <div
            class="modal__fondo"
            data-cerrar-detalles
        ></div>

        <div
            class="
                modal__tarjeta
                modal__tarjeta--detalle-v3
            "
        >
            <div class="detalle-v3__cabecera">
                <div>
                    <span class="subtitulo">
                        TRANSFERENCIA
                    </span>

                    <h3 id="detalleV3Titulo">
                        Detalles
                    </h3>
                </div>

                <button
                    id="detalleV3Cerrar"
                    class="
                        boton
                        boton--mini
                        boton--secundario
                    "
                    type="button"
                >
                    Cerrar
                </button>
            </div>

            <div
                id="detalleV3Contenido"
                class="detalle-v3"
            ></div>
        </div>
    `;

    document.body.appendChild(
        modal
    );

    const cerrar = () => {
        modal.classList.add(
            'modal--oculto'
        );
    };

    modal
        .querySelector(
            '[data-cerrar-detalles]'
        )
        ?.addEventListener(
            'click',
            cerrar
        );

    $('detalleV3Cerrar')
        ?.addEventListener(
            'click',
            cerrar
        );

    return modal;
}


function detalleV3Fila(
    etiqueta,
    valor,
    amplia = false
) {
    return `
        <div
            class="
                detalle-v3__fila
                ${
                    amplia
                        ? 'detalle-v3__fila--amplia'
                        : ''
                }
            "
        >
            <span>
                ${escapar(etiqueta)}
            </span>

            <strong>
                ${escapar(
                    valor === null
                    || valor === undefined
                    || valor === ''
                        ? '—'
                        : valor
                )}
            </strong>
        </div>
    `;
}


function abrirDetallesTransferencia(
    transferenciaId
) {
    const transferencia =
        transferencias.find(
            (item) =>
                Number(item.id)
                === Number(
                    transferenciaId
                )
        );

    if (!transferencia) {
        toast(
            'No se encontró la transferencia.',
            'error'
        );

        return;
    }

    const modal =
        asegurarModalDetalles();

    $('detalleV3Titulo').textContent =
        transferencia.nombre_snapshot;

    const partes = [];

    partes.push(
        detalleV3Fila(
            'Estado',
            transferencia.estado
        )
    );

    partes.push(
        detalleV3Fila(
            'Prioridad',
            transferencia.prioridad_nombre
            || nombrePrioridad(
                transferencia.prioridad
            )
        )
    );

    partes.push(
        detalleV3Fila(
            'Posición',
            transferencia.posicion_cola
        )
    );

    partes.push(
        detalleV3Fila(
            'Progreso',
            `${Number(
                transferencia.porcentaje
                || 0
            ).toFixed(1)}%`
        )
    );

    partes.push(
        detalleV3Fila(
            'Tamaño total',
            bytes(
                transferencia.tamano_total
            )
        )
    );

    partes.push(
        detalleV3Fila(
            'Remoto',
            bytes(
                transferencia.bytes_remotos
            )
        )
    );

    partes.push(
        detalleV3Fila(
            'Pendiente',
            bytes(
                transferencia.bytes_pendientes
            )
        )
    );

    partes.push(
        detalleV3Fila(
            'Velocidad actual',
            velocidad(
                transferencia.velocidad_bps
            )
        )
    );

    partes.push(
        detalleV3Fila(
            'Velocidad promedio',
            velocidad(
                transferencia
                    .velocidad_promedio_bps
            )
        )
    );

    partes.push(
        detalleV3Fila(
            'Duración',
            tiempo(
                transferencia
                    .duracion_segundos
            )
        )
    );

    partes.push(
        detalleV3Fila(
            'Espera inicial',
            tiempo(
                transferencia
                    .espera_segundos
            )
        )
    );

    partes.push(
        detalleV3Fila(
            'Intentos',
            transferencia.intentos
        )
    );

    partes.push(
        detalleV3Fila(
            'Reanudada',
            transferencia.reanudada
                ? 'Sí'
                : 'No'
        )
    );

    partes.push(
        detalleV3Fila(
            'PID lftp',
            transferencia.pid
        )
    );

    partes.push(
        detalleV3Fila(
            'Juego',
            transferencia.titulo_juego
            || '—',
            true
        )
    );

    partes.push(
        detalleV3Fila(
            'Código',
            transferencia.codigo_juego
            || '—'
        )
    );

    partes.push(
        detalleV3Fila(
            'Parte',
            transferencia.parte_numero
            ?? '—'
        )
    );

    partes.push(
        detalleV3Fila(
            'Creada',
            fecha(
                transferencia.creada_utc
            )
        )
    );

    partes.push(
        detalleV3Fila(
            'Iniciada',
            fecha(
                transferencia.iniciada_utc
            )
        )
    );

    partes.push(
        detalleV3Fila(
            'Finalizada',
            fecha(
                transferencia.finalizada_utc
            )
        )
    );

    partes.push(
        detalleV3Fila(
            'Mensaje',
            transferencia.mensaje
            || '—',
            true
        )
    );

    if (
        transferencia.error_codigo
        || transferencia.error_detalle
    ) {
        partes.push(
            detalleV3Fila(
                'Código de error',
                transferencia.error_codigo
                || '—',
                true
            )
        );

        partes.push(
            detalleV3Fila(
                'Detalle de error',
                transferencia.error_detalle
                || '—',
                true
            )
        );
    }

    $('detalleV3Contenido').innerHTML =
        partes.join('');

    modal.classList.remove(
        'modal--oculto'
    );
}


function decorarDetallesTransferencias() {
    for (
        const transferencia
        of transferencias
    ) {
        const tarjeta =
            document.querySelector(
                (
                    '.transferencia'
                    + `[data-transferencia-id="${transferencia.id}"]`
                )
            );

        if (!tarjeta) {
            continue;
        }

        if (!transferencia.activa) {
            const informacion =
                tarjeta.querySelectorAll(
                    '.progreso-info span'
                );

            if (
                informacion.length >= 2
            ) {
                informacion[1]
                    .textContent =
                    (
                        `${velocidad(
                            transferencia
                                .velocidad_promedio_bps
                        )} promedio`
                        + ' · '
                        + `${tiempo(
                            transferencia
                                .duracion_segundos
                        )}`
                    );
            }
        }

        let acciones =
            tarjeta.querySelector(
                '.transferencia__acciones'
            );

        if (!acciones) {
            acciones =
                document.createElement(
                    'div'
                );

            acciones.className =
                'transferencia__acciones';

            tarjeta.appendChild(
                acciones
            );
        }

        const boton =
            document.createElement(
                'button'
            );

        boton.type =
            'button';

        boton.className =
            (
                'boton boton--mini '
                + 'boton--secundario'
            );

        boton.textContent =
            'Detalles';

        boton.addEventListener(
            'click',
            () => {
                abrirDetallesTransferencia(
                    transferencia.id
                );
            }
        );

        acciones.appendChild(
            boton
        );
    }
}


function renderColaProfesional(datos) {
    const resumen =
        datos.resumen
        || {
            activas: 0,
            en_cola: 0,
            pausadas: 0,
            pendientes_bytes: 0,
            velocidad_referencia_bps: 0,
            eta_cola_segundos: null,
            cola_pausada: false,
        };

    renderResumenCola(
        resumen
    );

    renderControlGlobal(
        resumen
    );

    decorarTransferenciasCola();

    decorarDetallesTransferencias();
}
