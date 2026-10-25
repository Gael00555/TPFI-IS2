# Changelog

Todos los cambios notables de este proyecto se registran en este archivo.

## [1.0.0] - 2026-10-25

### Agregado
- Patrones Singleton (`SingletonMeta`), Proxy (`UpdateProxy`) y Observer (`EventPublisher`).
- Acceso a DynamoDB con dos singletons: `CorporateDataSingleton` y `CorporateLogSingleton`.
- `CorporateService`: fachada con `get`, `set`, `list` y `subscribe`, con auditoría en `CorporateLog`.
- Protocolo de mensajes JSON delimitados por salto de línea sobre sockets TCP.
- Servidor multihilo (`singletonproxyobserver.py`) con detección de doble arranque.
- Clientes `singletonclient.py` y `observerclient.py` (con reconexión cada 30 s).
- Suite de 87 tests (unitarios y de aceptación) con cobertura superior al 85 %.
- Controles de calidad en CI: ruff (incluye PEP257), black, mypy, pyright, bandit y pytest.
- Documentación automática con pdoc, publicada en GitHub Pages.

### Corregido
- Serialización de `Decimal` (números de DynamoDB) al armar respuestas JSON.
- Timeout de lectura que cortaba al observer a los 5 segundos sin novedades.
- Corte abrupto del socket, tratado ahora como conexión perdida.
- El servidor cierra la conexión tras responder `get` y `list`, como pide la consigna.
- Nombre del campo `idreq`, unificado según la Tabla 1 del enunciado.

## [0.1.0] - 2026-09-24

### Agregado
- Estructura inicial del proyecto generada con CookieCutter.
- Configuración de ruff, black, mypy, pyright y bandit.