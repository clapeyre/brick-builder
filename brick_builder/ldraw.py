import os
from dataclasses import dataclass
from pathlib import Path

from .errors import BrickBuilderError


class LDrawDiscoveryError(BrickBuilderError):
    pass


@dataclass(frozen=True)
class LDrawLibrary:
    root: Path

    @property
    def parts_dir(self) -> Path:
        return self.root / "parts"

    @property
    def config_file(self) -> Path:
        return self.root / "LDConfig.ldr"

    def has_part(self, part_id: str) -> bool:
        return (self.parts_dir / part_id).is_file()


def _is_library_root(path: Path) -> bool:
    return (path / "parts").is_dir() and (path / "LDConfig.ldr").is_file()


def discover_ldraw_library(override: str | Path | None = None) -> LDrawLibrary:
    """Find an installed official LDraw library without modifying the machine."""
    candidates: list[Path] = []
    if override is not None:
        candidates.append(Path(override).expanduser())
    else:
        env_override = os.environ.get("BRICK_BUILDER_LDRAW_LIBRARY")
        if env_override:
            candidates.append(Path(env_override).expanduser())
        else:
            local_app_data = os.environ.get("LOCALAPPDATA")
            program_files = os.environ.get("PROGRAMFILES")
            program_files_x86 = os.environ.get("PROGRAMFILES(X86)")
            candidates.extend(
                path
                for base in (local_app_data, program_files, program_files_x86)
                if base
                for path in (
                    Path(base) / "BrickLink" / "Studio 2.0" / "ldraw",
                    Path(base) / "Studio 2.0" / "ldraw",
                    Path(base) / "BrickLink Studio" / "ldraw",
                )
            )
    checked: list[str] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        checked.append(str(resolved))
        if _is_library_root(resolved):
            return LDrawLibrary(resolved)
    hint = ", ".join(checked) if checked else "no configured or standard locations"
    raise LDrawDiscoveryError(
        "No LDraw library found. Set BRICK_BUILDER_LDRAW_LIBRARY or pass an explicit override. "
        f"Checked: {hint}"
    )
