# Centro Transferencias PS3

Centro Transferencias PS3 (CTPS3) es una aplicación web para administrar, observar y automatizar transferencias entre un servidor doméstico y una consola PlayStation 3 mediante una arquitectura desacoplada.

El proyecto combina una interfaz PHP/JavaScript, una base SQLite, un worker Python, transporte FTP, herramientas de inventario y servicios systemd.

Esta versión del repositorio fue preparada específicamente para publicación: no contiene credenciales, direcciones privadas reales, bases productivas, registros, juegos, imágenes de disco, paquetes de instalación ni datos personales.

## Componentes

- **Aplicación web:** vistas, APIs y recursos frontend desarrollados en PHP, JavaScript y CSS.
- **Worker:** proceso Python encargado de ejecutar y supervisar operaciones de transferencia.
- **SQLite:** persistencia de cola, inventario, estados y metadatos.
- **Herramientas:** catálogo, inventario, inspección remota, almacenamiento y auditoría.
- **systemd:** servicios y temporizadores para ejecución automática.
- **FTP:** transporte entre servidor y consola.
- **webMAN MOD:** integración utilizada para inspección y operaciones compatibles en la consola.

## Arquitectura

<pre>
 Navegador
     |
     v
 Aplicación PHP
     |
     +------> Consultas / estado / inventario
     |
     v
   SQLite
     |
     v
 Worker Python
     |
     v
 lftp / FTP
     |
     v
 PlayStation 3

 Herramientas auxiliares
     |
     +------> catálogo
     +------> inventario
     +------> almacenamiento
     +------> auditoría
</pre>

La interfaz web no necesita ejecutar directamente las operaciones de transferencia. Las solicitudes se registran y son procesadas por el worker, manteniendo separada la presentación de la ejecución operativa.

La descripción técnica ampliada está disponible en `docs/ARCHITECTURE.md`.

## Estructura

<pre>
centro-transferencias-ps3/
├── app/          Aplicación PHP y frontend
├── worker/       Worker Python
├── tools/        Herramientas operativas
├── config/       Configuración de ejemplo
├── database/     Schema SQLite sin datos
├── systemd/      Units sanitizadas
├── docs/         Documentación técnica
└── .github/      Automatización CI
</pre>

## Configuración

La configuración productiva no forma parte del repositorio.

`config/config.example.ini` contiene únicamente valores de ejemplo. Antes de utilizar el proyecto debe crearse una configuración local adaptada al entorno.

La dirección `192.0.2.10`, cuando aparece en ejemplos, pertenece al rango reservado para documentación y no representa una máquina real.

## Base de datos

`database/schema.sql` contiene solamente la estructura de la base SQLite.

No contiene filas productivas ni historial operativo.

## Validación

El repositorio incorpora GitHub Actions para validar automáticamente:

- sintaxis PHP 8.2;
- sintaxis Python;
- sintaxis JavaScript con Node.js;
- scripts shell;
- archivos JSON;
- recreación del schema SQLite.

## Seguridad y privacidad

La publicación excluye deliberadamente:

- contraseñas y credenciales FTP;
- claves, tokens y secretos;
- direcciones IP privadas reales;
- rutas internas del servidor original;
- bases SQLite productivas;
- logs y auditorías operativas;
- respaldos e históricos;
- contenido de juegos, PKG, ISO u otros archivos multimedia.

Consulte `SECURITY.md` para información adicional.

## Alcance

CTPS3 documenta una solución personal de automatización e integración para hardware propio. El repositorio contiene el software de gestión y su arquitectura, no contenido distribuido mediante el sistema.

## Autor

Desarrollado por ProgDeveloperr.
