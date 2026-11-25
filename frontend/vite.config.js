import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import http from 'http'

// Python execution is an internal n8n -> Gateway call, never a public proxy API.
function internalPythonPath(url = '') {
  try {
    const path = decodeURIComponent(url.split('?')[0]).replace(/\/{2,}/g, '/')
    return /^\/enzymind\/api\/workspace\/tools\/python\/?$/.test(path)
  } catch { return true }
}

export default defineConfig({
  plugins: [
    vue(),
    // Custom plugin for streaming requests
    {
      name: 'streaming-proxy',
      configureServer(server) {
        server.middlewares.use('/enzymind/api/agent/chat', (req, res) => {
          // Forward directly to the gateway, bypassing http-proxy
          const options = {
            hostname: 'localhost',
            port: 8080,
            path: '/enzymind/api/agent/chat',
            method: req.method,
            headers: {
              ...req.headers,
              host: 'localhost:8080',
            },
            // Allow ten minutes for long-running tool calls
            timeout: 600000,
          };

          const proxyReq = http.request(options, (proxyRes) => {
            // Set response headers to disable buffering
            res.writeHead(proxyRes.statusCode, {
              ...proxyRes.headers,
              'cache-control': 'no-cache',
              'x-accel-buffering': 'no',
            });
            // Pipe streaming data directly
            proxyRes.pipe(res);
            
            proxyRes.on('error', (err) => {
              console.error('Proxy response error:', err);
              if (!res.headersSent) {
                res.writeHead(502);
              }
              res.end();
            });
          });

          // Set the request timeout
          proxyReq.setTimeout(600000, () => {
            console.error('Proxy request timeout');
            proxyReq.destroy();
            if (!res.headersSent) {
              res.writeHead(504);
              res.end('Gateway Timeout');
            }
          });

          proxyReq.on('error', (err) => {
            console.error('Proxy error:', err);
            if (!res.headersSent) {
              res.writeHead(502);
              res.end('Proxy error');
            }
          });

          // Forward the request body
          req.pipe(proxyReq);
        });
      },
    },
  ],
  base: '/enzymind/',
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      events: resolve(__dirname, 'node_modules/events/events.js'),
    },
  },
  worker: { format: 'es' },
  optimizeDeps: { exclude: ['ketcher-standalone'], include: ['ketcher-core', 'ketcher-react', 'react', 'react-dom/client', 'process/browser', 'events', '@babel/runtime/regenerator', 'echarts/core', 'echarts/charts', 'echarts/components', 'echarts/renderers'] },
  server: {
    host: '0.0.0.0',
    port: 3010,
    allowedHosts: [
      'cadd.zju.edu.cn',
      'cadd.iddd.group',
      'localhost',
      '127.0.0.1',
      '.iddd.group',
      '.drugflow.com',
    ],
    proxy: {
      // Keep the standard proxy for other API requests
      '/enzymind/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        // Append the actual peer so Workspace IP limits cannot trust a forged XFF.
        xfwd: true,
        bypass(req, res) {
          if (internalPythonPath(req.url)) {
            return false
          }
        },
        configure(proxy) {
          proxy.on('proxyReq', proxyReq => proxyReq.removeHeader('x-enzymind-turn'))
        },
      },
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    commonjsOptions: { transformMixedEsModules: true },
    rollupOptions: { input: { main: resolve(__dirname, 'index.html'), ketcher: resolve(__dirname, 'ketcher/index.html') } },
  },
})
