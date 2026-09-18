# Arquitectura de CTPS3

## Objetivo

CTPS3 separa la interfaz de usuario de la ejecución de operaciones sobre la consola.

La aplicación web se ocupa de presentar información y registrar solicitudes. Un worker independiente procesa las operaciones persistidas y utiliza transporte FTP para comunicarse con la PS3.

## Capas

### Interfaz web

El directorio `app/` contiene:

- vistas PHP;
- endpoints API;
- JavaScript del navegador;
- hojas de estilo;
- componentes de navegación y presentación.

### Persistencia

SQLite funciona como punto de coordinación entre la aplicación web, el worker y las herramientas auxiliares.

El repositorio publica únicamente el schema.

### Worker

`worker/worker.py` concentra la ejecución operativa.

Entre sus responsabilidades se encuentran el procesamiento de cola, control de operaciones, seguimiento de transferencias y coordinación con el transporte FTP.

### Herramientas

`tools/` contiene procesos auxiliares para:

- catalogación;
- inventario;
- inspección de la consola;
- enriquecimiento de biblioteca;
- clasificación de almacenamiento;
- auditoría.

### Automatización

Las units de `systemd/` permiten ejecutar el worker y actualizar inventarios o catálogos de forma desacoplada de la aplicación web.

## Flujo general

1. El usuario interactúa con la aplicación web.
2. La aplicación consulta o registra información en SQLite.
3. El worker obtiene operaciones pendientes.
4. El worker valida y prepara la operación.
5. El transporte FTP realiza la transferencia correspondiente.
6. El estado resultante vuelve a persistirse.
7. La interfaz refleja el nuevo estado.

## Separación de responsabilidades

La arquitectura evita concentrar toda la lógica en el proceso web.

Esto permite:

- desacoplar operaciones largas de las peticiones HTTP;
- recuperar operaciones después de interrupciones;
- mantener observabilidad sobre la cola;
- limitar la superficie operativa expuesta al navegador;
- ejecutar tareas periódicas independientemente de la interfaz.

## Publicación sanitizada

Las rutas de producción fueron reemplazadas por ubicaciones genéricas como:

- `/opt/ctps3`;
- `/var/lib/ctps3`;
- `/var/log/ctps3`;
- `/srv/ps3`.

Las direcciones privadas reales y los datos productivos no forman parte del repositorio.
