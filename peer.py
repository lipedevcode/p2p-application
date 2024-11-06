import socket
import threading
import uuid
import os
import json
import time
import ast
import re

class Peer:
    def __init__(self, host=socket.gethostbyname(socket.gethostname()), port=5000):
        self.id = str(uuid.uuid4())  # Gera um ID único para o peer
        self.host = host if host != '127.0.0.1' else self.get_local_ip()
        self.port = port
        self.peers = [] # Lista de peers conectados
        self.conns = [] # Lista de conexões do peer
        self.files = {}  # Dicionário para armazenar os arquivos (nome do arquivo -> caminho local)
        self.connection_socket = []
        self.incidents_peers = [] # Peers que estão conectados neste peer
        self.disconnected_peers = [] # Lista de peers que já saíram da conexão

    def get_local_ip(self):
        try:
            # Tenta obter o IP local da rede
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))  # Google DNS para garantir uma saída
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception as e:
            print(f"[ERROR] Não foi possível obter o IP local: {e}")
            return "127.0.0.1"

    def start(self):
        # Inicializa o socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(5)
        print(f"[INFO] Peer iniciado com ID : {self.id} em {self.host}:{self.port}")
        threading.Thread(target=self.accept_peers).start()

    def send_request(self, sock, msg, bufsize=1024, flag_recv=True, flag_recv_binary_msg=False):
        sock.send(msg.encode())
        if flag_recv_binary_msg:
            response = self.receive(sock, bufsize, flag_recv_binary_msg) ##resposta em binario
            return response
        if flag_recv:
            response = self.receive(sock, bufsize) ##resposta decodificada
            return response
        return None
    
    def receive(self, sock, bufsize=1024, flag_recv_binary_msg=False):
        if flag_recv_binary_msg == False:
            return sock.recv(bufsize).decode()
        return sock.recv(bufsize)
    
    def extract_list(self, data):
        match = re.search(r"\[.*\]", data)
        if match:
            lst_str = match.group(0) 
            try:
                lst = ast.literal_eval(lst_str)
                return lst
            except (ValueError, SyntaxError):
                print("Erro ao converter a string para lista.")
                return None
        else:
            print("Nenhuma lista encontrada na string.")
            return None
    
    def upload_file_txt(self, filename):
        if os.path.exists(filename):
            self.files[filename] = os.path.abspath(filename) 
            print(f"[INFO] Arquivo '{filename}' está disponível para outros peers.")
        else:
            print(f"[INFO] Arquivo '{filename}' não encontrado.")

    def identify_data_peer(self, filename, id_request_data=None, visited_peers=None):
        if filename in self.files:
            print("[INFO] Arquivo está no host local")
            return None, None, None
        self.check_peer_connections()
        if visited_peers == None:
            visited_peers = []
        for peer, conn in zip(self.peers, self.conns):
            if peer['id'] in visited_peers:
                continue
            response = self.send_request(conn, f"CHECK {filename}")
            command, *args = response.split()
            if command == 'FOUND':
                print(f"[INFO] Peer {peer['id']} tem o arquivo {filename}.")
                return peer['id'], peer['host'], peer['port']
            else:
                visited_peers.append(args[0])
                if id_request_data == peer['id']: #evita que o peer A pergunte para o peer B se este tem o arquivo, o mesmo que pediu o arquivo 
                    continue
                elif id_request_data == None:
                    id_request_data = self.id
                response = self.send_request(conn, f"VERIFY {id_request_data} {filename} {visited_peers}")
                if "{" in response: ##ACHOU PEER QUE TEM O ARQUIVO
                    response = json.loads(response)
                    print(f"[INFO] Peer {response['id']} em {response['host']} : {response['port']} tem o arquivo {filename}")
                    return response['id'], response['host'], response['port']
        print(f"[INFO] Não encontrei o arquivo {filename}")
        return None, None, None
        
    def _connect_to_peer(self, peer_host, peer_port):
        """Conecta ao peer, porém não adiciona informações do peer em seu objeto"""
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((peer_host, peer_port))
            self.send_request(client_socket, f'connect', flag_recv=False)
            time.sleep(0.5) ##===============
            return client_socket    
        except:
            client_socket.close()
            return None
    
    def download_file_txt(self, filename, peer_ip, peer_port):
        if filename in self.files:
            print("[INFO] Arquivo já foi baixado")
            return
        if not peer_ip or not peer_port:
            print("[INFO] Arquivo não encontrado para download")
            return
        client_socket = self._connect_to_peer(peer_ip, peer_port)
        response = self.send_request(client_socket, f"DOWNLOAD {filename}", 4096, flag_recv_binary_msg=True) #4096 tamanho do buffer que vai receber a resposta
        file_data = response  #arquivo
        if file_data:
            with open(filename, 'wb') as f:
                f.write(file_data)
            print(f"[INFO] Arquivo {filename} baixado com sucesso")
            self.files[filename] = os.path.abspath(filename) #adicionando o arquivo ao dicionario de arquivos deste peer
        else:
            print(f"[INFO] Arquivo {filename} não pôde ser baixado")
        client_socket.close()

    def connect_to_peer(self, peer_host, peer_port):
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((peer_host, peer_port))
        except:
            print('[INFO] Erro ao conectar no peer')
            client_socket.close()
            return
        self.conns.append(client_socket)
        response = self.send_request(client_socket, "getID")
        id_peer = response
        print(f"[INFO] Conectado ao peer {peer_host}:{peer_port} - Peer {id_peer}")
        self.send_request(client_socket, f'{{"id": "{self.id}", "host": "{self.host}", "port": {self.port}}}', flag_recv=False) 
        peer_info = {'id': id_peer, 'host': peer_host, 'port': peer_port}
        self.peers.append(peer_info)

    def exit_peer(self):
        print('[INFO] Saindo do servidor...') 
        self.check_peer_connections()
        for peer in self.incidents_peers:
            if any(peer['id'] == p['id'] for p in self.peers):
                continue
            sock = self._connect_to_peer(peer['host'], peer['port'])
            self.send_request(sock, f"{self} saiu", flag_recv=False)
            #time.sleep(0.01) #caso dê erro json extra data
            sock.close()

    def close_connections_sock(self):
        for c_sock in self.connection_socket:
            c_sock.close() #fechando connection socket para sair do loop infinito da função handle_peer

    def accept_peers(self):
        # Aceita conexões de outros peers
        connection_socket = None
        try:
            while True:
                connection_socket, addr = self.server_socket.accept() 
                self.check_peer_connections()
                threading.Thread(target=self.handle_peer, args=(connection_socket,)).start()
                time.sleep(0.5)
                peer_info = None
                while peer_info == None:
                    try:
                        peer_info = self.incidents_peers[-1]
                    except IndexError:
                        pass
                if peer_info == 0:
                    self.incidents_peers.pop()
                    continue
                print(f"[INFO] Conexão aceita de {addr} - Peer {peer_info['id']}")
                self.connection_socket.append(connection_socket)
        except OSError:
            self.exit_peer()
        finally:
            self.close_connections_sock()
            self.server_socket.close()

    def pop_incidents_peers(self, id):
        if not self.incidents_peers:
            return
        index = -1
        for i in range(len(self.incidents_peers)):
            if self.incidents_peers[i] == 0:
                continue
            if id == self.incidents_peers[i]['id']:
                index = i
                break
        if index == -1:
            return
        self.incidents_peers.pop(index)

    def send_msg_leave_to_peers_connected(self, msg):
        for conn in self.conns:
            self.send_request(conn, f"_{msg}", flag_recv=False)

    def handle_peer(self, connection_socket):
        while True:
            try:
                data = self.receive(connection_socket)
            except:
                #check_peer
                break
            if not data:
                break
            command, *args = data.split()
            if command == 'CHECK':
                filename = args[0]
                if filename in self.files:
                    self.send_request(connection_socket, f"FOUND", flag_recv=False)
                else:
                    self.send_request(connection_socket, f"NOTFOUND {self.id}", flag_recv=False)
            elif command == 'VERIFY':
                id_request_data = args[0]
                filename = args[1]
                visited_peers = self.extract_list(data)
                id, ip, port = self.identify_data_peer(filename, id_request_data, visited_peers)
                if id == None:
                    self.send_request(connection_socket, f"NOTFOUND", flag_recv=False)
                    print(f"[INFO] Pedido de procura feito pelo peer {id_request_data} - Não encontrei o arquivo {filename}.")
                else:
                    self.send_request(connection_socket, f'{{ "id": "{id}", "host": "{ip}", "port": {port}}}', flag_recv=False) #Info do peer que possui o arquivo
                    print(f"[INFO] Pedido de procura feito pelo peer {id_request_data} - Encontrei o arquivo {filename}.")
            elif command == 'DOWNLOAD':
                filename = args[0]
                if filename in self.files:
                    with open(self.files[filename], 'rb') as f:
                        connection_socket.send(f.read())
                else:
                    self.send_request(connection_socket, "", flag_recv=False)
            elif command == 'Peer': #saiu do servidor
                exited_peer_id = args[0]
                if exited_peer_id in self.disconnected_peers: #este peer já foi avisado
                    continue
                print(f'[INFO] {data}')
                self.check_peer_connections()
                self.pop_incidents_peers(exited_peer_id)
                self.send_msg_leave_to_peers_connected(data)
                self.incidents_peers.append(0)
                self.disconnected_peers.append(exited_peer_id)
                self.send_request(connection_socket, "", flag_recv=False)
            elif command == '_Peer':
                exited_peer_id = args[0]
                if exited_peer_id == self.id:
                    continue
                if exited_peer_id in self.disconnected_peers:
                    continue
                if not any(exited_peer_id == peer['id'] for peer in self.peers):
                    print(f"[INFO] {data[1:]}")
                    self.send_msg_leave_to_peers_connected(data[1:])
                    self.send_request(connection_socket, "", flag_recv=False) 
            elif data == 'getID':
                self.send_request(connection_socket, f"{self.id}", flag_recv=False)
            elif data[0] == '{': #informações do peer que conectou neste peer
                peer_info = json.loads(data)
                if any(peer_info['id'] == peer['id'] for peer in self.incidents_peers):
                    self.incidents_peers.append(0) #flag que indica que este peer já estava conectado, portanto resolve a redundancia de ter duas conexões com um mesmo peer
                    self.send_request(connection_socket, "", flag_recv=False)
                    continue
                self.incidents_peers.append(peer_info)
                self.send_request(connection_socket, "", flag_recv=False)
            elif data == 'connect':
                self.incidents_peers.append(0)
                self.send_request(connection_socket, "", flag_recv=False)
            elif data == 'getFile':
                list_files = list(self.files.keys())
                self.send_request(connection_socket, f"{list_files}", flag_recv=False)
            
    def check_peer_connections(self):
        aux_conns = []
        aux_peers = []
        for i in range(len(self.conns)):
            try:
                self.send_request(self.conns[i], "oi", False)
                aux_conns.append(self.conns[i])
                aux_peers.append(self.peers[i])
            except:
                continue
        try:
            self.incidents_peers.remove(0)
        except ValueError:
            pass
        self.conns, self.peers = aux_conns, aux_peers

    def get_list_of_peers_files(self):
        self.check_peer_connections()
        peers_files = {}
        for i, conn in enumerate(self.conns):
            response = self.send_request(conn, 'getFile')
            peers_files[i] = self.extract_list(response)    
        list_of_peers_files = {peer['id']: file for peer, file in zip(self.peers, peers_files.values())}
        return list_of_peers_files
    
    def get_list_of_peers(self):
        self.check_peer_connections() #verificação adicional para o caso de algum peer conectado a este peer tenha saido sem ter avisado.
        return self.peers, self.incidents_peers
    
    def close_conn(self):
        #check_peer
        for conn in self.conns:
            try:
                self.send_request(conn, f"{self} saiu", False)
                conn.close()
            except:
                conn.close()
        self.server_socket.close()

    def __str__(self):
        return f"Peer {self.id} em {self.host}:{self.port}"