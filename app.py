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
    def __init__(self, name, url, template, default={}, headers={}, xpath=[], exclude_xpath=[], seperator="", link_conversion={}):
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

    async def query(self, session, **kwargs):
        if 'refresh' in kwargs and kwargs.pop('refresh') == 'true':
            do_refresh = True
        else:
            do_refresh = False
        self.payload = benedict(self.default.copy())
        for k, v in kwargs.items():
            self.payload[k] = v
        if self.xpath:
            self.response = await self.get(session)
        else:
            self.response = await self.post(session)

    async def post(self, session):
        r = await session.request(method="POST",url=self.url, data=json.dumps(self.payload), headers=self.headers)
        return await r.json()

    async def get(self, session):
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
            has_found_query = re.search(regex, a_tag.get('href'))
            if has_found_query:
                query = has_found_query.group(1)
                a_tag.set('href', '?query={query}'.format(query=query))

        for xpath, regex in self.link_conversion.items():
            a_tags = node.xpath(xpath)
            list(map(replace_a_href, a_tags))

    def render(self):
        if isinstance(self.response, dict):
            debug_json = dict([(k, v) for k, v in self.response.items() if k != 'list' and v is not None and v != []])
            return render_template(self.template, raw_json = json.dumps(debug_json, indent=4, ensure_ascii=False), payload=self.payload, **self.response)
        else:
            return render_template(self.template, payload=self.payload, responses=self.response, service_name=self.name, url=self.url.format(**self.payload))

    def has_empty_response(self):
        return "".join(self.response) == ""

services = {
    'reverso-context': Browser('reverso', "https://context.reverso.net/bst-query-service", "reverso_context.html", {'source_lang': 'en', 'target_lang': 'zh', 'source_text': '', 'target_text': '', 'mode': '1', 'nrows': '50'}),
    'deepl': Browser('deepl', "https://www2.deepl.com/jsonrpc", "deepl.html",
        {"jsonrpc":"2.0","method": "LMT_handle_jobs","params":{"jobs":[{"kind":"default","sentences":[{"text":"","id":0,"prefix":""}],"raw_en_context_before":[],"raw_en_context_after":[],"preferred_num_beams":4,"quality":"fast"}],"lang":{"user_preferred_langs":["ZH","EN"],"source_lang_user_selected":"auto","target_lang":"ZH"},"priority":-1,"commonJobParams":{"browserType":129,"formality":None},"apps":{"usage":5},"timestamp":1646624556415},"id":48930046}
        ),
    'merriam-webster': Browser('merriam-webster', 'https://www.merriam-webster.com/dictionary/{query}', 'dictionary.html', {'query': '', 'extract': 'html'}, xpath=['//*[@class="vg" or @class="drp" or @class="fl"]'], link_conversion={'//a[@class="mw_t_sx" or @class="mw_t_d_link" or @class="mw_t_a_link" or @class="important-blue-link" or @class="mw_t_dxt"]': '/dictionary/([a-zA-Z \+]+)#*'}),
    'collins': Browser('collins', 'https://www.collinsdictionary.com/zh/search/?dictCode={source_lang}-{target_lang}&q={query}', 'dictionary.html', {'query': '', 'source_lang': 'english', 'target_lang': 'chinese', 'extract': 'html'}, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:98.0) Gecko/20100101 Firefox/98.0', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'}, xpath=['//div[@class="he"]/div'], exclude_xpath=['//*[@class="socialButtons"]', '//a[@class="hwd_sound sound audio_play_button icon-volume-up ptr"]', '//div[@class="mpuslot_b-container"]', '//script'], link_conversion={'//a[@class="xr_ref_link"]': '.*/(.*)#'}),
    'linguee': Browser('linguee', 'https://www.linguee.com/{source_lang}-{target_lang}/search?source=auto&query={query}', 'dictionary.html', {'query': '', 'source_lang': 'english', 'target_lang': 'chinese', 'extract': 'html'}, xpath=['//div[@class="isMainTerm"]', '//div[@class="isForeignTerm"]', '//table[@class="result_table"]//tr', '//div[@class="textcontent"]/h1'], exclude_xpath=['//*[not(normalize-space())]'], seperator = "<hr>", link_conversion={'//a[contains(@class, "dictLink")]': '/translation/(.*).html$'}),
    'linguee-lite': Browser('linguee-lite', 'https://www.linguee.com/{source_lang}-{target_lang}/search?source=auto&query={query}', 'dictionary.html', {'query': '', 'source_lang': 'english', 'target_lang': 'chinese', 'extract': 'html'}, xpath=['//div[@class="isMainTerm"]', '//div[@class="isForeignTerm"]', '//div[@class="textcontent"]/h1'], exclude_xpath=['//*[not(normalize-space())]'], seperator = "<hr>", link_conversion={'//a[contains(@class, "dictLink")]': '/translation/(.*).html$'}),
    'cambridge': Browser('cambridge', 'https://dictionary.cambridge.org/dictionary/{source_lang}-{target_lang}-simplified/{query}', 'dictionary.html', {'query': '', 'source_lang': 'english', 'target_lang': 'chinese', 'extract': 'html'}, xpath=['//div[@class="entry"]', '//div[@class="idiom-block"]', '//div[@class="lmb-20"]'], exclude_xpath=['//*[not(normalize-space())]', '//span[@class="daud"]', '//div[@class="daccord"]', '//div[contains(@class,"grammar")]', '//span[contains(@class,"headword")]', '//div[contains(@class, "contentslot")]', '//a[contains(@class,"lp-20")]', '//script'], seperator = "<hr>", link_conversion={'//a[@class="query"]': '.*/(.*)$', '//div[@class="lmb-12" or contains(@class, "item")]/a': '.*/(.*)$'}),
    'termcodex': Browser('termcodex', 'https://www.termcodex.com/wiki/{query}', 'dictionary.html', {'query': '', 'extract': 'html'}, xpath=['//div[contains(@class, "jumbotron")]', '//span[contains(@class,"badge") and contains("词典 数学 计算机 统计学", text())]/parent::*/parent::*/parent::*'], exclude_xpath=[], seperator = "<hr>", link_conversion={'//a[@class="new"]': 'title=(\w+)', '//p/a': '/wiki/(.*)$', '//b/a': '/wiki/(.*)$'}),
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
        await query_services(service.split(','), **request.args)
        responses = {}
        for s_name in service.split(','):
            responses[s_name] = services[s_name].render()
        return render_template('index.html', responses=responses, services=services, payload=services[s_name].payload)
    else:
        await query_services([service], **request.args)
        return services[service].render()


if __name__ == '__main__':
      app.run(host='0.0.0.0', port=5678, debug=True)
