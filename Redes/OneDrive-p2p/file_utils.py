import os
import hashlib

import config


def caminho_completo(filename):
    return os.path.join(config.SYNC_FOLDER, filename)


def garantir_pasta():
    os.makedirs(config.SYNC_FOLDER, exist_ok=True)


def calcular_hash(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            bloco = f.read(65536)
            if not bloco:
                break
            h.update(bloco)
    return h.hexdigest()


def _ignorar_arquivo(nome):
    return nome.startswith(".p2p_")

def listar_arquivos_locais():
    garantir_pasta()
    arquivos = {}
    for nome in os.listdir(config.SYNC_FOLDER):
        if _ignorar_arquivo(nome):
            continue
        caminho = caminho_completo(nome)
        if os.path.isfile(caminho):
            stat = os.stat(caminho)
            arquivos[nome] = {
                "hash": calcular_hash(caminho),
                "mtime": stat.st_mtime,
                "size": stat.st_size,
            }
    return arquivos


def ler_arquivo_bytes(filename):
    with open(caminho_completo(filename), "rb") as f:
        return f.read()


def escrever_arquivo_bytes(filename, dados):
    garantir_pasta()
    with open(caminho_completo(filename), "wb") as f:
        f.write(dados)


def remover_arquivo(filename):
    caminho = caminho_completo(filename)
    if os.path.exists(caminho):
        os.remove(caminho)


def arquivo_existe(filename):
    return os.path.isfile(caminho_completo(filename))
