# EnzyMind

<div align="center">

![EnzyMind Logo](frontend/src/assets/enzymind_logo_icon_v3.png)

**Enzyme Intelligence Platform**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)](https://fastapi.tiangolo.com/)
[![n8n](https://img.shields.io/badge/n8n-Agent-orange.svg)](https://n8n.io/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3.4-green.svg)](https://vuejs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)


</div>

---

## Overview

**EnzyMind** is an open-source, LLM-orchestrated agent framework designed for reliable enzyme annotation and engineering-oriented analysis. It combines large language models with domain-specific biochemical predictors to provide reliable, end-to-end functional annotation via a unified agent interface and programmable APIs. The platform is publicly accessible at http://cadd.zju.edu.cn/enzymind/, with an alternate access link at http://cadd.iddd.group/enzymind/.

---


## Repository Structure

```
enzymind/
├── services/                # 18 FastAPI microservices
│   ├── enzy_recognize/      
│   ├── ecnumber_predict/    
│   ├── substrate_predict/   
│   ├── kcat_predict/        
│   ├── km_predict/          
│   ├── structure_predict/   
│   ├── active_sites/        
│   ├── enzyme_type/         
│   ├── protparam/           
│   ├── sequence_alignment/  
│   ├── function_get/        
│   ├── enzyme_subclass/    
│   ├── ec_reaction_info/    
│   ├── enzyme_check/       
│   ├── enzyme_full_info/  
│   ├── functional_site/     
│   ├── kinetic_params/      
│   └── sequence_info/       
│
├── gateway/                 # API gateway (FastAPI, port 8080)
│   ├── main.py
│   ├── requirements.txt
│   └── README.md            
│
├── frontend/                # Vue 3 + Vite app (port 3000)
│   ├── src/
│   │   ├── views/
│   │   ├── components/
│   │   ├── api/
│   │   └── router/
│   ├── public/static/jsme/  # JSME molecule editor assets
│   ├── vite.config.js
│   └── README.md
│
├── agent_n8n/               # n8n Agent assets and Python client
│   ├── config_files/        # n8n workflow JSON (DeepSeek-V3.2)
│   ├── client.py            # Python Webhook client
│   └── README.md
│
├── scripts/                 # management scripts
│   ├── deploy.sh
│   ├── hf_models_download.py
│   ├── hf_models_download.sh
│   ├── hf_models_manifest.json
│   ├── start.sh
│   ├── start_web.sh
│   ├── stop.sh
│   └── status.sh
│
├── shared/                  # shared utilities/config
├── tests/                   # notebooks and test assets
└── README.md       
```

---


## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+ and npm 9+
- Docker (for n8n agent deployment)

### 1) Clone

```bash

git clone https://github.com/xiaodanyin/EnzyMind.git
cd EnzyMind
```

### 2) Deploy microservices

```bash
# Deploy all services (creates venvs and installs deps)
./scripts/deploy.sh

# Or deploy specific services
./scripts/deploy.sh enzyme_check ecnumber_predict
```

### 3) Start services

```bash
# Start all backend microservices
./scripts/start.sh

# Start gateway + frontend
./scripts/start_web.sh start
```

### 4) Access

- Frontend: http://localhost:3000/enzymind
- Gateway: http://localhost:8080

### 5) Manage

```bash
./scripts/status.sh           # service status
./scripts/start_web.sh status
./scripts/stop.sh             # stop services
./scripts/start_web.sh stop
./scripts/start_web.sh restart
```

---

## Download Checkpoints

### Install dependencies

```bash
python -m pip install -U huggingface_hub
```

### Download 

```bash
./scripts/hf_models_download.sh
```

---

## AI Agent

The agent is delivered as an n8n workflow using DeepSeek-V3.2 via the built-in model node.

1. Run n8n (Docker):
   ```bash
   docker run -it --rm \
     --name n8n \
     -p 5678:5678 \
     -v n8n_data:/home/node/.n8n \
     docker.n8n.io/n8nio/n8n
   ```
2. Import workflow: `config_files/EnzyMind AI Agent with Full Tools handle fasta streaming add mcsa.json`
3. Open the DeepSeek model node and set your DeepSeek API key (and base URL if self-hosted)
4. Save and toggle the workflow to Active; the Webhook URL will be shown in the Webhook node

---

## Python client (Webhook)

```python
from agent_n8n.client import EnzyMindN8NClient

client = EnzyMindN8NClient()

# Stateless single call
resp = client.chat("Predict the EC number for P12345.")
print(resp)

# With FASTA upload
resp = client.chat(
    "Predict whether the protein in this file is enzyme?",
    fasta_file="/path/to/protein.fasta",
)
print(resp)
```

---


## Gateway

- FastAPI proxy on port 8080
- Maps `/api/...` to services on ports 18901–18918
- 300-second timeout for long-running jobs
- See gateway/README.md for full endpoint examples and port mapping

---

## Service Ports

| Service | Port | Description |
|:--------|:----:|:------------|
| enzy_recognize | 18901 | [Enzyme recognition](services/enzy_recognize/README.md) |
| ecnumber_predict | 18902 | [EC number prediction](services/ecnumber_predict/README.md) |
| substrate_predict | 18903 | [Substrate determination](services/substrate_predict/README.md) |
| kcat_predict | 18904 | [Kcat prediction](services/kcat_predict/README.md) |
| km_predict | 18905 | [Km prediction](services/km_predict/README.md) |
| structure_predict | 18906 | [Structure prediction](services/structure_predict/README.md) |
| active_sites | 18907 | [Active site prediction](services/active_sites/README.md) |
| enzyme_type | 18908 | [Enzyme type recommendation](services/enzyme_type/README.md) |
| protparam | 18909 | [Physicochemical parameters](services/protparam/README.md) |
| sequence_alignment | 18910 | [BLAST alignment](services/sequence_alignment/README.md) |
| function_get | 18911 | [Function query](services/function_get/README.md) |
| enzyme_subclass | 18912 | [Enzyme subclass query](services/enzyme_subclass/README.md) |
| ec_reaction_info | 18913 | [EC reaction info](services/ec_reaction_info/README.md) |
| enzyme_check | 18914 | [Enzyme check](services/enzyme_check/README.md) |
| enzyme_full_info | 18915 | [Full enzyme info](services/enzyme_full_info/README.md) |
| functional_site | 18916 | [Functional site query](services/functional_site/README.md) |
| kinetic_params | 18917 | [Kinetic parameters](services/kinetic_params/README.md) |
| sequence_info | 18918 | [Sequence info](services/sequence_info/README.md) |
| Gateway | 8080 | API gateway |
| Frontend | 3000 | Vue dev server |

---

## Frontend

```bash
cd frontend
npm install
npm run dev    # dev server on 3000
npm run build  # production build
```

Features: prediction dashboards, BLAST search, structure visualization (3Dmol.js), and JSME molecule editor under `public/static/jsme`.

---

## Environment Variables

```bash
export ENZYMIND_HOST=localhost        # microservice host (default localhost)
# Optional: set DeepSeek base URL in n8n DeepSeek credential if self-hosted
```

Gateway- and service-specific variables are documented inside each service folder and gateway/README.md.

---

## Development

- Each microservice is an independent FastAPI app; run tests with `pytest` inside the service directory.
- To add a new service: create a folder under `services/`, add `main.py` and `requirements.txt`, register the port in gateway `SERVICES`, and update scripts/start.sh if needed.
- Logs (when using provided scripts): `.pids/<service>.log`, `.logs/gateway.log`, `.logs/frontend.log`.



