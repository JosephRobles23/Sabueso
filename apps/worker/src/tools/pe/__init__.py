"""Tools de Perú (first-class).

Importar este paquete fuerza el registro de las 8 tools en ``ToolRegistry``.
"""

from ..rate_limit import get_rate_limiter
from . import el_peruano, jne, legalize, manolo, news, relatives, seace, stubs, sunarp

__all__ = [
    "el_peruano",
    "jne",
    "legalize",
    "manolo",
    "news",
    "relatives",
    "seace",
    "stubs",
    "sunarp",
    "apply_pe_rate_limits",
]


def apply_pe_rate_limits() -> None:
    """Configura los rate limits específicos por host para fuentes PE.

    El default es 2 req/s. SEACE / JNE son más estrictos por experiencia
    operativa; bajamos a 1 req/s.
    """
    limiter = get_rate_limiter()
    limiter.set("contratacionesabiertas.osce.gob.pe", rate=1.0, capacity=1.0)
    limiter.set("plataformaelectoral.jne.gob.pe", rate=1.0, capacity=1.0)
    limiter.set("www.manolo.pe", rate=2.0, capacity=2.0)
    limiter.set("busquedas.elperuano.pe", rate=2.0, capacity=2.0)
    limiter.set("www.sunarp.gob.pe", rate=1.0, capacity=1.0)
    limiter.set("web.archive.org", rate=2.0, capacity=2.0)
