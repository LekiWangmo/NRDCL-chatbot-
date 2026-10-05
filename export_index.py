"""Package only the public-site index, rather than local data or secrets."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from rag import DATA, ROOT, KnowledgeBase


def export_index():
    source = DATA / 'index.json'
    kb = KnowledgeBase(source)
    if not kb.payload or not kb.payload['entries']:
        raise ValueError('Run ingest.py before exporting the index.')
    for entry in kb.payload['entries']:
        url = urlsplit(entry['url'])
        if url.scheme != 'https' or url.hostname not in ('www.nrdcl.bt', 'nrdcl.bt'):
            raise ValueError('Only public NRDCL website sources can be packaged.')
    target = ROOT / 'knowledge' / 'index.json'
    target.parent.mkdir(exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(kb.payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    temporary.replace(target)
    print(f'Packaged {len(kb.payload["entries"])} chunks in {target}')


if __name__ == '__main__':
    export_index()
