# EnzyMind Vue Frontend

Modern Vue 3 frontend for the EnzyMind enzyme informatics platform.

## Enzyme–molecule result cards

`ResearchResult` uses `EnzymePairResult` / `EnzymePartner` for kcat, Km,
substrate compatibility, reaction-conditioned active sites, enzyme recommendations,
and recorded catalytic reactions. Tool pages, saved Results and the Agent inspector
share this renderer. Partners stack vertically at the same width on every screen, with independent
content heights. Molecular previews use a plain expand control; residue panels
retain the structure viewer’s responsive layout and natural content height.
Returned rows retain their own sequences, structures and reactions. Original inputs
and complete result JSON remain in the provenance / export controls.

The enzyme side reuses `SequencePreview`, `ProteinViewer`, `ReferenceStructure`
and `EcClassification`. EC-only results describe a function, not a particular
protein. Reaction text without SMILES stays text; no chemical structure is inferred.
Accession-only historical records may load a separate, explicitly labelled reference
sequence via GET `/api/query/enzyme-full-info/{accession}/sequence`, and a reference
AlphaFold model through the existing structure GET. These reads do not create
analysis records or rerun prediction services. Missing reference data leaves the
saved pair and its scalar result available, with independent retry controls.

Deploy using `bash scripts/deploy.sh frontend` and restart frontend with the existing
start/stop scripts. When reference endpoints change, also restart `enzyme_full_info`
and Gateway after active requests finish.
No new package or environment variable is required. The sequence lookup uses the
existing `ENZYMIND_UNIPROT_LOCAL_DB_PATH` configuration and local-first policy.

## Tech Stack

- **Vue 3** - Composition API with `<script setup>`
- **Vite 5** - Fast build tool
- **Vue Router 4** - Client-side routing
- **Pinia** - State management (if needed)
- **Axios** - HTTP client
- **SCSS** - Styling with CSS variables
- **marked** - Markdown rendering
- **Mol\*** - Protein structure visualization

## Project Structure

```
frontend_vue/
├── public/              # Static assets
├── src/
│   ├── api/             # API client and endpoints
│   ├── assets/          # Images, fonts
│   ├── components/      # Reusable components
│   │   ├── common/      # Input, result, loading components
│   │   └── layout/      # Header, footer, page containers
│   ├── router/          # Vue Router configuration
│   ├── styles/          # Global SCSS
│   └── views/           # Page components
│       ├── predict/     # Prediction tools
│       └── utility/     # Utility tools
├── index.html
├── package.json
└── vite.config.js
```

## Installation

```bash
cd frontend
wget https://nodejs.org/dist/v20.9.0/node-v20.9.0-linux-x64.tar.xz
tar -xJf node-v20.9.0-linux-x64.tar.xz
sudo mv node-v20.9.0-linux-x64.tar.xz /usr/local/node20
echo 'export NODE_HOME=/usr/local/node20' >> ~/.bashrc
echo 'export PATH=$NODE_HOME/bin:$PATH' >> ~/.bashrc
npm install
```

## Development

```bash
npm run dev
```

The development server runs at `http://localhost:3010` and proxies API requests to the gateway at `http://localhost:8080`.

The public API base URL is:

```text
https://cadd.zju.edu.cn/enzymind/api/
```

For example, the active-site prediction endpoint is `https://cadd.zju.edu.cn/enzymind/api/predict/active-sites`.

## Production Build

```bash
npm run build
npm run preview
```

## API Proxy Configuration

In development, Vite proxies `/enzymind/api` requests to the gateway server:

```javascript
// vite.config.js
server: {
  proxy: {
    '/enzymind/api': {
      target: 'http://localhost:8080',
      changeOrigin: true
    }
  }
}
```

## Help guide artwork

Quick Start's tool images and editable SVG sources live in
[`src/assets/help-guides/`](src/assets/help-guides/README.md). Keep production
images in this existing asset tree; root-level `artifacts/` is reserved for local
captures, intermediate renders and review previews and is ignored by Git.

## Styling

The design system uses CSS variables for consistent theming:

- Primary color: `#2563eb` (blue)
- Success: `#059669` (green)
- Warning: `#d97706` (amber)
- Error: `#dc2626` (red)

Responsive breakpoints:
- Mobile: < 768px
- Tablet: 768px - 1024px
- Desktop: > 1024px

## Adding New Pages

1. Create view component in `src/views/`
2. Add route in `src/router/index.js`
3. Add API function in `src/api/index.js` if needed
4. Update navigation in `AppHeader.vue`

## Component Guidelines

- Use Composition API with `<script setup>`
- Use TypeScript-like JSDoc comments for better IDE support
- Keep components focused and reusable
- Use scoped SCSS styles
