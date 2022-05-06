FROM python:3.9.12-slim-bullseye

RUN apt update && apt install -y --no-install-recommends git
RUN git clone https://github.com/gahoo/minimalist_browser_for_omegat.git && \
    cd minimalist_browser_for_omegat && \
    pip install -r requirements.txt && \
    cp static/linguee.css static/linguee-lite.css

WORKDIR /minimalist_browser_for_omegat

ENTRYPOINT python3 app.py
