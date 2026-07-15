import socket
import json
import threading
import time

import config
from state import estado


def thread_anunciar(tcp_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    msg = {
        "type": "discovery_announce",
        "peer_id": config.PEER_ID,
        "tcp_port": tcp_port,
    }

    while True:
        try:
            payload = json.dumps(msg).encode()
            sock.sendto(payload, (config.BROADCAST_ADDR, config.UDP_DISCOVERY_PORT))
        except Exception as e:
            print(f"[ descoberta ] erro ao anunciar: {e}")
        time.sleep(config.DISCOVERY_INTERVAL)


def thread_escutar(quando_achar_novo_peer):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("", config.UDP_DISCOVERY_PORT))

    print(f"[ descoberta ] escutando na porta UDP {config.UDP_DISCOVERY_PORT}")

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            ip_origem = addr[0]
            msg = json.loads(data.decode())

            if msg.get("type") != "discovery_announce":
                continue

            peer_id = msg["peer_id"]
            tcp_port = msg["tcp_port"]

            if peer_id == config.PEER_ID:
                continue

            peers_atuais = estado.listar_peers()
            eh_nova = peer_id not in peers_atuais

            estado.atualizar_peer(peer_id, ip_origem, tcp_port)

            if eh_nova:
                print(f"[ descoberta ] novo computador: {peer_id[:8]} em {ip_origem}:{tcp_port}")
                if quando_achar_novo_peer:
                    threading.Thread(
                        target=quando_achar_novo_peer,
                        args=(peer_id, ip_origem, tcp_port),
                        daemon=True,
                    ).start()

        except Exception as e:
            print(f"[ descoberta ] erro: {e}")


def thread_verificar_heartbeat():
    while True:
        time.sleep(config.DISCOVERY_INTERVAL)
        removidas = estado.remover_peers_inativos(config.PEER_TIMEOUT)
        for pid in removidas:
            print(f"[ descoberta ] {pid[:8]} saiu da rede (timeout)")


def iniciar_discovery(tcp_port, quando_achar_novo_peer):
    threading.Thread(target=thread_anunciar, args=(tcp_port,), daemon=True).start()
    threading.Thread(target=thread_escutar, args=(quando_achar_novo_peer,), daemon=True).start()
    threading.Thread(target=thread_verificar_heartbeat, daemon=True).start()
