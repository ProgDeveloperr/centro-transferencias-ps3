(() => {
    'use strict';

    const raiz =
        document.getElementById(
            'opsEstadoCtps3'
        );

    if (!raiz) {
        return;
    }

    const $ = (selector) =>
        raiz.querySelector(selector);

    const texto = (
        selector,
        valor,
        fallback = '—'
    ) => {
        const nodo = $(selector);

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

    const bytes = (valor) => {
        const n = Number(valor);

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

    const estadoTimer = (timer) => {
        if (!timer) {
            return 'SIN DATOS';
        }

        const enabled =
            timer?.enabled?.ok === true;

        const active =
            timer?.active?.ok === true;

        if (enabled && active) {
            return 'ACTIVO';
        }

        if (enabled || active) {
            return 'REVISAR';
        }

        return 'INACTIVO';
    };

    const aplicarEstado = (estado) => {
        const badge =
            $('[data-ops="estado"]');

        if (!badge) {
            return;
        }

        badge.textContent = estado;

        badge.classList.remove(
            'ops-estado__badge--ok',
            'ops-estado__badge--warn',
            'ops-estado__badge--fail'
        );

        if (estado === 'SALUDABLE') {
            badge.classList.add(
                'ops-estado__badge--ok'
            );
        } else if (
            estado === 'REVISAR'
            || estado === 'ADVERTENCIA'
        ) {
            badge.classList.add(
                'ops-estado__badge--warn'
            );
        } else {
            badge.classList.add(
                'ops-estado__badge--fail'
            );
        }
    };

    const render = (datos) => {
        const auditoria =
            datos.auditoria || {};

        const release =
            datos.release || {};

        const backup =
            datos.backup || {};

        const timers =
            datos.timers || {};

        const ps3 =
            datos.ps3 || {};

        aplicarEstado(
            auditoria.estado_general
            || 'DESCONOCIDO'
        );

        texto(
            '[data-ops="audit-pass"]',
            auditoria.pass
        );

        texto(
            '[data-ops="audit-warn"]',
            auditoria.warn
        );

        texto(
            '[data-ops="audit-fail"]',
            auditoria.fail
        );

        texto(
            '[data-ops="audit-fecha"]',
            fecha(
                auditoria.fecha
            )
        );

        texto(
            '[data-ops="auditor-version"]',
            auditoria.auditor_version
        );

        texto(
            '[data-ops="release"]',
            release.nombre
        );

        texto(
            '[data-ops="release-fecha"]',
            fecha(
                release.fecha_utc
            )
        );

        texto(
            '[data-ops="schema"]',
            release.schema_version
        );

        texto(
            '[data-ops="integrity"]',
            release.integrity_check
                === 'ok'
                ? 'OK'
                : release.integrity_check
        );

        texto(
            '[data-ops="fk"]',
            release.foreign_key_check
        );

        texto(
            '[data-ops="backup-fecha"]',
            fecha(
                backup.fecha_utc
            )
        );

        texto(
            '[data-ops="backup-files"]',
            backup.archivos_payload
        );

        texto(
            '[data-ops="backup-bytes"]',
            bytes(
                backup.bytes_payload
            )
        );

        texto(
            '[data-ops="timer-inventario"]',
            estadoTimer(
                timers[
                    'ctps3-inventory.timer'
                ]
            )
        );

        texto(
            '[data-ops="timer-catalogo"]',
            estadoTimer(
                timers[
                    'ctps3-catalog.timer'
                ]
            )
        );

        texto(
            '[data-ops="ps3-audit"]',
            ps3.requerida_para_auditoria
                ? 'REQUERIDA'
                : 'NO REQUERIDA'
        );

        texto(
            '[data-ops="e2e"]',
            ps3.eliminacion_real_e2e
        );

        texto(
            '[data-ops="generado"]',
            fecha(
                datos.generado_utc
            )
        );

        const cargando =
            $('[data-ops="cargando"]');

        if (cargando) {
            cargando.hidden = true;
        }

        const contenido =
            $('[data-ops="contenido"]');

        if (contenido) {
            contenido.hidden = false;
        }
    };

    const error = (mensaje) => {
        aplicarEstado(
            'NO DISPONIBLE'
        );

        const cargando =
            $('[data-ops="cargando"]');

        if (cargando) {
            cargando.hidden = true;
        }

        const errorNodo =
            $('[data-ops="error"]');

        if (errorNodo) {
            errorNodo.hidden = false;
            errorNodo.textContent =
                mensaje;
        }
    };

    const cargar = async () => {
        const boton =
            $('[data-ops="actualizar"]');

        if (boton) {
            boton.disabled = true;
        }

        try {
            const respuesta =
                await fetch(
                    'api/ops-estado.php',
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

            render(
                datos
            );
        } catch (e) {
            error(
                'No se pudo leer el '
                + 'último estado consolidado: '
                + (
                    e?.message
                    || 'error desconocido'
                )
            );
        } finally {
            if (boton) {
                boton.disabled = false;
            }
        }
    };

    $('[data-ops="actualizar"]')
        ?.addEventListener(
            'click',
            cargar
        );

    cargar();
})();
