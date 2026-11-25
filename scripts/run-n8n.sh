#!/usr/bin/env bash
set -euo pipefail
if docker container inspect n8n >/dev/null 2>&1; then
    docker start n8n
else
    docker run -d --name n8n -p 5678:5678 \
      --add-host host.docker.internal:host-gateway \
      -e EASIFA_BACKEND_BASE_URL=http://host.docker.internal:8006/easifa \
      -e N8N_BLOCK_ENV_ACCESS_IN_NODE=false \
      -e EASIFA_AGENT_BASE_URL=http://host.docker.internal:8011/easifa-agent \
      -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
fi
