"""Top-level package for Trabajo Final."""

"""Servidor de datos corporativos con patrones Singleton, Proxy y Observer sobre DynamoDB.

El paquete implementa un servidor TCP que centraliza el acceso a las tablas
CorporateData y CorporateLog de AWS DynamoDB, junto con la logica de los
clientes singletonclient y observerclient.

Modulos principales:

- patterns: patrones Singleton, Proxy y Observer.
- db: acceso fisico a las tablas de DynamoDB.
- service: fachada que une los tres patrones.
- protocol: mensajes JSON delimitados por salto de linea sobre sockets.
- server_core y server_app: atencion de conexiones y servidor TCP.
- client_core y observer_core: logica de los dos clientes.
- cli_args: parseo de argumentos de linea de comandos.
"""
