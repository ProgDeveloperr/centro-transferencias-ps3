'use strict';

const csrf =
    document
        .querySelector('meta[name="csrf-token"]')
        .content;

const seleccionados = new Set();

/* ==========================================================
 * BIB-UX2 — NAVEGACION DE BIBLIOTECA
 * Capa visual: búsqueda, filtros, orden y resumen.
 * ========================================================== */
const bibliotecaUx = {
    controlesIniciados: false,

    preflight: null,
    preflightFirma: '',
    preflightActualizadoMs: 0,
    preflightSecuencia: 0,
    preflightTemporizador: null,
};

function normalizarTextoBiblioteca(valor) {
    return String(valor ?? '')
        .trim()
        .toLocaleLowerCase('es-AR');
}

function valorControlBiblioteca(id) {
    return $(id)?.value || '';
}

function etiquetaFormatoBiblioteca(formato) {
    if (formato === 'PS3ISO') return 'PS3 ISO';
    if (formato === 'PS2ISO') return 'PS2';
    return 'PKG';
}

function estadoPs3JuegoBiblioteca(archivos) {
    const estados = new Set(
        archivos.map(
            (archivo) => String(archivo.estado_ps3 || 'AUSENTE')
        )
    );

    return estados.size === 1
        ? [...estados][0]
        : 'MIXTO';
}

function iniciarControlesBiblioteca() {
    if (bibliotecaUx.controlesIniciados) return;
    if (!$('bibliotecaControles')) return;

    bibliotecaUx.controlesIniciados = true;

    $('bibliotecaBuscar')?.addEventListener('input', renderBiblioteca);

    for (const id of [
        'bibliotecaFiltroFormato',
        'bibliotecaFiltroPs3',
        'bibliotecaOrden',
    ]) {
        $(id)?.addEventListener('change', renderBiblioteca);
    }
}


let catalogo = [];
let transferencias = [];
let estadoServidor = null;

const $ = (id) =>
    document.getElementById(id);

