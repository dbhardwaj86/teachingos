"""Read-only source adapters and their registry."""
from __future__ import annotations

from .base import Adapter, Artifact, CATALOG_COLUMNS
from .booklets import BookletAdapter
from .gnocr import GnocrAdapter
from .insp import INSPAdapter
from .lecturepdf import LecturepdfAdapter
from .mcd import McdAdapter
from .munshi import MunshiAdapter
from .onedpull import OnedpullAdapter
from .qx import QXAdapter
from .questiondb import QuestionDBAdapter
from .sims import SimsAdapter
from .textbook import TextbookAdapter

ALL_ADAPTERS: list[Adapter] = [
    QXAdapter(),
    TextbookAdapter(),
    BookletAdapter(),
    INSPAdapter(),
    SimsAdapter(),
    QuestionDBAdapter(),
    McdAdapter(),
    MunshiAdapter(),
    # read-only corpus subsystems (desktop-icons-corpus-apps slice)
    GnocrAdapter(),
    OnedpullAdapter(),
    LecturepdfAdapter(),
]


def get_adapter(name: str) -> Adapter | None:
    for adapter in ALL_ADAPTERS:
        if adapter.name == name:
            return adapter
    return None


__all__ = ["Adapter", "Artifact", "CATALOG_COLUMNS", "ALL_ADAPTERS", "get_adapter"]
