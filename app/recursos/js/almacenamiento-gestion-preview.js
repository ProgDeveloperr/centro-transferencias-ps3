(() => {
    'use strict';

    if (document.body?.dataset?.vista !== 'almacenamiento') {
        return;
    }

    const API_ALM = 'api/almacenamiento.php';
    const API_DATOS = 'api/eliminar-datos-asociados.php';
    const CSRF = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    const $ = (id) => document.getElementById(id);

    let inventario = [];
    let juegoActual = null;
    let previewActual = null;
    let previewSeleccionClave = '';
    let eliminacionId = null;
    let solicitando = false;
    let seguimientoTimer = null;
    let secuenciaPreview = 0;

    const escapar = (valor) => String(valor ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');

    const bytes = (valor) => {
        const n = Number(valor || 0);
        if (n < 1024) return `${n} B`;

        const unidades = ['KiB', 'MiB', 'GiB', 'TiB'];
        let x = n;
        let i = -1;

        do {
            x /= 1024;
            i++;
        } while (x >= 1024 && i < unidades.length - 1);

        return `${x.toFixed(x >= 10 ? 1 : 2)} ${unidades[i]}`;
    };

    const elegible = (item) => (
        item?.clase === 'VINCULADO'
        && item?.confianza === 'ALTA'
        && item?.posible_huerfano === false
        && item?.eliminacion_automatica_permitida === false
        && item?.politica === 'NO_LIMPIEZA_AUTOMATICA;GESTIONAR_COMO_DATO_ASOCIADO'
        && ['DATOS_GAME', 'CACHE_GAME'].includes(item?.subtipo)
        && Number(item?.juego_id) > 0
        && Number(item?.juego_componente_id) > 0
    );

    const limpiarSeguimiento = () => {
        if (seguimientoTimer !== null) {
            window.clearTimeout(seguimientoTimer);
            seguimientoTimer = null;
        }
    };

    const errorApi = (respuesta, datos) => {
        const error = new Error(
            datos?.error
            || `HTTP ${respuesta.status}`
        );

        error.codigo = datos?.error || null;
        error.datos = datos || null;
        error.http = respuesta.status;

        return error;
    };

    const postDatos = async (accion, payload) => {
        if (!CSRF) {
            throw new Error('CSRF_NO_DISPONIBLE');
        }

        const respuesta = await fetch(API_DATOS, {
            method: 'POST',
            cache: 'no-store',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-CSRF-Token': CSRF,
            },
            body: JSON.stringify({
                accion,
                ...payload,
            }),
        });

        let datos = null;

        try {
            datos = await respuesta.json();
        } catch {
            throw new Error(`HTTP ${respuesta.status}`);
        }

        if (!respuesta.ok || datos?.ok !== true) {
            throw errorApi(respuesta, datos);
        }

        return datos;
    };

    const postPreview = (juegoId, ids) => postDatos(
        'PREVISUALIZAR',
        {
            juego_id: Number(juegoId),
            componentes_ids: ids,
        }
    );

    const postSolicitar = (juegoId, ids, confirmacion) => postDatos(
        'SOLICITAR',
        {
            juego_id: Number(juegoId),
            componentes_ids: ids,
            confirmacion,
        }
    );

    const postEstado = (id) => postDatos(
        'ESTADO',
        {
            eliminacion_id: Number(id),
        }
    );

    const cargarInventario = async () => {
        const respuesta = await fetch(
            API_ALM,
            {
                cache: 'no-store',
                headers: {
                    'Accept': 'application/json',
                },
            }
        );

        const datos = await respuesta.json();

        if (
            !respuesta.ok
            || datos?.ok !== true
            || !Array.isArray(datos.elementos)
        ) {
            throw new Error(
                datos?.error
                || `HTTP ${respuesta.status}`
            );
        }

        inventario = datos.elementos;
    };

    const idsSeleccionados = () => [
        ...document.querySelectorAll(
            '[data-alm-preview-componente]:checked'
        ),
    ]
        .map(
            (nodo) => Number(
                nodo.dataset.almPreviewComponente
            )
        )
        .filter(
            (id) => Number.isInteger(id) && id > 0
        );

    const claveSeleccion = (ids) => [...ids]
        .map((id) => Number(id))
        .filter((id) => Number.isInteger(id) && id > 0)
        .sort((a, b) => a - b)
        .join(',');

    const bloquearSeleccion = (bloquear) => {
        document.querySelectorAll(
            '[data-alm-preview-componente]'
        ).forEach(
            (nodo) => {
                nodo.disabled = bloquear;
            }
        );
    };

    const actualizarBotonSolicitar = () => {
        const input = $('almGestionConfirmacion');
        const boton = $('almGestionSolicitar');

        if (!input || !boton) {
            return;
        }

        const esperada = String(
            previewActual?.confirmacion_esperada
            || ''
        );

        const ids = idsSeleccionados();

        boton.disabled = (
            solicitando
            || !previewActual
            || !esperada
            || input.value.trim() !== esperada
            || ids.length < 1
            || claveSeleccion(ids) !== previewSeleccionClave
        );
    };

    const resetAccion = () => {
        limpiarSeguimiento();

        previewActual = null;
        previewSeleccionClave = '';
        eliminacionId = null;
        solicitando = false;
        secuenciaPreview += 1;

        const accion = $('almGestionAccion');
        const esperada = $('almGestionConfirmacionEsperada');
        const input = $('almGestionConfirmacion');
        const estado = $('almGestionSolicitarEstado');
        const boton = $('almGestionSolicitar');

        if (accion) accion.hidden = true;
        if (esperada) esperada.textContent = '—';

        if (input) {
            input.value = '';
            input.disabled = false;
        }

        if (estado) {
            estado.textContent = '';
            estado.className = 'alm-gestion-accion__estado';
        }

        if (boton) {
            boton.disabled = true;
        }

        bloquearSeleccion(false);
    };

    const cerrar = () => {
        limpiarSeguimiento();

        const dialogo = $('almGestionPreview');

        if (
            dialogo?.open
            && typeof dialogo.close === 'function'
        ) {
            dialogo.close();
        } else {
            dialogo?.removeAttribute('open');
        }

        juegoActual = null;
        resetAccion();
    };

    const mostrarErrorAccion = (error) => {
        const estado = $('almGestionSolicitarEstado');

        if (!estado) {
            return;
        }

        let mensaje = (
            error?.message
            || String(error)
        );

        if (error?.codigo === 'RECONCILIACION_PENDIENTE') {
            mensaje = (
                'Existe una eliminación anterior pendiente '
                + 'de reconciliación con un inventario posterior.'
            );
        } else if (error?.codigo === 'CONFIRMACION_INVALIDA') {
            mensaje = 'La frase de confirmación no coincide.';
        } else if (error?.codigo === 'ELIMINACION_YA_ACTIVA') {
            mensaje = 'Ya existe una eliminación activa para este juego.';
        }

        estado.textContent = mensaje;
        estado.className = (
            'alm-gestion-accion__estado '
            + 'alm-gestion-accion__estado--error'
        );
    };

    const pintarEstadoOperacion = (operacion) => {
        const estado = $('almGestionSolicitarEstado');

        if (!estado) {
            return;
        }

        const valor = String(
            operacion?.estado
            || ''
        );

        if (valor === 'PENDIENTE') {
            estado.textContent = (
                'Solicitud encolada. Esperando al worker…'
            );

            estado.className = (
                'alm-gestion-accion__estado '
                + 'alm-gestion-accion__estado--aviso'
            );

            return;
        }

        if (valor === 'PROCESANDO') {
            estado.textContent = (
                'Eliminación en proceso. '
                + 'No cierres la PS3 ni interrumpas la red.'
            );

            estado.className = (
                'alm-gestion-accion__estado '
                + 'alm-gestion-accion__estado--aviso'
            );

            return;
        }

        if (valor === 'COMPLETADO') {
            estado.textContent = (
                'Eliminación confirmada por el worker. '
                + 'El próximo inventario reconciliará la vista.'
            );

            estado.className = (
                'alm-gestion-accion__estado '
                + 'alm-gestion-accion__estado--ok'
            );

            return;
        }

        if (valor === 'ERROR') {
            estado.textContent = (
                'La operación terminó con error. '
                + 'No vuelvas a solicitar hasta que un inventario '
                + 'posterior confirme el estado real.'
            );

            estado.className = (
                'alm-gestion-accion__estado '
                + 'alm-gestion-accion__estado--error'
            );

            return;
        }

        estado.textContent = (
            operacion?.mensaje
            || `Estado: ${valor || 'desconocido'}`
        );

        estado.className = (
            'alm-gestion-accion__estado '
            + 'alm-gestion-accion__estado--aviso'
        );
    };

    const consultarEstado = async () => {
        if (!eliminacionId) {
            return;
        }

        try {
            const datos = await postEstado(
                eliminacionId
            );

            const operacion = datos?.eliminacion;

            if (!operacion) {
                throw new Error(
                    'ESTADO_SIN_OPERACION'
                );
            }

            pintarEstadoOperacion(
                operacion
            );

            const valor = String(
                operacion.estado
                || ''
            );

            if (
                valor === 'PENDIENTE'
                || valor === 'PROCESANDO'
            ) {
                seguimientoTimer = window.setTimeout(
                    consultarEstado,
                    1200
                );

                return;
            }

            solicitando = false;
            bloquearSeleccion(true);

            const input = $('almGestionConfirmacion');

            if (input) {
                input.disabled = true;
            }

            actualizarBotonSolicitar();

        } catch (error) {
            solicitando = false;
            mostrarErrorAccion(error);
            actualizarBotonSolicitar();
        }
    };

    const renderPreview = (datos, claveSolicitada) => {
        const p = datos.preview;
        const componentes = Array.isArray(
            p?.componentes
        )
            ? p.componentes
            : [];

        const claveBackend = claveSeleccion(
            componentes.map(
                (c) => Number(c?.juego_componente_id)
            )
        );

        if (
            !claveSolicitada
            || claveBackend !== claveSolicitada
        ) {
            throw new Error(
                'PREVIEW_COMPONENTES_NO_COINCIDEN'
            );
        }

        const resultado = $('almGestionPreviewResultado');
        const estado = $('almGestionPreviewEstado');
        const titulo = $('almGestionPreviewTitulo');
        const accion = $('almGestionAccion');
        const esperada = $('almGestionConfirmacionEsperada');
        const input = $('almGestionConfirmacion');

        previewActual = p;
        previewSeleccionClave = claveSolicitada;

        if (resultado) {
            resultado.innerHTML = `
                <div class="alm-gestion-preview__resumen">
                    <div>
                        <span>Juego</span>
                        <strong>${escapar(p?.nombre || '—')}</strong>
                    </div>
                    <div>
                        <span>Componentes</span>
                        <strong>${escapar(p?.cantidad_componentes ?? componentes.length)}</strong>
                    </div>
                    <div>
                        <span>Espacio recuperable</span>
                        <strong>${escapar(bytes(p?.tamano_liberable_bytes))}</strong>
                    </div>
                </div>

                <div class="alm-gestion-preview__rutas">
                    ${componentes.map((c) => `
                        <article>
                            <div>
                                <strong>${escapar(c.tipo)}</strong>
                                <span>${escapar(bytes(c.tamano_bytes))}</span>
                            </div>
                            <code>${escapar(c.ruta_remota)}</code>
                        </article>
                    `).join('')}
                </div>

                <div class="alm-gestion-preview__frase">
                    <span>Frase exacta requerida:</span>
                    <code>${escapar(p?.confirmacion_esperada || '—')}</code>
                </div>
            `;
        }

        if (titulo) {
            titulo.textContent = (
                `Datos asociados · ${p?.nombre || 'Juego'}`
            );
        }

        if (estado) {
            estado.textContent = (
                'Previsualización validada. '
                + 'Revisá componentes, rutas y espacio antes de continuar.'
            );
        }

        if (accion) {
            accion.hidden = false;
        }

        if (esperada) {
            esperada.textContent = (
                p?.confirmacion_esperada
                || '—'
            );
        }

        if (input) {
            input.value = '';
            input.disabled = false;
        }

        actualizarBotonSolicitar();

        if (
            datos?.eliminacion_activa?.id
        ) {
            eliminacionId = Number(
                datos.eliminacion_activa.id
            );

            bloquearSeleccion(true);

            if (input) {
                input.disabled = true;
            }

            pintarEstadoOperacion(
                datos.eliminacion_activa
            );

            seguimientoTimer = window.setTimeout(
                consultarEstado,
                250
            );
        }
    };

    const actualizar = async () => {
        const estado = $('almGestionPreviewEstado');
        const resultado = $('almGestionPreviewResultado');
        const ids = idsSeleccionados();

        resetAccion();

        if (!ids.length) {
            if (estado) {
                estado.textContent = (
                    'Seleccioná al menos un componente.'
                );
            }

            if (resultado) {
                resultado.textContent = (
                    'Sin previsualización.'
                );
            }

            return;
        }

        const claveSolicitada = claveSeleccion(ids);
        const secuencia = ++secuenciaPreview;

        if (estado) {
            estado.textContent = (
                'Validando selección con el backend…'
            );
        }

        try {
            const datos = await postPreview(
                juegoActual,
                ids
            );

            if (
                secuencia !== secuenciaPreview
                || claveSeleccion(idsSeleccionados())
                    !== claveSolicitada
            ) {
                return;
            }

            renderPreview(
                datos,
                claveSolicitada
            );

        } catch (error) {
            if (estado) {
                estado.textContent = (
                    `No se pudo validar: ${
                        error?.message
                        || String(error)
                    }`
                );
            }

            if (resultado) {
                resultado.textContent = (
                    'Previsualización no disponible.'
                );
            }

            mostrarErrorAccion(error);
        }
    };

    const solicitar = async () => {
        if (
            solicitando
            || !previewActual
        ) {
            return;
        }

        const input = $('almGestionConfirmacion');
        const ids = idsSeleccionados();

        if (
            !input
            || !ids.length
        ) {
            return;
        }

        const claveActual = claveSeleccion(ids);

        if (
            !previewSeleccionClave
            || claveActual !== previewSeleccionClave
        ) {
            await actualizar();
            return;
        }

        const confirmacion = input.value.trim();

        if (
            confirmacion
            !== previewActual.confirmacion_esperada
        ) {
            mostrarErrorAccion(
                Object.assign(
                    new Error('CONFIRMACION_INVALIDA'),
                    {
                        codigo: 'CONFIRMACION_INVALIDA',
                    }
                )
            );

            actualizarBotonSolicitar();
            return;
        }

        solicitando = true;
        limpiarSeguimiento();
        bloquearSeleccion(true);
        input.disabled = true;
        actualizarBotonSolicitar();

        const estado = $('almGestionSolicitarEstado');

        if (estado) {
            estado.textContent = (
                'Revalidando y enviando solicitud…'
            );

            estado.className = (
                'alm-gestion-accion__estado '
                + 'alm-gestion-accion__estado--aviso'
            );
        }

        try {
            const datos = await postSolicitar(
                juegoActual,
                ids,
                confirmacion
            );

            eliminacionId = Number(
                datos.eliminacion_id
            );

            if (
                !Number.isInteger(eliminacionId)
                || eliminacionId < 1
            ) {
                throw new Error(
                    'ELIMINACION_ID_INVALIDO'
                );
            }

            pintarEstadoOperacion({
                estado: datos.estado,
                mensaje: datos.mensaje,
            });

            seguimientoTimer = window.setTimeout(
                consultarEstado,
                250
            );

        } catch (error) {
            solicitando = false;
            bloquearSeleccion(false);
            input.disabled = false;
            mostrarErrorAccion(error);
            actualizarBotonSolicitar();
        }
    };

    const abrir = async (
        juegoId,
        componenteInicial
    ) => {
        const dialogo = $('almGestionPreview');
        const opciones = $('almGestionPreviewOpciones');
        const titulo = $('almGestionPreviewTitulo');
        const estado = $('almGestionPreviewEstado');

        juegoActual = Number(juegoId);
        resetAccion();

        if (estado) {
            estado.textContent = (
                'Cargando datos asociados…'
            );
        }

        if (!inventario.length) {
            await cargarInventario();
        }

        const items = inventario
            .filter(
                (item) => (
                    elegible(item)
                    && Number(item.juego_id) === juegoActual
                )
            )
            .sort(
                (a, b) => (
                    Number(b.tamano_bytes)
                    - Number(a.tamano_bytes)
                )
            );

        if (!items.length) {
            throw new Error(
                'SIN_COMPONENTES_ELEGIBLES'
            );
        }

        if (titulo) {
            titulo.textContent = (
                'Datos asociados'
            );
        }

        if (opciones) {
            opciones.innerHTML = items.map((item) => `
                <label class="alm-gestion-preview__opcion">
                    <input
                        type="checkbox"
                        data-alm-preview-componente="${Number(item.juego_componente_id)}"
                        ${Number(item.juego_componente_id) === Number(componenteInicial) ? 'checked' : ''}
                    >
                    <span>
                        <strong>${escapar(item.subtipo)} · ${escapar(bytes(item.tamano_bytes))}</strong>
                        <code>${escapar(item.ruta_remota)}</code>
                    </span>
                </label>
            `).join('');

            opciones.querySelectorAll(
                '[data-alm-preview-componente]'
            ).forEach(
                (input) => input.addEventListener(
                    'change',
                    actualizar
                )
            );
        }

        if (
            typeof dialogo?.showModal
            === 'function'
        ) {
            dialogo.showModal();
        } else {
            dialogo?.setAttribute(
                'open',
                ''
            );
        }

        await actualizar();
    };

    $('almLista')?.addEventListener(
        'click',
        async (evento) => {
            const boton = evento.target.closest(
                '[data-alm-preview]'
            );

            if (!boton) {
                return;
            }

            const juegoId = Number(
                boton.dataset.juegoId
            );

            const componenteId = Number(
                boton.dataset.componenteId
            );

            if (
                !Number.isInteger(juegoId)
                || juegoId < 1
                || !Number.isInteger(componenteId)
                || componenteId < 1
            ) {
                return;
            }

            try {
                await abrir(
                    juegoId,
                    componenteId
                );
            } catch (error) {
                console.error(
                    'CTPS3 ESP-4F solicitar:',
                    error
                );
            }
        }
    );

    $('almGestionConfirmacion')?.addEventListener(
        'input',
        actualizarBotonSolicitar
    );

    $('almGestionSolicitar')?.addEventListener(
        'click',
        solicitar
    );

    $('almGestionPreview')?.addEventListener(
        'click',
        (evento) => {
            if (
                evento.target === $('almGestionPreview')
                || evento.target.closest(
                    '[data-alm-preview-cerrar]'
                )
            ) {
                cerrar();
            }
        }
    );

    $('almGestionPreview')?.addEventListener(
        'close',
        () => {
            limpiarSeguimiento();
        }
    );
})();
