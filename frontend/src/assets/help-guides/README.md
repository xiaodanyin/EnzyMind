# Help tool guide assets

The Help page's Quick Start uses 11 approved tool guides and the Workspace
walkthrough (`12-workspace`). Keep them in the
existing `frontend/src/assets/` image tree, alongside the original Help artwork.

- `*.webp`: the images served by Quick Start (2200 × 1550, lossless WebP).
- `source/*.svg`: editable source artwork with embedded screenshot excerpts;
  these files do not depend on temporary capture paths.
- `manifest.json`: tool routes, public example inputs, capture dates and notes.
  Temporary saved-result IDs are deliberately omitted.

`src/config/helpGuides.js` maps tool IDs to the WebP files. It imports image URL
strings; Quick Start lazily fetches the Workspace image and the selected tool
image. SVG sources and this
manifest are not imported by the application and are not included in its build.

## Updating a guide

1. Edit the matching SVG or replace its screenshot excerpts after checking the
   current tool UI. Keep the shared layout and 2200 × 1550 canvas.
2. Render to a temporary PNG in a browser with the project's fonts loaded, then
   convert it to lossless WebP, for example with Pillow:

   ```python
   from PIL import Image
   Image.open("/tmp/guide.png").save("path/to/guide.webp", lossless=True, method=6)
   ```

3. Update the matching manifest entry and check the guide at inline size and in
   the full-image dialog. Keep the SVG and WebP together in the same commit.
4. Run `npm run build` and the Help Quick Start browser checks from `frontend/`.
   The browser tests use the local frontend on port 3011.

The Sequence Alignment guide shows a completed P00761 search against the local
reviewed UniProt snapshot dated 2026-06-14 (575,503 sequences), captured on
2026-11-23. It retains the original three-step layout: the method workflow across
the top, input and search settings at lower left, and completed results with
export at lower right. The result panel combines hit comparison, selection of
P08426 for colored residue alignment, and the Differences table. P08426 has
98.7% query coverage, 86.4% identity and 31
residue differences. These are actual BLAST results, displayed unchanged through
browser-local responses in the current UI. The first three of five returned hits,
first alignment block (80 columns), and first two difference rows are shown as
excerpts. The expanded table and export
controls were exercised. The manifest records provenance and the response hash;
intermediate captures are in ignored `artifacts/alignment-guide-review/`.

Other guides use completed public-example results; the manifest records excerpt
and chart-layout notes.

The Workspace walkthrough uses browser-local fixtures in the current frontend
to show stacked sequence and 3D/site cards, highlighted Python code, a composition
plot and a CSV excerpt. The example is carboxylesterase 1 (UniProt Q0ZPV7,
Actinidia eriantha). UniProt annotations and the EnzyMind enzyme-information and
active-site responses were retrieved on 2026-11-23. The 335-residue sequence agrees
exactly across UniProt, the annotation response and every alpha carbon in the
platform-supplied AlphaFold model. Original residue numbering is retained; the
sequence card displays residues 1–150 as an explicitly labeled excerpt.

The structure excerpt uses the viewer’s catalytic-site filter. Its labels come
from the completed EasIFA `all_features` prediction: SER 169, ASP 276 and HIS 306. They are model predictions, not experimental
validation; site scores are separate from the model's pLDDT confidence.
The displayed Python code was executed locally to produce the composition PNG
and CSV (20 residue types totaling 335 residues). The guide is an illustrative
assembly of real data and current UI excerpts, not a replay of an Agent turn.
The manifest records response, model and CSV hashes. Intermediate responses,
calculation files and captures are in ignored `artifacts/workspace-guide-review/v4/`.

## Local working files

`artifacts/help-run-predictions/` and `artifacts/help-quick-start/` at the repository
root hold intermediate PNGs, early drafts, a gallery, review screenshots and a
ZIP export. They are ignored by Git. Do not add duplicate renders, browser
reports, temporary API responses or workspace access files to this asset tree.
The archived SVGs and runtime WebP files are sufficient to maintain the guides.
