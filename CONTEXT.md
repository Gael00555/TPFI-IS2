# Uso de herramientas de IA

Este proyecto se desarrolló con asistencia de **Claude (Anthropic)**, usado como
asistente de programación. 

A continuación se resumen los prompts principales, por etapa.

| Etapa | Prompt (resumido) | Resultado / decisión |
|---|---|---|
| Enunciado | «Este es el trabajo: analizalo, leelo y explicámelo.» | Resumen de los 3 programas, los 3 patrones y los requisitos no funcionales. |
| Planificación | Cuánta complejidad tiene el TP y cómo avanzar sin perderse. | Plan de 8 etapas, de lo simple a lo complejo. |
| Esqueleto | Qué es CookieCutter y por qué se pide. | Proyecto base, adaptado para usar mypy, pyright, black, bandit, pdoc y requirements.txt. |
| Patrones | Implementar Singleton, Proxy y Observer de forma aislada y con tests. | `SingletonMeta`, `UpdateProxy`, `EventPublisher`. |
| Datos y negocio | Integrar los patrones con DynamoDB y auditar cada acción. | `db.py` y `service.py`. |
| Servidor | Servidor TCP con protocolo propio, hilos y notificaciones entre conexiones. | `protocol.py`, `server_core.py`, `server_app.py`. |
| Clientes | Clientes con argumentos `-i=`, `-p=`, reconexión automática y salida a archivo. | `client_core.py`, `observer_core.py`, `cli_args.py`. |
| Pruebas manuales | Probar servidor, observer y cliente en tres terminales contra AWS real. | Bugs encontrados y corregidos: timeout del observer, `Decimal`, corte abrupto del socket. |
| Consigna | Revisar cada punto de «Validación y Verificación». | Suite de aceptación; el servidor cierra la conexión tras `get` y `list`; nombre `idreq`. |
| Calidad | Cumplir PEP257, cobertura y tests que verifiquen los patrones. | Control de docstrings en el CI y `test_patterns_compliance.py`. |
| CI/CD | Subir a GitHub y automatizar los controles y la documentación. | `ci.yml` y `docs.yml` en verde. |
