from flask import Flask, render_template
from flask import request
import json
import pdb
import requests
import time
import re
from benedict import benedict
from lxml import html, etree
import aiohttp
import asyncio
from aiohttp_client_cache import CachedSession, SQLiteBackend



app = Flask(__name__)

class Browser(object):
    def __init__(self, name, url, template, default={}, headers={}, xpath=[], exclude_xpath=[], seperator="", link_conversion={}, method="POST"):
        self.name = name
        self.url = url
        if headers:
            self.headers = headers
        else:
            self.headers = {
                    'accept': 'application/json, text/javascript, */*; q=0.01', 
                    'content-type': 'application/json; charset=UTF-8', 
                    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36', 
                    'accept-language': 'zh-CN,zh;q=0.9'}
        self.template = template
        self.default = default.copy()
        self.payload = {}
        self.xpath = xpath
        self.exclude_xpath = exclude_xpath
        self.seperator = seperator
        self.link_conversion = link_conversion
        self.response = None
        self.method = method

    async def query(self, session, **kwargs):
        def replace_query():
            remove_query = False
            for k,v in self.payload.items():
                if v == '{query}':
                    self.payload[k] = self.payload.get('query')
                    remove_query = True
            if 'query' in self.payload and remove_query:
                self.payload.pop('query')

        if 'refresh' in kwargs and kwargs.pop('refresh') == 'true':
            do_refresh = True
        else:
            do_refresh = False
        self.payload = benedict(self.default.copy())
        for k, v in kwargs.items():
            self.payload[k] = v
        replace_query()

        if self.xpath:
            self.response = await self.get_html(session)
        else:
            self.response = await self.get_json(session, self.method)

    async def get_json(self, session, method="POST"):
        if method == "GET":
            r = await session.request(method=method, url=self.url.format(**self.payload), headers=self.headers)
        elif method == "POST":
            r = await session.request(method=method, url=self.url, data=json.dumps(self.payload), headers=self.headers)
        return await r.json()

    async def get_html(self, session):
        def extract_html(xpath):
            selected = doc.xpath(xpath)
            if self.link_conversion:
                list(map(self.convert_links, selected))
            if self.exclude_xpath:
                list(map(self.remove_xpath, selected))
            return self.seperator.join([etree.tostring(node).decode('utf-8').replace('\\n','') for node in selected])

        def extract_text(xpath):
            return "</br>".join([node.text_content() for node in doc.xpath(xpath)])

        print(self.url.format(**self.payload))
        r = await session.request(method="GET", url=self.url.format(**self.payload), headers=self.headers)
        doc = html.fromstring(await r.text())
        if self.payload['extract'] == 'html':
            selected  = [extract_html(xpath) for xpath in self.xpath]
        else:
            selected  = [extract_text(xpath) for xpath in self.xpath]
        return selected

    def remove_xpath(self, node):
        for xpath in self.exclude_xpath:
            tags_to_remove = node.xpath(xpath)
            list(map(lambda tag:tag.getparent().remove(tag), tags_to_remove))

    def convert_links(self, node):
        def replace_a_href(a_tag):
            if isinstance(regex, list):
                has_found_query = list(map(lambda x:re.search(x, a_tag.get('href')), regex))
                query = dict()
                [query.update(m.groupdict()) for m in has_found_query if m]
                if not query:
                    return
                query = ["{k}={v}".format(k=k,v=v) for k, v in query.items()]
                query_string = "&".join(query)
                a_tag.set('href', target.format(query_string=query_string))
            elif isinstance(regex, str):
                has_found_query = re.search(regex, a_tag.get('href'))
                if has_found_query:
                    if has_found_query.groupdict():
                        query = {k:v if v is not None else '' for k, v in has_found_query.groupdict().items()}
                        a_tag.set('href', target.format(**query))
                    else:
                        query = has_found_query.group(1)
                        a_tag.set('href', target.format(query=query))

        for xpath, conversion in self.link_conversion.items():
            if isinstance(conversion, dict):
                regex = conversion.get('regex')
                target = conversion.get('target')
            elif isinstance(conversion, str):
                regex = conversion
                target = '?query={query}'
            a_tags = node.xpath(xpath)
            a_tags = [a for a in a_tags if a.get('href')]
            list(map(replace_a_href, a_tags))

    def render(self):
        if isinstance(self.response, dict):
            debug_json = dict([(k, v) for k, v in self.response.items() if k != 'list' and v is not None and v != []])
            return render_template(self.template, raw_json = json.dumps(debug_json, indent=4, ensure_ascii=False), payload=self.payload, **self.response)
        elif isinstance(self.response, list) and not self.xpath:
            return render_template(self.template, raw_json = json.dumps(self.response, indent=4, ensure_ascii=False), payload=self.payload, resp_list=self.response)
        else:
            return render_template(self.template, payload=self.payload, responses=self.response, service_name=self.name, url=self.url.format(**self.payload))

    def has_empty_response(self):
        return len(self.response) == 0 or (isinstance(self.response, list) and isinstance(self.response[0], str) and "".join(self.response) == "")

