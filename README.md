## Smart Meter CSV Export – FastAPI

This service provides endpoints to request CSV exports for smart meters, check job status, and download completed files. Jobs are processed asynchronously in a thread pool.

## Quick Start


```bash

#Venv for linux and Mac
python -m venv .venv && source .venv/bin/activate 

#Venv for Windows

python -m venv venv
.\venv\Scripts\activate
 
# Install requirements
pip install -r requirements.txt

# Copy app/.env.example and change app/.env according to your needs

# Then, launch 
python -m app.main

Serve on a shown HOST_URL:PORT
```
## Launch test & coverage

```bash
pytest --cov=app --cov-report=html -q
```

View coverage here : `root_dir/htmlcov/index.html`

## API docs

```bash
http://{HOST_URL:PORT}/api/docs
http://{HOST_URL:PORT}/api/redoc

```
