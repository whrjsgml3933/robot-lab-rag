"""기존 프로젝트의 공개 출처만 사용합니다. 수집 실패를 문서로 만들지 않습니다."""
import html
import json
import re
import time
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
from urllib.parse import quote

SOURCE_NAMES = {
    'wikipedia': '위키백과', 'arxiv': 'arXiv 논문',
    'semantic_scholar': 'Semantic Scholar', 'crossref': 'Crossref 학술 저널',
    'ieee': 'IEEE Spectrum 뉴스', 'reddit': 'Reddit 커뮤니티',
    'patents': 'Google Patents 특허', 'ros': 'ROS Index 패키지',
    'wikidata': 'Wikidata 팩트', 'github': 'GitHub 문서',
}


def clean(value):
    if not isinstance(value, str):
        return ''
    return html.unescape(re.sub(r'<[^>]+>', '', value)).strip()


def doc(source, title, url, text, kind='본문'):
    title, text = clean(title), clean(text)
    if not title or not text or not isinstance(url, str) or not url.startswith(('http://', 'https://')):
        return None
    return {'source_type': SOURCE_NAMES[source], 'source_key': source,
            'title': title, 'url': url, 'text': text, 'content_kind': kind}


class Collector:
    def __init__(self, settings, progress=None):
        self.settings = settings
        self.progress = progress or (lambda message: None)
        self.last_call = 0.0
        self.session = None
        self.active_source = ''

    def get(self, url, params=None, headers=None, xml=False):
        import requests
        if self.session is None:
            self.session = requests.Session()
        request_headers = {'User-Agent': os.getenv('ROBOTLAB_USER_AGENT') or self.settings['user_agent']}
        request_headers.update(headers or {})
        retries = self.settings['http_retries']
        for attempt in range(retries + 1):
            wait = self.settings['request_interval'] - (time.monotonic() - self.last_call)
            if wait > 0:
                time.sleep(wait)
            self.last_call = time.monotonic()
            try:
                response = self.session.get(url, params=params, headers=request_headers,
                                            timeout=self.settings['http_timeout'])
                if response.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                    delay = response.headers.get('Retry-After', '')
                    try:
                        seconds = max(0, float(delay))
                    except ValueError:
                        try:
                            seconds = max(0, (parsedate_to_datetime(delay) - datetime.now(timezone.utc)).total_seconds())
                        except (ValueError, TypeError, OverflowError):
                            seconds = 2 ** attempt
                    if seconds > 60:
                        self.progress(f'{self.active_source}: 서버 대기 요청이 60초를 초과해 이번 요청 중단')
                        return None
                    time.sleep(seconds)
                    continue
                if response.status_code != 200:
                    self.progress(f"{self.active_source}: HTTP {response.status_code} · 해당 요청 생략")
                    return None
                return ET.fromstring(response.content) if xml else response.json()
            except (requests.RequestException, ValueError, ET.ParseError):
                if attempt < retries:
                    time.sleep(min(2 ** attempt, 10))
                else:
                    self.progress(f'{self.active_source}: 요청·응답 해석 실패 · 해당 요청 생략')
        return None

    def collect(self, source, query):
        self.active_source = SOURCE_NAMES.get(source, source)
        try:
            method = getattr(self, source)
            values = method(query)
            return [value for value in values if value]
        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            self.progress(f'{SOURCE_NAMES.get(source, source)}: 응답 구조를 처리하지 못해 생략')
            return []

    def wikipedia(self, query):
        data = self.get('https://ko.wikipedia.org/w/api.php', {
            'action': 'query', 'format': 'json', 'generator': 'search',
            'gsrsearch': query, 'gsrlimit': 5, 'prop': 'extracts|info',
            'explaintext': 1, 'exintro': 1, 'exchars': 1800, 'inprop': 'url',
        })
        pages = (data or {}).get('query', {}).get('pages', {})
        result = []
        for page in pages.values():
            value = doc('wikipedia', page.get('title'), page.get('fullurl') or
                        'https://ko.wikipedia.org/?curid=' + str(page.get('pageid', '')),
                        page.get('extract'), '도입부 후보')
            if value:
                value['wiki_page_id'] = str(page.get('pageid', ''))
                result.append(value)
        return result

    def full_document(self, value):
        if value.get('source_key') != 'wikipedia' or not value.get('wiki_page_id'):
            return value
        data = self.get('https://ko.wikipedia.org/w/api.php', {
            'action': 'query', 'format': 'json', 'pageids': value['wiki_page_id'],
            'prop': 'extracts', 'explaintext': 1,
        })
        try:
            page = (data or {}).get('query', {}).get('pages', {}).get(value['wiki_page_id'], {})
            text = clean(page.get('extract'))
        except (AttributeError, TypeError):
            return None
        if not text:
            self.progress('선별된 위키 문서의 본문 수집 실패: 색인 생략')
            return None
        return dict(value, text=text, content_kind='본문')

    def arxiv(self, query):
        # 전체 문장을 정확한 구절 하나로 찾지 않고 검색 토큰으로 나눕니다.
        # 카테고리가 다른 Aibo/HRI 논문을 제외하지 않도록 cs.RO 제한도 제거합니다.
        tokens = re.findall(r"[A-Za-z0-9가-힣][A-Za-z0-9가-힣_-]*", query)[:8]
        if not tokens:
            return []
        expression = ' AND '.join('all:' + json.dumps(token) for token in tokens)
        root = self.get('https://export.arxiv.org/api/query', {
            'search_query': expression, 'start': 0, 'max_results': 5,
        }, xml=True)
        if root is None:
            return []
        ns = {'a': 'http://www.w3.org/2005/Atom'}
        return [doc('arxiv', item.findtext('a:title', '', ns),
                    item.findtext('a:id', '', ns), item.findtext('a:summary', '', ns), '초록')
                for item in root.findall('a:entry', ns)]

    def semantic_scholar(self, query):
        data = self.get('https://api.semanticscholar.org/graph/v1/paper/search', {
            'query': query, 'limit': 5, 'fields': 'title,abstract,year,url',
        })
        return [doc('semantic_scholar', item.get('title'), item.get('url'),
                    item.get('abstract'), '초록') for item in (data or {}).get('data', [])]

    def crossref(self, query):
        data = self.get('https://api.crossref.org/works', {'query': query + ' robot', 'rows': 6})
        result = []
        for item in (data or {}).get('message', {}).get('items', []):
            titles = item.get('title') or []
            result.append(doc('crossref', titles[0] if titles else '', item.get('URL'),
                              item.get('abstract'), '초록'))
        return result

    def ieee(self, query):
        root = self.get('https://spectrum.ieee.org/feeds/topic/robotics.rss', xml=True)
        if root is None:
            return []
        result = []
        for item in root.findall('.//item'):
            title = item.findtext('title') or ''
            text = item.findtext('description') or ''
            tokens = re.findall(r'[a-z0-9가-힣][a-z0-9가-힣_-]*', query.casefold())
            tokens = [token for token in tokens if token not in ('robot', 'robots', '로봇', 'the', 'and', 'of')]
            searchable = (title + ' ' + clean(text)).casefold()
            if any(token in searchable for token in tokens):
                result.append(doc('ieee', title, item.findtext('link'), text, 'RSS 요약'))
        return result[:5]

    def reddit(self, query):
        data = self.get('https://www.reddit.com/r/robotics/search.json', {
            'q': query, 'restrict_sr': 1, 'limit': 2,
        })
        result = []
        for item in (data or {}).get('data', {}).get('children', []):
            post = item.get('data') or {}
            text = clean(post.get('selftext'))
            if text in ('', '[removed]', '[deleted]'):
                continue
            path = post.get('permalink') or ''
            if not path:
                continue
            result.append(doc('reddit', post.get('title'), 'https://www.reddit.com' + path,
                              text, '게시글 본문'))
        return result

    def patents(self, query):
        data = self.get('https://patents.google.com/xhr/query', {'q': query + ' robot'})
        clusters = ((data or {}).get('results') or {}).get('cluster') or []
        result = []
        for cluster in clusters:
            for item in cluster.get('result') or []:
                patent = item.get('patent') or {}
                number = patent.get('publication_number')
                if number:
                    result.append(doc('patents', patent.get('title'),
                                      f'https://patents.google.com/patent/{quote(number)}/en',
                                      patent.get('snippet'), '검색 요약'))
        return result[:2]

    def ros(self, query):
        data = self.get('https://index.ros.org/api/packages/')
        if not isinstance(data, list):
            self.progress('ROS Index: 기존 엔드포인트 응답 규격 확인 필요, 수집 생략')
            return []
        result = []
        for package in data:
            if not isinstance(package, dict):
                continue
            name = package.get('name') or ''
            if query.casefold() in name.casefold():
                result.append(doc('ros', name, f'https://index.ros.org/p/{quote(name)}/',
                                  package.get('description'), '패키지 설명'))
        return result[:2]

    def wikidata(self, query):
        literal = json.dumps(query, ensure_ascii=False)
        sparql = f'''PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>
SELECT ?item ?description WHERE {{
?item rdfs:label {literal}@en.
?item schema:description ?description.
FILTER(LANG(?description) = "en")
}} LIMIT 2'''
        data = self.get('https://query.wikidata.org/sparql', {'query': sparql, 'format': 'json'})
        return [doc('wikidata', query, row.get('item', {}).get('value'),
                    row.get('description', {}).get('value'), '구조화 설명')
                for row in (data or {}).get('results', {}).get('bindings', [])]

    def github(self, query):
        # 기존 /search/code는 인증 의존성이 있고 원문을 수집하지 않았습니다.
        # 새 토큰/인증을 추가하지 않고 이 출처를 비활성 처리합니다.
        self.progress('GitHub 코드 검색: 인증 및 원문 수집 미구현으로 생략')
        return []
