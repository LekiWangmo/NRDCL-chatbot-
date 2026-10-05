import unittest
from unittest.mock import patch, Mock
import numpy as np
from ingest import normalize, fetch
from rag import KnowledgeBase, EMBED_MODEL, chunks


class RagTests(unittest.TestCase):
    def test_chunks_preserve_tail_and_overlap(self):
        text = ' '.join(str(i) for i in range(1000))
        parts = list(chunks(text, 200, 30))
        self.assertTrue(parts[-1].endswith('999'))
        self.assertTrue(all(len(part) <= 200 for part in parts))
        for a, b in zip(parts, parts[1:]):
            self.assertEqual(a[-30:], b[:30])

    def test_url_boundaries(self):
        self.assertEqual(normalize('http://nrdcl.bt/about/#top'), 'https://www.nrdcl.bt/about/')
        for url in ['https://erp.nrdcl.bt/', 'https://evil.com/', 'https://www.nrdcl.bt/wp-admin/',
                    'https://www.nrdcl.bt/?s=timber', 'https://www.nrdcl.bt/file.jpg',
                    'https://www.nrdcl.bt:1234/', 'file:///etc/passwd']:
            self.assertIsNone(normalize(url))

    def test_retrieval_threshold_and_source_diversity(self):
        kb = KnowledgeBase.__new__(KnowledgeBase)
        kb.payload = {'model': EMBED_MODEL, 'entries': [
            {'url': url, 'text': str(i)} for i, url in enumerate(['a', 'a', 'a', 'b', 'c'])]}
        kb.vectors = np.array([[1, 0], [.99, .01], [.98, .02], [.9, .1], [0, 1]])
        with patch('rag.embed', return_value=np.array([[1, 0]])):
            result = kb.retrieve('timber')
        self.assertEqual([entry['url'] for entry in result], ['a', 'a', 'b'])

    def test_no_evidence_does_not_generate(self):
        kb = KnowledgeBase.__new__(KnowledgeBase)
        with patch.object(kb, 'retrieve', return_value=[]), patch('rag.httpx.Client') as client:
            result = kb.answer('unrelated question')
        client.assert_not_called()
        self.assertEqual(result['sources'], [])

    def test_invalid_citations_are_not_presented(self):
        kb = KnowledgeBase.__new__(KnowledgeBase)
        evidence = [{'title': 'Example', 'url': 'https://www.nrdcl.bt/', 'text': 'Timber', 'fetched_at': 'today'}]
        for output in [{'answer': 'Made up answer [99]', 'citations': [99]},
                       {'answer': 'Uncited answer', 'citations': []}]:
            response = Mock()
            import json
            response.json.return_value = {'message': {'content': json.dumps(output)}}
            with patch.object(kb, 'retrieve', return_value=evidence), patch('rag.httpx.Client') as client:
                client.return_value.__enter__.return_value.post.return_value = response
                self.assertEqual(kb.answer('timber')['sources'], [])


if __name__ == '__main__':
    unittest.main()
