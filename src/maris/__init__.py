"""
MARIS - Multi-Agent Repository Intelligence System

A local-first repository intelligence platform for understanding,
navigating, and analyzing source code.
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("maris")
except PackageNotFoundError:
    # Package is not installed, fallback to a default
    __version__ = "0.0.0-dev"

from maris.core.models import Symbol, SymbolType, RetrievalContext, Commit

__all__ = [
    "__version__",
    "Symbol",
    "SymbolType",
    "RetrievalContext",
    "Commit",
]

# Made with Bob
