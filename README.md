# LakeB2B Pitch Deck Creator

Batch pitch deck generation from Excel prospect lists. Upload an Excel file with prospect companies, and the system will:

1. **Research** each company via Perplexity Sonar API
2. **Generate** personalized pitch content via Claude Sonnet
3. **Create** slide decks via Gamma API with LakeB2B branding
4. **Save** all deck URLs back into the Excel file

## Quick Start

### Prerequisites
- Python 3.11+
- Docker (for Redis)
- API keys: Gamma, Perplexity, Anthropic

### 1. Setup
```bash
cd "Pitch Deck Creator"
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start Redis
```bash
docker-compose up -d
```

### 3. Start Celery Worker
```bash
celery -A app.workers.tasks worker --concurrency=1 --loglevel=info
```

### 4. Start Web Server
```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Open
Visit [http://localhost:8000](http://localhost:8000) and upload your Excel file.

## Excel Format

| Company Name | Industry | Website URL | Contact Name | Contact Title |
|---|---|---|---|---|
| Acme Corp | SaaS | acme.com | John Doe | VP Sales |

**Required column:** `Company Name` (or `Company`, `Account Name`)  
**Optional columns:** `Industry`, `Website URL`, `Contact Name`, `Contact Title`

## Architecture

```
Excel Upload → FastAPI → Celery Queue → [Research → Content Gen → Gamma API] × N rows → Output Excel
```

## Configuration

Edit `data/services_catalog.yaml` to customize LakeB2B service definitions.
Edit `.env` to set API keys and branding colors.
