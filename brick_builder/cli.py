import argparse
from pathlib import Path

from .compiler import load_and_compile
from .palette import load_palette


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile a Brick Builder JSON model to LDraw")
    parser.add_argument("model", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--palette", type=Path, default=Path("config/palettes/classic-core-v0.json"))
    args = parser.parse_args()
    load_and_compile(args.model, args.output, load_palette(args.palette))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
