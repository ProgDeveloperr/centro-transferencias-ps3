'use strict';

const mapaEstadoPs3 = {
    COMPLETO: [
        'EN PS3',
        'estado-ps3--completo',
    ],

    PARCIAL: [
        'PARCIAL',
        'estado-ps3--parcial',
    ],

    AUSENTE: [
        'FALTA',
        'estado-ps3--ausente',
    ],

    CONFLICTO: [
        'CONFLICTO',
        'estado-ps3--conflicto',
    ],
};


function estadoPs3Ui(estado) {
    return (
        mapaEstadoPs3[estado]
        || mapaEstadoPs3.AUSENTE
    );
}


function detallePs3Ui(archivo) {
    const estado =
        archivo.estado_ps3
        || 'AUSENTE';

    if (estado === 'COMPLETO') {
        return 'Copia completa verificada';
    }

    if (estado === 'PARCIAL') {
        return (
            `${bytes(
                archivo.remoto_tamano_bytes
            )} de ${bytes(
                archivo.tamano_bytes
            )} en PS3`
        );
    }

    if (estado === 'CONFLICTO') {
        return (
            `Remoto ${
                bytes(
                    archivo.remoto_tamano_bytes
                )
            } · local ${
                bytes(
                    archivo.tamano_bytes
                )
            }`
        );
    }

    return 'No está en la PS3';
}


async function encolarFaltantesPs3(
    ids,
    boton
) {
    const unicos = [
        ...new Set(
            ids
                .map(Number)
                .filter(
                    (id) =>
                        Number.isInteger(id)
                        && id > 0
                )
        ),
    ];

    if (!unicos.length) {
        return;
    }

    const texto =
        boton.textContent;

    boton.disabled = true;

    boton.textContent =
        'Agregando…';

    try {
        const datos = await post(
            'api/encolar.php',
            {
                ids: unicos,
            }
        );

        for (const id of unicos) {
            seleccionados.delete(id);
        }

        if (
            datos.agregadas.length
        ) {
            toast(
                datos.agregadas.length === 1
                    ? '1 faltante agregado a la cola.'
                    : (
                        `${datos.agregadas.length} `
                        + 'faltantes agregados a la cola.'
                    )
            );
        }

        if (
            datos.omitidas.length
        ) {
            toast(
                (
                    `${datos.omitidas.length} `
                    + 'archivo(s) fueron omitidos.'
                ),
                'error'
            );
        }

        await cargarTodo();

    } catch (error) {
        toast(
            (
                'No se pudo encolar: '
                + error.message
            ),
            'error'
        );

    } finally {
        boton.textContent =
            texto;

        actualizarSeleccion();
    }
}


function decorarArchivoPs3(
    input,
    archivo,
    activos
) {
    const id =
        Number(
            archivo.id
        );

    const fila =
        input.closest(
            '.archivo'
        );

    if (!fila) {
        return false;
    }

    const estado =
        archivo.estado_ps3
        || 'AUSENTE';

    const [
        etiqueta,
        clase,
    ] = estadoPs3Ui(
        estado
    );

    fila.classList.add(
        (
            'archivo--estado-'
            + estado.toLowerCase()
        )
    );


    const meta =
        fila.querySelector(
            '.archivo__meta'
        );

    if (meta) {
        const detalle =
            document.createElement(
                'span'
            );

        detalle.className =
            'archivo__remoto-v2';

        detalle.textContent =
            detallePs3Ui(
                archivo
            );

        meta.insertAdjacentElement(
            'afterend',
            detalle
        );
    }


    const lado =
        document.createElement(
            'div'
        );

    lado.className =
        'archivo__lado-v2';


    const badge =
        document.createElement(
            'span'
        );

    badge.className =
        `estado-ps3 ${clase}`;

    badge.textContent =
        etiqueta;

    lado.appendChild(
        badge
    );


    const tamano =
        fila.querySelector(
            '.archivo__tamano'
        );

    if (tamano) {
        lado.appendChild(
            tamano
        );
    }

    fila.appendChild(
        lado
    );


    if (
        [
            'COMPLETO',
            'CONFLICTO',
        ].includes(
            estado
        )
    ) {
        input.checked =
            false;

        input.disabled =
            true;

        input.hidden =
            true;

        const indicador =
            document.createElement(
                'span'
            );

        indicador.className =
            estado === 'COMPLETO'
                ? (
                    'archivo__check-v2 '
                    + 'archivo__check-v2--ok'
                )
                : (
                    'archivo__check-v2 '
                    + 'archivo__check-v2--error'
                );

        indicador.textContent =
            estado === 'COMPLETO'
                ? '✓'
                : '!';

        input.insertAdjacentElement(
            'beforebegin',
            indicador
        );

        return (
            seleccionados.delete(
                id
            )
        );
    }


    if (
        !activos.has(id)
    ) {
        input.disabled =
            false;
    }

    return false;
}


