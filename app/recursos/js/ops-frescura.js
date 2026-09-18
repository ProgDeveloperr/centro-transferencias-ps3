(() => {
    'use strict';

    const obtener = (id) =>
        document.getElementById(id);

    const normalizarSegundos = (
        valor
    ) => {
        const n = Number(valor);

        if (!Number.isFinite(n)) {
            return null;
        }

        return Math.max(
            0,
            Math.round(n)
        );
    };

    const relativo = (
        segundos
    ) => {
        const s =
            normalizarSegundos(
                segundos
            );

        if (s === null) {
            return 'sin antigüedad conocida';
        }

        if (s < 60) {
            return `hace ${s} s`;
        }

        const minutos =
            Math.floor(s / 60);

        if (minutos < 60) {
            return `hace ${minutos} min`;
        }

        const horas =
            Math.floor(
                minutos / 60
            );

        if (horas < 24) {
            const restoMin =
                minutos % 60;

            return restoMin > 0
                ? `hace ${horas} h ${restoMin} min`
                : `hace ${horas} h`;
        }

        const dias =
            Math.floor(
                horas / 24
            );

        const restoHoras =
            horas % 24;

        return restoHoras > 0
            ? `hace ${dias} d ${restoHoras} h`
            : `hace ${dias} d`;
    };

    const fecha = (
        valor
    ) => {
        if (!valor) {
            return '—';
        }

        const d =
            new Date(valor);

        if (
            Number.isNaN(
                d.getTime()
            )
        ) {
            return String(valor);
        }

        return d.toLocaleString(
            'es-AR',
            {
                dateStyle: 'short',
                timeStyle: 'short',
            }
        );
    };

    const segundosDesde = (
        valor
    ) => {
        if (!valor) {
            return null;
        }

        const d =
            new Date(valor);

        if (
            Number.isNaN(
                d.getTime()
            )
        ) {
            return null;
        }

        return Math.max(
            0,
            (
                Date.now()
                - d.getTime()
            ) / 1000
        );
    };

    const crearIndicador = (
        id,
        referencia
    ) => {
        let nodo =
            obtener(id);

        if (nodo) {
            return nodo;
        }

        nodo =
            document.createElement(
                'span'
            );

        nodo.id = id;
        nodo.className =
            'ops-frescura';

        referencia.insertAdjacentElement(
            'afterend',
            nodo
        );

        return nodo;
    };

    const aplicarEstado = (
        nodo,
        estado,
        texto
    ) => {
        nodo.className =
            (
                'ops-frescura '
                + 'ops-frescura--'
                + estado
            );

        nodo.textContent =
            texto;
    };

    const estadoHdd = (
        almacenamiento
    ) => {
        if (
            !almacenamiento
            || almacenamiento.disponible
                !== true
            || !almacenamiento
                .ultima_lectura_ok_utc
        ) {
            return {
                estado:
                    'no-disponible',
                texto:
                    'NO DISPONIBLE · sin lectura válida',
            };
        }

        const antiguedad =
            almacenamiento
                .antiguedad_segundos;

        if (
            almacenamiento.fresca
            === true
        ) {
            return {
                estado:
                    'actualizado',
                texto:
                    (
                        'ACTUALIZADO · '
                        + relativo(
                            antiguedad
                        )
                    ),
            };
        }

        return {
            estado:
                'antiguo',
            texto:
                (
                    'ANTIGUO · última lectura '
                    + relativo(
                        antiguedad
                    )
                ),
        };
    };

    const cargarResumen =
        async () => {
            const detalle =
                obtener(
                    'metricaHddPs3Detalle'
                );

            if (!detalle) {
                return;
            }

            const indicador =
                crearIndicador(
                    'opsFrescuraResumenHdd',
                    detalle
                );

            aplicarEstado(
                indicador,
                'neutral',
                'VIGENCIA · consultando'
            );

            try {
                const r =
                    await fetch(
                        'api/ps3.php',
                        {
                            method: 'GET',
                            cache: 'no-store',
                            headers: {
                                Accept:
                                    'application/json',
                            },
                        }
                    );

                const d =
                    await r.json();

                if (
                    !r.ok
                    || d?.ok !== true
                ) {
                    throw new Error(
                        'API PS3 no disponible'
                    );
                }

                const resultado =
                    estadoHdd(
                        d.ps3
                            ?.almacenamiento
                    );

                aplicarEstado(
                    indicador,
                    resultado.estado,
                    resultado.texto
                );
            } catch (_) {
                aplicarEstado(
                    indicador,
                    'no-disponible',
                    'NO DISPONIBLE · no se pudo verificar vigencia'
                );
            }
        };

    const cargarAlmacenamiento =
        async () => {
            const detalle =
                obtener(
                    'almLibreDetalle'
                );

            const actualizado =
                obtener(
                    'almActualizado'
                );

            if (
                !detalle
                && !actualizado
            ) {
                return;
            }

            let indicadorHdd = null;
            let indicadorInv = null;

            if (detalle) {
                indicadorHdd =
                    crearIndicador(
                        'opsFrescuraAlmHdd',
                        detalle
                    );

                aplicarEstado(
                    indicadorHdd,
                    'neutral',
                    'VIGENCIA · consultando'
                );
            }

            if (actualizado) {
                indicadorInv =
                    crearIndicador(
                        'opsFrescuraInventario',
                        actualizado
                    );

                aplicarEstado(
                    indicadorInv,
                    'neutral',
                    'INVENTARIO · consultando última ejecución correcta'
                );
            }

            try {
                const r =
                    await fetch(
                        'api/almacenamiento.php',
                        {
                            method: 'GET',
                            cache: 'no-store',
                            headers: {
                                Accept:
                                    'application/json',
                            },
                        }
                    );

                const d =
                    await r.json();

                if (
                    !r.ok
                    || d?.ok !== true
                ) {
                    throw new Error(
                        'API almacenamiento no disponible'
                    );
                }

                if (indicadorHdd) {
                    const resultado =
                        estadoHdd(
                            d.ps3
                                ?.espacio_libre
                        );

                    aplicarEstado(
                        indicadorHdd,
                        resultado.estado,
                        resultado.texto
                    );
                }

                if (indicadorInv) {
                    const ultima =
                        d.inventario
                            ?.ultima_ok_utc;

                    if (ultima) {
                        const edad =
                            segundosDesde(
                                ultima
                            );

                        aplicarEstado(
                            indicadorInv,
                            'neutral',
                            (
                                'ÚLTIMO INVENTARIO CORRECTO · '
                                + fecha(
                                    ultima
                                )
                                + ' · '
                                + relativo(
                                    edad
                                )
                            )
                        );
                    } else {
                        aplicarEstado(
                            indicadorInv,
                            'no-disponible',
                            'INVENTARIO · sin ejecución correcta registrada'
                        );
                    }
                }
            } catch (_) {
                if (indicadorHdd) {
                    aplicarEstado(
                        indicadorHdd,
                        'no-disponible',
                        'NO DISPONIBLE · no se pudo verificar vigencia'
                    );
                }

                if (indicadorInv) {
                    aplicarEstado(
                        indicadorInv,
                        'no-disponible',
                        'INVENTARIO · no se pudo consultar vigencia'
                    );
                }
            }
        };

    const iniciar = () => {
        cargarResumen();
        cargarAlmacenamiento();
    };

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