function escapar(valor) {
    return String(valor ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

function bytes(valor) {
    const numero =
        Number(valor || 0);

    if (numero < 1024) {
        return `${numero} B`;
    }

    const unidades =
        ['KB', 'MB', 'GB', 'TB'];

    let n = numero;
    let indice = -1;

    do {
        n /= 1024;
        indice++;
    } while (
        n >= 1024
        && indice < unidades.length - 1
    );

    return `${n.toFixed(
        n >= 10 ? 1 : 2
    )} ${unidades[indice]}`;
}

function velocidad(valor) {
    if (!valor || valor <= 0) {
        return '—';
    }

    return `${bytes(valor)}/s`;
}

function tiempo(segundos) {
    if (
        segundos === null
        || segundos === undefined
        || segundos < 0
    ) {
        return '—';
    }

    segundos =
        Math.round(segundos);

    if (segundos < 60) {
        return `${segundos}s`;
    }

    const minutos =
        Math.floor(segundos / 60);

    const resto =
        segundos % 60;

    if (minutos < 60) {
        return `${minutos}m ${resto}s`;
    }

    const horas =
        Math.floor(minutos / 60);

    return `${horas}h ${minutos % 60}m`;
}

function fecha(valor) {
    if (!valor) {
        return '—';
    }

    const date = new Date(valor);

    return new Intl.DateTimeFormat(
        'es-AR',
        {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        }
    ).format(date);
}

async function api(url, opciones = {}) {
    const respuesta = await fetch(
        url,
        {
            cache: 'no-store',
            ...opciones,
        }
    );

    let datos;

    try {
        datos = await respuesta.json();
    } catch {
        throw new Error(
            `Respuesta inválida de ${url}`
        );
    }

    if (!respuesta.ok || !datos.ok) {
        throw new Error(
            datos.error
            || `HTTP ${respuesta.status}`
        );
    }

    return datos;
}

async function post(url, cuerpo) {
    return api(
        url,
        {
            method: 'POST',

            headers: {
                'Content-Type':
                    'application/json',

                'X-CSRF-Token':
                    csrf,
            },

            body: JSON.stringify(cuerpo),
        }
    );
}

function toast(
    mensaje,
    tipo = 'ok'
) {
    const elemento =
        document.createElement('div');

    elemento.className =
        `toast toast--${tipo}`;

    elemento.textContent =
        mensaje;

    $('toasts').appendChild(
        elemento
    );

    setTimeout(
        () => elemento.remove(),
        3800
    );
}

function claseEstado(estado) {
    if (
        [
            'COMPLETADO',
            'YA_EXISTE',
        ].includes(estado)
    ) {
        return 'estado--ok';
    }

    if (
        [
            'ERROR',
            'CONFLICTO',
            'CANCELADO',
        ].includes(estado)
    ) {
        return 'estado--error';
    }

    if (
        [
            'PAUSADO',
            'REINTENTANDO',
            'PAUSANDO',
        ].includes(estado)
    ) {
        return 'estado--aviso';
    }

    if (
        [
            'TRANSFIRIENDO',
            'PREPARANDO',
            'COMPROBANDO',
            'VERIFICANDO',
            'EN_COLA',
        ].includes(estado)
    ) {
        return 'estado--info';
    }

    return 'estado--neutro';
}

function activosPorArchivo() {
    const mapa = new Map();

    for (const transferencia of transferencias) {
        if (transferencia.activa) {
            mapa.set(
                Number(
                    transferencia.archivo_id
                ),
                transferencia
            );
        }
    }

    return mapa;
}


/*
 * =========================================================
 * BIB — PERFIL ZUKOSTORE
 * =========================================================
 *
 * Esta capa solamente interpreta nombres para la
 * presentación de Biblioteca.
 *
 * NO modifica:
 * - multipart real;
 * - parte_numero;
 * - es_fragmentado;
 * - SQLite;
 * - operaciones del worker.
 */

function analizarNombreZukoBiblioteca(
    nombre
) {
    const original =
        String(
            nombre || ''
        ).trim();


    const perfiles = [
        {
            familia:
                'ZUKO3G',

            expresion:
                /^ZUKO3G_(\d{2})(GM|PT|DL)_([A-Z0-9_]+)\.pkg$/i,
        },

        {
            familia:
                'ZUKOSTORE_3G',

            expresion:
                /^ZUKOSTORE_3G_(\d{2})(GM|PT|DL)_([A-Z0-9_]+)\.pkg$/i,
        },
    ];


    for (const perfil of perfiles) {

        const coincidencia =
            original.match(
                perfil.expresion
            );


        if (!coincidencia) {
            continue;
        }


        const orden =
            Number(
                coincidencia[1]
            );

        const tipo =
            String(
                coincidencia[2]
            ).toUpperCase();

        const resto =
            String(
                coincidencia[3]
            ).toUpperCase();


        if (
            !Number.isInteger(
                orden
            )
            || orden < 1
        ) {
            return null;
        }


        /*
         * Con la evidencia actual:
         *
         * 01GM es la base canónica.
         * PT/DL siempre aparecen después.
         */
        if (
            tipo === 'GM'
            && orden !== 1
        ) {
            return null;
        }


        if (
            tipo !== 'GM'
            && orden <= 1
        ) {
            return null;
        }


        return {
            familia:
                perfil.familia,

            orden,
            tipo,
            resto,
        };
    }


    /*
     * ZUKO3H y cualquier variante futura
     * quedan deliberadamente fuera.
     */
    return null;
}


function rolZukoBiblioteca(
    tipo
) {
    const roles = {
        GM:
            'Juego base',

        PT:
            'Patch',

        DL:
            'DLC / Fix',
    };


    return (
        roles[tipo]
        || tipo
    );
}


function restoCompatibleZukoBiblioteca(
    tipo,
    resto,
    identidad
) {
    if (
        resto === identidad
    ) {
        return true;
    }


    /*
     * Único sufijo adicional realmente
     * observado y certificado hasta ahora.
     *
     * No usamos startsWith() genérico para
     * evitar unir juegos distintos.
     */
    if (
        tipo === 'DL'
        && resto
            === (
                identidad
                + 'ALLDLPACKFIX'
            )
    ) {
        return true;
    }


    return false;
}


function construirIndiceZukoBiblioteca(
    archivos
) {
    const analizados =
        [];


    for (const archivo of archivos) {

        const id =
            Number(
                archivo.id
            );

        if (
            !Number.isInteger(id)
            || id < 1
        ) {
            continue;
        }


        const zuko =
            analizarNombreZukoBiblioteca(
                archivo.nombre
            );


        if (!zuko) {
            continue;
        }


        analizados.push({
            archivo,
            id,
            ...zuko,
        });
    }


    const bases =
        analizados.filter(
            (item) =>
                item.tipo === 'GM'
        );


    const provisionales =
        new Map();


    for (const item of analizados) {

        const candidatos =
            bases.filter(
                (base) =>
                    base.familia
                        === item.familia

                    && restoCompatibleZukoBiblioteca(
                        item.tipo,
                        item.resto,
                        base.resto
                    )
            );


        /*
         * Ante cualquier ambigüedad:
         * NO agrupar.
         */
        if (
            candidatos.length !== 1
        ) {
            continue;
        }


        const base =
            candidatos[0];

        const clave =
            (
                base.familia
                + '::'
                + base.resto
            ).toLocaleLowerCase(
                'es'
            );


        if (
            !provisionales.has(
                clave
            )
        ) {
            provisionales.set(
                clave,
                {
                    clave:
                        `zuko::${clave}`,

                    familia:
                        base.familia,

                    identidad:
                        base.resto,

                    items:
                        [],
                }
            );
        }


        provisionales
            .get(clave)
            .items
            .push(item);
    }


    const indice =
        new Map();


    for (
        const grupo
        of provisionales.values()
    ) {

        /*
         * Un archivo aislado continúa siendo
         * un PKG normal. Sólo hablamos de
         * "conjunto" con 2 o más elementos.
         */
        if (
            grupo.items.length < 2
        ) {
            continue;
        }


        const basesGrupo =
            grupo.items.filter(
                (item) =>
                    item.tipo === 'GM'
            );


        if (
            basesGrupo.length !== 1
        ) {
            continue;
        }


        const ordenes =
            grupo.items
                .map(
                    (item) =>
                        item.orden
                )
                .sort(
                    (a, b) =>
                        a - b
                );


        /*
         * No permitimos posiciones repetidas.
         */
        if (
            new Set(
                ordenes
            ).size
                !== ordenes.length
        ) {
            continue;
        }


        /*
         * De momento exigimos secuencia
         * correlativa exacta:
         *
         * 01,02
         * 01,02,03
         *
         * Una variante con huecos se audita
         * antes de aceptarla.
         */
        const secuenciaValida =
            ordenes.every(
                (orden, indice) =>
                    orden
                        === indice + 1
            );


        if (!secuenciaValida) {
            continue;
        }


        for (
            const item
            of grupo.items
        ) {

            indice.set(
                item.id,
                {
                    clave:
                        grupo.clave,

                    familia:
                        grupo.familia,

                    identidad:
                        grupo.identidad,

                    orden:
                        item.orden,

                    tipo:
                        item.tipo,

                    rol:
                        rolZukoBiblioteca(
                            item.tipo
                        ),
                }
            );
        }
    }


    return indice;
}


function renderBiblioteca() {
    const contenedor = $('biblioteca');

    if (!contenedor) {
        return;
    }

    iniciarControlesBiblioteca();

    const activos = activosPorArchivo();
    const juegos = new Map();
    const indiceZuko = construirIndiceZukoBiblioteca(catalogo);

    for (const archivo of catalogo) {
        const zuko = indiceZuko.get(Number(archivo.id)) || null;
        const formato = (
            archivo.formato === 'PS3ISO'
            || archivo.formato === 'PS2ISO'
        ) ? archivo.formato : 'PKG';

        const baseClave =
            archivo.codigo_juego
            || archivo.titulo_juego
            || archivo.nombre;

        const clave = zuko
            ? 'PKG::ZUKO::' + zuko.clave
            : formato + '::' + baseClave;

        if (!juegos.has(clave)) {
            juegos.set(clave, {
                formato,
                titulo: zuko
                    ? zuko.identidad
                    : (archivo.titulo_juego || archivo.nombre),
                codigo: zuko
                    ? ('CONJUNTO ZUKO · ' + zuko.familia)
                    : archivo.codigo_juego,
                perfil_zuko: Boolean(zuko),
                archivos: [],
            });
        }

        juegos.get(clave).archivos.push(
            zuko
                ? {
                    ...archivo,
                    zuko_orden: zuko.orden,
                    zuko_tipo: zuko.tipo,
                    zuko_rol: zuko.rol,
                }
                : archivo
        );
    }

    for (const juego of juegos.values()) {
        if (juego.perfil_zuko) {
            juego.archivos.sort(
                (a, b) => Number(a.zuko_orden) - Number(b.zuko_orden)
            );
        }

        juego.tamano_total = juego.archivos.reduce(
            (suma, archivo) => suma + Number(archivo.tamano_bytes || 0),
            0
        );

        juego.estado_ps3 = estadoPs3JuegoBiblioteca(juego.archivos);
    }

    const buscar = normalizarTextoBiblioteca(
        valorControlBiblioteca('bibliotecaBuscar')
    );
    const filtroFormato = valorControlBiblioteca('bibliotecaFiltroFormato');
    const filtroPs3 = valorControlBiblioteca('bibliotecaFiltroPs3');
    const orden = valorControlBiblioteca('bibliotecaOrden') || 'nombre-asc';

    const lista = [...juegos.values()];

    for (const juego of lista) {
        const texto = [
            juego.titulo,
            juego.codigo,
            etiquetaFormatoBiblioteca(juego.formato),
            ...juego.archivos.map((archivo) => archivo.nombre),
        ].filter(Boolean).join(' ');

        juego.visible = (
            (!filtroFormato || juego.formato === filtroFormato)
            && (!filtroPs3 || juego.estado_ps3 === filtroPs3)
            && (!buscar || normalizarTextoBiblioteca(texto).includes(buscar))
        );
    }

    const compararNombre = (a, b) =>
        String(a.titulo || '').localeCompare(
            String(b.titulo || ''),
            'es-AR',
            { sensitivity: 'base', numeric: true }
        );

    lista.sort((a, b) => {
        if (orden === 'nombre-desc') return -compararNombre(a, b);
        if (orden === 'tamano-desc') {
            return (b.tamano_total - a.tamano_total) || compararNombre(a, b);
        }
        if (orden === 'tamano-asc') {
            return (a.tamano_total - b.tamano_total) || compararNombre(a, b);
        }
        return compararNombre(a, b);
    });

    const visibles = lista.filter((juego) => juego.visible);
    const totalVisibleBytes = visibles.reduce(
        (suma, juego) => suma + juego.tamano_total,
        0
    );
    const totalVisibleArchivos = visibles.reduce(
        (suma, juego) => suma + juego.archivos.length,
        0
    );

    const resumenVisible = $('bibliotecaResumenVisible');
    if (resumenVisible) {
        resumenVisible.textContent =
            `${visibles.length} de ${lista.length} juegos`
            + ` · ${totalVisibleArchivos} archivos`
            + ` · ${bytes(totalVisibleBytes)}`;
    }

    if (!catalogo.length) {
        contenedor.innerHTML =
            '<div class="vacio">No hay archivos disponibles.</div>';
        actualizarSeleccion();
        return;
    }

    if (!visibles.length) {
        contenedor.innerHTML =
            '<div class="vacio">No hay juegos que coincidan con los filtros actuales.</div>';
        actualizarSeleccion();
        return;
    }

    contenedor.innerHTML = lista
        .map((juego) => {
            const etiquetaFormato = etiquetaFormatoBiblioteca(juego.formato);

            const filas = juego.archivos
                .map((archivo) => {
                    const activo = activos.has(Number(archivo.id));
                    const etiquetaZuko = (
                        archivo.zuko_rol
                        && Number.isInteger(archivo.zuko_orden)
                    )
                        ? String(archivo.zuko_orden).padStart(2, '0')
                            + ' · ' + archivo.zuko_rol
                        : null;

                    const formatoArchivo = (
                        archivo.formato === 'PS3ISO'
                        || archivo.formato === 'PS2ISO'
                    ) ? archivo.formato : 'PKG';

                    const parte = etiquetaZuko || (
                        formatoArchivo === 'PS3ISO'
                            ? 'ISO PS3'
                            : (
                                formatoArchivo === 'PS2ISO'
                                    ? 'PS2 BIN.ENC'
                                    : (
                                        archivo.parte_numero
                                            ? `Parte ${archivo.parte_numero}`
                                            : 'PKG único'
                                    )
                            )
                    );

                    const estadoPs3 = String(archivo.estado_ps3 || 'AUSENTE');

                    return `
                        <label class="archivo ${activo ? 'archivo--ocupado' : ''}">
                            <input
                                type="checkbox"
                                data-archivo-id="${archivo.id}"
                                ${activo ? 'disabled' : ''}
                                ${seleccionados.has(Number(archivo.id)) ? 'checked' : ''}
                            >

                            <div>
                                <div class="archivo__nombre">
                                    ${escapar(archivo.nombre)}
                                </div>

                                <div class="archivo__meta">
                                    ${escapar(parte)}
                                    · PS3: ${escapar(estadoPs3)}
                                    · SHA-256: ${escapar(archivo.sha256_estado)}
                                    ${activo ? ' · YA EN COLA' : ''}
                                </div>
                            </div>

                            <span class="archivo__tamano">
                                ${bytes(archivo.tamano_bytes)}
                            </span>
                        </label>
                    `;
                })
                .join('');

            return `
                <article class="juego" ${juego.visible ? '' : 'hidden'}>
                    <div class="juego__cabecera">
                        <div>
                            <h3 class="juego__titulo">
                                ${escapar(juego.titulo)}
                            </h3>
                            <span class="juego__codigo">
                                ${escapar(
                                    etiquetaFormato + ' · '
                                    + (juego.codigo || 'SIN CÓDIGO')
                                )}
                            </span>
                        </div>

                        <span class="juego__resumen">
                            ${juego.archivos.length} ${etiquetaFormato}
                            · ${bytes(juego.tamano_total)}
                            · PS3: ${escapar(juego.estado_ps3)}
                        </span>
                    </div>

                    <div class="archivos">${filas}</div>
                </article>
            `;
        })
        .join('');

    contenedor
        .querySelectorAll('input[data-archivo-id]')
        .forEach((input) => {
            input.addEventListener('change', () => {
                const id = Number(input.dataset.archivoId);
                if (input.checked) seleccionados.add(id);
                else seleccionados.delete(id);
                actualizarSeleccion();
            });
        });

    actualizarSeleccion();
}

function firmaSeleccionPreflight() {
    return [...seleccionados]
        .map(Number)
        .filter((id) => Number.isInteger(id) && id > 0)
        .sort((a, b) => a - b)
        .join(',');
}

function renderPreflightSeleccion() {
    const elemento = $('seleccionCapacidad');
    if (!elemento) return;

    if (!seleccionados.size) {
        elemento.textContent = 'Capacidad: sin selección';
        elemento.title = '';
        return;
    }

    const preflight = bibliotecaUx.preflight;
    if (!preflight) {
        elemento.textContent = 'Capacidad: comprobando…';
        elemento.title = 'Consultando el control de admisión del servidor';
        return;
    }

    if (preflight.verificado === true && preflight.estado === 'OK') {
        elemento.textContent =
            'Capacidad: cabe'
            + (preflight.capacidad_nueva_bytes !== null
                ? ` · ${bytes(preflight.capacidad_nueva_bytes)} disponibles`
                : '');
    } else if (
        preflight.verificado === true
        && preflight.estado === 'INSUFICIENTE'
    ) {
        elemento.textContent =
            'Capacidad: no cabe'
            + (Number(preflight.faltante_bytes || 0) > 0
                ? ` · faltan ${bytes(preflight.faltante_bytes)}`
                : '');
    } else {
        elemento.textContent = 'Capacidad: no verificable · se puede encolar';
    }

    const detalles = [];
    if (preflight.hdd_libre_texto) detalles.push(`PS3: ${preflight.hdd_libre_texto}`);
    detalles.push(`Selección: ${bytes(preflight.solicitado_bytes || 0)}`);
    detalles.push(`Reservado: ${bytes(preflight.reservado_activo_bytes || 0)}`);
    detalles.push(`Margen: ${bytes(preflight.margen_seguridad_bytes || 0)}`);
    if (preflight.motivo) detalles.push(`Motivo: ${preflight.motivo}`);
    elemento.title = detalles.join(' · ');
}

async function consultarPreflightSeleccion(firma, ids, secuencia) {
    try {
        const datos = await post(
            'api/encolar.php',
            { ids, preflight: true }
        );

        if (
            secuencia !== bibliotecaUx.preflightSecuencia
            || firma !== firmaSeleccionPreflight()
        ) return;

        bibliotecaUx.preflight = datos.preflight || null;
        bibliotecaUx.preflightFirma = firma;
        bibliotecaUx.preflightActualizadoMs = Date.now();
    } catch (error) {
        if (
            secuencia !== bibliotecaUx.preflightSecuencia
            || firma !== firmaSeleccionPreflight()
        ) return;

        bibliotecaUx.preflight = {
            verificado: false,
            estado: 'NO_VERIFICABLE',
            motivo: 'PREVIEW_NO_DISPONIBLE',
            solicitado_bytes: ids.reduce((suma, id) => {
                const archivo = catalogo.find((item) => Number(item.id) === id);
                return suma + Number(archivo?.tamano_bytes || 0);
            }, 0),
            reservado_activo_bytes: 0,
            margen_seguridad_bytes: 512 * 1024 * 1024,
            hdd_libre_texto: null,
            capacidad_nueva_bytes: null,
            faltante_bytes: 0,
        };
        bibliotecaUx.preflightFirma = firma;
        bibliotecaUx.preflightActualizadoMs = Date.now();
    }

    renderPreflightSeleccion();

    const boton = $('botonEncolar');
    if (boton) {
        boton.disabled =
            seleccionados.size === 0
            || (
                bibliotecaUx.preflight?.verificado === true
                && bibliotecaUx.preflight?.estado === 'INSUFICIENTE'
            );
    }
}

function programarPreflightSeleccion(forzar = false) {
    if (!$('seleccionCapacidad')) return;

    const firma = firmaSeleccionPreflight();

    if (!firma) {
        if (bibliotecaUx.preflightTemporizador) {
            clearTimeout(bibliotecaUx.preflightTemporizador);
        }
        bibliotecaUx.preflightTemporizador = null;
        bibliotecaUx.preflightSecuencia++;
        bibliotecaUx.preflight = null;
        bibliotecaUx.preflightFirma = '';
        bibliotecaUx.preflightActualizadoMs = 0;
        renderPreflightSeleccion();
        return;
    }

    const mismaFirma = firma === bibliotecaUx.preflightFirma;
    const reciente = (Date.now() - bibliotecaUx.preflightActualizadoMs) < 5000;

    if (!forzar && mismaFirma && reciente) {
        renderPreflightSeleccion();
        return;
    }

    if (!mismaFirma) {
        bibliotecaUx.preflight = null;
        renderPreflightSeleccion();
    }

    if (bibliotecaUx.preflightTemporizador) {
        clearTimeout(bibliotecaUx.preflightTemporizador);
    }

    const secuencia = ++bibliotecaUx.preflightSecuencia;
    const ids = firma.split(',').map(Number);

    bibliotecaUx.preflightTemporizador = setTimeout(
        () => {
            bibliotecaUx.preflightTemporizador = null;
            consultarPreflightSeleccion(firma, ids, secuencia);
        },
        180
    );
}

function actualizarSeleccion() {
    const contador = $('seleccionContador');
    const boton = $('botonEncolar');

    let tamanoSeleccionado = 0;

    for (const archivo of catalogo) {
        if (seleccionados.has(Number(archivo.id))) {
            tamanoSeleccionado += Number(archivo.tamano_bytes || 0);
        }
    }

    if (contador) {
        contador.textContent =
            `${seleccionados.size} seleccionados`
            + (seleccionados.size ? ` · ${bytes(tamanoSeleccionado)}` : '');
    }

    programarPreflightSeleccion();

    if (boton) {
        boton.disabled =
            seleccionados.size === 0
            || (
                bibliotecaUx.preflight?.verificado === true
                && bibliotecaUx.preflight?.estado === 'INSUFICIENTE'
            );
    }
}

function accionesPara(transferencia) {
    const estado =
        transferencia.estado;

    const botones = [];

    if (
        [
            'EN_COLA',
            'COMPROBANDO',
            'PREPARANDO',
            'TRANSFIRIENDO',
            'REINTENTANDO',
        ].includes(estado)
    ) {
        botones.push(
            botonAccion(
                transferencia.id,
                'PAUSAR',
                'Pausar'
            )
        );
    }

    if (estado === 'PAUSADO') {
        botones.push(
            botonAccion(
                transferencia.id,
                'REANUDAR',
                'Reanudar'
            )
        );
    }

    if (estado === 'ERROR') {
        botones.push(
            botonAccion(
                transferencia.id,
                'REINTENTAR',
                'Reintentar'
            )
        );
    }

    if (
        [
            'EN_COLA',
            'COMPROBANDO',
            'PREPARANDO',
            'TRANSFIRIENDO',
            'PAUSANDO',
            'PAUSADO',
            'REINTENTANDO',
            'ERROR',
        ].includes(estado)
    ) {
        botones.push(
            botonAccion(
                transferencia.id,
                'CANCELAR',
                'Cancelar',
                true
            )
        );
    }

    return botones.join('');
}

function botonAccion(
    id,
    accion,
    texto,
    peligro = false
) {
    return `
        <button
            class="boton boton--mini ${
                peligro
                ? 'boton--peligro'
                : 'boton--secundario'
            }"
            type="button"
            data-transferencia="${id}"
            data-accion="${accion}"
        >
            ${texto}
        </button>
    `;
}

function tarjetaTransferencia(
    transferencia,
    mostrarAcciones = true
) {
    const porcentaje =
        Number(
            transferencia.porcentaje || 0
        );

    const velocidadActual =
        transferencia.velocidad_bps;

    const telemetriaDisponible =
        Boolean(
            transferencia.telemetria_ftp_disponible
        );

    const sesionesFtp =
        Number(
            transferencia.sesiones_ftp || 0
        );

    const bytesFtp =
        Number(
            transferencia.bytes_ftp || 0
        );

    const textoTelemetria =
        telemetriaDisponible
            ? (
                `FTP enviado: ${bytes(bytesFtp)}`
                + ` · ${sesionesFtp} sesión`
                + (
                    sesionesFtp === 1
                        ? ''
                        : 'es'
                )
            )
            : (
                'Telemetría FTP: '
                + 'histórico anterior a 8B'
            );

    return `
        <article
            class="transferencia"
            data-transferencia-id="${transferencia.id}"
            data-transferencia-estado="${escapar(
                transferencia.estado
            )}"
        >

            <div>
                <div class="transferencia__superior">
                    <div style="min-width:0">
                        <div class="transferencia__titulo">
                            ${escapar(
                                transferencia.nombre_snapshot
                            )}
                        </div>

                        <div class="transferencia__detalle">
                            #${transferencia.id}
                            · ${escapar(
                                transferencia.mensaje || ''
                            )}
                        </div>
                    </div>

                    <span
                        class="estado ${
                            claseEstado(
                                transferencia.estado
                            )
                        }"
                    >
                        ${escapar(
                            transferencia.estado
                        )}
                    </span>
                </div>

                <div class="progreso">
                    <div
                        class="progreso__barra"
                        style="width:${porcentaje}%"
                    ></div>
                </div>

                <div class="progreso-info">
                    <span>
                        ${porcentaje.toFixed(1)}%
                        ·
                        ${bytes(
                            transferencia.bytes_transferidos
                        )}
                        /
                        ${bytes(
                            transferencia.tamano_total
                        )}
                    </span>

                    <span>
                        ${velocidad(
                            velocidadActual
                        )}
                        · ETA
                        ${tiempo(
                            transferencia.eta_segundos
                        )}
                    </span>
                </div>

                <div class="transferencia__detalle">
                    ${textoTelemetria}
                </div>
            </div>

            ${
                mostrarAcciones
                    ? `
                    <div class="transferencia__acciones">
                        ${accionesPara(transferencia)}
                    </div>
                    `
                    : ''
            }

        </article>
    `;
}

function renderTransferencias() {
    const activas =
        transferencias.filter(
            (item) => item.activa
        );


    const historial =
        transferencias.filter(
            (item) => !item.activa
        );


    const contenedorCola =
        $('cola');


    if (contenedorCola) {
        contenedorCola.innerHTML =
            activas.length
                ? activas
                    .map(
                        (item) =>
                            tarjetaTransferencia(
                                item,
                                true
                            )
                    )
                    .join('')
                : `
                    <div class="vacio">
                        No hay transferencias
                        en cola.
                    </div>
                `;
    }


    const contenedorHistorial =
        $('historial');


    if (contenedorHistorial) {
        contenedorHistorial.innerHTML =
            historial.length
                ? historial
                    .slice(0, 30)
                    .map(
                        (item) =>
                            tarjetaTransferencia(
                                item,
                                item.estado
                                    === 'ERROR'
                            )
                    )
                    .join('')
                : `
                    <div class="vacio">
                        Todavía no hay historial.
                    </div>
                `;
    }


    document
        .querySelectorAll(
            '[data-transferencia][data-accion]'
        )
        .forEach(
            (boton) => {
                boton.addEventListener(
                    'click',
                    () => {
                        confirmarAccion(
                            Number(
                                boton.dataset
                                    .transferencia
                            ),
                            boton.dataset
                                .accion
                        );
                    }
                );
            }
        );


    const metricaCola =
        $('metricaCola');


    if (metricaCola) {
        metricaCola.textContent =
            String(
                activas.length
            );
    }


    const activa =
        transferencias.find(
            (item) =>
                item.estado
                === 'TRANSFIRIENDO'
        );


    const metricaVelocidad =
        $('metricaVelocidad');


    if (metricaVelocidad) {
        metricaVelocidad.textContent =
            activa
                ? velocidad(
                    activa.velocidad_bps
                )
                : '—';
    }
}

function renderEstado() {
    if (!estadoServidor) {
        return;
    }


    const worker =
        estadoServidor.worker;


    const estado =
        $('estadoWorker');


    if (estado) {
        estado.textContent =
            `WORKER · ${worker.estado}`;

        estado.className =
            'estado '
            + (
                worker.estado === 'OCUPADO'
                    ? 'estado--info'
                    : worker.estado === 'ERROR'
                        ? 'estado--error'
                        : (
                            worker.estado
                                === 'ESPERANDO_PS3'
                            || (
                                worker.estado
                                    === 'ESPERANDO'
                                && String(
                                    worker.mensaje
                                    || ''
                                ).startsWith(
                                    'Esperando PS3:'
                                )
                            )
                        )
                            ? 'estado--ps3-aviso'
                            : 'estado--ok'
            );
    }


    const mensajeWorker =
        $('mensajeWorker');


    if (mensajeWorker) {
        mensajeWorker.textContent =
            worker.mensaje
            || 'Sin mensaje';
    }


    const metricaArchivos =
        $('metricaArchivos');


    if (metricaArchivos) {
        metricaArchivos.textContent =
            estadoServidor
                .catalogo
                .archivos;
    }


    const metricaTamano =
        $('metricaTamano');


    if (metricaTamano) {
        metricaTamano.textContent =
            bytes(
                estadoServidor
                    .catalogo
                    .tamano_total_bytes
            );
    }


    const aviso =
        $('avisoWorker');


    if (!aviso) {
        return;
    }


    if (
        worker.mensaje
        && worker.mensaje
            .toLowerCase()
            .includes(
                'lftp externo'
            )
    ) {
        aviso.classList.remove(
            'aviso--oculto'
        );

        aviso.textContent =
            'El motor está protegido y en espera '
            + 'porque detectó una transferencia '
            + 'lftp iniciada manualmente. '
            + worker.mensaje
            + '.';

    } else {

        aviso.classList.add(
            'aviso--oculto'
        );

        aviso.textContent =
            '';
    }
}

function renderEventos(eventos) {
    const contenedor =
        $('eventos');


    if (!contenedor) {
        return;
    }


    contenedor.innerHTML =
        eventos.length
            ? eventos
                .map(
                    (evento) => `
                        <div class="evento">
                            <span class="evento__fecha">
                                ${fecha(
                                    evento.creado_utc
                                )}
                            </span>

                            <span class="evento__tipo">
                                ${escapar(
                                    evento.nivel
                                )}
                            </span>

                            <span class="evento__mensaje">
                                ${escapar(
                                    evento.mensaje
                                )}
                            </span>
                        </div>
                    `
                )
                .join('')
            : `
                <div class="vacio">
                    Sin eventos registrados.
                </div>
            `;
}

let cargaTodoPromesa = null;
let errorActualizacionActivo = false;

function cargarTodo() {
    if (cargaTodoPromesa) {
        return cargaTodoPromesa;
    }

    cargaTodoPromesa =
        cargarTodoInterno()
            .finally(
                () => {
                    cargaTodoPromesa = null;
                }
            );

    return cargaTodoPromesa;
}

async function cargarTodoInterno() {
    try {
        const [
            datosCatalogo,
            datosTransferencias,
            datosEstado,
            datosEventos,
            datosPs3,
            datosEstadisticas,
        ] = await Promise.all([
            api('api/catalogo.php'),
            api('api/transferencias.php'),
            api('api/estado.php'),
            api('api/eventos.php'),
            api('api/ps3.php'),
            api('api/estadisticas.php'),
        ]);


        catalogo =
            datosCatalogo.archivos;

        transferencias =
            datosTransferencias
                .transferencias;

        estadoServidor =
            datosEstado;


        for (
            const id
            of [...seleccionados]
        ) {
            const sigueDisponible =
                catalogo.some(
                    (archivo) =>
                        Number(
                            archivo.id
                        ) === id
                );


            if (!sigueDisponible) {
                seleccionados.delete(
                    id
                );
            }
        }


        renderEstado();


        if ($('biblioteca')) {
            renderBiblioteca();
        }


        if (
            $('cola')
            || $('historial')
            || $('metricaCola')
            || $('metricaVelocidad')
        ) {
            renderTransferencias();
        }


        if (
            (
                $('cola')
                || $('historial')
            )
            && typeof renderColaProfesional
                === 'function'
        ) {
            renderColaProfesional(
                datosTransferencias
            );
        }


        if (
            $('historial')
            && typeof renderHistorialProfesional
                === 'function'
        ) {
            renderHistorialProfesional(
                datosEstadisticas
            );
        }


        if ($('eventos')) {
            renderEventos(
                datosEventos.eventos
            );
        }


        if (
            typeof renderPs3Inteligente
                === 'function'
        ) {
            renderPs3Inteligente(
                datosPs3,
                datosCatalogo
            );

        renderGestorPkg(
            datosPs3
        );
        }


        if (errorActualizacionActivo) {
            errorActualizacionActivo = false;

            toast(
                'Conexión con el servidor restablecida',
                'ok'
            );
        }


    } catch (error) {

        console.error(
            error
        );


        if (!errorActualizacionActivo) {
            errorActualizacionActivo = true;

            toast(
                `Error actualizando: ${error.message}`,
                'error'
            );
        }
    }
}

async function encolarSeleccion() {
    if (!seleccionados.size) {
        return;
    }

    const boton =
        $('botonEncolar');

    boton.disabled = true;
    boton.textContent =
        'Agregando…';

    /*
     * BIB-2C.2
     *
     * Set conserva el orden de interacción
     * del usuario. Para una secuencia lógica
     * como Zuko necesitamos encolar según el
     * orden visual certificado de Biblioteca.
     *
     * No cambia la selección: solamente
     * canonicaliza el orden de esos mismos IDs.
     */
    const ordenDom =
        new Map(
            [
                ...document.querySelectorAll(
                    (
                        '#biblioteca '
                        + 'input[data-archivo-id]'
                    )
                ),
            ].map(
                (input, indice) => [
                    Number(
                        input.dataset
                            .archivoId
                    ),
                    indice,
                ]
            )
        );


    const idsOrdenados =
        [
            ...seleccionados,
        ].sort(
            (a, b) => {

                const ordenA =
                    ordenDom.has(a)
                        ? ordenDom.get(a)
                        : Number.MAX_SAFE_INTEGER;

                const ordenB =
                    ordenDom.has(b)
                        ? ordenDom.get(b)
                        : Number.MAX_SAFE_INTEGER;


                return (
                    ordenA
                    - ordenB
                );
            }
        );


    try {
        const datos = await post(
            'api/encolar.php',
            {
                ids: idsOrdenados,
            }
        );

        const cantidad =
            datos.agregadas.length;

        seleccionados.clear();

        toast(
            cantidad === 1
                ? '1 archivo agregado a la cola.'
                : `${cantidad} archivos agregados a la cola.`
        );

        if (datos.omitidas.length) {
            toast(
                `${datos.omitidas.length} archivo(s) fueron omitidos.`,
                'error'
            );
        }

        await cargarTodo();

    } catch (error) {
        toast(
            `No se pudo encolar: ${error.message}`,
            'error'
        );

    } finally {
        boton.textContent =
            'Agregar a la cola';

        actualizarSeleccion();
    }
}


/* =========================================================
   CTPS3 11C - GESTOR PKG

   Reutiliza:
   - datosPs3.archivos
   - api/ps3.php
   - api/accion.php
   - post()
   - toast()
   - bytes()
   - modal global
   - cargarTodo()
   ========================================================= */


function crearNodoPkg(
    etiqueta,
    clase = '',
    texto = ''
) {
    const elemento =
        document.createElement(
            etiqueta
        );

    if (clase) {
        elemento.className =
            clase;
    }

    if (texto !== '') {
        elemento.textContent =
            texto;
    }

    return elemento;
}


function analizarNombrePkg(
    nombre
) {
    const original =
        String(
            nombre || ''
        ).trim();


    const multiparte =
        original.match(
            /^(.*?)(?:[\s_-]+)(?:Pt|Part)\s*(\d+)\.pkg$/i
        );


    if (multiparte) {
        return {
            nombre:
                original,

            base:
                multiparte[1].trim(),

            parte:
                Number(
                    multiparte[2]
                ),

            multiparte:
                true,
        };
    }


    return {
        nombre:
            original,

        base:
            original
                .replace(
                    /\.pkg$/i,
                    ''
                )
                .trim(),

        parte:
            null,

        multiparte:
            false,
    };
}


function agruparPkgPs3(
    archivos
) {
    const grupos =
        new Map();


    for (const archivo of archivos) {

        const analisis =
            analizarNombrePkg(
                archivo.nombre
            );


        const clave =
            analisis.base
                .toLocaleLowerCase(
                    'es'
                );


        if (!grupos.has(clave)) {

            grupos.set(
                clave,
                {
                    titulo:
                        analisis.base,

                    multiparte:
                        analisis.multiparte,

                    archivos:
                        [],
                }
            );
        }


        const grupo =
            grupos.get(
                clave
            );


        grupo.multiparte =
            grupo.multiparte
            || analisis.multiparte;


        grupo.archivos.push({
            ...archivo,

            parte_pkg:
                analisis.parte,
        });
    }


    const salida = [
        ...grupos.values(),
    ];


    for (const grupo of salida) {

        grupo.archivos.sort(
            (a, b) => {

                const parteA =
                    Number.isInteger(
                        a.parte_pkg
                    )
                        ? a.parte_pkg
                        : Number.MAX_SAFE_INTEGER;

                const parteB =
                    Number.isInteger(
                        b.parte_pkg
                    )
                        ? b.parte_pkg
                        : Number.MAX_SAFE_INTEGER;


                if (parteA !== parteB) {
                    return (
                        parteA
                        - parteB
                    );
                }


                return String(
                    a.nombre
                ).localeCompare(
                    String(
                        b.nombre
                    ),
                    'es',
                    {
                        numeric:
                            true,

                        sensitivity:
                            'base',
                    }
                );
            }
        );
    }


    salida.sort(
        (a, b) =>
            a.titulo.localeCompare(
                b.titulo,
                'es',
                {
                    numeric:
                        true,

                    sensitivity:
                        'base',
                }
            )
    );


    return salida;
}


function estadoOperacionPkgUi(
    archivo
) {
    if (
        archivo.operacion_pkg
        === 'INSTALAR_PKG'
    ) {
        return (
            archivo.operacion_pkg_estado
            === 'PROCESANDO'
                ? 'Instalando en PS3…'
                : 'Instalación pendiente'
        );
    }


    if (
        archivo.operacion_pkg
        === 'ELIMINAR_PKG'
    ) {
        return (
            archivo.operacion_pkg_estado
            === 'PROCESANDO'
                ? 'Eliminando…'
                : 'Eliminación pendiente'
        );
    }


    return null;
}


function textoPreflightInstalacionPkg(
    preflight,
    multipart = false
) {
    const estado =
        String(
            preflight?.estado || ''
        );

    const libre =
        Number(
            preflight?.hdd_libre_bytes_aprox
            || 0
        );

    const requerido =
        Number(
            preflight?.requerido_total_bytes
            || 0
        );

    const faltante =
        Number(
            preflight?.faltante_bytes
            || 0
        );

    const temporal =
        Number(
            preflight?.temporal_maximo_bytes
            || 0
        );

    const margen =
        Number(
            preflight?.margen_seguridad_bytes
            || 0
        );

    if (
        preflight?.verificado === true
        && estado === 'OK'
    ) {
        let texto =
            (
                'Capacidad: cabe estimado. '
                + `Requiere aprox. ${bytes(requerido)}; `
                + `libres ${bytes(libre)}; `
                + `margen ${bytes(margen)}.`
            );

        if (
            multipart
            && temporal > 0
        ) {
            texto +=
                (
                    ' Multipart incluye temporal máximo '
                    + `${bytes(temporal)}.`
                );
        }

        return {
            permitido: true,
            texto,
        };
    }

    if (
        preflight?.verificado === true
        && estado === 'INSUFICIENTE'
    ) {
        return {
            permitido: false,
            texto:
                (
                    'Capacidad: no cabe. '
                    + `Requiere aprox. ${bytes(requerido)}; `
                    + `libres ${bytes(libre)}; `
                    + `faltan aprox. ${bytes(faltante)} `
                    + `manteniendo ${bytes(margen)} de margen.`
                ),
        };
    }

    return {
        permitido: true,
        texto:
            (
                'Capacidad: no verificable ahora. '
                + 'Podés dejar la instalación pendiente; '
                + 'el worker no la iniciará hasta validar '
                + 'lectura HDD fresca y espacio suficiente.'
            ),
    };
}


async function obtenerPreflightInstalacionPkg(
    archivoRemotoId
) {
    const datos = await post(
        'api/accion.php',
        {
            accion:
                'INSTALAR_PKG',

            archivo_remoto_id:
                archivoRemotoId,

            preflight:
                true,
        }
    );

    if (
        datos?.modo
        !== 'PREFLIGHT_INSTALACION_PKG'
        || !datos?.preflight
    ) {
        throw new Error(
            'PREFLIGHT_INSTALACION_PKG_INVALIDO'
        );
    }

    return datos.preflight;
}


async function obtenerPreflightInstalacionLotePkg(
    ids
) {
    const datos = await post(
        'api/accion.php',
        {
            accion:
                'INSTALAR_LOTE_PKG',

            archivos_remotos_ids:
                ids,

            preflight:
                true,
        }
    );

    if (
        datos?.modo
        !== 'PREFLIGHT_INSTALACION_PKG'
        || !datos?.preflight
    ) {
        throw new Error(
            'PREFLIGHT_INSTALACION_PKG_INVALIDO'
        );
    }

    return datos.preflight;
}


async function confirmarAccionPkg(
    archivo,
    accion
) {
    const id =
        Number(
            archivo.id
        );


    if (
        !Number.isInteger(id)
        || id < 1
    ) {
        toast(
            'PKG remoto inválido.',
            'error'
        );

        return;
    }


    let estadoCapacidad = null;


    if (
        accion
        === 'INSTALAR_PKG'
    ) {
        try {
            const preflight =
                await obtenerPreflightInstalacionPkg(
                    id
                );

            estadoCapacidad =
                textoPreflightInstalacionPkg(
                    preflight,
                    false
                );

        } catch (error) {
            toast(
                (
                    'No se pudo comprobar capacidad: '
                    + error.message
                ),
                'error'
            );

            return;
        }


        if (!estadoCapacidad.permitido) {
            toast(
                estadoCapacidad.texto,
                'error'
            );

            return;
        }
    }


    confirmacionActual = {
        tipo:
            'pkg',

        archivoRemotoId:
            id,

        accion,

        nombre:
            String(
                archivo.nombre || ''
            ),

        tamanoBytes:
            Number(
                archivo.tamano_bytes || 0
            ),
    };


    if (
        accion
        === 'CONFIRMAR_INSTALACION_PKG'
    ) {
        $('modalTitulo').textContent =
            'Confirmar instalación';

        $('modalTexto').textContent =
            (
                'Confirmá únicamente si la PS3 '
                + 'ya terminó de instalar '
                + `"${archivo.nombre}".`
            );

    } else if (
        accion
        === 'MARCAR_FALLO_INSTALACION_PKG'
    ) {
        $('modalTitulo').textContent =
            'Marcar instalación fallida';

        $('modalTexto').textContent =
            (
                'CTPS3 liberará esta operación '
                + 'como fallida. El PKG se conserva.'
            );

    } else if (
        accion
        === 'INSTALAR_PKG'
    ) {
        $('modalTitulo').textContent =
            'Instalar PKG';

        $('modalTexto').textContent =
            (
                'Se solicitará a webMAN instalar '
                + `"${archivo.nombre}". `
                + 'El instalador permanecerá en '
                + '/dev_hdd0/packages después de '
                + 'la solicitud. '
                + (
                    estadoCapacidad?.texto
                    || ''
                )
            );

    } else {

        $('modalTitulo').textContent =
            'Eliminar instalador PKG';

        $('modalTexto').textContent =
            (
                'Se eliminará definitivamente '
                + `"${archivo.nombre}" de `
                + '/dev_hdd0/packages. '
                + `Liberará aproximadamente ${
                    bytes(
                        archivo.tamano_bytes
                    )
                }. `
                + 'Esta acción no desinstala '
                + 'el contenido del juego que '
                + 'ya haya sido instalado.'
            );
    }


    $('modal').classList.remove(
        'modal--oculto'
    );
}


async function ejecutarAccionPkg(
    archivoRemotoId,
    accion
) {
    try {

        const resolucion =
            accion
            === 'CONFIRMAR_INSTALACION_PKG'
                ? 'CONFIRMAR_FINALIZADA'
                : (
                    accion
                    === 'MARCAR_FALLO_INSTALACION_PKG'
                        ? 'MARCAR_FALLO'
                        : null
                );


        const datos =
            await post(
                'api/accion.php',
                {
                    archivo_remoto_id:
                        archivoRemotoId,

                    accion:
                        resolucion
                            ? 'INSTALAR_PKG'
                            : accion,

                    ...(resolucion
                        ? {resolucion}
                        : {}),
                }
            );


        if (
            accion
            === 'CONFIRMAR_INSTALACION_PKG'
        ) {
            toast(
                'Instalación confirmada como finalizada.'
            );

        } else if (
            accion
            === 'MARCAR_FALLO_INSTALACION_PKG'
        ) {
            toast(
                'Instalación marcada como fallida.',
                'error'
            );

        } else if (
            accion
            === 'INSTALAR_PKG'
        ) {
            toast(
                'Instalación iniciada en la PS3.'
            );

        } else {
            toast(
                'Solicitud de eliminación enviada.'
            );
        }


        setTimeout(
            cargarTodo,
            350
        );


        return datos;


    } catch (error) {

        const mensajes = {

            PKG_OPERACION_PENDIENTE:
                (
                    'Ese PKG ya tiene una '
                    + 'operación pendiente.'
                ),

            PKG_NO_DISPONIBLE:
                (
                    'El PKG ya no está '
                    + 'disponible en la PS3.'
                ),

            PKG_RUTA_NO_PERMITIDA:
                (
                    'La ruta del PKG fue '
                    + 'bloqueada por seguridad.'
                ),

            ESPACIO_INSUFICIENTE_INSTALACION_PKG:
                (
                    'El espacio disponible cambió '
                    + 'y ya no alcanza para instalar.'
                ),
        };


        toast(
            mensajes[
                error.message
            ]
            || (
                'No se pudo ejecutar '
                + 'la operación: '
                + error.message
            ),
            'error'
        );
    }
}



function validarGrupoPkgMultiparte(
    grupo
) {
    const archivos =
        Array.isArray(
            grupo?.archivos
        )
            ? grupo.archivos
            : [];


    if (
        !grupo?.multiparte
        || archivos.length < 2
    ) {
        return {
            valido:
                false,

            motivo:
                'El grupo no es multipart válido.',

            ids:
                [],
        };
    }


    const ids = [];
    const partes = [];


    for (const archivo of archivos) {

        const id =
            Number(
                archivo.id
            );

        const parte =
            Number(
                archivo.parte_pkg
            );


        if (
            !Number.isInteger(id)
            || id < 1
            || !Number.isInteger(parte)
            || parte < 1
        ) {
            return {
                valido:
                    false,

                motivo:
                    'Una parte tiene datos inválidos.',

                ids:
                    [],
            };
        }


        ids.push(
            id
        );

        partes.push(
            parte
        );
    }


    if (
        new Set(ids).size
        !== ids.length
    ) {
        return {
            valido:
                false,

            motivo:
                'Hay archivos duplicados.',

            ids:
                [],
        };
    }


    if (
        new Set(partes).size
        !== partes.length
    ) {
        return {
            valido:
                false,

            motivo:
                'Hay números de parte duplicados.',

            ids:
                [],
        };
    }


    const secuenciaCorrecta =
        partes.every(
            (
                parte,
                indice
            ) =>
                parte
                === indice + 1
        );


    if (!secuenciaCorrecta) {
        return {
            valido:
                false,

            motivo:
                (
                    'La secuencia multipart '
                    + 'está incompleta.'
                ),

            ids:
                [],
        };
    }


    const totalBytes =
        archivos.reduce(
            (
                total,
                archivo
            ) =>
                total
                + Number(
                    archivo.tamano_bytes
                    || 0
                ),
            0
        );


    return {
        valido:
            true,

        motivo:
            null,

        ids,

        totalPartes:
            archivos.length,

        totalBytes,
    };
}



async function confirmarAccionLotePkg(
    grupo,
    validacion
) {
    if (
        !validacion?.valido
        || !Array.isArray(
            validacion.ids
        )
        || validacion.ids.length < 2
    ) {
        toast(
            (
                validacion?.motivo
                || 'Lote multipart inválido.'
            ),
            'error'
        );

        return;
    }


    let estadoCapacidad = null;


    try {
        const preflight =
            await obtenerPreflightInstalacionLotePkg(
                [
                    ...validacion.ids,
                ]
            );

        estadoCapacidad =
            textoPreflightInstalacionPkg(
                preflight,
                true
            );

    } catch (error) {
        toast(
            (
                'No se pudo comprobar capacidad del lote: '
                + error.message
            ),
            'error'
        );

        return;
    }


    if (!estadoCapacidad.permitido) {
        toast(
            estadoCapacidad.texto,
            'error'
        );

        return;
    }


    confirmacionActual = {
        tipo:
            'pkg_lote',

        archivosRemotosIds:
            [
                ...validacion.ids,
            ],

        titulo:
            String(
                grupo?.titulo || ''
            ),

        totalPartes:
            Number(
                validacion.totalPartes
            ),

        tamanoBytes:
            Number(
                validacion.totalBytes
            ),
    };


    $('modalTitulo').textContent =
        'Instalar todas las partes';


    $('modalTexto').textContent =
        (
            `Se instalarán automáticamente ${
                validacion.totalPartes
            } partes de `
            + `"${grupo.titulo}" en orden. `
            + `Tamaño total: ${
                bytes(
                    validacion.totalBytes
                )
            }. `
            + 'Los PKG originales permanecerán '
            + 'en /dev_hdd0/packages. '
            + 'La PS3 debe permanecer encendida '
            + 'con HEN/webMAN hasta finalizar. '
            + (
                estadoCapacidad?.texto
                || ''
            )
        );


    $('modal').classList.remove(
        'modal--oculto'
    );
}



async function ejecutarAccionLotePkg(
    archivosRemotosIds
) {
    try {

        const ids =
            (
                Array.isArray(
                    archivosRemotosIds
                )
                    ? archivosRemotosIds
                    : []
            ).map(
                (valor) =>
                    Number(
                        valor
                    )
            );


        if (
            ids.length < 2
            || ids.some(
                (id) =>
                    !Number.isInteger(id)
                    || id < 1
            )
            || new Set(ids).size
                !== ids.length
        ) {
            throw new Error(
                'LOTE_PKG_ARCHIVOS_INVALIDOS'
            );
        }


        const datos =
            await post(
                'api/accion.php',
                {
                    accion:
                        'INSTALAR_LOTE_PKG',

                    archivos_remotos_ids:
                        ids,
                }
            );


        const total =
            Number(
                datos?.total_partes
                || ids.length
            );


        toast(
            (
                'Instalación multipart iniciada: '
                + `${total} partes.`
            )
        );


        setTimeout(
            cargarTodo,
            350
        );


        return datos;


    } catch (error) {

        const mensajes = {

            PKG_OPERACION_ACTIVA:
                (
                    'Ya existe otra operación '
                    + 'PKG activa.'
                ),

            PKG_LOTE_ACTIVO:
                (
                    'Ya existe una instalación '
                    + 'multipart activa.'
                ),

            LOTE_PKG_ARCHIVOS_INVALIDOS:
                (
                    'El conjunto multipart '
                    + 'no es válido.'
                ),

            LOTE_PKG_ARCHIVO_INVALIDO:
                (
                    'Una de las partes '
                    + 'no es válida.'
                ),

            LOTE_PKG_ARCHIVOS_DUPLICADOS:
                (
                    'El conjunto contiene '
                    + 'archivos duplicados.'
                ),

            LOTE_PKG_SECUENCIA_INCOMPLETA:
                (
                    'La secuencia multipart '
                    + 'está incompleta.'
                ),

            PKG_NO_DISPONIBLE:
                (
                    'Una de las partes ya no '
                    + 'está disponible.'
                ),

            PKG_RUTA_NO_PERMITIDA:
                (
                    'Una ruta PKG fue bloqueada '
                    + 'por seguridad.'
                ),

            ESPACIO_INSUFICIENTE_INSTALACION_PKG:
                (
                    'El espacio disponible cambió '
                    + 'y ya no alcanza para el lote.'
                ),
        };


        toast(
            mensajes[
                error.message
            ]
            || (
                'No se pudo iniciar el lote: '
                + error.message
            ),
            'error'
        );
    }
}


function crearFilaPkg(
    archivo,
    estadoPs3
) {
    const fila =
        crearNodoPkg(
            'div',
            'gestor-pkg__archivo'
        );


    const informacion =
        crearNodoPkg(
            'div',
            'gestor-pkg__archivo-info'
        );


    const titulo =
        crearNodoPkg(
            'strong',
            'gestor-pkg__archivo-titulo',

            Number.isInteger(
                archivo.parte_pkg
            )
                ? `Parte ${archivo.parte_pkg}`
                : archivo.nombre
        );


    informacion.appendChild(
        titulo
    );


    if (
        Number.isInteger(
            archivo.parte_pkg
        )
    ) {
        informacion.appendChild(
            crearNodoPkg(
                'span',
                'gestor-pkg__archivo-nombre',
                archivo.nombre
            )
        );
    }


    const lateral =
        crearNodoPkg(
            'div',
            'gestor-pkg__archivo-lateral'
        );


    lateral.appendChild(
        crearNodoPkg(
            'span',
            'gestor-pkg__tamano',
            bytes(
                archivo.tamano_bytes
            )
        )
    );


    const operacion =
        estadoOperacionPkgUi(
            archivo
        );


    if (operacion) {

        lateral.appendChild(
            crearNodoPkg(
                'span',
                'gestor-pkg__operacion',
                operacion
            )
        );

    } else {

        const acciones =
            crearNodoPkg(
                'div',
                'gestor-pkg__acciones'
            );


        const botonInstalar =
            crearNodoPkg(
                'button',
                (
                    'boton boton--mini '
                    + 'boton--secundario'
                ),
                'Instalar'
            );


        botonInstalar.type =
            'button';


        const puedeInstalar =
            estadoPs3.lista
            && estadoPs3.ftp
            && estadoPs3.http;


        botonInstalar.disabled =
            !puedeInstalar;


        if (!puedeInstalar) {
            botonInstalar.title =
                (
                    'La PS3 debe estar lista '
                    + 'con HEN/webMAN y HTTP '
                    + 'disponible.'
                );
        }


        botonInstalar.addEventListener(
            'click',
            () => {
                confirmarAccionPkg(
                    archivo,
                    'INSTALAR_PKG'
                );
            }
        );


        const botonEliminar =
            crearNodoPkg(
                'button',
                (
                    'boton boton--mini '
                    + 'boton--peligro'
                ),
                'Eliminar'
            );


        botonEliminar.type =
            'button';


        const puedeEliminar =
            estadoPs3.lista
            && estadoPs3.ftp;


        botonEliminar.disabled =
            !puedeEliminar;


        if (!puedeEliminar) {
            botonEliminar.title =
                (
                    'La PS3 debe estar lista '
                    + 'con HEN/webMAN y FTP '
                    + 'disponible.'
                );
        }


        botonEliminar.addEventListener(
            'click',
            () => {
                confirmarAccionPkg(
                    archivo,
                    'ELIMINAR_PKG'
                );
            }
        );


        acciones.append(
            botonInstalar,
            botonEliminar
        );


        lateral.appendChild(
            acciones
        );
    }


    if (
        archivo.operacion_pkg
        === 'INSTALAR_PKG'
        && archivo.operacion_pkg_estado
            === 'PROCESANDO'
        && !archivo.controlada_por_lote
    ) {
        const accionesFin =
            crearNodoPkg(
                'div',
                'gestor-pkg__acciones'
            );

        const confirmar =
            crearNodoPkg(
                'button',
                'boton boton--mini boton--secundario',
                'Confirmar finalizada'
            );

        confirmar.type = 'button';

        confirmar.addEventListener(
            'click',
            () => confirmarAccionPkg(
                archivo,
                'CONFIRMAR_INSTALACION_PKG'
            )
        );


        const fallo =
            crearNodoPkg(
                'button',
                'boton boton--mini boton--peligro',
                'Marcar fallo'
            );

        fallo.type = 'button';

        fallo.addEventListener(
            'click',
            () => confirmarAccionPkg(
                archivo,
                'MARCAR_FALLO_INSTALACION_PKG'
            )
        );


        accionesFin.append(
            confirmar,
            fallo
        );

        lateral.appendChild(
            accionesFin
        );
    }


    fila.append(
        informacion,
        lateral
    );


    return fila;
}


function renderGestorPkg(
    datosPs3
) {
    const biblioteca =
        $('biblioteca');


    /*
     * app.js se carga en todas las vistas.
     * El gestor solamente aparece en Biblioteca.
     */
    if (!biblioteca) {
        return;
    }


    const archivos =
        (
            Array.isArray(
                datosPs3?.archivos
            )
                ? datosPs3.archivos
                : []
        ).filter(
            (archivo) => {

                const nombre =
                    String(
                        archivo.nombre || ''
                    );

                const ruta =
                    String(
                        archivo.ruta_remota || ''
                    );


                return (
                    ruta.startsWith(
                        '/dev_hdd0/packages/'
                    )

                    && nombre
                        .toLowerCase()
                        .endsWith(
                            '.pkg'
                        )
                );
            }
        );


    const ps3 =
        datosPs3?.ps3
        || {};


    const estadoPs3 = {

        lista:
            ps3.estado_operativo
            === 'LISTA',

        ftp:
            Boolean(
                ps3.ftp_disponible
            ),

        http:
            Boolean(
                ps3.http_disponible
            ),
    };


    const ancla =
        biblioteca.closest(
            '.panel'
        )
        || biblioteca;


    let panel =
        $('gestorPkg');


    if (!panel) {

        panel =
            document.createElement(
                'section'
            );

        panel.id =
            'gestorPkg';

        panel.className =
            'panel gestor-pkg';


        ancla.insertAdjacentElement(
            'afterend',
            panel
        );
    }


    panel.replaceChildren();


    const cabecera =
        crearNodoPkg(
            'div',
            'gestor-pkg__cabecera'
        );


    const cabeceraTexto =
        crearNodoPkg(
            'div',
            'gestor-pkg__cabecera-texto'
        );


    cabeceraTexto.append(
        crearNodoPkg(
            'span',
            'subtitulo',
            'GESTOR PKG'
        ),

        crearNodoPkg(
            'h3',
            '',
            'Instaladores en la PS3'
        )
    );


    const totalBytes =
        archivos.reduce(
            (
                acumulado,
                archivo
            ) =>
                acumulado
                + Number(
                    archivo.tamano_bytes || 0
                ),
            0
        );


    const resumen =
        crearNodoPkg(
            'div',
            'gestor-pkg__resumen'
        );


    resumen.append(
        crearNodoPkg(
            'strong',
            '',
            String(
                archivos.length
            )
        ),

        crearNodoPkg(
            'span',
            '',
            archivos.length === 1
                ? 'PKG disponible'
                : 'PKG disponibles'
        ),

        crearNodoPkg(
            'span',
            'gestor-pkg__separador',
            '·'
        ),

        crearNodoPkg(
            'strong',
            '',
            bytes(
                totalBytes
            )
        )
    );


    const estado =
        crearNodoPkg(
            'span',
            (
                'gestor-pkg__estado '
                + (
                    estadoPs3.lista
                        ? 'gestor-pkg__estado--ok'
                        : 'gestor-pkg__estado--off'
                )
            ),

            estadoPs3.lista
                ? 'PS3 lista'
                : 'PS3 no disponible'
        );


    const ladoCabecera =
        crearNodoPkg(
            'div',
            'gestor-pkg__cabecera-lado'
        );


    ladoCabecera.append(
        estado,
        resumen
    );


    cabecera.append(
        cabeceraTexto,
        ladoCabecera
    );


    panel.appendChild(
        cabecera
    );


    panel.appendChild(
        crearNodoPkg(
            'p',
            'gestor-pkg__aviso',
            (
                'Instalar conserva el archivo PKG. '
                + 'Eliminar borra únicamente el '
                + 'instalador de /dev_hdd0/packages; '
                + 'no desinstala el juego.'
            )
        )
    );


    if (!archivos.length) {

        panel.appendChild(
            crearNodoPkg(
                'div',
                'vacio',
                (
                    'No hay instaladores PKG '
                    + 'disponibles en la PS3.'
                )
            )
        );

        return;
    }


    const grupos =
        agruparPkgPs3(
            archivos
        );


    const contenedor =
        crearNodoPkg(
            'div',
            'gestor-pkg__grupos'
        );


    const hayOperacionPkgActiva =
        archivos.some(
            (archivo) =>
                Boolean(
                    archivo.operacion_pkg
                )
                && (
                    archivo.operacion_pkg_estado
                    === 'PENDIENTE'
                    || archivo.operacion_pkg_estado
                        === 'PROCESANDO'
                )
        );


    for (const grupo of grupos) {

        const tarjeta =
            crearNodoPkg(
                'article',
                'gestor-pkg__grupo'
            );


        const cabeceraGrupo =
            crearNodoPkg(
                'div',
                'gestor-pkg__grupo-cabecera'
            );


        const tituloGrupo =
            crearNodoPkg(
                'div',
                'gestor-pkg__grupo-titulo'
            );


        tituloGrupo.appendChild(
            crearNodoPkg(
                'strong',
                '',
                grupo.titulo
            )
        );


        const totalGrupo =
            grupo.archivos.reduce(
                (
                    acumulado,
                    archivo
                ) =>
                    acumulado
                    + Number(
                        archivo.tamano_bytes || 0
                    ),
                0
            );


        tituloGrupo.appendChild(
            crearNodoPkg(
                'span',
                '',
                (
                    grupo.archivos.length === 1
                        ? '1 instalador'
                        : (
                            `${grupo.archivos.length} `
                            + (
                                grupo.multiparte
                                    ? 'partes'
                                    : 'instaladores'
                            )
                        )
                )
                + ` · ${bytes(totalGrupo)}`
            )
        );


        cabeceraGrupo.appendChild(
            tituloGrupo
        );


        if (grupo.multiparte) {

            const controlesGrupo =
                crearNodoPkg(
                    'div',
                    'gestor-pkg__acciones'
                );


            controlesGrupo.appendChild(
                crearNodoPkg(
                    'span',
                    'gestor-pkg__badge',
                    'MULTIPARTE'
                )
            );


            const validacionLote =
                validarGrupoPkgMultiparte(
                    grupo
                );


            if (validacionLote.valido) {

                const botonLote =
                    crearNodoPkg(
                        'button',
                        (
                            'boton boton--mini '
                            + 'boton--secundario'
                        ),
                        'Instalar todas las partes'
                    );


                botonLote.type =
                    'button';


                const puedeInstalarLote =
                    estadoPs3.lista
                    && estadoPs3.ftp
                    && estadoPs3.http
                    && !hayOperacionPkgActiva;


                botonLote.disabled =
                    !puedeInstalarLote;


                if (!puedeInstalarLote) {

                    botonLote.title =
                        hayOperacionPkgActiva
                            ? (
                                'Esperá a que termine '
                                + 'la operación PKG activa.'
                            )
                            : (
                                'La PS3 debe estar lista '
                                + 'con HEN/webMAN, FTP '
                                + 'y HTTP disponibles.'
                            );
                }


                botonLote.addEventListener(
                    'click',
                    () => {
                        confirmarAccionLotePkg(
                            grupo,
                            validacionLote
                        );
                    }
                );


                controlesGrupo.appendChild(
                    botonLote
                );
            }


            cabeceraGrupo.appendChild(
                controlesGrupo
            );
        }


        tarjeta.appendChild(
            cabeceraGrupo
        );


        const lista =
            crearNodoPkg(
                'div',
                'gestor-pkg__lista'
            );


        for (
            const archivo
            of grupo.archivos
        ) {

            lista.appendChild(
                crearFilaPkg(
                    archivo,
                    estadoPs3
                )
            );
        }


        tarjeta.appendChild(
            lista
        );


        contenedor.appendChild(
            tarjeta
        );
    }


    panel.appendChild(
        contenedor
    );
}


let confirmacionActual = null;

function confirmarAccion(
    transferenciaId,
    accion
) {
    if (accion !== 'CANCELAR') {
        ejecutarAccion(
            transferenciaId,
            accion
        );

        return;
    }

    confirmacionActual = {
        transferenciaId,
        accion,
    };

    $('modalTitulo').textContent =
        'Cancelar transferencia';

    $('modalTexto').textContent =
        'Se detendrá la transferencia, pero '
        + 'el archivo parcial permanecerá en '
        + 'la PS3 para evitar borrar datos '
        + 'por accidente.';

    $('modal').classList.remove(
        'modal--oculto'
    );
}

function cerrarModal() {
    confirmacionActual = null;

    $('modal').classList.add(
        'modal--oculto'
    );
}

async function ejecutarAccion(
    transferenciaId,
    accion
) {
    try {
        await post(
            'api/accion.php',
            {
                transferencia_id:
                    transferenciaId,

                accion,
            }
        );

        toast(
            `Orden ${accion.toLowerCase()} enviada.`
        );

        setTimeout(
            cargarTodo,
            350
        );

    } catch (error) {
        toast(
            `Error: ${error.message}`,
            'error'
        );
    }
}

$('botonEncolar')
    ?.addEventListener(
        'click',
        encolarSeleccion
    );

$('modalCancelar')
    .addEventListener(
        'click',
        cerrarModal
    );

$('modalAceptar')
    .addEventListener(
        'click',
        async () => {
            if (!confirmacionActual) {
                return;
            }

            const actual =
                confirmacionActual;

            cerrarModal();

            if (
                actual.tipo
                === 'pkg_lote'
            ) {
                await ejecutarAccionLotePkg(
                    actual.archivosRemotosIds
                );

                return;
            }


            if (
                actual.tipo
                === 'pkg'
            ) {
                await ejecutarAccionPkg(
                    actual.archivoRemotoId,
                    actual.accion
                );

                return;
            }

            await ejecutarAccion(
                actual.transferenciaId,
                actual.accion
            );
        }
    );

document
    .querySelector('.modal__fondo')
    .addEventListener(
        'click',
        cerrarModal
    );

cargarTodo();

setInterval(
    cargarTodo,
    2000
);
