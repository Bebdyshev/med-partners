# MedArchive — AWS Step Functions Pipeline

Serverless alternative to the Celery worker for asynchronous document processing.

## Architecture

```
S3 Upload Trigger
      │
      ▼
  EventBridge ──► Step Functions State Machine
                        │
                        ├─ ValidateUpload (Lambda)
                        ├─ ChooseExtractor (Choice state)
                        │     ├─ VisionOCRExtract (Lambda — Qwen2.5-VL / gpt-4o)
                        │     ├─ PDFExtract (Lambda)
                        │     ├─ SpreadsheetExtract (Lambda)
                        │     └─ GenericExtract (Lambda — DOCX)
                        ├─ LLMNormalize (Lambda — Qwen2.5:7b / gpt-4o-mini)
                        ├─ EmbedAndRerank (ECS Fargate — multilingual-e5-large / openai)
                        ├─ StoreResults (Lambda → RDS PostgreSQL)
                        └─ NotifyComplete (SNS → webhook / email)
```

## Local vs Cloud AI providers

| Stage | OpenAI (cloud) | Ollama (on-premise) |
|---|---|---|
| Name normalization | `gpt-4o-mini` | `qwen2.5:7b` |
| LLM reranking | `gpt-4o-mini` | `qwen2.5:7b` |
| Vision OCR | `gpt-4o` | `qwen2.5vl:7b` |
| Embeddings | `text-embedding-3-large` | `intfloat/multilingual-e5-large` |

Switch with a single env var: `LLM_PROVIDER=ollama`.

## Setup

```bash
# 1. Install AWS SAM CLI
brew install aws-sam-cli

# 2. Deploy state machine
aws cloudformation deploy \
  --template-file cloudformation.yaml \
  --stack-name medarchive-pipeline \
  --capabilities CAPABILITY_IAM

# 3. Set state machine ARN in backend .env
AWS_SFN_ARN=arn:aws:states:us-east-1:ACCOUNT:stateMachine:medarchive-document-pipeline
```

## Local Ollama setup (on-premise mode)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull models
ollama pull qwen2.5:7b          # LLM judge + name cleaning (~4.7 GB)
ollama pull qwen2.5vl:7b        # Vision OCR (~5.6 GB)

# Local embeddings (Python)
pip install sentence-transformers
# Model downloads automatically on first use:
# intfloat/multilingual-e5-large (~560 MB)

# Switch to local AI in backend/.env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_VISION_MODEL=qwen2.5vl:7b
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=intfloat/multilingual-e5-large
```

## Cost comparison

| Mode | Embedding | Normalization | Reranking | Vision OCR | Monthly (10k docs) |
|---|---|---|---|---|---|
| Full OpenAI | $0.13/1M tok | $0.15/1M tok | $0.15/1M tok | $5/1k img | ~$80–200 |
| Hybrid (embed local) | $0 | $0.15/1M tok | $0.15/1M tok | $5/1k img | ~$30–80 |
| Full local (Ollama) | $0 | $0 | $0 | $0 | $0 (hardware only) |