function decorarJuegosPs3(
    datosCatalogo,
    activos
) {
    /*
     * BIB-2C
     *
     * La tarjeta renderizada por Biblioteca
     * es la fuente de verdad del agrupamiento.
     *
     * No reconstruimos grupos mediante
     * codigo_juego/titulo_juego ni asociamos
     * tarjetas por posición.
     *
     * Cada tarjeta declara sus archivos
     * mediante input[data-archivo-id].
     */

    const archivosCatalogo =
        Array.isArray(
            datosCatalogo?.archivos
        )
            ? datosCatalogo.archivos
            : [];


    const porId =
        new Map(
            archivosCatalogo.map(
                (archivo) => [
                    Number(
                        archivo.id
                    ),
                    archivo,
                ]
            )
        );


    const tarjetas = [
        ...document.querySelectorAll(
            '#biblioteca .juego'
        ),
    ];


    for (const tarjeta of tarjetas) {

        /*
         * Defensa ante una segunda decoración
         * sobre el mismo DOM.
         */
        tarjeta
            .querySelector(
                '.juego__ps3-v2'
            )
            ?.remove();


        /*
         * El orden de estos inputs es el mismo
         * orden visual producido por app.js.
         *
         * Para Zuko:
         * 01GM -> 02PT -> 03DL.
         */
        const ids =
            [
                ...tarjeta
                    .querySelectorAll(
                        'input[data-archivo-id]'
                    ),
            ]
                .map(
                    (input) =>
                        Number(
                            input.dataset
                                .archivoId
                        )
                )
                .filter(
                    (
                        id,
                        indice,
                        lista
                    ) =>
                        Number.isInteger(id)
                        && id > 0
                        && lista.indexOf(id)
                            === indice
                );


        const archivos =
            ids
                .map(
                    (id) =>
                        porId.get(id)
                )
                .filter(
                    Boolean
                );


        /*
         * Una tarjeta sin archivos válidos
         * no recibe decoración ni acciones.
         */
        if (!archivos.length) {
            continue;
        }


        const completos =
            archivos.filter(
                (archivo) =>
                    archivo.estado_ps3
                    === 'COMPLETO'
            ).length;


        const conflictos =
            archivos.filter(
                (archivo) =>
                    archivo.estado_ps3
                    === 'CONFLICTO'
            ).length;


        /*
         * IMPORTANTE:
         *
         * archivos conserva el orden del DOM.
         * pendientes conserva ese mismo orden.
         * Por lo tanto "Enviar faltantes"
         * entrega a api/encolar.php los IDs
         * exactamente en secuencia visual.
         */
        const pendientes =
            archivos.filter(
                (archivo) =>
                    [
                        'AUSENTE',
                        'PARCIAL',
                    ].includes(
                        archivo.estado_ps3
                    )
                    && !activos.has(
                        Number(
                            archivo.id
                        )
                    )
            );


        const activosJuego =
            archivos.filter(
                (archivo) =>
                    activos.has(
                        Number(
                            archivo.id
                        )
                    )
            ).length;


        const bloque =
            document.createElement(
                'div'
            );

        bloque.className =
            'juego__ps3-v2';


        const contador =
            document.createElement(
                'span'
            );

        contador.className =
            completos === archivos.length
                ? (
                    'juego__ps3-contador '
                    + 'juego__ps3-contador--ok'
                )
                : 'juego__ps3-contador';

        contador.textContent =
            (
                `${completos}/`
                + `${archivos.length} en PS3`
            );


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


        if (
            pendientes.length
        ) {
            boton.textContent =
                'Enviar faltantes';

            boton.addEventListener(
                'click',
                () => {
                    encolarFaltantesPs3(
                        pendientes.map(
                            (archivo) =>
                                Number(
                                    archivo.id
                                )
                        ),
                        boton
                    );
                }
            );

        } else {

            boton.disabled =
                true;

            boton.textContent =
                completos === archivos.length
                    ? 'Completo en PS3'
                    : conflictos
                        ? 'Revisar conflicto'
                        : activosJuego
                            ? 'Transferencia en curso'
                            : 'Sin faltantes';
        }


        bloque.append(
            contador,
            boton
        );


        tarjeta
            .querySelector(
                '.juego__cabecera'
            )
            ?.appendChild(
                bloque
            );
    }
}

