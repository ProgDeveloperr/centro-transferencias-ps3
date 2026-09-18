<main class="contenedor">

<?php
require __DIR__
    . '/../includes/interfaz/aviso-worker.php';
?>

<section class="vista-cabecera">
    <div>
        <span class="subtitulo">
            DIAGNÓSTICO
        </span>

        <h2>
            Sistema
        </h2>

        <p>
            Telemetría FTP real, salud y mecanismos de resiliencia.
        </p>
    </div>
</section>

<section
        id="telemetriaFtpPanel"
        class="panel telemetria-ftp"
    >

        <div class="telemetria-ftp__cabecera">

            <div>
                <span class="subtitulo">
                    TELEMETRÍA FTP REAL
                </span>

                <h2>
                    Estadísticas de red
                </h2>

                <p>
                    Métricas calculadas únicamente
                    desde sesiones lftp registradas
                    por el worker 1.5.0.
                </p>
            </div>

            <div class="telemetria-ftp__periodo">
                <span class="telemetria-ftp__punto"></span>

                <span id="telemetriaFtpDesde">
                    Consultando periodo…
                </span>

                <span>
                    ·
                </span>

                <strong id="telemetriaFtpVersion">
                    Motor —
                </strong>
            </div>

        </div>


        <div class="telemetria-ftp__metricas">

            <article class="telemetria-ftp__metrica">

                <span>
                    Enviado por FTP
                </span>

                <strong id="telemetriaFtpBytes">
                    —
                </strong>

                <small>
                    Payload real agregado
                    a archivos remotos
                </small>

            </article>


            <article class="telemetria-ftp__metrica">

                <span>
                    Datos validados
                </span>

                <strong id="telemetriaFtpValidados">
                    —
                </strong>

                <small>
                    COMPLETADO + YA_EXISTE
                    dentro del periodo
                </small>

            </article>


            <article class="telemetria-ftp__metrica">

                <span>
                    Reutilizado / evitado
                </span>

                <strong id="telemetriaFtpReutilizados">
                    —
                </strong>

                <small id="telemetriaFtpReutilizadosDetalle">
                    —
                </small>

            </article>


            <article class="telemetria-ftp__metrica">

                <span>
                    Velocidad FTP media
                </span>

                <strong id="telemetriaFtpVelocidad">
                    —
                </strong>

                <small>
                    Media ponderada por
                    duración real de sesiones
                </small>

            </article>

        </div>


        <div class="telemetria-ftp__chips">

            <span class="telemetria-ftp__chip">
                Sesiones
                <strong id="telemetriaFtpSesionesTotal">
                    —
                </strong>
            </span>

            <span class="telemetria-ftp__chip">
                Reanudadas
                <strong id="telemetriaFtpReanudadas">
                    —
                </strong>
            </span>

            <span class="telemetria-ftp__chip">
                Tiempo FTP
                <strong id="telemetriaFtpTiempo">
                    —
                </strong>
            </span>

            <span class="telemetria-ftp__chip">
                FTP no validado
                <strong id="telemetriaFtpNoValidado">
                    —
                </strong>
            </span>

            <span class="telemetria-ftp__chip">
                Sesiones problemáticas
                <strong id="telemetriaFtpErrores">
                    —
                </strong>
            </span>

            <span class="telemetria-ftp__chip">
                Transferencias del periodo
                <strong id="telemetriaFtpTransferenciasTotal">
                    —
                </strong>
            </span>

        </div>


        <div class="telemetria-ftp__columnas">

            <section class="telemetria-ftp__subpanel">

                <div class="telemetria-ftp__subcabecera">

                    <h3>
                        Historial de transferencias
                    </h3>

                    <span>
                        Desde 8B
                    </span>

                </div>

                <div
                    id="telemetriaFtpTransferencias"
                    class="telemetria-ftp__lista"
                >
                    <div class="telemetria-ftp__vacio">
                        Consultando…
                    </div>
                </div>

            </section>


            <section class="telemetria-ftp__subpanel">

                <div class="telemetria-ftp__subcabecera">

                    <h3>
                        Sesiones FTP recientes
                    </h3>

                    <span>
                        Hasta 30
                    </span>

                </div>

                <div
                    id="telemetriaFtpSesiones"
                    class="telemetria-ftp__lista"
                >
                    <div class="telemetria-ftp__vacio">
                        Consultando…
                    </div>
                </div>

            </section>

        </div>

    </section>

