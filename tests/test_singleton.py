"""Tests del patrón Singleton."""

import threading
from collections.abc import Iterator

import pytest

from spo_core.patterns.singleton import SingletonMeta


class Alpha(metaclass=SingletonMeta):
    """Clase de prueba A."""

    def __init__(self) -> None:
        """Inicializa el estado de la instancia."""
        self.value = 0


class Beta(metaclass=SingletonMeta):
    """Clase de prueba B."""


@pytest.fixture(autouse=True)
def _clean_instances() -> Iterator[None]:
    """Aísla cada test descartando las instancias previas."""
    SingletonMeta.reset_instances()
    yield
    SingletonMeta.reset_instances()


def test_same_instance_returned() -> None:
    """Dos llamadas al constructor devuelven el mismo objeto."""
    assert Alpha() is Alpha()


def test_state_is_shared() -> None:
    """El estado modificado en una referencia se ve en la otra."""
    Alpha().value = 42
    assert Alpha().value == 42


def test_different_classes_have_different_instances() -> None:
    """Cada clase tiene su propia instancia única."""
    assert Alpha() is not Beta()


def test_reset_creates_new_instance() -> None:
    """Después de reset_instances se crea una instancia nueva."""
    first = Alpha()
    SingletonMeta.reset_instances()
    assert Alpha() is not first


def test_thread_safe_single_instance() -> None:
    """Muchos hilos creando la clase a la vez obtienen la misma instancia."""
    results: list[Alpha] = []

    def build() -> None:
        results.append(Alpha())

    threads = [threading.Thread(target=build) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 20
    assert all(item is results[0] for item in results)
