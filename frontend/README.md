# EnzyMind Vue Frontend

Modern Vue 3 frontend for the EnzyMind enzyme informatics platform.

## Tech Stack

- **Vue 3** - Composition API with `<script setup>`
- **Vite 5** - Fast build tool
- **Vue Router 4** - Client-side routing
- **Pinia** - State management (if needed)
- **Axios** - HTTP client
- **SCSS** - Styling with CSS variables
- **marked** - Markdown rendering
- **3Dmol.js** - Protein structure visualization

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

The development server runs at `http://localhost:3000` and proxies API requests to the gateway at `http://localhost:8080`.

## Production Build

```bash
npm run build
npm run preview
```

## API Proxy Configuration

In development, Vite proxies `/api` requests to the gateway server:

```javascript
// vite.config.js
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8080',
      changeOrigin: true
    }
  }
}
```

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