services = {
    'reverso-context': Browser('reverso', "https://context.reverso.net/bst-query-service", "reverso_context.html", {'source_lang': 'en', 'target_lang': 'zh', 'source_text': '{query}', 'target_text': '', 'mode': '1', 'nrows': '50'}),
    'wantwords': Browser('wantwords', "https://wantwords.net/ChineseRD/?q={query}&m={m}", "wantwords.html", {'query':'', 'm':'EnZh'}, method='GET'),
    'deepl': Browser('deepl', "https://www2.deepl.com/jsonrpc", "deepl.html",
        {"jsonrpc":"2.0","method": "LMT_handle_jobs","params":{"jobs":[{"kind":"default","sentences":[{"text":"","id":0,"prefix":""}],"raw_en_context_before":[],"raw_en_context_after":[],"preferred_num_beams":4,"quality":"fast"}],"lang":{"user_preferred_langs":["ZH","EN"],"source_lang_user_selected":"auto","target_lang":"ZH"},"priority":-1,"commonJobParams":{"browserType":129,"formality":None},"apps":{"usage":5},"timestamp":1646624556415},"id":48930046}
        ),
    'merriam-webster': Browser('merriam-webster', 'https://www.merriam-webster.com/dictionary/{query}', 'dictionary.html', {'query': '', 'extract': 'html'}, xpath=['//*[@class="vg" or @class="drp" or @class="fl"]'], link_conversion={'//a[@class="mw_t_sx" or @class="mw_t_d_link" or @class="mw_t_a_link" or @class="important-blue-link" or @class="mw_t_dxt"]': '/dictionary/([a-zA-Z \+]+)#*'}),
    'collins': Browser('collins', 'https://www.collinsdictionary.com/zh/search/?dictCode={source_lang}-{target_lang}&q={query}', 'dictionary.html', {'query': '', 'source_lang': 'english', 'target_lang': 'chinese', 'extract': 'html'}, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:98.0) Gecko/20100101 Firefox/98.0', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'}, xpath=['//div[@class="he"]/div'], exclude_xpath=['//*[@class="socialButtons"]', '//a[@class="hwd_sound sound audio_play_button icon-volume-up ptr"]', '//div[@class="mpuslot_b-container"]', '//div[@class="title_frequency_container"]', '//input[@class="selectorOpernerBig"]', '//label', '//div[contains(@class, "cB-e") or contains(@class, "cB-v") or contains(@class, "copyright")]', '//script'], link_conversion={'//a[@class="xr_ref_link"]': '.*/(.*)#'}),
    'linguee': Browser('linguee', 'https://www.linguee.com/{source_lang}-{target_lang}/search?source=auto&query={query}', 'dictionary.html', {'query': '', 'source_lang': 'english', 'target_lang': 'chinese', 'extract': 'html'}, xpath=['//div[@class="isMainTerm"]', '//div[@class="isForeignTerm"]', '//table[@class="result_table"]//tr', '//div[@class="textcontent"]/h1'], exclude_xpath=['//*[not(normalize-space())]'], seperator = "<hr>", link_conversion={'//a[contains(@class, "dictLink")]': '/translation/(.*).html$'}),
    'linguee-lite': Browser('linguee-lite', 'https://www.linguee.com/{source_lang}-{target_lang}/search?source=auto&query={query}', 'dictionary.html', {'query': '', 'source_lang': 'english', 'target_lang': 'chinese', 'extract': 'html'}, xpath=['//div[@class="isMainTerm"]', '//div[@class="isForeignTerm"]', '//div[@class="textcontent"]/h1'], exclude_xpath=['//*[not(normalize-space())]'], seperator = "<hr>", link_conversion={'//a[contains(@class, "dictLink")]': '/translation/(.*).html$'}),
    'cambridge': Browser('cambridge', 'https://dictionary.cambridge.org/dictionary/{source_lang}-{target_lang}-simplified/{query}', 'dictionary.html', {'query': '', 'source_lang': 'english', 'target_lang': 'chinese', 'extract': 'html'}, xpath=['//div[@class="entry"]', '//div[@class="idiom-block"]', '//div[@class="lmb-20"]'], exclude_xpath=['//*[not(normalize-space())]', '//span[@class="daud"]', '//div[@class="daccord"]', '//div[contains(@class,"grammar")]', '//span[contains(@class,"headword")]', '//div[contains(@class, "contentslot")]', '//a[contains(@class,"lp-20")]', '//div[contains(@class, "phrase-head")]/i', '//script'], seperator = "<hr>", link_conversion={'//a[@class="query"]': '.*/(.*)$', '//div[@class="lmb-12" or contains(@class, "item")]/a': '.*/(.*)$'}),
    'termcodex': Browser('termcodex', 'https://www.termcodex.com/wiki/{query}', 'dictionary.html', {'query': '', 'extract': 'html'}, xpath=['//div[contains(@class, "jumbotron")]', '//span[contains(@class,"badge") and contains("词典 数学 计算机 统计学 社会学 新闻传播学", text())]/parent::*/parent::*/parent::*'], exclude_xpath=[], seperator = "<hr>", link_conversion={'//a[@class="new"]': 'title=(\w+)', '//p/a': '/wiki/(.*)$', '//b/a': '/wiki/(.*)$'}),
    'dict.cn': Browser('dict.cn', 'https://dict.cn/{query}', 'dictionary.html', {'query': '', 'extract': 'html'}, xpath=['//div[contains(@class, "basic")]/ul', '//div[@class="layout detail"]/preceding-sibling::h3|//div[@class="layout detail"]', '//div[contains(@class, "ess")]/preceding-sibling::h3|//div[contains(@class, "ess")]', '//div[contains(@class, "discrim")]/preceding-sibling::h3[1]|//div[contains(@class, "discrim")]', '//div[contains(@class, "sort")]/preceding-sibling::h3|//div[contains(@class, "sort")]', '//div[contains(@class, "unfind")]/preceding-sibling::h3|//div[contains(@class, "unfind")]'], exclude_xpath=['//script/parent::li'], seperator = "", link_conversion={'//div[contains(@class, "unfind")]/ul/li/a':'^/(.*)$'}),
    'dictwiki': Browser('dictwiki', 'https://dictwiki.net/zh/{query}', 'dictionary.html', {'query': '', 'extract': 'html'}, xpath=['//h2[@class="word-title"]', '//div[@class="medit detail" or @class="medit example" or @class="medit enen cizu" or @class="medit ee cizu tongyibianxi" or @class="medit enen cizu hangyecidian"]'], exclude_xpath=['//script', '//ins[@class="adsbygoogle"]'], seperator = "", link_conversion={}),
    'yiym': Browser('yiym', 'http://yiym.com/{query}', 'yiym.html', {'query': '', 'extract': 'html'}, xpath=['//div[contains(@class, "entry")]'], exclude_xpath=['//div[contains(@class, "entry")]/div[contains(@class, "postmetadata")]', '//script', '//div[@id="sidebar"]', '//div[@class="foot-new"]'], seperator = "", link_conversion={'//p[@class="slang_reference"]/a':'odict.net/(.*)/'}),
    'yiym_search': Browser('yiym_search', 'http://yiym.com/page/{page}?s={query}', 'dictionary.html', {'query': '', 'page':1, 'extract': 'html'}, xpath=['//h3[@class="title"]', '//div[@id="pagenavi"]'], exclude_xpath=['//script', '//div[@id="sidebar"]', '//div[@class="foot-new"]'], seperator = "", link_conversion={'//div[@class="inner"]/div/h3[@class="title"]/a':{'regex':'www.yiym.com/(.*)', 'target':'/yiym/?query={query}'}, '//div[@id="pagenavi"]/a':{'regex':'page/(?P<page>\d+)\?s=(?P<query>.*)', 'target':'?query={query}&page={page}'}}),
    'odict': Browser('odict', 'http://odict.net/{query}', 'dictionary.html', {'query': '', 'extract': 'html'}, xpath=['//div[@class="abc_b"]', '//div[@class="abc_c"]'], exclude_xpath=['//script', '//ins', '//div[@class="abc_c"]/br[1]'], seperator = "", link_conversion={'//div[@class="abc_b"]//a':'/(.*)/'}),
    'naer_search': Browser('naer_search', 'https://terms.naer.edu.tw/search/?q={query}&field=ti&op=AND&match={match}&q=&field=ti&op=AND&order={order}&num={num}&show=&page={page}&group={group}&q=noun:"{category}"&field=&op=AND&q=word:"{word}"&field=&op=AND&q=name:"{name}"&field=&op=AND&q=au:"{au}"&field=&op=AND&heading=#result', 'naer.html', {'query': '', 'match':'full', 'category':'', 'word':'', 'name':'', 'au':'', 'order':'', 'group':'', 'num':50, 'page':1, 'extract': 'html'}, xpath=['//div[@class="result_keyword"]/em', '(//li[@class="pagination"])[1]', '//ul[@class="category_list"]', '//table[@class="resultlisttable"]/tr[@class="dash"]'], exclude_xpath=['//td[@class="sourceW"]/br', '//th[@class="cboxW"]', '//i[@class="icon-info-sign"]'], seperator = "<br>", link_conversion={'./ul/li/a':{'regex':['q=(?P<query>[\w ]+)?&', 'q=noun:"(?P<category>[\u3400-\u4db5\w\-]+)"', 'q=word:"(?P<word>[\u3400-\u4db5\w\-]+)"', 'q=name:"(?P<name>[\u3400-\u4db5\w\-]+)"', 'q=au:"(?P<au>[\u3400-\u4db5\w\-]+)"', 'group=(?P<group>\d+)', 'num=(?P<num>\d+)', 'match=(?P<match>\w+)', 'page=(?P<page>\d+)'], 'target': '/naer_search/?{query_string}'}, './li/a':{'regex':['q=(?P<query>[\w ]+)?&', 'q=noun:%22(?P<category>[\u3400-\u4db5\w\-]+)%22', 'q=word:%22(?P<word>[\u3400-\u4db5\w\-]+)%22', 'q=name:%22(?P<name>[\u3400-\u4db5\w\-]+)%22', 'q=au:%22(?P<au>[\u3400-\u4db5\w\-]+)%22', 'match=(?P<match>\w+)'], 'target': '/naer_search/?{query_string}'}, './/td[@class="ennameW" or @class="zhtwnameW" or @class="sourceW"]/a':{'regex':'/detail/(?P<query>\d+)/\?index=(?P<index>\d+)', 'target': '/naer_detail/?query={query}&index={index}'}}),
    'naer_detail': Browser('naer_detail', 'https://terms.naer.edu.tw/detail/{query}/?index={index}', 'dictionary.html', {'query': '', 'index': 1, 'extract': 'html'}, xpath=['//div[@id="explanation"]', '//div[@class="searchresultstab-content"]', '//table[@class="resultlisttable"]'], exclude_xpath=['//td[@class="sourceW"]/br'], seperator = '<hr class="naer_hr">', link_conversion={'//th[@class="ennameW" or @class="zhtwnameW"]/a':{'regex':'/detail/(?P<query>\d+)/', 'target': '/naer_detail/?query={query}'}, '//ul[@class="category_list"]/li/a':{'regex':'/detail/(?P<query>\d+)/', 'target': '/naer_detail/?query={query}'}}),
    'tr-ex': Browser('tr-ex', 'https://tr-ex.me/translation/{from}-{to}/{query}?search={query}&t={t}&qt={qt}', 'dictionary.html', {'query': '', 'from':'english', 'to':'chinese', 't':'', 'qt':'', 'extract': 'html'}, xpath=['//div[contains(@class,"query-part")]', '//div[@class="doc-group"]'], exclude_xpath=['//div[@class="placer" or @class="bts" or @class="ads" or @class="context-examples-wrapper"]', '//div[@class="b h" or @class="e h"]', '//img[contains(@class, "chunk-translation-icon")]', '//img[@class="mobile-inline"]', '//img[@class="icon"]'], seperator = '', link_conversion={'//a[@class="text"]': '/translation/english-chinese/(.*)', '//a[@class="ctx-link"]': {'regex': ['/translation/(?P<from>english)-(?P<to>chinese)/(?P<query>.*)', '/translation/(?P<from>chinese)-(?P<to>english)/(?P<query>.*)'], 'target':'/tr-ex.me/?{query_string}'}, '//a[@class="translation"]':{'regex': '/translation/english-chinese/(?P<query>[\w \+]+)\?t=(?P<t>[\u4e00-\u9fa5]+)&qt=(?P<qt>[\w \+]+)', 'target':'/tr-ex.me/?query={query}&t={t}&qt={qt}'}}),
}


