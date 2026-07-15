import sys
import time

import config
import file_utils
import discovery
import monitor
import peer_network
import web_status
from state import estado


def main():
    tcp_port = config.TCP_PORT
    pasta = config.SYNC_FOLDER

    if len(sys.argv) >= 2:
        tcp_port = int(sys.argv[1])
    if len(sys.argv) >= 3:
        pasta = sys.argv[2]

    config.TCP_PORT = tcp_port
    config.SYNC_FOLDER = pasta
    config.HTTP_PORT = config.HTTP_PORT_BASE + (tcp_port - 6000)

    file_utils.garantir_pasta()

    estado.carregar()

    print(f"Sincronizador P2P rodando na porta {tcp_port}")

    peer_network.iniciar_servidor_tcp(tcp_port)

    monitor.iniciar_monitor(on_mudanca=peer_network.propagar_mudanca)

    discovery.iniciar_discovery(
        tcp_port=tcp_port,
        quando_achar_novo_peer=peer_network.iniciar_sync_com_peer,
    )

    web_status.iniciar_servidor_web()

    print(f"\nInterface web: http://localhost:{config.HTTP_PORT}\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nEncerrando...")


if __name__ == "__main__":
    main()
