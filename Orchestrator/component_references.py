"""Small curated reference catalogue, not arbitrary model-directed browsing."""
from html.parser import HTMLParser
import re
import time
import urllib.request
from cognitive_providers import NoRedirect
from investigation import validate_sources
from research_providers import WikipediaRetrieval


class Paragraphs(HTMLParser):
    def __init__(self):
        super().__init__();self.depth=0;self.skip=0;self.buffer=[];self.rows=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
        if tag in ('p','li'):
            if not self.depth:self.buffer=[]
            self.depth+=1
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
        if tag in ('p','li') and self.depth:
            self.depth-=1
            if not self.depth:self.rows.append(' '.join(' '.join(self.buffer).split()))
    def handle_data(self,data):
        if self.depth and not self.skip:self.buffer.append(data)


class ComponentReferences:
    name='curated_component_catalog_v1'
    URL='https://www.felpro.com/parts/performance/valve-cover-gaskets.html'
    def __init__(self,opener=None,fallback=None):
        self.opener=opener or urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        self.fallback=fallback or WikipediaRetrieval();self.cache=None
    def retrieve(self,query):
        terms=set(re.findall('[a-z0-9]+',query.casefold()))
        if not {'engine','cover'}<=terms:return self.fallback.retrieve(query)
        if self.cache is None:
            request=urllib.request.Request(self.URL,headers={'User-Agent':'ORYN-ResearchPrototype/0.1','Accept':'text/html'})
            with self.opener.open(request,timeout=20) as response:raw=response.read(524289)
            if len(raw)>524288:raise ValueError('Reference exceeds bound.')
            parser=Paragraphs();parser.feed(raw.decode('utf-8'))
            rows=[r for r in parser.rows if re.search(r'valve cover|valvetrain|V8 engines',r,re.I)]
            excerpt='\n'.join(dict.fromkeys(rows))[:2500]
            self.cache=validate_sources([{'id':'felpro-valve-cover-performance','title':'Fel-Pro performance valve cover gaskets',
                'url':self.URL,'excerpt':excerpt,'source_type':'primary_manufacturer_general_application',
                'retrieved_at':time.time(),'object_revision':None,'object_match':None,'revision_match':None}])
        return self.cache