function decorarBibliotecaPs3(
    datosCatalogo
) {
    const porId =
        new Map(
            datosCatalogo
                .archivos
                .map(
                    (archivo) => [
                        Number(
                            archivo.id
                        ),
                        archivo,
                    ]
                )
        );


    const activos =
        activosPorArchivo();

    let cambioSeleccion =
        false;


    document
        .querySelectorAll(
            (
                '#biblioteca '
                + 'input[data-archivo-id]'
            )
        )
        .forEach(
            (input) => {
                const archivo =
                    porId.get(
                        Number(
                            input.dataset
                                .archivoId
                        )
                    );

                if (
                    archivo
                    && decorarArchivoPs3(
                        input,
                        archivo,
                        activos
                    )
                ) {
                    cambioSeleccion =
                        true;
                }
            }
        );


    decorarJuegosPs3(
        datosCatalogo,
        activos
    );


    if (
        cambioSeleccion
    ) {
        actualizarSeleccion();
    }
}


function renderInventarioPs3(
    datosPs3,
    datosCatalogo
) {
    const contenedor =
        $('inventarioPs3');

    const resumen =
        $('inventarioPs3Resumen');


    const locales =
        new Set(
            datosCatalogo
                .archivos
                .map(
                    (archivo) =>
                        archivo.nombre
                )
        );


    const remotos =
        Array.isArray(
            datosPs3.archivos
        )
            ? datosPs3.archivos
            : [];


    const exclusivos =
        remotos.filter(
            (archivo) =>
                !locales.has(
                    archivo.nombre
                )
        );


    const total =
        exclusivos.reduce(
            (
                suma,
                archivo
            ) =>
                suma
                + Number(
                    archivo.tamano_bytes
                ),
            0
        );


    resumen.textContent =
        (
            `${exclusivos.length} archivo`
            + (
                exclusivos.length === 1
                    ? ''
                    : 's'
            )
            + ` · ${bytes(total)}`
        );


    if (
        !exclusivos.length
    ) {
        contenedor.innerHTML =
            (
                '<div class="vacio vacio--ok">'
                + 'No hay PKG exclusivos en la PS3.'
                + '</div>'
            );

        return;
    }


    contenedor.innerHTML =
        exclusivos
            .map(
                (archivo) => `
                    <div class="remoto-v2">

                        <div class="remoto-v2__icono">
                            PS3
                        </div>

                        <div class="remoto-v2__contenido">

                            <div class="remoto-v2__nombre">
                                ${escapar(
                                    archivo.nombre
                                )}
                            </div>

                            <div class="remoto-v2__meta">
                                ${escapar(
                                    archivo.ruta_remota
                                )}
                            </div>

                        </div>

                        <span class="remoto-v2__tamano">
                            ${bytes(
                                archivo.tamano_bytes
                            )}
                        </span>

                    </div>
                `
            )
            .join('');
}


