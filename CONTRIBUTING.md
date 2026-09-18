# Contribuciones

Centro Transferencias PS3 es una publicación sanitizada de una aplicación utilizada originalmente en un entorno doméstico privado.

## Requisitos

Los cambios no deben introducir:

- credenciales, contraseñas, tokens o claves privadas;
- direcciones IP privadas reales;
- rutas internas del entorno productivo original;
- bases SQLite productivas;
- logs, auditorías o snapshots operativos;
- archivos PKG, ISO o contenido de juegos;
- datos personales.

La configuración pública debe utilizar únicamente valores de ejemplo.

## Validación

Antes de realizar un commit deben mantenerse válidos:

- PHP 8.2;
- Python;
- JavaScript;
- shell scripts;
- JSON;
- schema SQLite;
- units systemd.

El workflow `Validate` ejecuta automáticamente las principales comprobaciones en cada push y pull request dirigido a `main`.

## Commits

Los commits deben representar un cambio lógico concreto y utilizar mensajes breves y descriptivos.

Ejemplos:

- `fix: validate transfer destination before enqueue`
- `docs: clarify worker architecture`
- `ci: update validation workflow`
- `refactor: isolate storage inventory logic`

## Seguridad

Los problemas de seguridad o exposiciones accidentales de información sensible deben tratarse según `SECURITY.md`.