<section
        id="resilienciaPanel"
        class="panel resiliencia-panel"
    >

        <div
            class="resiliencia-panel__cabecera"
        >

            <div>

                <span class="subtitulo">
                    RESILIENCIA OPERATIVA
                </span>

                <h2>
                    Salud y recuperaciones
                </h2>

                <p>
                    Supervisión del worker,
                    sesiones FTP y recuperación
                    automática frente a
                    interrupciones inesperadas.
                </p>

            </div>


            <div>
                <div
                    id="resilienciaEstadoGeneral"
                    class="
                        resiliencia-panel__estado-general
                        resiliencia-panel__estado-general--saludable
                    "
                >
                    CONSULTANDO
                </div>

                <div
                    id="resilienciaActualizado"
                    style="
                        margin-top: 7px;
                        text-align: right;
                        font-size: 10px;
                        opacity: .55;
                    "
                >
                    —
                </div>
            </div>

        </div>


        <div
            class="resiliencia-panel__metricas"
        >

            <article
                class="resiliencia-panel__metrica"
            >
                <span>
                    Worker
                </span>

                <strong
                    id="resilienciaWorker"
                >
                    —
                </strong>

                <small
                    id="resilienciaWorkerDetalle"
                >
                    —
                </small>
            </article>


            <article
                class="resiliencia-panel__metrica"
            >
                <span>
                    Heartbeat
                </span>

                <strong
                    id="resilienciaHeartbeat"
                >
                    —
                </strong>

                <small
                    id="resilienciaHeartbeatDetalle"
                >
                    —
                </small>
            </article>


            <article
                class="resiliencia-panel__metrica"
            >
                <span>
                    En ejecución
                </span>

                <strong
                    id="resilienciaEjecucion"
                >
                    —
                </strong>

                <small
                    id="resilienciaEjecucionDetalle"
                >
                    —
                </small>
            </article>


            <article
                class="resiliencia-panel__metrica"
            >
                <span>
                    Sesiones FTP
                </span>

                <strong
                    id="resilienciaSesiones"
                >
                    —
                </strong>

                <small
                    id="resilienciaSesionesDetalle"
                >
                    —
                </small>
            </article>


            <article
                class="resiliencia-panel__metrica"
            >
                <span>
                    Recuperaciones
                </span>

                <strong
                    id="resilienciaRecuperadas"
                >
                    —
                </strong>

                <small
                    id="resilienciaRecuperadasDetalle"
                >
                    —
                </small>
            </article>


            <article
                class="resiliencia-panel__metrica"
            >
                <span>
                    Pendientes
                </span>

                <strong
                    id="resilienciaPendientes"
                >
                    —
                </strong>

                <small
                    id="resilienciaPendientesDetalle"
                >
                    —
                </small>
            </article>

        </div>


        <div
            class="resiliencia-panel__metricas"
            style="
                grid-template-columns:
                    repeat(
                        2,
                        minmax(0, 1fr)
                    );
            "
        >

            <article
                class="resiliencia-panel__metrica"
            >
                <span>
                    Sesiones huérfanas recuperadas
                </span>

                <strong
                    id="resilienciaHuerfanas"
                >
                    —
                </strong>

                <small
                    id="resilienciaHuerfanasDetalle"
                >
                    —
                </small>
            </article>


            <article
                class="resiliencia-panel__metrica"
            >
                <span>
                    Validación de resiliencia
                </span>

                <strong>
                    9C REAL
                </strong>

                <small>
                    SIGKILL + reconciliación +
                    reanudación verificadas
                </small>
            </article>

        </div>


        <div
            class="resiliencia-panel__columnas"
        >

            <section
                class="resiliencia-panel__subpanel"
            >

                <div
                    class="resiliencia-panel__subcabecera"
                >
                    <h3>
                        Comprobaciones automáticas
                    </h3>

                    <span>
                        cada 10 segundos
                    </span>
                </div>


                <div
                    id="resilienciaChecks"
                    class="resiliencia-panel__lista"
                >
                    <div
                        class="resiliencia-panel__vacio"
                    >
                        Consultando…
                    </div>
                </div>

            </section>


            <section
                class="resiliencia-panel__subpanel"
            >

                <div
                    class="resiliencia-panel__subcabecera"
                >
                    <h3>
                        Historial de recuperaciones
                    </h3>

                    <span>
                        últimas 25
                    </span>
                </div>


                <div
                    id="resilienciaRecuperaciones"
                    class="resiliencia-panel__lista"
                >
                    <div
                        class="resiliencia-panel__vacio"
                    >
                        Consultando…
                    </div>
                </div>

            </section>

        </div>

    </section>

