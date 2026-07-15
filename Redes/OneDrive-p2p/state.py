import json
import os
import threading
import time


class EstadoGlobal:
    def __init__(self):
        self.lock = threading.Lock()
        self.peers_conhecidas = {}
        self.estado_arquivos = {}
        self.ignorar_proximo = set()

    def atualizar_peer(self, peer_id, ip, tcp_port):
        with self.lock:
            self.peers_conhecidas[peer_id] = {
                "ip": ip,
                "tcp_port": tcp_port,
                "ultimo_contato": time.time(),
            }

    def remover_peers_inativos(self, timeout):
        agora = time.time()
        removidas = []
        with self.lock:
            for pid in list(self.peers_conhecidas.keys()):
                if agora - self.peers_conhecidas[pid]["ultimo_contato"] > timeout:
                    removidas.append(pid)
                    del self.peers_conhecidas[pid]
        return removidas

    def listar_peers(self):
        with self.lock:
            return dict(self.peers_conhecidas)

    def get_estado_arquivos(self):
        with self.lock:
            return {k: dict(v) for k, v in self.estado_arquivos.items()}

    def atualizar_arquivo(self, filename, hash_, mtime, size, version, deleted=False):
        with self.lock:
            self.estado_arquivos[filename] = {
                "hash": hash_,
                "mtime": mtime,
                "size": size,
                "version": version,
                "deleted": deleted,
            }
        self.salvar()

    def get_arquivo(self, filename):
        with self.lock:
            info = self.estado_arquivos.get(filename)
            return dict(info) if info else None

    def marcar_para_ignorar(self, filename):
        with self.lock:
            self.ignorar_proximo.add(filename)

    def deve_ignorar(self, filename):
        with self.lock:
            if filename in self.ignorar_proximo:
                self.ignorar_proximo.discard(filename)
                return True
            return False

    def _caminho_estado(self):
        import config
        return os.path.join(config.SYNC_FOLDER, ".p2p_state.json")

    def salvar(self):
        with self.lock:
            dados = {
                "estado_arquivos": {
                    k: dict(v) for k, v in self.estado_arquivos.items()
                }
            }
        try:
            caminho = self._caminho_estado()
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ estado ] erro ao salvar: {e}")

    def carregar(self):
        try:
            caminho = self._caminho_estado()
            with open(caminho, "r", encoding="utf-8") as f:
                dados = json.load(f)
            with self.lock:
                self.estado_arquivos = dados.get("estado_arquivos", {})
            print(f"[ estado ] carregado ({len(self.estado_arquivos)} arquivo(s))")
        except FileNotFoundError:
            print("[ estado ] nenhum estado salvo encontrado, comecando do zero")
        except Exception as e:
            print(f"[ estado ] erro ao carregar: {e}")


estado = EstadoGlobal()