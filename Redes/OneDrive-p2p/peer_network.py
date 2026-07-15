import os
import socket
import threading
import json
import base64
import time

import config
import file_utils
from state import estado


def enviar_msg(sock, msg):
    payload = (json.dumps(msg) + "\n").encode()
    sock.sendall(payload)


def receber_msg(sock):
    buffer = b""
    while True:
        dados = sock.recv(65536)
        if not dados:
            break
        buffer += dados
        while b"\n" in buffer:
            linha, buffer = buffer.split(b"\n", 1)
            if linha.strip():
                yield json.loads(linha.decode())


def thread_servidor_tcp(tcp_port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", tcp_port))
    server.listen()
    print(f"[ tcp ] servidor rodando na porta {tcp_port}")

    while True:
        conn, addr = server.accept()
        threading.Thread(target=_tratar_conexao, args=(conn, addr), daemon=True).start()


def _tratar_conexao(conn, addr):
    try:
        for msg in receber_msg(conn):
            tipo = msg.get("type")

            if tipo == "sync_request":
                _responder_sync(conn, msg)

            elif tipo == "file_update":
                _processar_file_update(msg, addr[0])

            elif tipo == "file_delete":
                _processar_file_delete(msg)

            elif tipo == "file_request":
                _responder_file_request(conn, msg)

            else:
                print(f"[ tcp ] mensagem desconhecida: {tipo}")

    except Exception as e:
        print(f"[ tcp ] erro com {addr}: {e}")
    finally:
        conn.close()


def _responder_sync(conn, msg):
    peer_id_origem = msg.get("peer_id")
    print(f"[ sync ] pedido de sync recebido de {peer_id_origem[:8] if peer_id_origem else '?'}")

    resposta = {
        "type": "sync_response",
        "peer_id": config.PEER_ID,
        "files": estado.get_estado_arquivos(),
    }
    enviar_msg(conn, resposta)


def iniciar_sync_com_peer(peer_id, ip, tcp_port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((ip, tcp_port))

        enviar_msg(sock, {"type": "sync_request", "peer_id": config.PEER_ID})

        for msg in receber_msg(sock):
            if msg.get("type") == "sync_response":
                _reconciliar(msg["files"], ip, tcp_port)
            break

        sock.close()

    except Exception as e:
        print(f"[ sync ] erro ao sincronizar com {peer_id[:8]}: {e}")


def _reconciliar(arquivos_remotos, ip, tcp_port):
    estado_local = estado.get_estado_arquivos()

    for nome, info_remota in arquivos_remotos.items():
        info_local = estado_local.get(nome)

        if info_remota.get("deleted"):
            if info_local and not info_local.get("deleted") and info_local["version"] < info_remota["version"]:
                _aplicar_delete_remoto(nome, info_remota)
            continue

        if info_local is None or info_local.get("deleted"):
            _solicitar_arquivo(ip, tcp_port, nome)

        elif info_local["hash"] != info_remota["hash"]:
            if _resolver_conflito(info_local, info_remota) == "remoto":
                _solicitar_arquivo(ip, tcp_port, nome)

    for nome, info_local in estado_local.items():
        if info_local.get("deleted"):
            continue
        if nome not in arquivos_remotos:
            _enviar_file_update_para(ip, tcp_port, nome)


def _resolver_conflito(info_local, info_remota):
    if info_local["version"] != info_remota["version"]:
        return "local" if info_local["version"] > info_remota["version"] else "remoto"

    if info_local["mtime"] != info_remota["mtime"]:
        return "local" if info_local["mtime"] > info_remota["mtime"] else "remoto"

    return "local" if info_local["hash"] > info_remota["hash"] else "remoto"


def _aplicar_delete_remoto(nome, info_remota):
    print(f"[ sync ] removendo '{nome}' (v{info_remota['version']}) por ordem remota")
    estado.marcar_para_ignorar(nome)
    file_utils.remover_arquivo(nome)
    estado.atualizar_arquivo(
        nome, info_remota["hash"], info_remota["mtime"], info_remota["size"],
        version=info_remota["version"], deleted=True
    )


def propagar_mudanca(tipo, filename):
    peers = estado.listar_peers()
    info = estado.get_arquivo(filename)
    if info is None:
        return

    for peer_id, dados_peer in peers.items():
        ip, porta = dados_peer["ip"], dados_peer["tcp_port"]
        try:
            if tipo == "update":
                _enviar_file_update_para(ip, porta, filename)
            elif tipo == "delete":
                _enviar_file_delete_para(ip, porta, filename, info)
        except Exception as e:
            print(f"[ propagacao ] erro ao enviar pra {peer_id[:8]}: {e}")


def _enviar_file_update_para(ip, porta, filename):
    info = estado.get_arquivo(filename)
    if info is None or info.get("deleted"):
        return
    msg = {
        "type": "file_update",
        "peer_id": config.PEER_ID,
        "tcp_port": config.TCP_PORT,
        "filename": filename,
        "hash": info["hash"],
        "mtime": info["mtime"],
        "size": info["size"],
        "version": info["version"],
    }
    _enviar_mensagem_simples(ip, porta, msg)


def _enviar_file_delete_para(ip, porta, filename, info):
    msg = {
        "type": "file_delete",
        "peer_id": config.PEER_ID,
        "filename": filename,
        "version": info["version"],
        "timestamp": time.time(),
    }
    _enviar_mensagem_simples(ip, porta, msg)


def _enviar_mensagem_simples(ip, porta, msg):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect((ip, porta))
    enviar_msg(sock, msg)
    sock.close()


def _processar_file_update(msg, ip_origem):
    filename = os.path.basename(msg["filename"])
    info_local = estado.get_arquivo(filename)

    info_remota = {
        "hash": msg["hash"],
        "mtime": msg["mtime"],
        "size": msg["size"],
        "version": msg["version"],
        "deleted": False,
    }

    if info_local is None or info_local.get("deleted") or info_local["hash"] != info_remota["hash"]:
        if info_local is None or _resolver_conflito(info_local, info_remota) == "remoto":
            print(f"[ update ] {filename}: nova versao (v{info_remota['version']}) de "
                  f"{msg['peer_id'][:8]}, baixando...")
            peers = estado.listar_peers()
            dados_peer = peers.get(msg["peer_id"])
            porta = dados_peer["tcp_port"] if dados_peer else msg.get("tcp_port")
            if porta:
                _solicitar_arquivo(ip_origem, porta, filename)
            return


def _processar_file_delete(msg):
    filename = os.path.basename(msg["filename"])
    info_local = estado.get_arquivo(filename)

    if info_local is None or info_local.get("deleted"):
        return

    if msg["version"] >= info_local["version"]:
        print(f"[ delete ] removendo '{filename}' (v{msg['version']}) por ordem de "
              f"{msg['peer_id'][:8]}")
        estado.marcar_para_ignorar(filename)
        file_utils.remover_arquivo(filename)
        estado.atualizar_arquivo(
            filename, info_local["hash"], info_local["mtime"], info_local["size"],
            version=msg["version"], deleted=True
        )


def _solicitar_arquivo(ip, porta, filename):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15)
        sock.connect((ip, porta))

        enviar_msg(sock, {
            "type": "file_request",
            "peer_id": config.PEER_ID,
            "filename": filename,
        })

        chunks_recebidos = {}
        total_chunks = None
        hash_esperado = None
        size_esperado = None
        version_recebida = None

        for msg in receber_msg(sock):
            if msg.get("type") != "file_data":
                continue

            total_chunks = msg["total_chunks"]
            hash_esperado = msg["hash"]
            size_esperado = msg["size"]
            version_recebida = msg.get("version", 1)
            chunks_recebidos[msg["chunk_index"]] = base64.b64decode(msg["data"])

            if len(chunks_recebidos) == total_chunks:
                break

        sock.close()

        if total_chunks is None:
            print(f"[ download ] arquivo '{filename}' nao existe mais no outro computador")
            return

        conteudo = b"".join(chunks_recebidos[i] for i in range(total_chunks))

        if len(conteudo) != size_esperado:
            print(f"[ download ] tamanho errado para '{filename}', ignorando")
            return

        estado.marcar_para_ignorar(filename)
        file_utils.escrever_arquivo_bytes(filename, conteudo)

        mtime = os.stat(file_utils.caminho_completo(filename)).st_mtime

        estado.atualizar_arquivo(
            filename, hash_esperado, mtime, size_esperado,
            version=version_recebida, deleted=False
        )
        print(f"[ download ] '{filename}' (v{version_recebida}) baixado "
              f"({size_esperado} bytes)")

    except Exception as e:
        print(f"[ download ] erro ao baixar '{filename}': {e}")


def _responder_file_request(conn, msg):
    filename = os.path.basename(msg["filename"])

    if not file_utils.arquivo_existe(filename):
        print(f"[ upload ] '{filename}' solicitado mas nao existe aqui")
        return

    info = estado.get_arquivo(filename)
    conteudo = file_utils.ler_arquivo_bytes(filename)

    total_chunks = max(1, (len(conteudo) + config.CHUNK_SIZE - 1) // config.CHUNK_SIZE)

    for i in range(total_chunks):
        inicio = i * config.CHUNK_SIZE
        fim = inicio + config.CHUNK_SIZE
        pedaco = conteudo[inicio:fim]

        msg_chunk = {
            "type": "file_data",
            "filename": filename,
            "hash": info["hash"],
            "size": info["size"],
            "version": info["version"],
            "chunk_index": i,
            "total_chunks": total_chunks,
            "data": base64.b64encode(pedaco).decode(),
        }
        enviar_msg(conn, msg_chunk)

    print(f"[ upload ] '{filename}' enviado ({total_chunks} parte(s))")


def forcar_sync_com_todos():
    peers = estado.listar_peers()
    n = 0
    for peer_id, info in peers.items():
        try:
            iniciar_sync_com_peer(peer_id, info["ip"], info["tcp_port"])
            n += 1
        except Exception as e:
            print(f"[ sync ] erro ao forcar sync com {peer_id[:8]}: {e}")
    return n


def iniciar_servidor_tcp(tcp_port):
    threading.Thread(target=thread_servidor_tcp, args=(tcp_port,), daemon=True).start()