<!-- OPS-1 · Estado consolidado CTPS3 -->
<link
    rel="stylesheet"
    href="recursos/css/sistema-ops.css?v=1.0.0"
>

<link
    rel="stylesheet"
    href="recursos/css/sistema-ops-historial.css?v=1.0.0"
>

<link
    rel="stylesheet"
    href="recursos/css/sistema-telemetria-listas.css?v=1.0.0"
>


<section
    class="panel ops-estado"
    id="opsEstadoCtps3"
    aria-labelledby="opsEstadoCtps3Titulo"
>
    <div class="ops-estado__cabecera">
        <div>
            <p class="ops-estado__eyebrow">
                CONSOLIDACIÓN
            </p>

            <h2
                class="ops-estado__titulo"
                id="opsEstadoCtps3Titulo"
            >
                Estado de CTPS3
            </h2>

            <p class="ops-estado__descripcion">
                Release, última auditoría,
                backup consolidado y estado
                operativo certificado.
            </p>
        </div>

        <div class="ops-estado__acciones">
            <span
                class="ops-estado__badge"
                data-ops="estado"
            >
                CONSULTANDO
            </span>

            <button
                class="ops-estado__boton"
                type="button"
                data-ops="actualizar"
            >
                Actualizar
            </button>
        </div>
    </div>

    <p
        class="ops-estado__mensaje"
        data-ops="cargando"
    >
        Leyendo el último estado consolidado…
    </p>

    <p
        class="ops-estado__mensaje ops-estado__error"
        data-ops="error"
        hidden
    ></p>

    <div
        class="ops-estado__grid"
        data-ops="contenido"
        hidden
    >
        <article class="ops-estado__card">
            <h3>Última auditoría</h3>

            <div class="ops-estado__contadores">
                <div class="ops-estado__contador">
                    <strong data-ops="audit-pass">—</strong>
                    <span>PASS</span>
                </div>

                <div class="ops-estado__contador">
                    <strong data-ops="audit-warn">—</strong>
                    <span>WARN</span>
                </div>

                <div class="ops-estado__contador">
                    <strong data-ops="audit-fail">—</strong>
                    <span>FAIL</span>
                </div>
            </div>

            <div class="ops-estado__dato">
                <span>Fecha</span>
                <strong data-ops="audit-fecha">—</strong>
            </div>

            <div class="ops-estado__dato">
                <span>Auditor</span>
                <strong data-ops="auditor-version">—</strong>
            </div>
        </article>

        <article class="ops-estado__card">
            <h3>Release</h3>

            <div class="ops-estado__dato">
                <span>Activa</span>
                <strong data-ops="release">—</strong>
            </div>

            <div class="ops-estado__dato">
                <span>Fecha</span>
                <strong data-ops="release-fecha">—</strong>
            </div>

            <div class="ops-estado__dato">
                <span>Schema</span>
                <strong data-ops="schema">—</strong>
            </div>
        </article>

        <article class="ops-estado__card">
            <h3>Base de datos</h3>

            <div class="ops-estado__dato">
                <span>Integridad</span>
                <strong data-ops="integrity">—</strong>
            </div>

            <div class="ops-estado__dato">
                <span>FK inválidas</span>
                <strong data-ops="fk">—</strong>
            </div>

            <div class="ops-estado__dato">
                <span>Fuente</span>
                <strong>Release certificada</strong>
            </div>
        </article>

        <article class="ops-estado__card">
            <h3>Backup consolidado</h3>

            <div class="ops-estado__dato">
                <span>Fecha</span>
                <strong data-ops="backup-fecha">—</strong>
            </div>

            <div class="ops-estado__dato">
                <span>Archivos</span>
                <strong data-ops="backup-files">—</strong>
            </div>

            <div class="ops-estado__dato">
                <span>Tamaño</span>
                <strong data-ops="backup-bytes">—</strong>
            </div>
        </article>

        <article class="ops-estado__card">
            <h3>Automatización</h3>

            <div class="ops-estado__dato">
                <span>Inventario PS3</span>
                <strong data-ops="timer-inventario">—</strong>
            </div>

            <div class="ops-estado__dato">
                <span>Catálogo PS3</span>
                <strong data-ops="timer-catalogo">—</strong>
            </div>

            <div class="ops-estado__dato">
                <span>Auditoría sin PS3</span>
                <strong data-ops="ps3-audit">—</strong>
            </div>
        </article>

        <article class="ops-estado__card">
            <h3>Eliminación</h3>

            <div class="ops-estado__dato">
                <span>E2E real</span>
                <strong data-ops="e2e">—</strong>
            </div>

            <div class="ops-estado__dato">
                <span>UI / backend</span>
                <strong>CERTIFICADO</strong>
            </div>

            <div class="ops-estado__dato">
                <span>PS3 requerida ahora</span>
                <strong>NO</strong>
            </div>
        </article>
    </div>

    <p class="ops-estado__pie">
        Estado generado:
        <strong data-ops="generado">—</strong>.
        El botón Actualizar vuelve a leer el último
        resultado disponible; no ejecuta una nueva auditoría.
    </p>
