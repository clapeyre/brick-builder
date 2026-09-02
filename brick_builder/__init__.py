"""Deterministic foundational tools for Brick Builder."""

from .compiler import compile_model
from .ldraw import LDrawLibrary, discover_ldraw_library
from .palette import load_palette
from .validation import ValidationError, validate_model
from .legoization import (CoverageReport, GatehouseScaffold, LEGOizationResult,
                          SteppedBoxScaffold, WallBoxScaffold,
                          legoize_gatehouse, legoize_stepped_box,
                          legoize_wall_box, legoize_wall_box_scaffold)

__all__ = [
    "LDrawLibrary",
    "ValidationError",
    "compile_model",
    "discover_ldraw_library",
    "load_palette",
    "validate_model",
    "CoverageReport",
    "GatehouseScaffold",
    "LEGOizationResult",
    "legoize_gatehouse",
    "WallBoxScaffold",
    "SteppedBoxScaffold",
    "legoize_stepped_box",
    "legoize_wall_box",
    "legoize_wall_box_scaffold",
]
