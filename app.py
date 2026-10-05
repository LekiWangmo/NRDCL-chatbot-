import logging
import os
import time
from collections import OrderedDict, deque
from pathlib import Path
from threading import BoundedSemaphore, Lock

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from rag import KnowledgeBase, CHAT_MODEL, EMBED_MODEL, validate_hosted_config

validate_hosted_config()
app = FastAPI(title='NRDCL Knowledge Assistant')
kb = KnowledgeBase()
if os.getenv('RENDER') and (not kb.payload or kb.payload['model'] != EMBED_MODEL):
    raise ValueError('Deploy a knowledge index matching EMBED_MODEL before starting Render.')
slots = BoundedSemaphore(2)
rate_lock = Lock()
recent_requests = OrderedDict()
RATE_LIMIT = int(os.getenv('CHAT_REQUESTS_PER_MINUTE', '10'))
STATIC = Path(__file__).resolve().parent / 'static'
app.mount('/static', StaticFiles(directory=STATIC), name='static')


class Question(BaseModel):
    question: str = Field(min_length=2, max_length=1500)


@app.get('/')
def home():
    return FileResponse(STATIC / 'index.html')


@app.get('/api/status')
def status():
    return {'indexed': kb.payload is not None, 'chat_model': CHAT_MODEL, 'embed_model': EMBED_MODEL,
            'documents': kb.payload['documents'] if kb.payload else 0,
            'indexed_at': kb.payload['indexed_at'] if kb.payload else None}


@app.get('/healthz')
def health():
    # Liveness checks must not load a model or consume remote inference capacity.
    return {'status': 'ok', 'indexed': kb.payload is not None}


def limit_requests(identity):
    now = time.monotonic()
    with rate_lock:
        expired = [key for key, hits in recent_requests.items() if not hits or hits[-1] <= now - 60]
        for key in expired:
            del recent_requests[key]
        hits = recent_requests.setdefault(identity, deque())
        recent_requests.move_to_end(identity)
        while hits and hits[0] <= now - 60:
            hits.popleft()
        if len(hits) >= RATE_LIMIT:
            raise HTTPException(429, 'Too many questions. Please wait a minute.', headers={'Retry-After': '60'})
        hits.append(now)
        if len(recent_requests) > 10000:
            recent_requests.popitem(last=False)


@app.post('/api/chat')
def chat(body: Question, request: Request):
    question = body.question.strip()
    if len(question) < 2:
        raise HTTPException(422, 'Please enter a question.')
    limit_requests(request.client.host if request.client else 'unknown')
    if not slots.acquire(blocking=False):
        raise HTTPException(429, 'The assistant is busy. Please try again shortly.')
    try:
        return kb.answer(question)
    except httpx.HTTPError:
        logging.exception('Ollama request failed')
        raise HTTPException(503, 'The model service is unavailable. Please try again later.')
    except ValueError as exc:
        logging.warning('Chat answer could not be generated: %s', type(exc).__name__)
        raise HTTPException(503, 'The knowledge or model configuration needs attention. Please contact the administrator.')
    finally:
        slots.release()
