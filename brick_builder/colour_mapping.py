"""Deterministic mapping from spatial concept colours to the active palette."""

from __future__ import annotations

from typing import Any, Mapping


# These are the fixed UI colours currently emitted by the spatial concept
# contract.  A source colour is never silently approximated.
SOURCE_COLOUR_NAMES = {
    "#202124": "black",
    "#0055bf": "blue",
    "#2878b5": "blue",
    "#237841": "green",
    "#2ca02c": "green",
    "#2e8b57": "green",
    "#d71920": "red",
    "#c91a09": "red",
    "#f2cd37": "yellow",
    "#ffffff": "white",
    "#f5a623": "orange",
    "#fe8a18": "orange",
    "#8dd35f": "lime",
}


def resolve_source_colour(source: str, palette: Mapping[str, Any]) -> tuple[int | None, str | None]:
    """Return the unique palette code for a supported source hex colour."""
    name = SOURCE_COLOUR_NAMES.get(source.lower())
    if name is None:
        return None, f"COLOUR_UNSUPPORTED: source colour {source!r} is not in the supported concept palette"
    matches = [item for item in palette.get("colours", []) if isinstance(item, dict) and str(item.get("name", "")).lower() == name]
    if len(matches) != 1 or not isinstance(matches[0].get("ldraw_code"), int):
        return None, f"COLOUR_AMBIGUOUS: source colour {source!r} does not map to exactly one palette colour named {name!r}"
    return matches[0]["ldraw_code"], None


def resolve_concept_colour(source_colours: list[str], palette: Mapping[str, Any]) -> tuple[int | None, str | None]:
    """Resolve one uniform source colour, rejecting mixed or unsupported input."""
    if not source_colours or len(set(source.lower() for source in source_colours)) != 1:
        return None, "COLOUR_AMBIGUOUS: all geometry must use one source colour"
    return resolve_source_colour(source_colours[0], palette)
