import assert from 'node:assert/strict'
import http from 'node:http'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { createServer, loadConfigFromFile } from 'vite'

test('Vite appends the real TCP peer after untrusted forwarded addresses', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'enzymind-proxy-'))
  const reached = []
  const upstream = http.createServer((req, res) => {
    reached.push({ path: req.url, turn: req.headers['x-enzymind-turn'] })
    res.end(req.headers['x-forwarded-for'] || '')
  })
  let server
  try {
    await new Promise(resolve => upstream.listen(0, '127.0.0.1', resolve))
    const { config } = await loadConfigFromFile({ command: 'serve', mode: 'test' })
    const proxy = config.server.proxy['/enzymind/api']
    server = await createServer({
      configFile: false, root: directory, base: config.base, logLevel: 'silent',
      server: { host: '127.0.0.1', port: 0, hmr: false, proxy: {
        '/enzymind/api': { ...proxy, target: `http://127.0.0.1:${upstream.address().port}` },
      } },
    })
    await server.listen()
    const response = await new Promise((resolve, reject) => {
      const req = http.get({ hostname: '127.0.0.1', port: server.httpServer.address().port,
        localAddress: '127.0.0.2', path: '/enzymind/api/health',
        headers: { 'X-Forwarded-For': '198.51.100.10, 127.0.0.1', 'X-Enzymind-Turn': 'untrusted-turn-token' } }, res => {
        let body = ''
        res.on('data', chunk => { body += chunk })
        res.on('end', () => resolve(body))
      })
      req.on('error', reject)
    })
    assert.equal(response, '198.51.100.10, 127.0.0.1,127.0.0.2')
    assert.equal(reached[0].turn, undefined)
    for (const path of ['/enzymind/api/workspace/tools/python', '/enzymind/api/workspace/tools/%70ython/', '/enzymind/api/workspace/tools/python?debug=true']) {
      const response = await fetch(`http://127.0.0.1:${server.httpServer.address().port}${path}`, {
        method: 'POST', headers: { 'X-Enzymind-Turn': 'untrusted-turn-token' }, body: '{}',
      })
      assert.equal(response.status, 404)
    }
    assert.equal(reached.length, 1, 'No Python request may reach the upstream from the public proxy')
  } finally {
    if (server) await server.close()
    await new Promise(resolve => upstream.close(resolve))
    await rm(directory, { recursive: true, force: true })
  }
})
