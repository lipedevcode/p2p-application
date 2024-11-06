from peer import Peer
import random

peer = Peer(port=random.randint(5000,9999)) #Caso esteja rodando os processos na mesma máquina 
#peer = Peer()
peer.start()
print(f'Peer criado: Adress - {peer.host} Port - {peer.port}')
menu = """1 - Upload de arquivo txt
2 - Identificar qual peer tem um determinado arquivo
3 - Conectar com um peer
4 - Printar lista de arquivos deste peer
5 - Printar lista de conexões deste peer
6 - Fazer download de um arquivo txt
7 - Printar lista de arquivos das conexões deste peer
0 - Sair"""
print(menu)
print('Digite uma opção: ')
while True:
    try:
        op = int(input(""))
        if op == 1:
            filename = input("Digite o nome do arquivo txt que deseja compartilhar: ")
            peer.upload_file_txt(filename)
        elif op == 2:
            filename = input('Digite o nome do arquivo txt: ')
            peer.identify_data_peer(filename)
            #a função peer.identify_data_peer retorna o uuid, endereço e porta do peer que contém o arquivo
        elif op == 3:
            peer_ip = input("Digite o IP do peer que você quer se conectar: ")
            peer_port = int(input("Digite a porta: "))
            peer.connect_to_peer(peer_host=peer_ip, peer_port=peer_port)
        elif op == 4:
            print(peer.files)
        elif op == 5:
            peers, incidents_peers = peer.get_list_of_peers()
            print("Conexões deste peer ->:", peers)
            print("Conexões incidentes a este peer <-:", incidents_peers)
        elif op == 6:
            filename = input('Digite o nome do arquivo txt: ')
            flag = input('Digite (S) se você tem o endereço e porta do peer que contém o arquivo deseja. SENÂO digite qualquer letra: ')
            if flag == 'S' or flag == 's':
                peer_ip = input("Digite o IP do peer que você quer se conectar: ")
                peer_port = int(input("Digite a porta: "))
            else:
                uuid, peer_ip, peer_port = peer.identify_data_peer(filename)
            peer.download_file_txt(filename, peer_ip, peer_port)
        elif op == 7:
            print("Lista de arquivos das conexões deste peer ->: ", peer.get_list_of_peers_files())
        elif op == 0:
            # passar por todas conexões encerrá-las e printar msg
            peer.close_conn()
            break
    except ValueError:
        print("Tente novamente uma das opções! De 0 a 7")