</section>

<section
    class="panel ops-historial"
    id="opsHistorialAuditorias"
    aria-labelledby="opsHistorialTitulo"
>
    <div class="ops-historial__cabecera">
        <div>
            <span class="subtitulo">
                AUDITORÍA
            </span>

            <h2 id="opsHistorialTitulo">
                Historial de auditorías
            </h2>

            <p>
                Últimos resultados del auditor general
                read-only de CTPS3.
            </p>
        </div>

        <div class="ops-historial__resumen">
            <span class="ops-historial__chip">
                Total
                <strong data-ops-historial="total">—</strong>
            </span>

            <span class="ops-historial__chip">
                Saludables
                <strong data-ops-historial="saludables">—</strong>
            </span>

            <span class="ops-historial__chip">
                Incidencias
                <strong data-ops-historial="incidencias">—</strong>
            </span>
        </div>
    </div>

    <div class="ops-historial__tabla-wrap">
        <table class="ops-historial__tabla">
            <thead>
                <tr>
                    <th>Fecha</th>
                    <th>Estado</th>
                    <th>PASS</th>
                    <th>WARN</th>
                    <th>FAIL</th>
                    <th>Auditor</th>
                    <th>Release</th>
                </tr>
            </thead>

            <tbody data-ops-historial="filas">
                <tr>
                    <td
                        class="ops-historial__vacio"
                        colspan="7"
                    >
                        Consultando historial…
                    </td>
                </tr>
            </tbody>
        </table>
    </div>

    <p class="ops-historial__pie">
        <span data-ops-historial="estado">
            Consultando…
        </span>.
        Se muestran como máximo 10 registros en pantalla.
    </p>
</section>

</main>

<script
    src="recursos/js/sistema-ops.js?v=1.0.0"
    defer
></script>

<script
    src="recursos/js/sistema-ops-historial.js?v=1.0.0"
    defer
></script>

<script
    src="recursos/js/sistema-telemetria-listas.js?v=1.0.0"
    defer
></script>