@app.route('/favicon.ico')
def favicon():
    return ''

async def query_services(service_names, **kwargs):
    async with CachedSession(cache=SQLiteBackend('caches', expire_after=-1)) as session:
        tasks = []
        for s_name in service_names:
            tasks.append(services[s_name].query(session, **kwargs))
        await asyncio.gather(*tasks)


@app.route('/<service>/')
@app.route('/<service>')
@app.route('/')
async def index(service=None):
    if service is None:
        responses = {}
        dictionaries = ['linguee-lite', 'collins', 'cambridge', 'merriam-webster']
        #await query_services(['deepl'], **{'params.jobs[0].sentences[0].text': request.args['query']})
        await query_services(['reverso-context'], **{'source_text': request.args['query'], 'nrows': 5})
        #responses['deepl'] = services['deepl'].render()
        responses['reverso-context'] = services['reverso-context'].render()
        await query_services(dictionaries, **request.args)
        for s_name in dictionaries:
            responses[s_name] =services[s_name].render()
        return render_template('index.html', responses=responses, services=services, payload=services[s_name].payload)
    elif ',' in service:
        if ':' in service:
            style, service = service.split(':')
        else:
            style = 'index'
        await query_services(service.split(','), **request.args)
        responses = {}
        for s_name in service.split(','):
            responses[s_name] = services[s_name].render()
        return render_template('{style}.html'.format(style=style), responses=responses, services=services, payload=services[s_name].payload)
    else:
        await query_services([service], **request.args)
        return services[service].render()


if __name__ == '__main__':
      app.run(host='0.0.0.0', port=5678, debug=True)
