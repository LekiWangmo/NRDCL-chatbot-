import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import rag
import app


class DeploymentTests(unittest.TestCase):
    def test_load_exported_index_without_local_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'index.json'
            path.write_text(json.dumps({'model': rag.EMBED_MODEL, 'entries': [{'text': 'hello'}],
                                        'vectors': [[1, 0]]}), encoding='utf-8')
            with patch.dict('os.environ', {'INDEX_PATH': str(path)}):
                kb = rag.KnowledgeBase()
            self.assertEqual(kb.vectors.shape, (1, 2))

    def test_render_rejects_localhost_and_missing_auth(self):
        with patch.dict('os.environ', {'RENDER': 'true'}):
            with patch.object(rag, 'OLLAMA', 'http://localhost:11434'):
                with self.assertRaises(ValueError):
                    rag.validate_hosted_config()
            with patch.object(rag, 'OLLAMA', 'https://model.example.com'), \
                    patch.object(rag, 'OLLAMA_API_KEY', ''), \
                    patch.object(rag, 'CF_ACCESS_CLIENT_ID', ''), \
                    patch.object(rag, 'CF_ACCESS_CLIENT_SECRET', ''):
                with self.assertRaises(ValueError):
                    rag.validate_hosted_config()

    def test_remote_credentials_sent_to_model_client(self):
        with patch.object(rag, 'OLLAMA_API_KEY', 'example-token'), \
                patch.object(rag, 'CF_ACCESS_CLIENT_ID', ''), \
                patch.object(rag, 'CF_ACCESS_CLIENT_SECRET', ''):
            self.assertEqual(rag.ollama_headers(), {'Authorization': 'Bearer example-token'})

    def test_health_and_request_rate_limit(self):
        client = TestClient(app.app)
        self.assertEqual(client.get('/healthz').status_code, 200)
        with patch.object(app, 'RATE_LIMIT', 1), patch.object(app, 'recent_requests', app.OrderedDict()), \
                patch.object(app.kb, 'answer', return_value={'answer': 'example', 'sources': []}):
            self.assertEqual(client.post('/api/chat', json={'question': 'Hello'}).status_code, 200)
            result = client.post('/api/chat', json={'question': 'Hello'})
            self.assertEqual(result.status_code, 429)
            self.assertEqual(result.headers['retry-after'], '60')


if __name__ == '__main__':
    unittest.main()
