"""Implementación del patrón Observer para notificar cambios en tiempo real."""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class Subscriber(Protocol):
    """Contrato que deben cumplir los suscriptores (observadores)."""

    def send_update(self, data: dict[str, Any]) -> bool:
        """Envia la actualización al suscriptor.

        Devuelve True si el envío fue exitoso, o False si falló/se desconectó.
        """
        ...


class EventPublisher:
    """Sujeto observable que gestiona las suscripciones y notificaciones.

    Permite que múltiples clientes (sockets TCP) se suscriban para recibir
    notificaciones cada vez que se modifiquen o inserten datos (acción "set")
    en la base de datos centralizada.
    """

    def __init__(self) -> None:
        """Inicializa la lista de suscriptores activos."""
        self._subscribers: list[Subscriber] = []

    def subscribe(self, subscriber: Subscriber) -> None:
        """Añade un nuevo suscriptor a la lista si no está registrado."""
        if subscriber not in self._subscribers:
            self._subscribers.append(subscriber)
            logger.info("Nuevo suscriptor registrado. Total: %d", len(self._subscribers))

    def unsubscribe(self, subscriber: Subscriber) -> None:
        """Remueve un suscriptor de la lista."""
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)
            logger.info("Suscriptor removido. Total: %d", len(self._subscribers))

    def notify(self, data: dict[str, Any]) -> None:
        """Notifica el evento a todos los suscriptores activos.

        Si la entrega hacia algún suscriptor falla (por ejemplo, socket cerrado),
        lo remueve automáticamente de la lista para evitar conexiones huérfanas.
        """
        failed_subscribers: list[Subscriber] = []

        for subscriber in self._subscribers:
            try:
                success = subscriber.send_update(data)
                if not success:
                    failed_subscribers.append(subscriber)
            except Exception as err:
                logger.warning("Error al notificar al suscriptor: %s", err)
                failed_subscribers.append(subscriber)

        # Limpieza de suscriptores caídos o desconectados
        for dead_subscriber in failed_subscribers:
            self.unsubscribe(dead_subscriber)

    @property
    def subscriber_count(self) -> int:
        """Devuelve la cantidad de suscriptores actualmente conectados."""
        return len(self._subscribers)
