(() => {
    'use strict';


    const $ = (id) =>
        document.getElementById(id);


    const escapar = (valor) =>
        String(
            valor ?? ''
        )
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');


    const fechaHumana = (valor) => {

        if (!valor) {
            return '—';
        }

        const fecha =
            new Date(valor);

        if (
            Number.isNaN(
                fecha.getTime()
            )
        ) {
            return valor;
        }


        return fecha.toLocaleString(
            'es-AR',
            {
                dateStyle:
                    'short',

                timeStyle:
                    'medium',
            }
        );
    };


    const bytesHumanos = (valor) => {

        let numero =
            Number(
                valor || 0
            );


        const unidades = [
            'B',
            'KiB',
            'MiB',
            'GiB',
            'TiB',
        ];


        let indice = 0;


        while (
            numero >= 1024
            && indice
                < unidades.length - 1
        ) {
            numero /= 1024;

            indice++;
        }


        return (
            `${numero.toFixed(
                indice === 0
                    ? 0
                    : 2
            )} ${unidades[indice]}`
        );
    };


    const tipoHumano = (tipo) => {

        switch (tipo) {

            case 'SESION_HUERFANA':
                return 'Sesión FTP huérfana';

            case 'TRANSFERENCIA_RECUPERADA':
                return 'Transferencia recuperada';

            default:
                return tipo || 'Recuperación';
        }
    };


    const actualizarEstadoGeneral = (
        estado
    ) => {

        const elemento =
            $('resilienciaEstadoGeneral');


        if (!elemento) {
            return;
        }


        elemento.className =
            'resiliencia-panel__estado-general';


        const normalizado =
            String(
                estado || 'INCIDENTE'
            ).toLowerCase();


        elemento.classList.add(
            'resiliencia-panel__estado-general--'
            + normalizado
        );


        elemento.textContent =
            estado || 'INCIDENTE';
    };


    const renderChecks = (
        comprobaciones
    ) => {

        const contenedor =
            $('resilienciaChecks');


        if (!contenedor) {
            return;
        }


        if (
            !Array.isArray(
                comprobaciones
            )
            || comprobaciones.length === 0
        ) {

            contenedor.innerHTML = `
                <div class="resiliencia-panel__vacio">
                    Sin comprobaciones disponibles.
                </div>
            `;

            return;
        }


        contenedor.innerHTML =
            comprobaciones
                .map(
                    (item) => {

                        const estado =
                            String(
                                item.estado
                                || 'ERROR'
                            ).toLowerCase();


                        return `
                            <div
                                class="
                                    resiliencia-panel__check
                                    resiliencia-panel__check--${escapar(
                                        estado
                                    )}
                                "
                            >
                                <span
                                    class="resiliencia-panel__check-indicador"
                                ></span>

                                <div>
                                    <strong>
                                        ${escapar(
                                            item.titulo
                                        )}
                                    </strong>

                                    <small>
                                        ${escapar(
                                            item.detalle
                                        )}
                                    </small>
                                </div>
                            </div>
                        `;
                    }
                )
                .join('');
    };


    const renderRecuperaciones = (
        recuperaciones
    ) => {

        const contenedor =
            $('resilienciaRecuperaciones');


        if (!contenedor) {
            return;
        }


        if (
            !Array.isArray(
                recuperaciones
            )
            || recuperaciones.length === 0
        ) {

            contenedor.innerHTML = `
                <div class="resiliencia-panel__vacio">
                    No hay incidentes de recuperación
                    conservados actualmente.
                </div>
            `;

            return;
        }


        contenedor.innerHTML =
            recuperaciones
                .map(
                    (item) => {

                        const pendiente =
                            Boolean(
                                item.pendiente
                            );


                        const archivo =
                            item.nombre_snapshot
                                ? escapar(
                                    item.nombre_snapshot
                                )
                                : 'Transferencia no disponible';


                        const bytesObservados =
                            item.bytes_observados
                                === null
                                ? '—'
                                : bytesHumanos(
                                    item.bytes_observados
                                );


                        const bytesReconciliados =
                            item.bytes_reconciliados
                                === null
                                ? 'pendiente'
                                : bytesHumanos(
                                    item.bytes_reconciliados
                                );


                        return `
                            <article
                                class="resiliencia-panel__recuperacion"
                            >

                                <div
                                    class="resiliencia-panel__recuperacion-arriba"
                                >
                                    <div
                                        class="resiliencia-panel__recuperacion-tipo"
                                        title="${archivo}"
                                    >
                                        #${item.id}
                                        ·
                                        ${escapar(
                                            tipoHumano(
                                                item.tipo
                                            )
                                        )}
                                    </div>

                                    <span
                                        class="
                                            resiliencia-panel__badge
                                            ${
                                                pendiente
                                                    ? 'resiliencia-panel__badge--pendiente'
                                                    : 'resiliencia-panel__badge--resuelta'
                                            }
                                        "
                                    >
                                        ${
                                            pendiente
                                                ? 'PENDIENTE'
                                                : 'RESUELTA'
                                        }
                                    </span>
                                </div>


                                <div
                                    class="resiliencia-panel__recuperacion-datos"
                                >

                                    ${
                                        item.transferencia_id
                                            !== null
                                            ? `
                                                <span>
                                                    Transferencia
                                                    #${item.transferencia_id}
                                                </span>
                                            `
                                            : ''
                                    }

                                    ${
                                        item.numero_sesion
                                            !== null
                                            ? `
                                                <span>
                                                    Sesión
                                                    #${item.numero_sesion}
                                                </span>
                                            `
                                            : ''
                                    }

                                    <span>
                                        ${escapar(
                                            item.estado_anterior
                                            || '—'
                                        )}
                                        →
                                        ${escapar(
                                            item.estado_nuevo
                                            || '—'
                                        )}
                                    </span>

                                    <span>
                                        Observado:
                                        ${bytesObservados}
                                    </span>

                                    <span>
                                        Reconciliado:
                                        ${bytesReconciliados}
                                    </span>

                                    <span>
                                        ${fechaHumana(
                                            item.creada_utc
                                        )}
                                    </span>

                                </div>


                                <div
                                    class="resiliencia-panel__detalle"
                                >
                                    ${archivo}

                                    ${
                                        item.detalle_reconciliacion
                                            ? (
                                                ' · '
                                                + escapar(
                                                    item.detalle_reconciliacion
                                                )
                                            )
                                            : ''
                                    }
                                </div>

                            </article>
                        `;
                    }
                )
                .join('');
    };


    const render = (datos) => {

        const worker =
            datos.worker || {};

        const operacion =
            datos.operacion || {};

        const auditoria =
            datos.auditoria || {};


        actualizarEstadoGeneral(
            datos.estado_general
        );


        $('resilienciaWorker').textContent =
            worker.estado || '—';


        $('resilienciaWorkerDetalle').textContent =
            (
                `v${worker.version || '—'}`
                + (
                    worker.pid !== null
                        && worker.pid !== undefined
                        ? ` · PID ${worker.pid}`
                        : ''
                )
            );


        $('resilienciaHeartbeat').textContent =
            worker.heartbeat_segundos
                !== null
                && worker.heartbeat_segundos
                    !== undefined
                ? (
                    `${worker.heartbeat_segundos} s`
                )
                : '—';


        $('resilienciaHeartbeatDetalle').textContent =
            worker.heartbeat_ok
                ? 'Heartbeat actualizado'
                : 'Heartbeat fuera de rango';


        $('resilienciaEjecucion').textContent =
            String(
                operacion.transferencias_ejecucion
                || 0
            );


        $('resilienciaEjecucionDetalle').textContent =
            (
                `${operacion.transferencias_cola || 0} en cola`
                + ' · '
                + `${operacion.transferencias_pausadas || 0} pausadas`
            );


        $('resilienciaSesiones').textContent =
            String(
                operacion.sesiones_en_curso
                || 0
            );


        $('resilienciaSesionesDetalle').textContent =
            (
                `${operacion.sesiones_inconsistentes || 0} inconsistentes`
            );


        $('resilienciaRecuperadas').textContent =
            String(
                auditoria.resueltas
                || 0
            );


        $('resilienciaRecuperadasDetalle').textContent =
            (
                `${auditoria.total || 0} registros históricos`
            );


        $('resilienciaPendientes').textContent =
            String(
                auditoria.pendientes
                || 0
            );


        $('resilienciaPendientesDetalle').textContent =
            auditoria.pendientes
                ? 'Requieren reconciliación'
                : 'Sin acciones pendientes';


        $('resilienciaHuerfanas').textContent =
            String(
                auditoria.sesiones_huerfanas
                || 0
            );


        $('resilienciaHuerfanasDetalle').textContent =
            (
                `${auditoria.transferencias_recuperadas || 0} transferencias recuperadas`
            );


        $('resilienciaActualizado').textContent =
            (
                'Actualizado '
                + new Date().toLocaleTimeString(
                    'es-AR'
                )
            );


        renderChecks(
            datos.comprobaciones
        );


        renderRecuperaciones(
            datos.recuperaciones
        );


        const panel =
            $('resilienciaPanel');


        if (panel) {
            panel.classList.remove(
                'resiliencia-panel__actualizando'
            );
        }
    };


    const mostrarError = (
        mensaje
    ) => {

        actualizarEstadoGeneral(
            'INCIDENTE'
        );


        const checks =
            $('resilienciaChecks');


        if (checks) {

            checks.innerHTML = `
                <div class="resiliencia-panel__vacio">
                    No se pudo consultar el estado:
                    ${escapar(mensaje)}
                </div>
            `;
        }


        const panel =
            $('resilienciaPanel');


        if (panel) {
            panel.classList.remove(
                'resiliencia-panel__actualizando'
            );
        }
    };


    const actualizar = async () => {

        const panel =
            $('resilienciaPanel');


        if (!panel) {
            return;
        }


        panel.classList.add(
            'resiliencia-panel__actualizando'
        );


        try {

            const respuesta =
                await fetch(
                    'api/resiliencia.php',
                    {
                        cache:
                            'no-store',
                    }
                );


            if (!respuesta.ok) {
                throw new Error(
                    `HTTP ${respuesta.status}`
                );
            }


            const datos =
                await respuesta.json();


            if (!datos.ok) {
                throw new Error(
                    datos.error
                    || 'Respuesta inválida'
                );
            }


            render(
                datos
            );


        } catch (error) {

            mostrarError(
                error.message
                || 'error desconocido'
            );
        }
    };


    document.addEventListener(
        'DOMContentLoaded',
        () => {

            actualizar();


            window.setInterval(
                actualizar,
                10000
            );
        }
    );

})();