function configuracionEstadoPs3V3(
    ps3
) {
    const estado =
        ps3.estado_operativo
        || (
            ps3.conectado
                ? 'LISTA'
                : 'NO_DISPONIBLE'
        );

    if (estado === 'LISTA') {
        return {
            superior:
                'PS3 · LISTA',

            claseSuperior:
                'estado--ok',

            conexion:
                'PS3 lista para transferencias',

            pulso:
                'ps3-pulso--ok',

            nivel:
                'ok',
        };
    }

    if (
        estado
        === 'ENCENDIDA_SIN_WEBMAN'
    ) {
        return {
            superior:
                'PS3 · ENCENDIDA',

            claseSuperior:
                'estado--ps3-aviso',

            conexion:
                'HEN / webMAN no disponible',

            pulso:
                'ps3-pulso--aviso',

            nivel:
                'aviso',
        };
    }

    if (
        estado
        === 'TRANSITORIO'
    ) {
        return {
            superior:
                'PS3 · VERIFICANDO',

            claseSuperior:
                'estado--ps3-aviso',

            conexion:
                (
                    'Incidencia transitoria '
                    + `${ps3.fallos_consecutivos}`
                    + '/'
                    + `${ps3.umbral_fallos}`
                ),

            pulso:
                'ps3-pulso--aviso',

            nivel:
                'aviso',
        };
    }

    return {
        superior:
            'PS3 · NO DISPONIBLE',

        claseSuperior:
            'estado--error',

        conexion:
            'PS3 no disponible',

        pulso:
            'ps3-pulso--error',

        nivel:
            'error',
    };
}


function textoServiciosPs3V3(
    ps3
) {
    const ftp =
        ps3.ftp_disponible
            ? 'FTP 21 ✓'
            : 'FTP 21 ×';

    const http =
        ps3.http_disponible
            ? 'HTTP 80 ✓'
            : 'HTTP 80 ×';

    if (
        ps3.estado_operativo
        === 'LISTA'
        && ps3.banner
    ) {
        return (
            `${ps3.banner}`
            + ` · ${ftp}`
            + ` · ${http}`
        );
    }

    return (
        `${ftp}`
        + ` · ${http}`
    );
}


function mensajeEstadoPs3V3(
    ps3
) {
    const estado =
        ps3.estado_operativo;

    if (estado === 'LISTA') {
        return '';
    }

    if (estado === 'TRANSITORIO') {
        return (
            'Incidencia transitoria '
            + `${ps3.fallos_consecutivos}`
            + '/'
            + `${ps3.umbral_fallos}`
            + '. '
            + (
                ps3.detalle_estado
                || (
                    'El servicio será '
                    + 'declarado caído sólo '
                    + 'si el problema persiste.'
                )
            )
        );
    }

    if (
        estado
        === 'ENCENDIDA_SIN_WEBMAN'
    ) {
        return (
            'La consola responde en la red, '
            + 'pero HEN/webMAN/FTP no está '
            + 'disponible. Activá HEN para '
            + 'habilitar las transferencias.'
        );
    }

    return (
        ps3.detalle_estado
        || (
            'La consola no responde '
            + 'en los servicios supervisados.'
        )
    );
}


