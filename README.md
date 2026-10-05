# NRDCL RAG chatbot

A Python chatbot over public content from https://www.nrdcl.bt/. Ollama runs both the language model and semantic embeddings. A small FastAPI server serves a responsive browser interface and returns numbered source links. It can run locally or on Render with a remotely hosted Ollama gateway.

For GitHub and Render setup, see [DEPLOYMENT.md](DEPLOYMENT.md). The included `render.yaml` configures the web service; `knowledge/index.json` packages the public-site index for deployment.

## Run on Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull llama3.2
ollama pull nomic-embed-text
Copy-Item .env.example .env
.\.venv\Scripts\python.exe ingest.py --max-pages 60
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Keep Ollama running. Open **http://127.0.0.1:8000**. No API key is required. You can change `CHAT_MODEL` in `.env` to another installed Ollama model. Changing `EMBED_MODEL` requires rebuilding the index.

## How it works

1. The crawler follows public NRDCL links, respects robots.txt, waits between requests, and extracts HTML and text PDF pages.
2. Text is split into overlapping chunks. Ollama embeds each chunk; normalized vectors and source metadata are stored in `data/index.json`.
3. A question is embedded and compared to the stored vectors. Up to five relevant chunks are supplied to the language model.
4. The model returns an answer and source numbers. Missing valid source numbers or invalid inline references trigger an insufficient-information response. If the model provides source numbers but omits inline markers, the server adds those markers. Source URLs come from the index, rather than model-generated links.

All model inference runs through the configured Ollama endpoint. A remote endpoint receives questions and retrieved excerpts to generate answers. The browser loads optional Google Fonts; remove the CSS import for a fully offline UI after ingestion and model download.

## Refresh the knowledge base

```powershell
.\.venv\Scripts\python.exe ingest.py --max-pages 100
```

Restart the web server after indexing. `data/crawl-report.json` lists skipped URLs. The crawl is bounded; it does not claim to cover the entire site. To separate downloading from embedding:

```powershell
.\.venv\Scripts\python.exe ingest.py --crawl-only --max-pages 60
.\.venv\Scripts\python.exe ingest.py --index-only
```

## Verify

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe check_answers.py
```

The second command runs live model checks and prints retrieved sources, raw model responses, and the final answers. Try “What is NRDCL's mission?”, “How can I contact NRDCL?” and an unrelated question. Verify every answer against its sources. `MIN_SIMILARITY` controls retrieval filtering and needs calibration against representative questions; it is not a confidence probability. `requirements.lock.txt` records the dependency versions installed for this prototype.

## Scope and deployment

This is an independent local prototype, not an official NRDCL service. It handles each question independently; prior chat turns are not supplied to the model. Text PDFs are supported, scanned PDFs require OCR. Dynamic pages, tables, and images may need custom extraction. Crawl timestamps indicate download time, not a notice's publication date. Old documents can contain outdated contacts or prices, and source citations do not guarantee factual correctness.

Before public website integration, evaluate answer accuracy with NRDCL staff, curate current sources, schedule refreshes, and add monitoring and an appropriate data-retention policy. The app includes model request timeouts, concurrency limits, and a basic in-memory per-client rate limit. The local run command binds to localhost; Render uses its managed HTTPS endpoint. Keep raw Ollama on a private interface behind an authenticated gateway. No deployment is performed by adding the configuration files alone.

Ollama API references: [embeddings](https://docs.ollama.com/api/embed), [chat](https://docs.ollama.com/api/chat).
