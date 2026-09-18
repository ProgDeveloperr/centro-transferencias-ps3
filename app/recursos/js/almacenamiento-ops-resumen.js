(() => {
    'use strict';

    const raiz =
        document.getElementById(
            'almResumenOperativo'
        );

    if (!raiz) {
        return;
    }

    const obtener =
        (selector) =>
            raiz.querySelector(selector);

    const poner = (
        selector,
        valor,
        fallback = '—'
    ) => {
        const nodo =
            obtener(selector);

        if (!nodo) {
            return;
        }

        nodo.textContent =
            valor === null
            || valor === undefined
            || valor === ''
                ? fallback
                : String(valor);
    };

    const bytes = (valor) => {
        const n =
            Number(valor);

        if (
            !Number.isFinite(n)
            || n < 0
        ) {
            return '—';
        }

        const unidades = [
            'B',
            'KiB',
            'MiB',
            'GiB',
        ];

        let actual = n;
        let indice = 0;

        while (
            actual >= 1024
            && indice < unidades.length - 1
        ) {
            actual /= 1024;
            indice += 1;
        }

        return (
            actual.toLocaleString(
                'es-AR',
                {
                    maximumFractionDigits:
                        indice === 0
                            ? 0
                            : 2,
                }
            )
            + ' '
            + unidades[indice]
        );
    };

    const porcentaje = (
        parte,
        total
    ) => {
        const p =
            Number(parte);

        const t =
            Number(total);

        if (
            !Number.isFinite(p)
            || !Number.isFinite(t)
            || t <= 0
        ) {
            return '—';
        }

        return (
            (
                p * 100 / t
            ).toLocaleString(
                'es-AR',
                {
                    maximumFractionDigits: 1,
                }
            )
            + ' %'
        );
    };

    const porClase = (
        clases
    ) => {
        const mapa =
            new Map();

        for (
            const item
            of Array.isArray(clases)
                ? clases
                : []
        ) {
            mapa.set(
                item.clase,
                {
                    cantidad:
                        Number(
                            item.cantidad
                            || 0
                        ),
                    bytes:
                        Number(
                            item.bytes
                            || 0
                        ),
                }
            );
        }

        return mapa;
    };

    const sumar = (
        mapa,
        nombres
    ) => {
        return nombres.reduce(
            (acc, nombre) => {
                const item =
                    mapa.get(nombre)
                    || {
                        cantidad: 0,
                        bytes: 0,
                    };

                acc.cantidad +=
                    item.cantidad;

                acc.bytes +=
                    item.bytes;

                return acc;
            },
            {
                cantidad: 0,
                bytes: 0,
            }
        );
    };

    const render = (datos) => {
        const mapa =
            porClase(
                datos.clases
            );

        const totalBytes =
            Number(
                datos.resumen
                    ?.bytes_inventariados
                || 0
            );

        const principal =
            sumar(
                mapa,
                [
                    'JUEGO_INSTALADO',
                ]
            );

        const asociados =
            sumar(
                mapa,
                [
                    'VINCULADO',
                ]
            );

        const sistema =
            sumar(
                mapa,
                [
                    'STORE_APLICACION',
                    'HOMEBREW_UTILIDAD',
                    'SOPORTE_PS2',
                    'SISTEMA_PROTEGIDO',
                ]
            );

        const revision =
            sumar(
                mapa,
                [
                    'POSIBLE_HUERFANO',
                    'DESCONOCIDO',
                ]
            );

        poner(
            '[data-alm-ops="principal-cantidad"]',
            principal.cantidad
        );

        poner(
            '[data-alm-ops="principal-bytes"]',
            bytes(principal.bytes)
        );

        poner(
            '[data-alm-ops="principal-porcentaje"]',
            porcentaje(
                principal.bytes,
                totalBytes
            )
        );

        poner(
            '[data-alm-ops="asociados-cantidad"]',
            asociados.cantidad
        );

        poner(
            '[data-alm-ops="asociados-bytes"]',
            bytes(asociados.bytes)
        );

        poner(
            '[data-alm-ops="asociados-porcentaje"]',
            porcentaje(
                asociados.bytes,
                totalBytes
            )
        );

        poner(
            '[data-alm-ops="sistema-cantidad"]',
            sistema.cantidad
        );

        poner(
            '[data-alm-ops="sistema-bytes"]',
            bytes(sistema.bytes)
        );

        poner(
            '[data-alm-ops="sistema-porcentaje"]',
            porcentaje(
                sistema.bytes,
                totalBytes
            )
        );

        const pendientes =
            revision.cantidad;

        const autoBorrado =
            Number(
                datos.resumen
                    ?.borrado_automatico
                || 0
            );

        poner(
            '[data-alm-ops="revision-cantidad"]',
            pendientes
        );

        poner(
            '[data-alm-ops="revision-bytes"]',
            bytes(revision.bytes)
        );

        poner(
            '[data-alm-ops="auto-borrado"]',
            autoBorrado
        );

        const badge =
            obtener(
                '[data-alm-ops="revision-estado"]'
            );

        if (badge) {
            badge.textContent =
                pendientes === 0
                && autoBorrado === 0
                    ? 'SIN PENDIENTES'
                    : 'REVISAR';

            badge.classList.toggle(
                'alm-ops-resumen__estado--ok',
                pendientes === 0
                && autoBorrado === 0
            );

            badge.classList.toggle(
                'alm-ops-resumen__estado--alerta',
                pendientes > 0
                || autoBorrado > 0
            );
        }

        const cargando =
            obtener(
                '[data-alm-ops="cargando"]'
            );

        if (cargando) {
            cargando.hidden = true;
        }

        const contenido =
            obtener(
                '[data-alm-ops="contenido"]'
            );

        if (contenido) {
            contenido.hidden = false;
        }
    };

    const error = (
        mensaje
    ) => {
        const cargando =
            obtener(
                '[data-alm-ops="cargando"]'
            );

        if (cargando) {
            cargando.hidden = true;
        }

        const nodo =
            obtener(
                '[data-alm-ops="error"]'
            );

        if (nodo) {
            nodo.hidden = false;
            nodo.textContent = mensaje;
        }
    };

    const cargar =
        async () => {
            try {
                const respuesta =
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

                const datos =
                    await respuesta.json();

                if (
                    !respuesta.ok
                    || datos?.ok !== true
                ) {
                    throw new Error(
                        datos?.error
                        || (
                            'HTTP '
                            + respuesta.status
                        )
                    );
                }

                render(datos);
            } catch (e) {
                error(
                    'No se pudo construir '
                    + 'el resumen operativo: '
                    + (
                        e?.message
                        || 'error desconocido'
                    )
                );
            }
        };

    cargar();
})();
