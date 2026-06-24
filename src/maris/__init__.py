"""
MARIS - Multi-Agent Repository Intelligence System

A local-first repository intelligence platform for understanding,
navigating, and analyzing source code.
"""

__version__ = "0.1.5"

from maris.core.models import Symbol, SymbolType, RetrievalContext, Commit

__all__ = [
    "__version__",
    "Symbol",
    "SymbolType",
    "RetrievalContext",
    "Commit",
]

# Made with Bob
