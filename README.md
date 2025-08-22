## Smart Meter CSV Export – FastAPI

This service provides endpoints to request CSV exports for smart meters, check job status, and download completed files. Jobs are processed asynchronously in a thread pool.

## Quick Start


```bash

#For linux and Mac
python -m venv .venv && source .venv/bin/activate 

#For Windows

python -m venv venv
.\venv\Scripts\activate
 

pip install -r requirements.txt
uvicorn app.main:app --reload

Serve on a shown HOST_URL:PORT
```
## Launch test & coverage

```bash
pytest --cov=app --cov-report=html -q
```

View coverage here : `root_dir/htmlcov/index.html`

## API docs

```bash
{HOST_URL:PORT}/api/docs
```
