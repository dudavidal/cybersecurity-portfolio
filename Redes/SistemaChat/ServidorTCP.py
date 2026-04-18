import socket
import threading
import json

HOST = "0.0.0.0"
PORT = 5050

clientes = {}  # nome -> socket
areas    = {}  # nome -> numero da area
lock     = threading.Lock()

AREAS = {1: "Comercial", 2: "Financeiro", 3: "Tecnologico", 4: "RH"}


def enviar(sock, dados):
    try:
        sock.send(json.dumps(dados).encode())
    except:
        pass


def avisar_todos_online():
    with lock:
        lista = [{"user": u, "area": areas[u]} for u in clientes]
        for s in clientes.values():
            enviar(s, {"type": "online", "users": lista})


def handle(conn):
    nome = None
    try:
        while True:
            dados = conn.recv(4096).decode()
            if not dados:
                break
            msg = json.loads(dados)
            tipo = msg["type"]

            if tipo == "login":
                nome = msg["user"]
                area = msg["area"]
                with lock:
                    if nome in clientes:
                        enviar(conn, {"type": "erro", "msg": "nome_em_uso"})
                        return
                    clientes[nome] = conn
                    areas[nome]    = area
                enviar(conn, {"type": "login_ok"})
                avisar_todos_online()

            elif tipo == "list":
                with lock:
                    lista = [{"user": u, "area": areas[u]} for u in clientes]
                enviar(conn, {"type": "online", "users": lista})

            elif tipo == "chat_request":
                destino = msg["to"]
                with lock:
                    if destino in clientes:
                        enviar(clientes[destino], {"type": "chat_invite", "from": nome})
                    else:
                        enviar(conn, {"type": "erro", "msg": "usuario_offline"})

            elif tipo in ("chat_accept", "chat_reject"):
                destino = msg["to"]
                with lock:
                    if destino in clientes:
                        enviar(clientes[destino], msg)

            elif tipo == "mensagem":
                destino = msg["to"]
                with lock:
                    if destino in clientes:
                        enviar(clientes[destino], msg)
                    else:
                        enviar(conn, {"type": "erro", "msg": "usuario_offline"})

            elif tipo == "broadcast":
                area_alvo = msg["area"]
                with lock:
                    alvos = [s for u, s in clientes.items() if areas[u] == area_alvo]
                for s in alvos:
                    enviar(s, msg)

            elif tipo == "aviso":
                with lock:
                    todos = list(clientes.values())
                for s in todos:
                    enviar(s, msg)

    except:
        pass
    finally:
        with lock:
            if nome:
                clientes.pop(nome, None)
                areas.pop(nome, None)
        avisar_todos_online()
        conn.close()


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen()
print(f"Servidor rodando na porta {PORT}...")

while True:
    conn, addr = server.accept()
    threading.Thread(target=handle, args=(conn,), daemon=True).start()