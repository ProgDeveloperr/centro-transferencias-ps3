(() => {
    'use strict';

    if (
        document.body?.dataset?.vista
        !== 'almacenamiento'
    ) {
        return;
    }

    const API =
        'api/almacenamiento.php';

    const estado = {
        datos: null,
        elementos: [],
    };

    const $ = (id) =>
        document.getElementById(id);

    const escapar = (valor) =>
        String(valor ?? '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');

    const bytes = (valor) => {
        const numero = Number(valor);

        if (!Number.isFinite(numero)) {
            return '—';
        }

        if (numero === 0) {
            return '0 B';
        }

        const unidades = [
            'B',
            'KiB',
            'MiB',
            'GiB',
            'TiB',
        ];

        const indice = Math.min(
            Math.floor(
                Math.log(numero)
                / Math.log(1024)
            ),
            unidades.length - 1
        );

        const cantidad =
            numero
            / Math.pow(
                1024,
                indice
            );

        const decimales =
            indice >= 3
                ? 2
                : indice >= 2
                    ? 1
                    : 0;

        return (
            cantidad.toFixed(decimales)
            + ' '
            + unidades[indice]
        );
    };

    const fecha = (valor) => {
        if (!valor) {
            return '—';
        }

        const fechaObj =
            new Date(valor);

        if (
            Number.isNaN(
                fechaObj.getTime()
            )
        ) {
            return String(valor);
        }

        return fechaObj.toLocaleString(
            'es-AR'
        );
    };

    const etiquetaClase = (clase) => {
        const mapa = {
            JUEGO_INSTALADO:
                'Juego instalado',

            VINCULADO:
                'Dato vinculado',

            STORE_APLICACION:
                'Store / aplicación',

            HOMEBREW_UTILIDAD:
                'Homebrew / utilidad',

            SOPORTE_PS2:
                'Soporte PS2',

            SISTEMA_PROTEGIDO:
                'Sistema protegido',

            POSIBLE_HUERFANO:
                'Posible huérfano',

            DESCONOCIDO:
                'Desconocido',
        };

        return (
            mapa[clase]
            ?? String(clase || '—')
        );
    };

    const etiquetaOrigen = (origen) =>
        origen === 'ESP_SUPLEMENTARIO'
            ? 'ESP suplementario'
            : origen === 'J3'
                ? 'J3'
                : String(origen || '—');

    const politicaLegible = (valor) =>
        String(valor || '')
            .split(';')
            .filter(Boolean)
            .map(
                (parte) =>
                    parte
                        .toLowerCase()
                        .replaceAll('_', ' ')
            )
            .join(' · ');

    const actualizarEstado = (
        texto,
        tipo
    ) => {
        const nodo = $('almEstado');

        if (!nodo) {
            return;
        }

        nodo.textContent =
            texto;

        nodo.className =
            'alm-estado'
            + (
                tipo
                    ? ` alm-estado--${tipo}`
                    : ''
            );
    };

    const renderResumen = () => {
        const datos =
            estado.datos;

        if (!datos) {
            return;
        }

        const libre =
            datos.ps3?.espacio_libre
            ?? {};

        $('almLibre').textContent =
            libre.texto
            || (
                libre.bytes_aprox != null
                    ? bytes(
                        libre.bytes_aprox
                    )
                    : 'No disponible'
            );

        const detallesLibre = [];

        if (libre.fuente) {
            detallesLibre.push(
                libre.fuente
            );
        }

        if (libre.fresca === false) {
            detallesLibre.push(
                'lectura no fresca'
            );
        }

        $('almLibreDetalle').textContent =
            detallesLibre.join(' · ')
            || 'telemetría webMAN';

        $('almInventariado').textContent =
            bytes(
                datos.resumen
                    ?.bytes_inventariados
            );

        $('almElementos').textContent =
            String(
                datos.resumen
                    ?.elementos
                ?? 0
            );

        $('almOrigenDetalle').textContent =
            (
                `${datos.resumen?.origen_j3 ?? 0} J3`
                + ' · '
                + `${datos.resumen?.origen_suplementario ?? 0} suplementarios`
            );

        $('almHuerfanos').textContent =
            String(
                datos.resumen
                    ?.posibles_huerfanos
                ?? 0
            );

        $('almActualizado').textContent =
            datos.inventario
                ?.ultima_ok_utc
                ? (
                    'Actualizado '
                    + fecha(
                        datos.inventario
                            .ultima_ok_utc
                    )
                )
                : 'Sin marca de actualización';

        const errorInventario =
            datos.inventario
                ?.ultimo_error;

        if (errorInventario) {
            actualizarEstado(
                'INVENTARIO CON ERROR',
                'alerta'
            );
        } else if (
            libre.fresca
            && datos.ps3?.conectado
        ) {
            actualizarEstado(
                'ACTUAL',
                'ok'
            );
        } else {
            actualizarEstado(
                'SNAPSHOT DISPONIBLE',
                'neutro'
            );
        }
    };

    const renderClases = () => {
        const contenedor =
            $('almClases');

        const clases =
            Array.isArray(
                estado.datos?.clases
            )
                ? estado.datos.clases
                : [];

        if (!clases.length) {
            contenedor.innerHTML =
                '<div class="alm-vacio">Sin clases disponibles.</div>';
            return;
        }

        contenedor.innerHTML =
            clases.map((item) => `
                <article class="alm-clase">
                    <div class="alm-clase__cabecera">
                        <strong>
                            ${escapar(
                                etiquetaClase(
                                    item.clase
                                )
                            )}
                        </strong>

                        <span>
                            ${escapar(
                                item.cantidad
                            )}
                        </span>
                    </div>

                    <div class="alm-clase__tamano">
                        ${escapar(
                            bytes(
                                item.bytes
                            )
                        )}
                    </div>

                    <small>
                        ${item.posibles_huerfanos
                            ? (
                                escapar(
                                    item.posibles_huerfanos
                                )
                                + ' posible(s) huérfano(s)'
                            )
                            : 'Sin candidatos huérfanos'}
                    </small>
                </article>
            `).join('');
    };

    const poblarFiltroClases = () => {
        const select =
            $('almFiltroClase');

        const clases =
            Array.isArray(
                estado.datos?.clases
            )
                ? estado.datos.clases
                : [];

        const actual =
            select.value;

        select.innerHTML =
            '<option value="">Todas</option>'
            + clases.map(
                (item) => `
                    <option value="${escapar(item.clase)}">
                        ${escapar(
                            etiquetaClase(
                                item.clase
                            )
                        )}
                    </option>
                `
            ).join('');

        if (
            [...select.options]
                .some(
                    (opcion) =>
                        opcion.value
                        === actual
                )
        ) {
            select.value =
                actual;
        }
    };

    const elementosFiltrados = () => {
        const termino =
            $('almBuscar').value
                .trim()
                .toLowerCase();

        const clase =
            $('almFiltroClase').value;

        const origen =
            $('almFiltroOrigen').value;

        const orden =
            $('almOrden').value;

        const filtrados =
            estado.elementos.filter(
                (item) => {
                    if (
                        clase
                        && item.clase
                            !== clase
                    ) {
                        return false;
                    }

                    if (
                        origen
                        && item.origen
                            !== origen
                    ) {
                        return false;
                    }

                    if (!termino) {
                        return true;
                    }

                    const bolsa = [
                        item.nombre_sfo,
                        item.nombre_directorio,
                        item.title_id_sfo,
                        item.ruta_remota,
                        item.clase,
                        item.subtipo,
                    ]
                        .filter(Boolean)
                        .join(' ')
                        .toLowerCase();

                    return bolsa.includes(
                        termino
                    );
                }
            );

        filtrados.sort(
            (a, b) => {
                if (
                    orden === 'tamano_asc'
                ) {
                    return (
                        Number(a.tamano_bytes)
                        - Number(b.tamano_bytes)
                    );
                }

                if (
                    orden === 'nombre_asc'
                ) {
                    return String(
                        a.nombre_sfo
                        || a.nombre_directorio
                    ).localeCompare(
                        String(
                            b.nombre_sfo
                            || b.nombre_directorio
                        ),
                        'es'
                    );
                }

                if (
                    orden === 'clase_asc'
                ) {
                    return String(
                        a.clase
                    ).localeCompare(
                        String(
                            b.clase
                        ),
                        'es'
                    );
                }

                return (
                    Number(b.tamano_bytes)
                    - Number(a.tamano_bytes)
                );
            }
        );

        return filtrados;
    };

    const renderLista = () => {
        const lista =
            $('almLista');

        const vacio =
            $('almVacio');

        const items =
            elementosFiltrados();

        $('almConteo').textContent =
            `${items.length} / ${estado.elementos.length}`;

        if (!items.length) {
            lista.innerHTML = '';
            vacio.hidden = false;
            return;
        }

        vacio.hidden = true;

        lista.innerHTML =
            items.map((item) => {
                const titulo =
                    item.nombre_sfo
                    || item.nombre_directorio;

                const titleId =
                    item.title_id_sfo
                    || 'Sin Title ID';

                const categoria =
                    item.categoria_sfo
                    || '—';

                const evidencia =
                    Array.isArray(
                        item.evidencia
                    )
                        ? item.evidencia
                        : [];

                return `
                    <tr>
                        <td>
                            <div class="alm-elemento">
                                <strong>
                                    ${escapar(titulo)}
                                </strong>

                                <span>
                                    ${escapar(titleId)}
                                    ·
                                    ${escapar(categoria)}
                                </span>

                                <code>
                                    ${escapar(
                                        item.ruta_remota
                                    )}
                                </code>

                                ${evidencia.length
                                    ? `
                                        <div class="alm-evidencia">
                                            ${evidencia.map(
                                                (valor) => `
                                                    <span>
                                                        ${escapar(
                                                            valor
                                                        )}
                                                    </span>
                                                `
                                            ).join('')}
                                        </div>
                                    `
                                    : ''}
                            </div>
                        </td>

                        <td>
                            <span class="alm-chip alm-chip--clase">
                                ${escapar(
                                    etiquetaClase(
                                        item.clase
                                    )
                                )}
                            </span>

                            ${item.subtipo
                                ? `
                                    <small class="alm-subtipo">
                                        ${escapar(
                                            item.subtipo
                                        )}
                                    </small>
                                `
                                : ''}
                        </td>

                        <td>
                            <span class="alm-chip">
                                ${escapar(
                                    etiquetaOrigen(
                                        item.origen
                                    )
                                )}
                            </span>
                        </td>

                        <td>
                            <strong class="alm-tamano">
                                ${escapar(
                                    bytes(
                                        item.tamano_bytes
                                    )
                                )}
                            </strong>
                        </td>

                        <td>
                            <span class="alm-chip">
                                ${escapar(
                                    item.confianza
                                )}
                            </span>

                            ${item.posible_huerfano
                                ? `
                                    <small class="alm-alerta-texto">
                                        Posible huérfano
                                    </small>
                                `
                                : ''}
                        </td>

                        <td>
                            <span class="alm-politica">
                                ${escapar(
                                    politicaLegible(
                                        item.politica
                                    )
                                )}
                            </span>
                        </td>

                        <td>
                            ${
                                item.clase === 'VINCULADO'
                                && item.confianza === 'ALTA'
                                && item.posible_huerfano === false
                                && item.eliminacion_automatica_permitida === false
                                && item.politica === 'NO_LIMPIEZA_AUTOMATICA;GESTIONAR_COMO_DATO_ASOCIADO'
                                && (item.subtipo === 'DATOS_GAME' || item.subtipo === 'CACHE_GAME')
                                && Number(item.juego_id) > 0
                                && Number(item.juego_componente_id) > 0
                                    ? `
                                        <button
                                            type="button"
                                            class="alm-gestionar-preview"
                                            data-alm-preview
                                            data-juego-id="${Number(item.juego_id)}"
                                            data-componente-id="${Number(item.juego_componente_id)}"
                                        >
                                            Previsualizar
                                        </button>
                                    `
                                    : '<span class="alm-gestion-no">—</span>'
                            }
                        </td>
                    </tr>
                `;
            }).join('');
    };

    const renderError = (mensaje) => {
        const nodo =
            $('almError');

        nodo.hidden =
            false;

        nodo.textContent =
            mensaje;

        actualizarEstado(
            'ERROR',
            'alerta'
        );
    };

    const cargar = async () => {
        actualizarEstado(
            'CONSULTANDO',
            'cargando'
        );

        try {
            const respuesta =
                await fetch(
                    API,
                    {
                        cache: 'no-store',
                        headers: {
                            'Accept':
                                'application/json',
                        },
                    }
                );

            const datos =
                await respuesta.json();

            if (
                !respuesta.ok
                || !datos
                || datos.ok !== true
            ) {
                throw new Error(
                    datos?.error
                    || `HTTP ${respuesta.status}`
                );
            }

            estado.datos =
                datos;

            estado.elementos =
                Array.isArray(
                    datos.elementos
                )
                    ? datos.elementos
                    : [];

            $('almError').hidden =
                true;

            renderResumen();
            renderClases();
            poblarFiltroClases();
            renderLista();

        } catch (error) {
            renderError(
                'No se pudo consultar el inventario de almacenamiento: '
                + (
                    error instanceof Error
                        ? error.message
                        : String(error)
                )
            );
        }
    };

    [
        'almBuscar',
        'almFiltroClase',
        'almFiltroOrigen',
        'almOrden',
    ].forEach((id) => {
        const nodo = $(id);

        if (!nodo) {
            return;
        }

        nodo.addEventListener(
            id === 'almBuscar'
                ? 'input'
                : 'change',
            renderLista
        );
    });

    cargar();
})();
