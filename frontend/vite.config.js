import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import http from 'http'

export default defineConfig({
  plugins: [
    vue(),
    // 自定义插件处理流式请求
    {
      name: 'streaming-proxy',
      configureServer(server) {
        server.middlewares.use('/enzymind/api/agent/chat', (req, res) => {
          // 直接转发到 gateway，不经过 http-proxy
          const options = {
            hostname: 'localhost',
            port: 8080,
            path: '/enzymind/api/agent/chat',
            method: req.method,
            headers: {
              ...req.headers,
              host: 'localhost:8080',
            },
            // 10分钟超时，支持长时间运行的工具调用
            timeout: 600000,
          };

          const proxyReq = http.request(options, (proxyRes) => {
            // 设置响应头，禁用缓冲
            res.writeHead(proxyRes.statusCode, {
              ...proxyRes.headers,
              'cache-control': 'no-cache',
              'x-accel-buffering': 'no',
            });
            // 直接 pipe 流式数据
            proxyRes.pipe(res);
            
            proxyRes.on('error', (err) => {
              console.error('Proxy response error:', err);
              if (!res.headersSent) {
                res.writeHead(502);
              }
              res.end();
            });
          });

          // 设置请求超时
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

          // 转发请求体
          req.pipe(proxyReq);
        });
      },
    },
  ],
  base: '/enzymind/',
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    allowedHosts: [
      'cadd.iddd.group',
      'localhost',
      '127.0.0.1',
    ],
    proxy: {
      // 其他 API 继续使用标准代理
      '/enzymind/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
})
