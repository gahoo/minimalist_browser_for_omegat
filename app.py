from flask import Flask, render_template
import json
import pdb
import requests
import shelve
import atexit

app = Flask(__name__)
cache = shelve.open('cache')

@atexit.register
def close_cache():
    print("Closing cache")
    cache.close()

@app.route('/')
def index():
    return render_template('index.html', page=0, npages=0)

@app.route('/<query>')
@app.route('/<query>/<int:page>')
@app.route('/<source_lang>-<target_lang>/<query>')
@app.route('/<source_lang>-<target_lang>/<query>/<int:page>')
def reverso(query, source_lang='en', target_lang='zh', page=1):
    query = requests.utils.unquote(query)
    payload = {"source_text":query,"target_text":"","source_lang":source_lang,"target_lang":target_lang,"npage":page,"mode":1, "nrows":50}
    print(payload)
    request_key = "_".join((query, source_lang, target_lang, str(page)))
    if request_key in cache:
        resp = cache[request_key]
    else:
        headers = {'accept': 'application/json, text/javascript, */*; q=0.01', 'content-type': 'application/json; charset=UTF-8', 'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36', 'accept-language': 'zh-CN,zh;q=0.9'}
        r = requests.post("https://context.reverso.net/bst-query-service", data=json.dumps(payload), headers=headers)
        resp = r.json()
        cache[request_key] = resp.copy()
    debug_json = dict([(k, v) for k, v in resp.items() if k != 'list' and v is not None and v != []])
    return render_template('index.html', raw_json = json.dumps(debug_json, indent=4, ensure_ascii=False), **resp)
    #return render_template('index.html', raw_json = '', **resp)

if __name__ == '__main__':
      app.run(host='0.0.0.0', port=5678, debug=True)
