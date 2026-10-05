"""Manual end-to-end quality check; requires the local models and index."""
from unittest.mock import patch
import httpx
from rag import KnowledgeBase

if __name__ == '__main__':
    kb = KnowledgeBase()
    original = httpx.Client.post

    def inspect(client, url, **kwargs):
        response = original(client, url, **kwargs)
        if url.endswith('/api/chat'):
            print('Model output:', response.json().get('message', {}).get('content'), flush=True)
        return response

    for question in ["What is NRDCL's mission?", 'Who won the football world cup in 2018?']:
        print('\nQuestion:', question, flush=True)
        print('Retrieved:', [(e['title'], e['score']) for e in kb.retrieve(question)], flush=True)
        with patch.object(httpx.Client, 'post', inspect):
            print('Result:', kb.answer(question), flush=True)
