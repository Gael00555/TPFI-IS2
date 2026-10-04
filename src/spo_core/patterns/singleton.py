"""Implementación del patrón Singleton mediante una metaclase."""

from __future__ import annotations

import threading
from typing import Any, ClassVar


class SingletonMeta(type):
    """Metaclase que garantiza una única instancia por cada clase que la use.

    Cada clase que declare ``metaclass=SingletonMeta`` tiene su propia
    instancia única e independiente de las demás. El acceso es seguro entre
    hilos, algo necesario porque el servidor atiende varios clientes a la vez.
    """

    _instances: ClassVar[dict[type, Any]] = {}
    _lock: ClassVar[threading.RLock] = threading.RLock()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """Devuelve la instancia única de la clase, creándola si no existe."""
        with SingletonMeta._lock:
            if cls not in SingletonMeta._instances:
                SingletonMeta._instances[cls] = super().__call__(*args, **kwargs)
            return SingletonMeta._instances[cls]

    @classmethod
    def reset_instances(mcs) -> None:
        """Descarta todas las instancias creadas (útil para aislar los tests)."""
        with mcs._lock:
            mcs._instances.clear()
