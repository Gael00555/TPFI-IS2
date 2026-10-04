"""Tests del patrón Observer."""

from __future__ import annotations

from typing import Any

from spo_core.patterns.observer import EventPublisher


class FakeSubscriber:
    """Suscriptor de prueba: registra lo que recibe y puede simular fallas."""

    def __init__(self, *, fail: bool = False, raise_error: bool = False) -> None:
        """Configura el comportamiento simulado del suscriptor."""
        self.fail = fail
        self.raise_error = raise_error
        self.received: list[dict[str, Any]] = []

    def send_update(self, data: dict[str, Any]) -> bool:
        """Simula el envío de una notificación al cliente."""
        if self.raise_error:
            raise ConnectionError("socket cerrado")
        if self.fail:
            return False
        self.received.append(data)
        return True


def test_new_subscriber_starts_at_zero() -> None:
    """Un publisher recién creado no tiene suscriptores."""
    publisher = EventPublisher()
    assert publisher.subscriber_count == 0


def test_subscribe_adds_subscriber() -> None:
    """Suscribirse incrementa el contador de suscriptores."""
    publisher = EventPublisher()
    sub = FakeSubscriber()

    publisher.subscribe(sub)

    assert publisher.subscriber_count == 1


def test_subscribe_is_idempotent() -> None:
    """Suscribir dos veces al mismo observador no lo duplica."""
    publisher = EventPublisher()
    sub = FakeSubscriber()

    publisher.subscribe(sub)
    publisher.subscribe(sub)

    assert publisher.subscriber_count == 1


def test_unsubscribe_removes_subscriber() -> None:
    """Desuscribirse remueve al observador de la lista."""
    publisher = EventPublisher()
    sub = FakeSubscriber()
    publisher.subscribe(sub)

    publisher.unsubscribe(sub)

    assert publisher.subscriber_count == 0


def test_unsubscribe_unknown_subscriber_is_safe() -> None:
    """Desuscribir a alguien no registrado no rompe nada."""
    publisher = EventPublisher()
    sub = FakeSubscriber()

    publisher.unsubscribe(sub)

    assert publisher.subscriber_count == 0


def test_notify_delivers_to_all_subscribers() -> None:
    """Al notificar, todos los suscriptores reciben el mismo evento."""
    publisher = EventPublisher()
    sub_a = FakeSubscriber()
    sub_b = FakeSubscriber()
    publisher.subscribe(sub_a)
    publisher.subscribe(sub_b)

    payload = {"id": "UADER-FCYT-IS2", "seqID": "24"}
    publisher.notify(payload)

    assert sub_a.received == [payload]
    assert sub_b.received == [payload]


def test_notify_removes_subscriber_that_returns_false() -> None:
    """Un suscriptor que devuelve False (fallo de envío) se da de baja solo."""
    publisher = EventPublisher()
    healthy = FakeSubscriber()
    broken = FakeSubscriber(fail=True)
    publisher.subscribe(healthy)
    publisher.subscribe(broken)

    publisher.notify({"id": "UADER-FCYT-IS2"})

    assert publisher.subscriber_count == 1
    assert healthy.received == [{"id": "UADER-FCYT-IS2"}]


def test_notify_removes_subscriber_that_raises() -> None:
    """Un suscriptor que lanza una excepción (socket caído) se da de baja solo."""
    publisher = EventPublisher()
    healthy = FakeSubscriber()
    broken = FakeSubscriber(raise_error=True)
    publisher.subscribe(healthy)
    publisher.subscribe(broken)

    publisher.notify({"id": "UADER-FCYT-IS2"})

    assert publisher.subscriber_count == 1
    assert healthy.received == [{"id": "UADER-FCYT-IS2"}]


def test_notify_with_no_subscribers_does_not_fail() -> None:
    """Notificar sin suscriptores no lanza ningún error."""
    publisher = EventPublisher()

    publisher.notify({"id": "UADER-FCYT-IS2"})

    assert publisher.subscriber_count == 0
