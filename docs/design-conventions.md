# Design and catalog conventions

Status: initial decision record for the deterministic design engine.

## Reuse established standards

The project uses LDraw as its external geometric and file-format standard. It does not define new part numbers, colour numbers, physical units, axes, or transformation syntax.

Primary references:

- [LDraw File Format Specification](https://www.ldraw.org/article/218.html)
- [LDraw Official Library Part Number Specification](https://www.ldraw.org/part-number-spec.html)
- [LDraw Colour Definition Reference](https://ldraw.org/parts/colour.html)
- [LDraw Official Parts Library](https://library.ldraw.org/)

## Part identity and names

- The canonical part identifier is the lowercase LDraw library filename, including `.dat`, for example `3004.dat`.
- LDraw uses a LEGO Design ID when one is known. A Design ID describes a shape; it is not the colour-specific Element ID printed in many instruction inventories.
- The canonical display name comes from the first description line of the corresponding official LDraw part file.
- Friendly child-facing words such as `long brick`, `roof slope`, or `eye` are aliases in a separate semantic taxonomy. They never replace the canonical identifier.
- BrickLink, LEGO Element ID, and other catalog mappings are optional cross-references. They must not silently replace the LDraw ID because mappings are not always one-to-one.

## Coordinates and transforms

Use LDraw coordinates without conversion in the canonical design document:

- Right-handed coordinate system
- `-Y` is up
- One stud pitch or brick width/depth is `20 LDU`
- One brick height is `24 LDU`
- One plate height is `8 LDU`
- One stud diameter is `12 LDU`
- One stud height is `4 LDU`

A placed part stores the LDraw type-1 translation and matrix explicitly:

```json
{
  "part": "3004.dat",
  "colour": 4,
  "translation_ldu": [0, -24, 20],
  "matrix": [1, 0, 0, 0, 1, 0, 0, 0, 1]
}
```

The matrix order corresponds to LDraw's `a b c d e f g h i` fields. The compiler emits:

```text
1 <colour> x y z a b c d e f g h i <file>
```

Initial designs permit translation plus proper orthonormal rotations in 90-degree increments. Scaling, shearing, and reflection are disallowed for physical parts even though the general LDraw matrix syntax can express them.

Part origins are defined by the part library and are not assumed to be geometric centres. Ground placement is therefore calculated from transformed part geometry or connection metadata. A model may be normalized for display or export, but normalization must apply one common translation to the complete assembly.

## Colours

- Store LDraw colour codes as integers.
- Resolve names and display values from the official `LDConfig.ldr` used for the run.
- Do not author arbitrary RGB colours for ordinary parts.
- A colour being defined by LDraw does not prove that a particular part exists in that colour or that the user owns it. Those are separate catalog and inventory validations.

## Connections

LDraw establishes part geometry and transforms but does not provide a universal semantic connection graph for models. The project therefore adds a small connection layer:

- Each supported part has typed local ports such as `stud`, `tube`, or `anti_stud`.
- A design records intended connections between two placed-part port identifiers.
- Validators compare intended connections with transformed port geometry and collision geometry.
- For basic rectangular bricks and plates, ports should be generated parametrically from stud dimensions instead of hand-entered one by one.
- Palette `studs` metadata retains LDraw part-name order `[z, x]`; geometry converts it immediately to explicit `x_studs`/`z_studs` profile fields.
- Supported stud and underside-port world X/Z positions use Studio-compatible zero-phase 20 LDU lattice coordinates; whole-assembly normalization must preserve relative geometry while applying one common translation.
- More complex connection families are added only with tests and physical examples.

BrickLink Studio contains its own connectivity and collider data. The application may inspect or use a user's local Studio installation through an adapter when permitted, but Studio data must not be copied into the public repository without a verified redistribution licence. The portable core should rely on project-authored metadata and the appropriately attributed official LDraw library.

## Inventory

Inventory is represented by `(part, colour, quantity)` tuples. A palette says what the engine understands; an inventory says what the user can physically build.

The first palette is deliberately generic and packaged at `brick_builder/palettes/classic-core-v0.json`. Once the LEGO Classic set numbers are known, their inventories should be imported into a user inventory and the generator should prefer or require owned part/colour combinations.

## Export

- Use `.ldr` for a simple single-model export.
- Use `.mpd` when the design contains named submodels or embedded build structure.
- Preserve submodels that express meaningful components such as a body, wing, wheel assembly, or roof.
- Add LDraw step markers only after the assembly-order system can justify them.

## Licensing and attribution

The LDraw library contains attribution and licence information in its files. If the project distributes the library or a subset, it must preserve the applicable terms and prominently attribute the LDraw Parts Library. Until packaging is designed, prefer detecting a user-installed official LDraw library or obtaining it through a documented installation step rather than committing geometry copied from Studio.
