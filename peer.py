import socket
import struct
import json
import threading
import time
from random import randint
#Multicast Global
PORTA_MC = 6000
IP_MC = "224.1.2.1"

class Peer:
    def __init__(self):
        self.nome = ""
        self.espera = 5.0
        self.active = True
        self.iniciar_socket()
        self.entrar_na_rede()
        self.rede_p2p()

    def iniciar_socket(self):#Cria Socket TCP para ouvir os demais peers
        while self.active:
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
        while(self.active):
            try:#Tenta registrar o usuario na rede
                print("Registrando-se")
                self.registrarse()
                return
            except socket.timeout:#Se o coordenador não foi encontrado, então cria uma nova rede
                print("Não Encontrou o Coordenador")
                self.iniciar_rede()
                return
            except KeyboardInterrupt:#Encerra o programa
                self.active = False
            except Exception as e:#Erro ao se registrar
                print(e)
                continue
        
    def registrarse(self):#comunicação em multicast com o servidor
        nome = input("\tNome de Usuário: ")
        ip,port = self.address
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        sock.settimeout(5.0)  # tempo máximo de espera pela resposta
        try:
            #Envia para o servidor multicast, ip e porta
            msg = f"0\x1f{nome}\x1f{ip}\x1f{port}".encode()
            sock.sendto(msg,(IP_MC,PORTA_MC))
            #Recebe uma resposta
            data, addr = sock.recvfrom(4096)
            data = data.decode().split("\x1f")
            msg_type = int(data[0])
            match msg_type:
                case 1:#Nome Aprovado
                    self.id = int(data[1])#recebe novo id
                    self.nome = nome
                    self.max_id = self.id #Atualmente é o maior id que conhece
                    self.coord_address = (data[2],int(data[3]))#recebe socket do coordenador
                    self.peers = json.loads(data[4])#lista dos peers
                    self.coord_id = int(data[5])
                    self.coord = False #O nó não é o coordenador
                    self.coord_existe = True
                    self.espera_padrao = 5.0#tempo que um peer espera por um contato com o coordenador
                    self.espera = self.espera_padrao
                    return
                case 2:#Nome Não Aprovado, fazer voltar o loop
                    print("Nome já está em uso")
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
        self.peers = {}
        self.virar_coordenador()

    def ouvir_Multicast(self):
        """
            Função que os Coordenadores usam para receberem o pedido de entrada na rede.
            Usada para responder quem quer entrar
        """
        #criar thread para ouvir o multicast
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', PORTA_MC))

        # Adiciona à assinatura multicast
        mreq = struct.pack('4s4s', socket.inet_aton(IP_MC),socket.inet_aton('0.0.0.0'))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        while self.active:
            try:
                sock.settimeout(1.0)
                data, addr = sock.recvfrom(4096)#espera mensagens
                data = data.decode().split("\x1f")
                msg_type = int(data[0])
                match msg_type:
                    case 0:#Recebeu um pedido de join
                        nome = data[1]#recebe o nome que o usuario quer
                        address = (data[2],int(data[3]))#recebe o endereço do usuario
                        if nome in self.peers:#se o nome já está registrado manda uma mensagem tipo 2
                            print("peer não aprovado, nome repetido")
                            msg = f"2\x1f".encode()
                            sock.sendto(msg,addr)
                        else:#Nome aprovado
                            self.peers[nome] = address
                            self.max_id += 1
                            ip,port = self.address
                            msg = f"1\x1f{self.max_id}\x1f{ip}\x1f{port}\x1f{json.dumps(self.peers)}\x1f{self.id}".encode()
                            sock.sendto(msg,addr)
                            self.repassar_mensagem(f"6\x1f{self.id}\x1f{nome}\x1f{ip}\x1f{port}".encode())
            except KeyboardInterrupt:#encerra programa
                self.active = False
            except socket.timeout:
                continue
            except:
                continue
        sock.close()
        print("Saiu do Multicast")
    
    def rede_p2p(self):
        #Cria uma thread para ouvir e outra para mandar mensagens
        try:
            self.Chat = threading.Thread(target = self.chat, daemon = True)
            self.Chat.start()
            self.ouvir_peers()
        except:
            return

    def chat(self):
        while self.active:
            try:
                msg = input("")
                msg = f"1\x1f{self.id}\x1f{self.nome}:{msg}".encode()
                #envia a mensagem para o coordenador, para que este envie para todos
                sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect(self.coord_address)
                sock.send(msg)
                sock.close()
            except KeyboardInterrupt:
                self.active = False
            except socket.timeout:
                self.coord_existe = False
            except Exception:
                break
        print("Encerrando Chat")
                
    def ouvir_peers(self):
        while self.active:
            try:
                if(not self.coord_existe):
                    raise socket.timeout
                self.sock.settimeout(self.espera_padrao)
                client_socket, client_address = self.sock.accept()
                client_socket.settimeout(self.espera_padrao)
                data = client_socket.recv(4096).decode().split("\x1f")#Causa trava nos programas
                client_socket.close()
                match (int(data[0])):
                    case 1:#recebeu uma mensagem
                        if self.coord:
                            msg = f"1\x1f{self.id}\x1f{data[2]}".encode()
                            self.repassar_mensagem(msg)
                            self.espera = self.espera_padrao
                            print(data[2])
                        elif int(data[1]) == self.coord_id:
                            print(data[2])
                            self.espera = self.espera_padrao
                    case 2:#mensagem de remoção
                        if int(data[1])== self.coord_id and self.peers[data[2]]:
                            self.espera = self.espera_padrao
                            del self.peers[data[2]]
                    case 3:#Mensagem de Heartbeat do servidor, somente o servidor envia esta mensagem
                        self.espera = self.espera_padrao#Tempo de espera máximo por heartbeat
                    case 4:#Mensagem de Candidato para Eleição
                        if self.id > int(data[1]):
                            self.Comecar_Eleicao()
                        else:
                            self.Eleicao(1)
                    case 6:#Mensagem de adição
                        if int(data[1])==self.coord_id:
                            self.peers[data[2]] = (data[3],int(data[4]))
            except socket.timeout:
                if self.coord:#se sou
                    self.Heartbeat()
                else:
                    self.Comecar_Eleicao()
            except KeyboardInterrupt:
                self.active = False
        self.sock.close()
        print("Encerrando Ouvir_peers")


    def repassar_mensagem(self,msg):#Repassa Mensagem para todos os peers e detecta quando um peer não responde
        threading.Thread(target = self._repassar,args = (msg,),daemon = True).start()
        
    def _repassar(self,msg):
        elimina = []
        temp = self.peers.items()
        for nome ,addr in temp:
            if nome == self.nome:
                continue
            try:#Envia mensagem para um peer
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect(tuple(addr))
                sock.send(msg)
                sock.close()
            except (ConnectionRefusedError,TimeoutError,OSError,socket.error):#Caso não é possível se conectar, assume que se desconectou
                elimina.append(nome)#adiciona mensagens e

        if not self.coord:
            return

        for nome in elimina:#elimina peers ausentes
            if nome != self.nome:
                del self.peers[nome]

        if self.coord and elimina:
            for nome_el in elimina:
                msg2 = f"2\x1f{self.id}\x1f{nome_el}".encode()
                for nome in self.peers:#Envia para todos os peers restantes
                    if nome == self.nome:
                        continue
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(2.0)
                        sock.connect(tuple(self.peers[nome]))
                        sock.send(msg2)
                        sock.close()
                    except:
                        continue
    
    def Heartbeat(self):
        """
            O Heartbeat envia uma mensagem a todos os nós, informando que o servidor está ativo e verificando que os nós ainda estão na rede
        """
        self.repassar_mensagem(f"3\x1f{self.id}".encode())

    def Comecar_Eleicao(self):
        """
            Ao detectar falha ao se conectar ao servidor ou heartbeat ausente por muito tempo, a eleição é chamada
            0 -> Peer sabe até agora que é o candidato com maior id
            1 -> Peer sabe que a eleição não acabou, mas ele não é o melhor candidato
        """
        self.repassar_mensagem(f"4\x1f{self.id}".encode())
        self.Eleicao()

    def Eleicao(self, estado = 0):
        while self.active:
            try:
                if(self.espera == 0.0):
                    raise socket.timeout
                self.sock.settimeout(randint(3,10))#espera por 5 segundos
                client_socket, _ = self.sock.accept()
                data = client_socket.recv(4096).decode().split("\x1f")#
                match int(data[0]):
                    case 4:#mensagem de eleição
                        if self.id == int(data[1]):
                            continue
                        elif self.id < int(data[1]):#se o id do novo candidato é maior, então passo ao estado 1
                            estado = 1
                    case 5:#mensagem de confirmação do novo coordenador
                        self.coord_id = int(data[1])
                        self.coord_address = (data[2],int(data[3]))
                        self.espera = self.espera_padrao
                        self.coord_existe = True
                        break
            except socket.timeout:
                if estado == 0:#se o tempo passou, então mandar mensagem confirmando ser o novo coordenador
                    ip,porta = self.address
                    self.virar_coordenador()
                    self.repassar_mensagem(f"5\x1f{self.id}\x1f{ip}\x1f{porta}".encode())
                    break
                else:#inicia nova eleição
                    estado = 0
                    self.repassar_mensagem(f"4\x1f{self.id}".encode())
                    self.espera = self.espera_padrao
            except KeyboardInterrupt:
                self.active = False
        
    def virar_coordenador(self):
        self.coord_id = self.id
        self.coord = True
        self.coord_existe = True
        self.coord_address = self.address
        self.MC_listener = threading.Thread(target = self.ouvir_Multicast,daemon = True)
        self.MC_listener.start()#inicia thread
        self.espera_padrao = 2.0 #tempo de heartbeat do servidor
        self.espera = self.espera_padrao

Peer()