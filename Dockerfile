FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        ripgrep \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py index.py retrieval.py parser.py ./

ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV INDEX_PATH=/data/multistream-index.txt
ENV DUMP_PATH=/data/multistream.xml.bz2

EXPOSE 8000

CMD ["python", "server.py"]
