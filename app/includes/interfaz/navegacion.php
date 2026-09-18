<nav
    class="navegacion-ctps3"
    aria-label="Secciones del Centro de Transferencias"
>
    <div class="navegacion-ctps3__interior">

        <?php foreach (
            $vistasCtps3
            as $clave => $configuracion
        ): ?>

            <a
                class="navegacion-ctps3__item<?= $vista === $clave
                    ? ' navegacion-ctps3__item--activo'
                    : ''
                ?>"
                href="?vista=<?= htmlspecialchars(
                    $clave,
                    ENT_QUOTES,
                    'UTF-8'
                ) ?>"
                <?= $vista === $clave
                    ? 'aria-current="page"'
                    : ''
                ?>
            >
                <span
                    class="navegacion-ctps3__indicador"
                    aria-hidden="true"
                ></span>

                <span class="navegacion-ctps3__texto">
                    <strong>
                        <?= htmlspecialchars(
                            $configuracion['titulo'],
                            ENT_QUOTES,
                            'UTF-8'
                        ) ?>
                    </strong>

                    <small>
                        <?= htmlspecialchars(
                            $configuracion['descripcion_nav'],
                            ENT_QUOTES,
                            'UTF-8'
                        ) ?>
                    </small>
                </span>
            </a>

        <?php endforeach; ?>

    </div>
</nav>
