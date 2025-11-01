import socket
import struct
import json
import threading
from random import randint
#Multicast Global
PORTA_MC = 4000
IP_MC = "224.1.1.1"

class Peer:
    def __init__(self):
        self.nome = ""
        self.iniciar_socket()
        self.entrar_na_rede()
        self.rede_p2p()

    def iniciar_socket(self):#Cria Socket TCP para ouvir os demais peers
        while True:
            try:#Gera um socket com porta aleatoria
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                addr = (socket.gethostbyname(socket.gethostname()), randint(1025,6000))
                self.sock.bind(addr)
                self.sock.listen(10)#Ouve até 10 peers
                self.address = addr
                break
            except KeyboardInterrupt:
                exit(0)
            except:#se não deu para fazer bind, tenta novamente
                continue

    def entrar_na_rede(self):
        while(True):
            try:#Tenta registrar o usuario na rede
                print("\tRegistrando-se")
                self.registrarse()
                break
            except socket.timeout:#Se o coordenador não foi encontrado, então cria uma nova rede
                print("\tVirou Coordenador")
                self.iniciar_rede()
                break
            except KeyboardInterrupt:#Encerra o programa
                exit(0)
            except Exception as e:#Erro ao se registrar
                print(e)
                continue
        
    def registrarse(self):#comunicação em multicast com o servidor
        nome = input("Nome de Usuário: ")
        ip,port = self.address
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        sock.settimeout(5.0)  # tempo máximo de espera pela resposta
        try:
            #Envia para o servidor multicast, ip e porta
            msg = f"0\x1f{nome}\x1f{ip}\x1f{port}".encode()
            sock.sendto(msg,(IP_MC,PORTA_MC));
            #Recebe uma resposta
            data, addr = sock.recvfrom(4096)
            data = data.decode().split("\x1f")
            match int(data[0]):
                case 1:#Nome Aprovado
                    self.id = int(data[1])#recebe novo id
                    self.nome = nome
                    self.max_id = self.id #Atualmente é o maior id que conhece
                    self.coord_address = (data[2],int(data[3]))#recebe socket do coordenador
                    self.peers = json.loads(data[4])#lista dos peers
                    self.coord_id = int(data[5])
                    self.coord = False #O nó não é o coordenador
                    return
                case 2:#Nome Não Aprovado, fazer voltar o loop
                    print("Nome já está em uso")
                    raise Exception
                case _:#Outro
                    return
            return
        except socket.timeout:#Passa para cima
            self.nome = nome
            raise socket.timeout
        finally:
            sock.close()

    def iniciar_rede(self):#Não existia coordenador no momento de entrar na rede
        self.max_id = 0
        self.id = 0
        self.coord_id = self.id
        self.coord = True
        self.peers = {}
        self.coord_address = self.address
        self.MC_listener = threading.Thread(target = self.ouvir_Multicast)
        self.MC_listener.start()#inicia thread

    def ouvir_Multicast(self):
        #criar thread para ouvir o multicast
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', PORTA_MC))

        # Adiciona à assinatura multicast
        mreq = struct.pack('4s4s', socket.inet_aton(IP_MC),socket.inet_aton('0.0.0.0'))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        while True:
            try:
                data, addr = sock.recvfrom(4096)#espera mensagens
                data = data.decode().split("\x1f")
                match int(data[0]):
                    case 0:#Recebeu um pedido de join
                        nome = data[1]#recebe o nome que o usuario quer
                        address = (data[2],int(data[3]))#recebe o endereço do usuario
                        if nome in self.peers:#se o nome já está registrado manda uma mensagem tipo 2
                            msg = f"2\x1f".encode()
                            sock.sendto(msg,addr)
                        else:#Nome aprovado
                            self.peers[nome] = address
                            self.max_id += 1
                            ip,port = self.address
                            msg = f"1\x1f{self.max_id}\x1f{ip}\x1f{port}\x1f{json.dumps(self.peers)}\x1f{self.id}".encode()
                            sock.sendto(msg,addr)
            except KeyboardInterrupt:
                exit(0)
            except:
                break
        return
    
    def rede_p2p(self):
        #Cria uma thread para ouvir e outra para mandar mensagens
        self.Chat = threading.Thread(target = self.chat)
        self.Chat.start()
        self.ouvir_peers()


    def chat(self):
        while True:
            try:
                msg = input("")
                msg = f"1\x1f{self.id}\x1f{("\033[36m" if self.coord else "\033[30m")}{self.nome}\033[0m:{msg}".encode()
                #envia a mensagem para o coordenador, para que este envie para todos
                sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                sock.connect(self.coord_address)
                sock.send(msg)
                sock.close()
            except KeyboardInterrupt:
                exit(0)
            
    def ouvir_peers(self):
        while True:
            client_socket, client_address = self.sock.accept()
            data = client_socket.recv(4096).decode().split("\x1f")#trava os programas
            client_socket.close()
            match int(data[0]):
                case 1:#recebeu uma mensagem
                    if self.coord:#int(data[1]) == self.coord_id:#Se foi manda
                        msg = f"1\x1f{self.id}\x1f{data[2]}".encode()
                        for nome in self.peers:
                            self.peers[nome]
                            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            sock.connect(tuple(self.peers[nome]))
                            sock.send(msg)
                            sock.close()
                        print(data[2])
                    elif int(data[1]) == self.coord_id:
                        print(data[2])

Peer()