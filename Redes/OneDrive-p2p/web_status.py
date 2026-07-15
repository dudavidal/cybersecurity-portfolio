import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import config
import file_utils
import monitor
import peer_network
from state import estado

_INICIO = time.time()

_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "status.html")


def _carregar_html():
    with open(_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()


class StatusHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._responder_html()
        elif self.path == "/status":
            self._responder_status()
        elif self.path.startswith("/download"):
            self._responder_download()
        else:
            self.send_error(404, "Not Found")

    def _responder_html(self):
        try:
            corpo = _carregar_html().encode("utf-8")
        except FileNotFoundError:
            corpo = b"<h1>status.html nao encontrado</h1>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _responder_status(self):
        peers = estado.listar_peers()
        arquivos = estado.get_estado_arquivos()
        agora = time.time()

        peers_fmt = []
        for pid, info in peers.items():
            peers_fmt.append({
                "peer_id": pid,
                "ip": info["ip"],
                "tcp_port": info["tcp_port"],
                "http_port": config.HTTP_PORT_BASE + (info["tcp_port"] - 6000),
                "segundos_desde_ultimo_contato": round(agora - info["ultimo_contato"], 1),
            })

        arquivos_fmt = []
        for nome, info in arquivos.items():
            if nome.startswith(".p2p_"):
                continue
            arquivos_fmt.append({
                "nome": nome,
                "hash": info["hash"][:10] + "...",
                "versao": info["version"],
                "tamanho": info["size"],
                "deletado": info.get("deleted", False),
                "modificado_em": time.strftime(
                    "%H:%M:%S", time.localtime(info["mtime"])
                ),
            })

        arquivos_fmt.sort(key=lambda a: a["nome"])

        payload = {
            "peer_id": config.PEER_ID,
            "tcp_port": config.TCP_PORT,
            "pasta": config.SYNC_FOLDER,
            "uptime_segundos": round(agora - _INICIO, 1),
            "peers": peers_fmt,
            "arquivos": arquivos_fmt,
        }

        self._responder_json(payload)

    def _responder_download(self):
        from urllib.parse import urlparse, parse_qs
        params = parse_qs(urlparse(self.path).query)
        filename = os.path.basename(params.get("filename", [None])[0] or "")

        if not filename or not file_utils.arquivo_existe(filename):
            self._responder_json({"ok": False, "erro": "arquivo nao encontrado"}, status=404)
            return

        try:
            dados = file_utils.ler_arquivo_bytes(filename)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition",
                             f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)
        except Exception as e:
            self._responder_json({"ok": False, "erro": str(e)}, status=500)

    def do_POST(self):
        if self.path == "/action/sync":
            self._acao_sync()
        elif self.path == "/action/check":
            self._acao_check()
        elif self.path == "/action/upload":
            self._acao_upload()
        elif self.path == "/action/delete":
            self._acao_delete()
        else:
            self.send_error(404, "Not Found")

    def _acao_sync(self):
        n = peer_network.forcar_sync_com_todos()
        self._responder_json({"ok": True, "peers_contatados": n})

    def _acao_check(self):
        monitor.verificar_mudancas(on_mudanca=peer_network.propagar_mudanca)
        self._responder_json({"ok": True})

    def _acao_delete(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            corpo = self.rfile.read(length).decode("utf-8")
            campos = parse_qs(corpo)
            filename = os.path.basename(campos.get("filename", [None])[0] or "")

            if not filename:
                self._responder_json({"ok": False, "erro": "filename ausente"}, status=400)
                return

            if not file_utils.arquivo_existe(filename):
                self._responder_json({"ok": False, "erro": "arquivo nao encontrado"}, status=404)
                return

            file_utils.remover_arquivo(filename)
            monitor.verificar_mudancas(on_mudanca=peer_network.propagar_mudanca)

            self._responder_json({"ok": True, "filename": filename})

        except Exception as e:
            self._responder_json({"ok": False, "erro": str(e)}, status=500)

    def _acao_upload(self):
        try:
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self._responder_json(
                    {"ok": False, "erro": "esperado multipart/form-data"}, status=400
                )
                return

            boundary = _extrair_boundary(content_type)
            length = int(self.headers.get("Content-Length", 0))
            corpo = self.rfile.read(length)

            filename, dados = _parsear_multipart_arquivo(corpo, boundary)

            if filename is None:
                self._responder_json(
                    {"ok": False, "erro": "nenhum arquivo enviado"}, status=400
                )
                return

            filename = os.path.basename(filename)

            file_utils.escrever_arquivo_bytes(filename, dados)
            monitor.verificar_mudancas(on_mudanca=peer_network.propagar_mudanca)

            self._responder_json({"ok": True, "filename": filename, "tamanho": len(dados)})

        except Exception as e:
            self._responder_json({"ok": False, "erro": str(e)}, status=500)

    def _responder_json(self, payload, status=200):
        corpo = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)


def _extrair_boundary(content_type):
    for parte in content_type.split(";"):
        parte = parte.strip()
        if parte.startswith("boundary="):
            boundary = parte[len("boundary="):]
            return boundary.strip('"')
    raise ValueError("boundary nao encontrado no Content-Type")


def _parsear_multipart_arquivo(corpo, boundary):
    delimitador = ("--" + boundary).encode()
    partes = corpo.split(delimitador)

    for parte in partes:
        if b'filename="' not in parte:
            continue

        if b"\r\n\r\n" not in parte:
            continue

        cabecalhos_raw, conteudo = parte.split(b"\r\n\r\n", 1)
        cabecalhos = cabecalhos_raw.decode(errors="ignore")

        filename = None
        for linha in cabecalhos.split("\r\n"):
            if "Content-Disposition" not in linha:
                continue
            for trecho in linha.split(";"):
                trecho = trecho.strip()
                if trecho.startswith("filename="):
                    filename = trecho[len("filename="):].strip('"')
                    break
            if filename:
                break

        if not filename:
            continue

        if conteudo.endswith(b"\r\n"):
            conteudo = conteudo[:-2]

        return filename, conteudo

    return None, None


def _thread_servidor_http():
    server = ThreadingHTTPServer(("0.0.0.0", config.HTTP_PORT), StatusHandler)
    print(f"[ web ] interface em http://localhost:{config.HTTP_PORT}")
    server.serve_forever()


def iniciar_servidor_web():
    threading.Thread(target=_thread_servidor_http, daemon=True).start()
