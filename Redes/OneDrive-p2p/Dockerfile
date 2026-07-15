FROM python:3.9-slim

LABEL description="Peer P2P de sincronizacao de arquivos"

WORKDIR /app

COPY config.py discovery.py file_utils.py main.py monitor.py peer_network.py state.py web_status.py ./

COPY templates/ ./templates/

RUN mkdir -p /app/sync_folder

EXPOSE 6000 9999 8000

ENV TCP_PORT=6000
ENV SYNC_FOLDER=/app/sync_folder
ENV NODE_NAME=""

CMD python main.py ${TCP_PORT} ${SYNC_FOLDER}
