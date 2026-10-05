# GitHub and Render deployment

## Hosting layout

GitHub stores the application code and a snapshot of the public NRDCL knowledge index. Render runs the web UI and FastAPI service. Both query embeddings and answer generation call a separately hosted Ollama service over authenticated HTTPS.

The Ollama models do not run on Render's free web instance. Render's `localhost` belongs to the Render instance, so it cannot reach the Ollama service running on your laptop using `http://localhost:11434`.

Choose a model host before launching the app:

- An always-on server running Ollama behind an authenticated HTTPS gateway, for independent online operation.
- Your existing computer behind an authenticated HTTPS tunnel, for a demo. Your computer, Ollama, and the tunnel must stay running for visitors to get answers.
- A hosted LLM API, which needs an additional provider integration and a compatible embedding model/index. The current deployment is prepared for Ollama.

## 1. Prepare the knowledge snapshot

The checked-in `knowledge/index.json` contains 46 chunks from 25 public website documents, collected on October 2, 2026. No local `.env` file or raw data directory is included.

After refreshing the local index, export it before committing:

```powershell
.\.venv\Scripts\python.exe ingest.py --max-pages 60
.\.venv\Scripts\python.exe export_index.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The export permits only public NRDCL HTTPS source URLs. Use the same embedding model and model version on the local indexing machine and the remote Ollama server. If that model changes, regenerate and export the index.

## 2. Publish to GitHub

Create an empty GitHub repository without adding a README, license, or `.gitignore`. If this project has not already been initialized, run `git init -b main`, then commit the files. Link and push the repository:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/nrdcl-chatbot.git
git push -u origin main
```

Git may request a GitHub sign-in through Git Credential Manager. Replace the URL with your actual repository URL. Never commit API keys, tunnel credentials, or `.env` files. GitHub Actions runs automated checks on pushes and pull requests.

## 3. Configure the remote model gateway

Install these models on the model host:

```text
ollama pull llama3.2
ollama pull nomic-embed-text
```

The HTTPS gateway must forward `/api/embed` and `/api/chat` to Ollama, support requests lasting up to 120 seconds, and enforce authentication. Keep raw port 11434 private. Ollama's local API does not itself enforce a bearer token: merely setting `OLLAMA_API_KEY` does not protect a self-hosted server. Your gateway must validate it.

For a bearer-token gateway, Render sends `Authorization: Bearer <OLLAMA_API_KEY>`. Alternatively, a Cloudflare Access gateway can require a service token using `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET`; set both secrets in Render and omit the bearer key. Do not use a public unauthenticated tunnel.

## 4. Deploy the web app on Render

In the Render dashboard, create a **Blueprint**, connect the GitHub repository, and select its `render.yaml`. It explicitly selects a free web instance for the web app; the separate model host may incur costs.

Set these values when prompted:

| Variable | Value |
| --- | --- |
| `OLLAMA_URL` | The authenticated HTTPS gateway base URL, for example `https://models.your-domain.com` (without `/api`) |
| `OLLAMA_API_KEY` | The secret enforced by the gateway |

For Cloudflare Access instead, remove the `OLLAMA_API_KEY` prompt from the Blueprint and add `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET` entries with `sync: false` before creating the Blueprint. Both authentication methods are supported by the app. Enter secrets only in Render's environment settings.

You can also create a Web Service manually with these settings:

| Setting | Value |
| --- | --- |
| Runtime | Python |
| Build command | `pip install -r requirements.lock.txt` |
| Start command | `python -m uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1` |
| Health check | `/healthz` |
| `PYTHON_VERSION` | `3.11.9` |
| `INDEX_PATH` | `knowledge/index.json` |
| `CHAT_MODEL` | `llama3.2:latest` |
| `EMBED_MODEL` | `nomic-embed-text` |

Set the model gateway URL and credentials as above. The service rejects a local or unauthenticated Ollama configuration on Render to avoid deploying an app that cannot make remote model calls.

## 5. Verify the online service

Open the Render-provided HTTPS URL. `/healthz` checks that the app is running without starting model inference. `/api/status` reports the loaded index; neither endpoint confirms the remote model is available.

Ask “What is NRDCL's mission?” and verify the cited company-profile link. Ask an unrelated question and verify that the assistant declines to answer. Check Render logs if the model service is unavailable. A successful page or health check alone is not proof that chat works.

## Updates and operating limits

The index is bundled into the deployment, so no persistent disk is needed. Refresh and export it locally, commit `knowledge/index.json`, and push to redeploy. Do not refresh it only on Render's temporary filesystem.

Free Render instances sleep after 15 minutes of inactivity and may take about a minute to wake up. They are intended for demos, rather than production. This app permits two concurrent chat calls and limits questions to ten per minute per observed client address. The limits are held in one process and reset on restart. If the proxy does not forward a trusted client address, visitors share the limit. Add gateway-level quotas for production workloads.

Documentation: [Render FastAPI deployment](https://render.com/docs/deploy-fastapi), [Blueprint reference](https://render.com/docs/blueprint-spec), [free-service limitations](https://render.com/docs/free), and [Ollama authentication](https://docs.ollama.com/api/authentication).
