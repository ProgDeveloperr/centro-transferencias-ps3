(() => {
    'use strict';

    const raiz =
        document.getElementById(
            'opsHistorialAuditorias'
        );

    if (!raiz) {
        return;
    }

    const cuerpo =
        raiz.querySelector(
            '[data-ops-historial="filas"]'
        );

    const estado =
        raiz.querySelector(
            '[data-ops-historial="estado"]'
        );

    const total =
        raiz.querySelector(
            '[data-ops-historial="total"]'
        );

    const saludables =
        raiz.querySelector(
            '[data-ops-historial="saludables"]'
        );

    const incidencias =
        raiz.querySelector(
            '[data-ops-historial="incidencias"]'
        );

    const fecha = (valor) => {
        if (!valor) {
            return '—';
        }

        const d = new Date(valor);

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
                timeStyle: 'medium',
            }
        );
    };

    const celda = (
        fila,
        contenido,
        clase = ''
    ) => {
        const td =
            document.createElement('td');

        td.textContent =
            contenido ?? '—';

        if (clase) {
            td.className = clase;
        }

        fila.appendChild(td);
    };

    const badge = (
        fila,
        valor
    ) => {
        const td =
            document.createElement('td');

        const span =
            document.createElement('span');

        span.className =
            'ops-historial__estado '
            + (
                valor === 'SALUDABLE'
                    ? 'ops-historial__estado--ok'
                    : 'ops-historial__estado--alerta'
            );

        span.textContent = valor;

        td.appendChild(span);
        fila.appendChild(td);
    };

    const render = (datos) => {
        const lista =
            Array.isArray(
                datos.auditorias
            )
                ? datos.auditorias.slice(0, 10)
                : [];

        cuerpo.replaceChildren();

        for (const item of lista) {
            const tr =
                document.createElement('tr');

            celda(
                tr,
                fecha(item.fecha)
            );

            badge(
                tr,
                item.estado_general
                || 'DESCONOCIDO'
            );

            celda(
                tr,
                item.pass,
                'ops-historial__numero'
            );

            celda(
                tr,
                item.warn,
                'ops-historial__numero'
            );

            celda(
                tr,
                item.fail,
                'ops-historial__numero'
            );

            celda(
                tr,
                item.auditor_version
            );

            celda(
                tr,
                item.referencia
            );

            cuerpo.appendChild(tr);
        }

        if (lista.length === 0) {
            const tr =
                document.createElement('tr');

            const td =
                document.createElement('td');

            td.colSpan = 7;
            td.className =
                'ops-historial__vacio';

            td.textContent =
                'No hay auditorías registradas.';

            tr.appendChild(td);
            cuerpo.appendChild(tr);
        }

        total.textContent =
            datos.resumen?.total ?? 0;

        saludables.textContent =
            datos.resumen?.saludables ?? 0;

        incidencias.textContent =
            (
                Number(
                    datos.resumen?.con_warn
                    ?? 0
                )
                + Number(
                    datos.resumen?.con_fail
                    ?? 0
                )
            );

        estado.textContent =
            'Últimas '
            + lista.length
            + ' de '
            + (
                datos.resumen?.total
                ?? lista.length
            );
    };

    const cargar = async () => {
        try {
            const respuesta =
                await fetch(
                    'api/ops-historial.php',
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
            estado.textContent =
                'No disponible';

            cuerpo.replaceChildren();

            const tr =
                document.createElement('tr');

            const td =
                document.createElement('td');

            td.colSpan = 7;
            td.className =
                'ops-historial__vacio';

            td.textContent =
                'No se pudo leer el historial: '
                + (
                    e?.message
                    || 'error desconocido'
                );

            tr.appendChild(td);
            cuerpo.appendChild(tr);
        }
    };

    cargar();
})();
