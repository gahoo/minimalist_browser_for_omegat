## Intro
This is a flask app that leverage Reverso Context API with a minimalism page and a companion groovy script to better serve OmegaT Brower Plugin.
After groovy script is copied and enabled. To query the selected text, right click on the text and choose `Search in Reverso Context` or just use the hot key`Ctrl/Command + .`

## How to use
```bash
git clone https://github.com/gahoo/reverso_context_for_omegat.git
cd reverso_context_for_omegat
cp reverso_context.groovy ~/.omegat/browser-scripts 
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
python3 app.py
```
