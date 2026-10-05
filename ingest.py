"""Bounded, robots-aware crawl of public NRDCL HTML and text PDFs."""
import argparse
import io
import json
import time
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from rag import DATA, build_index

BASE = 'https://www.nrdcl.bt/'
AGENT = 'NRDCLKnowledgeBot'
MAX_BYTES = 15 * 1024 * 1024


def normalize(url):
    parts = urlsplit(url)
    if parts.scheme not in ('https', 'http') or parts.hostname not in ('www.nrdcl.bt', 'nrdcl.bt'):
        return None
    if parts.username or parts.password or parts.port not in (None, 80, 443):
        return None
    if parts.query or any(p in parts.path.lower() for p in ('/wp-admin', '/wp-login', '/feed/', '/xmlrpc', '/wp-json')):
        return None
    suffix = parts.path.lower().rsplit('/', 1)[-1]
    if '.' in suffix and not suffix.endswith(('.pdf', '.html', '.htm')):
        return None
    return urlunsplit(('https', 'www.nrdcl.bt', parts.path or '/', '', ''))


def fetch(client, url):
    # Redirects are followed manually so the crawler cannot leave the allowlisted site.
    for _ in range(5):
        with client.stream('GET', url) as response:
            if response.is_redirect:
                target = normalize(urljoin(url, response.headers.get('location', '')))
                if not target:
                    raise ValueError('Blocked external redirect')
                url = target
                continue
            response.raise_for_status()
            body = bytearray()
            for block in response.iter_bytes():
                body.extend(block)
                if len(body) > MAX_BYTES:
                    raise ValueError('Document exceeds 15 MB limit')
            return url, response.headers.get('content-type', ''), bytes(body)
    raise ValueError('Too many redirects')


def crawl(max_pages=60, delay=1):
    documents, errors = [], []
    queue = deque([BASE, urljoin(BASE, 'about-us/company-profile/'),
                   urljoin(BASE, 'contact-us/contact/'), urljoin(BASE, 'announcement/general/')])
    seen = set()
    with httpx.Client(timeout=30, headers={'User-Agent': AGENT}, follow_redirects=False) as client:
        robots = RobotFileParser()
        response = client.get(urljoin(BASE, 'robots.txt'))
        if response.status_code == 404:
            robots.parse([])
        else:
            response.raise_for_status()
            robots.parse(response.text.splitlines())
        delay = max(delay, robots.crawl_delay(AGENT) or robots.crawl_delay('*') or 0)
        while queue and len(seen) < max_pages:
            url = queue.popleft()
            if url in seen:
                continue
            seen.add(url)
            if not robots.can_fetch(AGENT, url):
                errors.append({'url': url, 'error': 'Disallowed by robots.txt'})
                continue
            time.sleep(delay)
            try:
                final, content_type, body = fetch(client, url)
                fetched = datetime.now(timezone.utc).isoformat()
                if 'application/pdf' in content_type or final.lower().endswith('.pdf'):
                    pdf = PdfReader(io.BytesIO(body))
                    for number, page in enumerate(pdf.pages[:150], 1):
                        text = (page.extract_text() or '').strip()
                        if text:
                            documents.append({'url': final + f'#page={number}',
                                              'title': f'{final.rsplit("/", 1)[-1]} — page {number}',
                                              'text': text, 'fetched_at': fetched})
                elif 'text/html' in content_type:
                    soup = BeautifulSoup(body, 'html.parser')
                    for link in soup.select('a[href]'):
                        target = normalize(urljoin(final, link['href']))
                        if target and target not in seen and target not in queue:
                            queue.append(target)
                    title = soup.title.get_text(' ', strip=True) if soup.title else final
                    for element in soup.select('script,style,nav,footer,header,form,.sidebar,#secondary'):
                        element.decompose()
                    main = soup.select_one('.entry-content') or soup.find('main') or soup.body or soup
                    text = '\n'.join(line.strip() for line in main.get_text('\n', strip=True).splitlines() if line.strip())
                    if len(text) > 80:
                        documents.append({'url': final, 'title': title, 'text': text, 'fetched_at': fetched})
                print(f'Fetched {len(seen)}/{max_pages}: {url}')
            except (httpx.HTTPError, ValueError, OSError) as exc:
                errors.append({'url': url, 'error': str(exc)})
                print(f'Skipped {url}: {exc}')
    return documents, errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-pages', type=int, default=60)
    parser.add_argument('--delay', type=float, default=1)
    parser.add_argument('--crawl-only', action='store_true', help='Save content without embedding')
    parser.add_argument('--index-only', action='store_true', help='Embed previously crawled content')
    args = parser.parse_args()
    if args.max_pages < 1 or args.delay < 0 or (args.crawl_only and args.index_only):
        parser.error('Invalid crawl options')
    DATA.mkdir(exist_ok=True)
    if args.index_only:
        documents = json.loads((DATA / 'documents.json').read_text(encoding='utf-8'))
    else:
        documents, errors = crawl(args.max_pages, args.delay)
        if not documents:
            raise SystemExit('No documents collected; existing data has been preserved.')
        (DATA / 'documents.json').write_text(json.dumps(documents, ensure_ascii=False), encoding='utf-8')
        (DATA / 'crawl-report.json').write_text(json.dumps(errors, indent=2), encoding='utf-8')
        print(f'Saved {len(documents)} documents; {len(errors)} skipped URLs.')
    if not args.crawl_only:
        print(f'Indexed {build_index(documents)} chunks. Restart the server to load the new index.')
