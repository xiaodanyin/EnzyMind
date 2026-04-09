# EnzyMind N8N Agent

Deploy the EnzyMind AI Agent on the n8n workflow platform and expose a Webhook-based chat interface.

## Table of Contents

- [1. Start n8n Service](#1-start-n8n-service)
- [2. Configure DeepSeek-V3.2](#2-configure-deepseek-v32)
- [3. Import Workflow Configuration](#3-import-workflow-configuration)
- [4. Configure API Keys](#4-configure-api-keys)
- [5. Activate Workflow](#5-activate-workflow)
- [6. Use the Python Client](#6-use-the-python-client)

---

## 1. Start n8n Service

Start n8n with Docker:

```bash
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  docker.n8n.io/n8nio/n8n
```

> **Run in background**: Replace `-it --rm` with `-d` to run the container in detached mode.

After startup, visit `http://localhost:5678` to open the n8n UI. On first visit, create an admin account.

---

## 2. Configure DeepSeek-V3.2

We use DeepSeek-V3.2 via the built-in model node. After importing the workflow, open the DeepSeek model node and set your credentials/base URL as needed.

---

## 3. Import Workflow Configuration

1. In the n8n main UI, click the **...** menu in the upper right
2. Choose **Import from File**
3. Select the config file:
  - `config_files/EnzyMind AI Agent with Full Tools handle fasta streaming add mcsa.json`

After importing, you will see the full workflow, including:
- **Webhook** entry node
- **AI Agent** core node
- Multiple **HTTP Tool** nodes (connecting to the EnzyMind Gateway API)
- **Simple Memory** node (maintains conversation context)

---

## 4. Configure API Keys

### DeepSeek API Key

1. Obtain your DeepSeek API key from your DeepSeek account
2. In n8n, double-click the **DeepSeek Chat Model** node (inside the imported workflow)
3. Click the **Credentials** dropdown > **Create New Credential**
4. Enter your DeepSeek API key (and base URL if using a self-hosted endpoint)
5. Save

---

## 5. Activate Workflow

1. After configuration, click **Save** in the upper right
2. Toggle **Inactive** to **Active** in the upper right
3. Once activated, the Webhook starts listening for requests

> **Production URL**: After activation, click the Webhook node to view the Production URL.
> Default format: `http://localhost:5678/webhook/8e6add2a-15cd-4a13-be8f-937593f5680a`

---

## 6. Use the Python Client

### Install dependency

```bash
pip install requests
```

### Basic usage

```python
from agent_n8n.client import EnzyMindN8NClient

# Create client (one initialization = one conversation session)
client = EnzyMindN8NClient()

# Send message
response = client.chat("Is P06865 an enzyme?")
print(response)

# Continue conversation (shared context, AI remembers prior turns)
response = client.chat("What are its active sites?")
print(response)
```
### With FASTA file input
```python
from agent_n8n.client import EnzyMindN8NClient

client = EnzyMindN8NClient()

# Regular chat
client.chat("Is P06865 an enzyme?")

# Upload FASTA file
client.chat(
  "Predict whether the proteins in this file are enzymes", 
    fasta_file="/path/to/protein.fasta"
)
```
### Custom configuration

```python
# Custom n8n service address
client = EnzyMindN8NClient(base_url="https://your-n8n-server.com")

# Custom userID (for restoring a specific session)
client = EnzyMindN8NClient(user_id="my-session-123")

# Adjust timeout (default 300 seconds)
client = EnzyMindN8NClient(timeout=600)
```

### Start a new conversation

```python
# Option 1: create new instances
client1 = EnzyMindN8NClient()  # conversation 1
client2 = EnzyMindN8NClient()  # conversation 2 (separate context)

# Option 2: reset the current instance
client = EnzyMindN8NClient()
client.chat("First round of conversation...")
client.new_conversation()  # reset userID
client.chat("This is a new conversation...")
```

### Quick stateless call

```python
from agent_n8n.client import quick_chat

# Stateless single call
response = quick_chat("Predict the EC number for P12345")
```

---

## API Reference

### EnzyMindN8NClient

| Method | Description |
|------|------|
| `__init__(base_url, user_id, timeout)` | Initialize the client |
| `chat(message) -> str` | Send a message and get the response |
| `new_conversation() -> str` | Start a new conversation and return the new userID |

### Properties

| Property | Description |
|------|------|
| `user_id` | Unique identifier for the current session |
| `webhook_url` | Full Webhook URL |
| `base_url` | Base URL of the n8n service |

---

## Troubleshooting

### Request timeout

AI inference can take time, especially for complex queries. Try increasing the timeout:

```python
client = EnzyMindN8NClient(timeout=600)  # 10 minutes
```

### Connection refused

1. Confirm the n8n service is running: `docker ps | grep n8n`
2. Confirm the workflow is activated (Active state)
3. Check firewall rules for port 5678

### Webhook 404

1. Confirm the workflow is activated
2. Verify the Webhook path (check the Webhook node configuration)

---

## Configuration Files

| File | Description |
|------|------|
| `EnzyMind AI Agent with Full Tools handle fasta streaming add mcsa.json` | Uses DeepSeek-V3.2 model |