function renderPs3Inteligente(
    datosPs3,
    datosCatalogo
) {
    const ps3 =
        datosPs3.ps3;


    const configuracion =
        configuracionEstadoPs3V3(
            ps3
        );


    const superior =
        $('estadoPs3Superior');


    if (superior) {
        superior.textContent =
            configuracion.superior;

        superior.className =
            (
                'estado '
                + configuracion
                    .claseSuperior
            );
    }


    const conexion =
        $('ps3Conexion');


    if (conexion) {
        conexion.textContent =
            configuracion.conexion;
    }


    const host =
        $('ps3Host');


    if (host) {
        host.textContent =
            `${ps3.host}:${ps3.puerto}`;
    }


    const banner =
        $('ps3Banner');


    if (banner) {
        banner.textContent =
            textoServiciosPs3V3(
                ps3
            );
    }


    const ruta =
        $('ps3Ruta');


    if (ruta) {
        ruta.textContent =
            ps3.ruta_packages
            || '—';
    }


    const ultima =
        $('ps3Ultima');


    if (ultima) {
        ultima.textContent =
            ps3.ultima_consulta_utc
                ? (
                    `${fecha(
                        ps3.ultima_consulta_utc
                    )}`
                    + (
                        ps3.duracion_consulta_ms
                        !== null
                            ? (
                                ` · ${
                                    ps3.duracion_consulta_ms
                                } ms`
                            )
                            : ''
                    )
                )
                : '—';
    }


    const pulso =
        $('ps3Pulso');


    if (pulso) {
        pulso.className =
            (
                'ps3-pulso '
                + configuracion.pulso
            );
    }


    const aviso =
        $('ps3Error');


    if (aviso) {
        const mensaje =
            mensajeEstadoPs3V3(
                ps3
            );


        aviso.classList.remove(
            'ps3-resumen__error--aviso',
            'ps3-resumen__error--error'
        );


        if (mensaje) {

            aviso.textContent =
                mensaje;

            aviso.classList.remove(
                'ps3-resumen__error--oculto'
            );

            aviso.classList.add(
                configuracion.nivel
                    === 'error'
                    ? 'ps3-resumen__error--error'
                    : 'ps3-resumen__error--aviso'
            );

        } else {

            aviso.textContent =
                '';

            aviso.classList.add(
                'ps3-resumen__error--oculto'
            );
        }
    }


    const completos =
        Number(
            datosCatalogo
                .resumen
                .ps3
                .COMPLETO
            || 0
        );


    const locales =
        Number(
            datosCatalogo
                .resumen
                .archivos
            || 0
        );


    const metricaEnPs3 =
        $('metricaEnPs3');


    if (metricaEnPs3) {
        metricaEnPs3.textContent =
            `${completos}/${locales}`;
    }


    const detalle =
        $('metricaEnPs3Detalle');


    if (detalle) {
        detalle.textContent =
            completos === locales
            && locales > 0
                ? (
                    ps3.inventario_actual
                        ? 'biblioteca local completa'
                        : 'según último inventario válido'
                )
                : (
                    ps3.inventario_actual
                        ? 'de la biblioteca local'
                        : 'según último inventario válido'
                );
    }


    /*
     * ALM-4C2
     *
     * El valor proviene de webMAN y es
     * aproximado. No se representa porcentaje
     * ni barra porque no disponemos de una
     * capacidad total fiable de la PS3.
     */
    const almacenamiento =
        (
            ps3.almacenamiento
            && typeof ps3.almacenamiento
                === 'object'
        )
            ? ps3.almacenamiento
            : null;


    const metricaHddPs3 =
        $('metricaHddPs3');


    if (metricaHddPs3) {
        metricaHddPs3.textContent =
            (
                almacenamiento
                && almacenamiento.disponible
                && almacenamiento.libre_texto
            )
                ? almacenamiento.libre_texto
                : '—';

        metricaHddPs3.title =
            (
                almacenamiento
                && almacenamiento.fuente
            )
                ? (
                    'Valor aproximado · '
                    + almacenamiento.fuente
                )
                : 'Valor aproximado reportado por la PS3';
    }


    const metricaHddPs3Detalle =
        $('metricaHddPs3Detalle');


    if (metricaHddPs3Detalle) {
        if (
            !almacenamiento
            || !almacenamiento.disponible
        ) {
            metricaHddPs3Detalle.textContent =
                'sin lectura disponible';

        } else if (
            almacenamiento.fresca
        ) {
            metricaHddPs3Detalle.textContent =
                'aprox. · lectura actual · webMAN';

        } else if (
            almacenamiento
                .ultima_lectura_ok_utc
        ) {
            metricaHddPs3Detalle.textContent =
                (
                    'aprox. · última lectura válida · '
                    + fecha(
                        almacenamiento
                            .ultima_lectura_ok_utc
                    )
                );

        } else {
            metricaHddPs3Detalle.textContent =
                'aprox. · lectura no verificable';
        }
    }


    const remotos =
        $('metricaRemotos');


    if (remotos) {
        remotos.textContent =
            String(
                ps3.paquetes_remotos
                ?? '—'
            );
    }


    if ($('biblioteca')) {
        decorarBibliotecaPs3(
            datosCatalogo
        );
    }


    if (
        $('inventarioPs3')
        && $('inventarioPs3Resumen')
    ) {
        renderInventarioPs3(
            datosPs3,
            datosCatalogo
        );
    }


    if (
        !ps3.inventario_actual
        && $('inventarioPs3Resumen')
    ) {
        const resumen =
            $('inventarioPs3Resumen');


        if (
            resumen
            && !resumen.textContent
                .includes(
                    'último inventario válido'
                )
        ) {
            resumen.textContent +=
                ' · último inventario válido';
        }
    }
}
