


import time
import threading

import config
import file_utils
from state import estado

_check_lock = threading.Lock()


def _inicializar_estado():
    arquivos_locais = file_utils.listar_arquivos_locais()
    for nome, info in arquivos_locais.items():
        antigo = estado.get_arquivo(nome)
        if antigo is None:
            estado.atualizar_arquivo(
                nome, info["hash"], info["mtime"], info["size"], version=1
            )


def _verificar_e_notificar(on_mudanca):
    arquivos_locais = file_utils.listar_arquivos_locais()
    estado_conhecido = estado.get_estado_arquivos()

    for nome, info in arquivos_locais.items():

        if estado.deve_ignorar(nome):
            antigo = estado_conhecido.get(nome)
            versao = antigo["version"] if antigo else 1
            estado.atualizar_arquivo(
                nome, info["hash"], info["mtime"], info["size"], version=versao
            )
            continue

        antigo = estado_conhecido.get(nome)

        if antigo is None:
            estado.atualizar_arquivo(
                nome, info["hash"], info["mtime"], info["size"], version=1
            )
            print(f"[ monitor ] novo arquivo: {nome}")
            on_mudanca("update", nome)

        elif antigo.get("deleted"):
            nova_versao = antigo["version"] + 1
            estado.atualizar_arquivo(
                nome, info["hash"], info["mtime"], info["size"], version=nova_versao
            )
            print(f"[ monitor ] arquivo recriado: {nome}")
            on_mudanca("update", nome)

        elif antigo["hash"] != info["hash"]:
            nova_versao = antigo["version"] + 1
            estado.atualizar_arquivo(
                nome, info["hash"], info["mtime"], info["size"], version=nova_versao
            )
            print(f"[ monitor ] arquivo modificado: {nome} (v{nova_versao})")
            on_mudanca("update", nome)

    for nome, antigo in estado_conhecido.items():
        if antigo.get("deleted"):
            continue
        if nome not in arquivos_locais:
            if estado.deve_ignorar(nome):
                estado.atualizar_arquivo(
                    nome, antigo["hash"], antigo["mtime"], antigo["size"],
                    version=antigo["version"], deleted=True
                )
                continue

            nova_versao = antigo["version"] + 1
            estado.atualizar_arquivo(
                nome, antigo["hash"], antigo["mtime"], antigo["size"],
                version=nova_versao, deleted=True
            )
            print(f"[ monitor ] arquivo removido: {nome} (v{nova_versao})")
            on_mudanca("delete", nome)


def thread_monitor(on_mudanca):
    _inicializar_estado()

    while True:
        time.sleep(config.POLL_INTERVAL)

        if not _check_lock.acquire(blocking=False):
            continue

        try:
            _verificar_e_notificar(on_mudanca)
        except Exception as e:
            print(f"[ monitor ] erro: {e}")
        finally:
            _check_lock.release()


def verificar_mudancas(on_mudanca):
    if not _check_lock.acquire(blocking=False):
        return

    try:
        _verificar_e_notificar(on_mudanca)
    finally:
        _check_lock.release()


def iniciar_monitor(on_mudanca):
    threading.Thread(target=thread_monitor, args=(on_mudanca,), daemon=True).start()
