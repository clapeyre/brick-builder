"""Project-authored parametric geometry for the conservative rectangular palette."""
from dataclasses import dataclass
from typing import Any

PITCH = 20
PLATE_HEIGHT = 8


@dataclass(frozen=True)
class RectProfile:
    part: str
    category: str
    x_studs: int
    z_studs: int
    height_plates: int

    @property
    def bounds(self):
        # LDraw primitive origins are on the top plane; +Y points downward.
        return (-self.x_studs * PITCH / 2, 0, -self.z_studs * PITCH / 2,
                self.x_studs * PITCH / 2, self.height_plates * PLATE_HEIGHT,
                self.z_studs * PITCH / 2)

    def ports(self, include_top=True):
        x0 = -(self.x_studs - 1) * PITCH / 2
        z0 = -(self.z_studs - 1) * PITCH / 2
        top = [] if self.category == "tile" else [(x0 + x * PITCH, 0, z0 + z * PITCH)
               for x in range(self.x_studs) for z in range(self.z_studs)] if include_top else []
        bottom = [(x0 + x * PITCH, self.height_plates * PLATE_HEIGHT, z0 + z * PITCH)
               for x in range(self.x_studs) for z in range(self.z_studs)]
        return top, bottom


@dataclass(frozen=True)
class GeometryAnalysis:
    """Deterministic geometric report shared by validation and CLI consumers."""
    issues: tuple
    edges: tuple
    per_part_bounds: dict
    overall_bounds: tuple | None
    support_plane: float | None
    grounded_ids: tuple
    root_id: str | None

    def __iter__(self):
        """Compatibility with the original ``issues, edges = ...`` API."""
        yield self.issues
        yield set(self.edges)


def profiles_from_palette(palette: dict[str, Any]) -> dict[str, RectProfile]:
    # Palette legacy `studs` follows LDraw name order [z, x], unlike the
    # profile's explicit x/z fields.
    return {p["ldraw_file"]: RectProfile(p["ldraw_file"], p["category"], p["studs"][1], p["studs"][0], p["height_plates"])
            for p in palette.get("parts", []) if p.get("category") in {"brick", "plate", "tile"}}


def transform(point, matrix, translation):
    x, y, z = point; a, b, c, d, e, f, g, h, i = matrix
    return (a*x + b*y + c*z + translation[0], d*x + e*y + f*z + translation[1], g*x + h*y + i*z + translation[2])


def transformed_profile(profile: RectProfile, placement: dict[str, Any]):
    lo = profile.bounds
    corners = [(x, y, z) for x in (lo[0], lo[3]) for y in (lo[1], lo[4]) for z in (lo[2], lo[5])]
    points = [transform(c, placement["matrix"], placement["translation_ldu"]) for c in corners]
    bbox = (min(p[0] for p in points), min(p[1] for p in points), min(p[2] for p in points), max(p[0] for p in points), max(p[1] for p in points), max(p[2] for p in points))
    top, bottom = profile.ports()
    return bbox, [transform(p, placement["matrix"], placement["translation_ldu"]) for p in top], [transform(p, placement["matrix"], placement["translation_ldu"]) for p in bottom]


def validate_geometry(model: dict[str, Any], palette: dict[str, Any]):
    from .validation import ValidationIssue
    profiles = profiles_from_palette(palette)
    categories = {p["ldraw_file"]: p.get("category") for p in palette.get("parts", []) if isinstance(p, dict)}
    issues = []
    items = []
    for idx, placement in enumerate(model.get("parts", [])):
        profile = profiles.get(placement.get("part"))
        if not profile:
            if placement.get("part") in categories:
                issues.append(ValidationIssue(f"parts[{idx}].part", "part geometry is outside the rectangular validator scope", "UNSUPPORTED_GEOMETRY"))
            continue
        matrix = placement.get("matrix", [])
        if len(matrix) == 9 and (matrix[3], matrix[4], matrix[5]) != (0, 1, 0):
            issues.append(ValidationIssue(f"parts[{idx}].matrix", "only rotations about the vertical Y axis are supported", "UNSUPPORTED_ORIENTATION"))
            continue
        bbox, top, bottom = transformed_profile(profile, placement)
        if any(coordinate % PITCH for port in top + bottom for coordinate in (port[0], port[2])):
            issues.append(ValidationIssue(f"parts[{idx}].translation_ldu", "stud and underside ports must align to the absolute 20 LDU grid", "GRID_MISALIGNMENT"))
        items.append((idx, placement, profile, bbox, top, bottom))
    edges = set()
    def overlap(a, b):
        return all(a[k] < b[k+3] and b[k] < a[k+3] for k in (0, 1, 2))
    def horizontal_contact(a, b):
        return a[3] > b[0] and b[3] > a[0] and a[5] > b[2] and b[5] > a[2]
    for n, (idx_a, pa, pra, ba, ta, ua) in enumerate(items):
        for m in range(n + 1, len(items)):
            idx_b, pb, prb, bb, tb, ub = items[m]
            if overlap(ba, bb):
                issues.append(ValidationIssue(f"parts[{idx_a}],parts[{idx_b}]", "parts interpenetrate", "GEOMETRY_OVERLAP"))
            for stud in ta:
                for anti in ub:
                    if stud == anti:
                        edges.add((pa["id"], pb["id"]))
            for stud in tb:
                for anti in ua:
                    if stud == anti:
                        edges.add((pb["id"], pa["id"]))
            if ba[4] == bb[1] or bb[4] == ba[1]:
                if horizontal_contact(ba, bb) and not any(e[0] in (pa["id"], pb["id"]) and e[1] in (pa["id"], pb["id"]) for e in edges):
                    issues.append(ValidationIssue(f"parts[{idx_a}],parts[{idx_b}]", "surface contact has no stud connection", "UNSUPPORTED_CONTACT"))
    ids = [p["id"] for _, p, *_ in items]
    support_plane = max((b[4] for _, _, _, b, *_ in items), default=0)
    grounded = [p["id"] for _, p, _, b, *_ in items if b[4] == support_plane]
    # Select one deterministic root; other grounded towers are still separate
    # assemblies and must be reported as disconnected.
    reachable = {min(grounded, key=lambda ident: ids.index(ident))} if grounded else set()
    changed = True
    while changed:
        changed = False
        for a, b in edges:
            if a in reachable and b not in reachable: reachable.add(b); changed = True
            if b in reachable and a not in reachable: reachable.add(a); changed = True
    for idx, p, *_ in items:
        if p["id"] not in reachable:
            issues.append(ValidationIssue(f"parts[{idx}]", "part is floating or disconnected", "DISCONNECTED_ASSEMBLY"))
    ordered_edges = tuple(sorted(edges))
    per_part_bounds = {p["id"]: b for _, p, _, b, *_ in items}
    overall = None
    if per_part_bounds:
        boxes = list(per_part_bounds.values())
        overall = (min(b[0] for b in boxes), min(b[1] for b in boxes), min(b[2] for b in boxes), max(b[3] for b in boxes), max(b[4] for b in boxes), max(b[5] for b in boxes))
    return GeometryAnalysis(tuple(sorted(issues, key=lambda i: (i.path, i.code, i.message))), ordered_edges, per_part_bounds, overall, support_plane if items else None, tuple(sorted(grounded)), min(grounded, key=lambda ident: ids.index(ident)) if grounded else None)
