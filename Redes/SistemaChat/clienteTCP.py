import socket
import threading
import queue
import json
import sys
import time

HOST = "127.0.0.1"
PORT = 5050

AREAS = {1: "Comercial", 2: "Financeiro", 3: "Tecnologico", 4: "RH"}

meu_nome = None
minha_area = None
usuarios_online = []

contexto = "menu"

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

fila_rede = queue.Queue()
fila_teclado = queue.Queue()

def enviar(dados):
    try:
        sock.send(json.dumps(dados).encode())
    except Exception as e:
        print(f"[erro ao enviar] {e}")


def thread_rede():
    while True:
        try:
            dados = sock.recv(4096).decode()
            if not dados:
                fila_rede.put({"type": "_desconectado"})
                return
            fila_rede.put(json.loads(dados))
        except:
            fila_rede.put({"type": "_desconectado"})
            return

def thread_teclado():
    while True:
        try:
            linha = sys.stdin.readline()
            if not linha:
                fila_teclado.put(None)
                return
            fila_teclado.put(linha.strip())
        except:
            fila_teclado.put(None)
            return

def fazer_login():
    global meu_nome, minha_area

    print("=== LOGIN ===")
    meu_nome = input("Nome: ").strip()

    print("Area:")
    for k, v in AREAS.items():
        print(f"  {k} - {v}")
    minha_area = int(input("> "))

    enviar({"type": "login", "user": meu_nome, "area": minha_area})

    # espera confirmacao (bloqueante, so aqui)
    resp = json.loads(sock.recv(4096).decode())
    if resp.get("type") != "login_ok":
        print("Falha no login.")
        sys.exit(1)

    print(f"\nConectado como {meu_nome} ({AREAS[minha_area]})\n")


def prompt():
    if contexto == "menu":
        print("\n=== MENU ===")
        print("1 - Ver usuarios online")
        print("2 - Iniciar chat privado")
        print("3 - Mensagem para meu setor")
        print("4 - Aviso global")
        print("5 - Sair")
        print("> ", end="", flush=True)
    elif contexto.startswith("chat:"):
        print("Voce: ", end="", flush=True)


def loop():
    global contexto, usuarios_online

    prompt()

    while True:
        time.sleep(0.05)

        while not fila_rede.empty():
            msg = fila_rede.get()
            tipo = msg.get("type")

            if tipo == "_desconectado":
                print("\nConexao encerrada.")
                sys.exit(0)

            elif tipo == "online":
                usuarios_online = msg["users"]

            elif tipo == "chat_invite":
                de = msg["from"]
                print(f"\n[convite de {de}]")
                print("Aceitar? (s/n): ", end="", flush=True)
                contexto = f"convite:{de}"

            elif tipo == "chat_accept":
                de = msg["from"]
                print(f"\n{de} aceitou o chat!")
                contexto = f"chat:{de}"
                prompt()

            elif tipo == "chat_reject":
                de = msg["from"]
                print(f"\n{de} recusou.")
                contexto = "menu"
                prompt()

            elif tipo == "mensagem":
                print(f"\r[{msg['from']}] {msg['text']}")
                prompt()

            elif tipo == "broadcast":
                if msg.get("from") != meu_nome:
                    area = AREAS.get(msg.get("area"), "?")
                    print(f"\r[Setor {area}] {msg['from']}: {msg['text']}")
                    prompt()

            elif tipo == "aviso":
                area = AREAS.get(msg.get("area"), "?")
                print(f"\r[AVISO de {msg['from']} ({area})]: {msg['text']}")
                prompt()

            elif tipo == "erro":
                print(f"\n[erro] {msg.get('msg')}")
                contexto = "menu"
                prompt()

        if not fila_teclado.empty():
            linha = fila_teclado.get()

            if linha is None:
                break

            tratar_input(linha)

def tratar_input(linha):
    global contexto

    if contexto.startswith("chat:"):
        com_quem = contexto.split(":", 1)[1]
        if linha.lower() == "/sair":
            print(f"[chat com {com_quem} encerrado]")
            contexto = "menu"
            prompt()
        elif linha:
            enviar({"type": "mensagem", "from": meu_nome, "to": com_quem, "text": linha})
            prompt()
        else:
            prompt()
        return

    if contexto.startswith("convite:"):
        de = contexto.split(":", 1)[1]
        if linha.lower() == "s":
            enviar({"type": "chat_accept", "from": meu_nome, "to": de})
            contexto = f"chat:{de}"
            print(f"[chat com {de} iniciado]")
            prompt()
        else:
            enviar({"type": "chat_reject", "from": meu_nome, "to": de})
            print("Recusado.")
            contexto = "menu"
            prompt()
        return

    if contexto.startswith("aguardando:"):
        return

    # menu
    if contexto == "menu":
        tratar_menu(linha)


def tratar_menu(op):
    global contexto

    if op == "1":
        enviar({"type": "list"})
        time.sleep(0.2)
        # drena a resposta online
        deadline = time.time() + 1
        while time.time() < deadline:
            if not fila_rede.empty():
                msg = fila_rede.get()
                if msg.get("type") == "online":
                    usuarios_online[:] = msg["users"]
                    break
                else:
                    fila_rede.put(msg)
            time.sleep(0.05)
        outros = [u for u in usuarios_online if u["user"] != meu_nome]
        if not outros:
            print("Ninguem online no momento.")
        else:
            print("Usuarios online:")
            for u in outros:
                print(f"  - {u['user']} ({AREAS.get(u['area'], '?')})")
        prompt()

    elif op == "2":
        outros = [u for u in usuarios_online if u["user"] != meu_nome]
        if not outros:
            print("Ninguem disponivel. Use opcao 1 para atualizar.")
            prompt()
            return
        print("Com quem:")
        for i, u in enumerate(outros, 1):
            print(f"  {i} - {u['user']} ({AREAS.get(u['area'], '?')})")
        print("  0 - Cancelar")
        print("> ", end="", flush=True)
        try:
            escolha = int(fila_teclado.get(timeout=30))
            if escolha == 0:
                prompt()
                return
            destino = outros[escolha - 1]["user"]
        except:
            print("Opcao invalida.")
            prompt()
            return
        enviar({"type": "chat_request", "from": meu_nome, "to": destino})
        print(f"Aguardando {destino} aceitar...")
        contexto = f"aguardando:{destino}"

    elif op == "3":
        print("Mensagem para o setor: ", end="", flush=True)
        texto = fila_teclado.get(timeout=60)
        if texto:
            enviar({"type": "broadcast", "from": meu_nome, "area": minha_area, "text": texto})
            print("Enviado!")
        prompt()

    elif op == "4":
        print("Texto do aviso (vai para todos): ", end="", flush=True)
        texto = fila_teclado.get(timeout=60)
        if texto:
            enviar({"type": "aviso", "from": meu_nome, "area": minha_area, "text": texto})
            print("Aviso enviado!")
        prompt()

    elif op == "5":
        print("Ate logo!")
        sys.exit(0)

    else:
        if op:
            print("Opcao invalida.")
        prompt()

sock.connect((HOST, PORT))
fazer_login()

threading.Thread(target=thread_rede,    daemon=True).start()
threading.Thread(target=thread_teclado, daemon=True).start()

enviar({"type": "list"})

try:
    loop()
except KeyboardInterrupt:
    print("\nSaindo...")
finally:
    sock.close()