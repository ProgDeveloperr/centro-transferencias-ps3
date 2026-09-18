(() => {
    'use strict';

    const LIMITE = 5;

    const configuraciones = [
        {
            id: 'telemetriaFtpTransferencias',
            etiqueta: 'transferencias',
        },
        {
            id: 'telemetriaFtpSesiones',
            etiqueta: 'sesiones',
        },
    ];

    const crearGestor = (
        configuracion
    ) => {
        const lista =
            document.getElementById(
                configuracion.id
            );

        if (!lista) {
            return;
        }

        let expandido = false;

        const control =
            document.createElement(
                'div'
            );

        control.className =
            'telemetria-lista-toggle';

        const boton =
            document.createElement(
                'button'
            );

        boton.type = 'button';

        boton.className =
            (
                'boton boton--secundario '
                + 'boton--mini '
                + 'telemetria-lista-toggle__boton'
            );

        boton.hidden = true;

        control.appendChild(
            boton
        );

        lista.insertAdjacentElement(
            'afterend',
            control
        );

        const filas = () =>
            Array.from(
                lista.children
            ).filter(
                (nodo) =>
                    nodo.classList
                        ?.contains(
                            'telemetria-ftp__fila'
                        )
            );

        const aplicar = () => {
            const actuales =
                filas();

            const total =
                actuales.length;

            actuales.forEach(
                (fila, indice) => {
                    fila.hidden =
                        !expandido
                        && indice >= LIMITE;
                }
            );

            if (total <= LIMITE) {
                expandido = false;
                boton.hidden = true;
                control.hidden = true;
                return;
            }

            control.hidden = false;
            boton.hidden = false;

            boton.textContent =
                expandido
                    ? 'Ver menos'
                    : (
                        'Ver todas ('
                        + total
                        + ')'
                    );

            boton.setAttribute(
                'aria-expanded',
                expandido
                    ? 'true'
                    : 'false'
            );

            boton.setAttribute(
                'aria-controls',
                configuracion.id
            );
        };

        boton.addEventListener(
            'click',
            () => {
                expandido =
                    !expandido;

                aplicar();

                if (!expandido) {
                    const panel =
                        lista.closest(
                            '.telemetria-ftp__subpanel'
                        );

                    panel?.scrollIntoView(
                        {
                            behavior: 'smooth',
                            block: 'nearest',
                        }
                    );
                }
            }
        );

        const observer =
            new MutationObserver(
                (mutaciones) => {
                    if (
                        mutaciones.some(
                            (m) =>
                                m.type
                                === 'childList'
                        )
                    ) {
                        aplicar();
                    }
                }
            );

        observer.observe(
            lista,
            {
                childList: true,
            }
        );

        aplicar();
    };

    const iniciar = () => {
        for (
            const configuracion
            of configuraciones
        ) {
            crearGestor(
                configuracion
            );
        }
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
