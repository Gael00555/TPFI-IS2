# TPFI IS2: Patrones Singleton, Proxy y Observer sobre AWS

Trabajo Práctico Final Integrador de Ingeniería de Software II (UADER-FCyT).

Servidor TCP que centraliza el acceso a datos corporativos en AWS DynamoDB
(tablas `CorporateData` y `CorporateLog`) y dos clientes: uno que pide
`get`, `set` o `list`, y otro que se suscribe para recibir en tiempo real
cada modificación.

## Patrones de diseño

| Patrón | Clase | Función |
|---|---|---|
| Singleton | `CorporateDataSingleton`, `CorporateLogSingleton` | Una única conexión por tabla |
| Proxy | `UpdateProxy` | Valida y controla las actualizaciones (`set`) |
| Observer | `EventPublisher` | Notifica a los clientes suscriptos cada cambio |

## Requisitos

- Python 3.12 o superior
- AWS CLI instalado y configurado (`aws configure`, región `us-east-1`)
- Acceso a las tablas `CorporateData` y `CorporateLog`

## Instalación

```
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

## Uso

Servidor:

```
python singletonproxyobserver.py {-p=puerto} {-v}
```

Cliente de `get` / `set` / `list`:

```
python singletonclient.py "-i=input.json" {"-o=output.json"} {-v}
```

Cliente suscriptor (queda escuchando, reconecta cada 30 s si se corta):

```
python observerclient.py {"-s=host"} {"-p=puerto"} {"-o=output.json"} {-v}
```

En PowerShell conviene escribir los argumentos con `=` entre comillas.

Formato de `input.json`:

```json
{"UUID": "MI-PC", "ID": "MI-REGISTRO", "ACTION": "set", "sede": "FCyT"}
{"UUID": "MI-PC", "ID": "MI-REGISTRO", "ACTION": "get"}
{"UUID": "MI-PC", "ACTION": "list"}
```

## Calidad y tests

```
pytest --cov=src --cov-report=term-missing
ruff check .
black --check .
mypy src
pyright src
bandit -r src
pdoc -o site spo_core
```

Cobertura mínima exigida: 85 %.

## Estructura

```
src/spo_core/
    patterns/      singleton.py, proxy.py, observer.py
    db.py          acceso a DynamoDB
    service.py     fachada que une los tres patrones
    protocol.py    mensajes JSON por socket
    server_core.py, server_app.py     servidor
    client_core.py, observer_core.py  clientes
    cli_args.py    argumentos de línea de comandos
tests/             tests unitarios y de aceptación
singletonproxyobserver.py, singletonclient.py, observerclient.py
```

## CI/CD y documentación

Cada push a `main` ejecuta en GitHub Actions todos los controles de calidad y
los tests, y publica la documentación generada con pdoc:
https://gael00555.github.io/TPFI-IS2/

## Licencia

MIT. Ver `LICENSE`.