(() => {
    'use strict';


    const $ = (id) =>
        document.getElementById(id);


    const escapar = (valor) =>
        String(
            valor ?? ''
        )
            .replaceAll(
                '&',
                '&amp;'
            )
            .replaceAll(
                '<',
                '&lt;'
            )
            .replaceAll(
                '>',
                '&gt;'
            )
            .replaceAll(
                '"',
                '&quot;'
            )
            .replaceAll(
                "'",
                '&#039;'
            );


    const bytesHumanos = (valor) => {
        let numero =
            Number(valor || 0);

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

        const decimales =
            indice === 0
                ? 0
                : (
                    numero >= 100
                        ? 1
                        : 2
                );

        return (
            `${numero.toFixed(decimales)} `
            + unidades[indice]
        );
    };


    const velocidadHumana = (valor) =>
        `${bytesHumanos(valor)}/s`;


    const tiempoHumano = (valor) => {
        const segundos =
            Math.max(
                0,
                Number(valor || 0)
            );

        if (segundos < 60) {
            return `${segundos.toFixed(1)} s`;
        }

        if (segundos < 3600) {
            const minutos =
                Math.floor(
                    segundos / 60
                );

            const resto =
                Math.round(
                    segundos % 60
                );

            return `${minutos}m ${resto}s`;
        }

        const horas =
            Math.floor(
                segundos / 3600
            );

        const minutos =
            Math.floor(
                (
                    segundos % 3600
                )
                / 60
            );

        return `${horas}h ${minutos}m`;
    };


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


    const solicitar = async () => {
        const respuesta =
            await fetch(
                'api/estadisticas-ftp.php',
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

        return datos;
    };


    const renderTransferencias = (
        transferencias
    ) => {

        const contenedor =
            $('telemetriaFtpTransferencias');

        if (!contenedor) {
            return;
        }

        if (
            !Array.isArray(
                transferencias
            )
            || transferencias.length === 0
        ) {
            contenedor.innerHTML = `
                <div class="telemetria-ftp__vacio">
                    Todavía no existen transferencias
                    reales posteriores a la activación
                    de la telemetría 8B.
                </div>
            `;

            return;
        }


        contenedor.innerHTML =
            transferencias
                .map(
                    (item) => {

                        const sesiones =
                            Number(
                                item.sesiones_ftp
                                || 0
                            );

                        const reanudadas =
                            Number(
                                item.sesiones_reanudadas
                                || 0
                            );

                        return `
                            <div class="telemetria-ftp__fila">

                                <div class="telemetria-ftp__fila-superior">

                                    <div
                                        class="telemetria-ftp__nombre"
                                        title="${escapar(
                                            item.nombre_snapshot
                                        )}"
                                    >
                                        #${item.id}
                                        ·
                                        ${escapar(
                                            item.nombre_snapshot
                                        )}
                                    </div>

                                    <span class="telemetria-ftp__estado">
                                        ${escapar(
                                            item.estado
                                        )}
                                    </span>

                                </div>

                                <div class="telemetria-ftp__datos">

                                    <span>
                                        FTP:
                                        <strong>
                                            ${bytesHumanos(
                                                item.bytes_ftp
                                            )}
                                        </strong>
                                    </span>

                                    <span>
                                        Validado:
                                        <strong>
                                            ${bytesHumanos(
                                                (
                                                    item.estado
                                                        === 'COMPLETADO'
                                                    || item.estado
                                                        === 'YA_EXISTE'
                                                )
                                                    ? item.tamano_total
                                                    : 0
                                            )}
                                        </strong>
                                    </span>

                                    <span>
                                        Reutilizado:
                                        <strong>
                                            ${bytesHumanos(
                                                item.bytes_reutilizados
                                            )}
                                        </strong>
                                    </span>

                                    <span>
                                        Sesiones:
                                        <strong>
                                            ${sesiones}
                                        </strong>
                                    </span>

                                    ${
                                        reanudadas > 0
                                            ? `
                                            <span>
                                                Reanudadas:
                                                <strong>
                                                    ${reanudadas}
                                                </strong>
                                            </span>
                                            `
                                            : ''
                                    }

                                    <span>
                                        ${fechaHumana(
                                            item.finalizada_utc
                                            || item.actualizada_utc
                                        )}
                                    </span>

                                </div>

                            </div>
                        `;
                    }
                )
                .join('');
    };


    const renderSesiones = (
        sesiones
    ) => {

        const contenedor =
            $('telemetriaFtpSesiones');

        if (!contenedor) {
            return;
        }

        if (
            !Array.isArray(
                sesiones
            )
            || sesiones.length === 0
        ) {
            contenedor.innerHTML = `
                <div class="telemetria-ftp__vacio">
                    Aún no hay sesiones FTP
                    reales conservadas en el historial.
                </div>
            `;

            return;
        }


        contenedor.innerHTML =
            sesiones
                .map(
                    (sesion) => `
                        <div class="telemetria-ftp__fila">

                            <div class="telemetria-ftp__fila-superior">

                                <div
                                    class="telemetria-ftp__nombre"
                                    title="${escapar(
                                        sesion.nombre_snapshot
                                    )}"
                                >
                                    Sesión
                                    #${sesion.id}
                                    · Transferencia
                                    #${sesion.transferencia_id}
                                </div>

                                <span class="telemetria-ftp__estado">
                                    ${escapar(
                                        sesion.resultado
                                    )}
                                </span>

                            </div>

                            <div class="telemetria-ftp__datos">

                                <span>
                                    Enviado:
                                    <strong>
                                        ${bytesHumanos(
                                            sesion.bytes_ftp
                                        )}
                                    </strong>
                                </span>

                                <span>
                                    ${bytesHumanos(
                                        sesion.bytes_remotos_inicio
                                    )}
                                    →
                                    ${bytesHumanos(
                                        sesion.bytes_remotos_fin
                                    )}
                                </span>

                                <span>
                                    Media:
                                    <strong>
                                        ${velocidadHumana(
                                            sesion.velocidad_media_bps
                                        )}
                                    </strong>
                                </span>

                                <span>
                                    Duración:
                                    <strong>
                                        ${tiempoHumano(
                                            sesion.duracion_segundos
                                        )}
                                    </strong>
                                </span>

                                ${
                                    sesion.reanudacion
                                        ? `
                                        <span>
                                            Reanudación:
                                            <strong>
                                                sí
                                            </strong>
                                        </span>
                                        `
                                        : ''
                                }

                                <span>
                                    ${fechaHumana(
                                        sesion.finalizada_utc
                                        || sesion.iniciada_utc
                                    )}
                                </span>

                            </div>

                        </div>
                    `
                )
                .join('');
    };


    const render = (datos) => {
        const resumen =
            datos.resumen || {};


        $('telemetriaFtpDesde').textContent =
            `Desde ${fechaHumana(
                datos.desde_utc
            )}`;


        $('telemetriaFtpVersion').textContent =
            `Motor ${datos.telemetria_version}`;


        $('telemetriaFtpBytes').textContent =
            bytesHumanos(
                resumen.bytes_ftp
            );


        $('telemetriaFtpValidados').textContent =
            bytesHumanos(
                resumen.bytes_validados
            );


        $('telemetriaFtpReutilizados').textContent =
            bytesHumanos(
                resumen.bytes_reutilizados
            );


        $('telemetriaFtpReutilizadosDetalle')
            .textContent =
                resumen.porcentaje_reutilizado
                    !== null
                    && resumen.porcentaje_reutilizado
                        !== undefined
                    ? (
                        `${Number(
                            resumen.porcentaje_reutilizado
                        ).toFixed(1)}% `
                        + 'del volumen validado'
                    )
                    : 'Sin volumen validado todavía';


        $('telemetriaFtpVelocidad').textContent =
            velocidadHumana(
                resumen.velocidad_media_bps
            );


        $('telemetriaFtpSesionesTotal').textContent =
            String(
                resumen.sesiones_ftp
                || 0
            );


        $('telemetriaFtpReanudadas').textContent =
            String(
                resumen.sesiones_reanudadas
                || 0
            );


        $('telemetriaFtpTiempo').textContent =
            tiempoHumano(
                resumen.duracion_ftp_segundos
            );


        $('telemetriaFtpNoValidado').textContent =
            bytesHumanos(
                resumen.bytes_ftp_no_validados
            );


        $('telemetriaFtpErrores').textContent =
            String(
                (
                    Number(
                        resumen.sesiones_error
                        || 0
                    )
                    + Number(
                        resumen.sesiones_incompletas
                        || 0
                    )
                )
            );


        $('telemetriaFtpTransferenciasTotal')
            .textContent =
                String(
                    resumen.transferencias_periodo
                    || 0
                );


        renderTransferencias(
            datos.transferencias
        );

        renderSesiones(
            datos.sesiones
        );


        const panel =
            $('telemetriaFtpPanel');

        if (panel) {
            panel.classList.remove(
                'telemetria-ftp__actualizando'
            );
        }
    };


    const error = (mensaje) => {
        const contenedores = [
            $('telemetriaFtpTransferencias'),
            $('telemetriaFtpSesiones'),
        ];

        for (
            const contenedor
            of contenedores
        ) {
            if (!contenedor) {
                continue;
            }

            contenedor.innerHTML = `
                <div class="telemetria-ftp__vacio">
                    No se pudo consultar la telemetría FTP:
                    ${escapar(mensaje)}
                </div>
            `;
        }
    };


    const actualizar = async () => {
        try {
            const panel =
                $('telemetriaFtpPanel');

            if (!panel) {
                return;
            }

            panel.classList.add(
                'telemetria-ftp__actualizando'
            );

            const datos =
                await solicitar();

            render(datos);

        } catch (excepcion) {

            const panel =
                $('telemetriaFtpPanel');

            if (panel) {
                panel.classList.remove(
                    'telemetria-ftp__actualizando'
                );
            }

            error(
                excepcion.message
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
