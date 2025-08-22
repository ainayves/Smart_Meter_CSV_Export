# Smart Meter CSV Export – FastAPI

This service provides endpoints to request CSV exports for smart meters, check job status, and download completed files. Jobs are processed asynchronously in a thread pool.

## Quick Start


```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
## Launch test & coverage

```bash
pytest --cov=app --cov-report=html -q
```

View coverage here : `root_dir/htmlcov/index.html`

## API docs

```bash
{HOST_URL}/api/docs
```
