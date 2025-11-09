import socket
import struct
import json
import threading
import errno
#Multicast Global
PORTA_MC = 6000
IP_MC = "224.1.2.1"

#Para iniciar é só chamar "python peer.py" que vai iniciar um peer


class Peer:
    def __init__(self):
        #Ao Iniciar um peer, ele chama as funções de inicialização e fica preso nelas em loop até abandonar o chat
        self.active = True
        self.iniciar_socket()
        self.entrar_na_rede()
        self.rede_p2p()
        print("Conexão Encerrada")

    def iniciar_socket(self):
        #Todo peer possui um socket TCP self.sock para ouvir outros peers da rede.
        #Este socket é utilizado para receber mensagens do coordenador, ou de outros peers durante a eleição.
        print("Configurando Socket")
        while self.active:
            try:#Gera um socket com porta aleatoria
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                addr = (input("\tIP:"), int(input("\tPORT:")))
                self.sock.bind(addr)
                self.sock.listen(10)#Ouve até 10 peers
                self.address = addr
                break
            except KeyboardInterrupt:
                self.active = False
            except ValueError:
                print("Um dos valores é inválido")
            except OSError as e:#se não deu para fazer bind, tenta novamente
                match e.errno :
                    case errno.EADDRINUSE:
                        print("Endereço já está sendo usado")
                    case errno.EADDRNOTAVAIL:
                        print("Endereço Não Disponível")
                    case errno.EACCES:
                        print("Acesso Negado")
                    case _:
                        self.active = False
                        print("Abortando Programa: ",e.errno)
                        return
                print("Tente novamente")

    def entrar_na_rede(self):
        #Este método gerencia a entrada de um nó na rede pelo canal de multicast.
        #Se o peer falhou não encontrou ninguém para atender seu pedido de registro no canal de multicast, 
        #então ele inicia a rede se tornando coordenador(ao receber socket.timeout)

        while(self.active):
            try:#Tenta registrar o usuario na rede
                print("Registrando Peer")
                self.registrarse()
                break
            except TimeoutError:#Se o coordenador não foi encontrado, então cria uma nova rede
                self.iniciar_rede()
                break
            except KeyboardInterrupt:#Encerra o programa
                self.active = False
            except:#Outros 
                continue
        
    def registrarse(self):#comunicação em multicast com o servidor
        #Nesta função o Usuário manda mensagem para o coordenador pelo IP multicast (224.1.2.1,6000)
        #Somente o Coordenador, se ele existir, responde à mensagem no canal de multicast.

        #O peer envia uma mensagem do tipo 0, para pedir sua entrada na rede.(JOIN_REQUEST)
        #Se a mensagem não for respondida a tempo, socket.timeout é detectado, e manda para cima outro socket.timeout

        #O peer pode receber 2 tipos de mensagens do coordenador
        #1 -> Peer aprovado. Recebe um id, self.sock do coordenador, lista de peers, e id do coordenador.
        #2 -> Nome de Usuário já está em uso. Não possui informações adicionais

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
            data, _ = sock.recvfrom(4096)
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
                    return
                case 2:#Nome Não Aprovado, fazer voltar o loop
                    print("Nome já está em uso")
                    raise Exception
            return
        except socket.timeout:#Passa para cima
            self.nome = nome
            self.coord_existe = True
            raise socket.timeout
        except Exception:
            raise Exception
        finally:
            sock.close()

    def iniciar_rede(self):
        #Esta função assume que ninguém estava na rede.
        #além do peer virar coordenador, a rede começa pelo ID 0 e sem nenhum peer
        self.max_id = 0
        self.id = 0
        self.peers = {}
        self.virar_coordenador()

    def ouvir_Multicast(self):
        #Esta função é usada como uma Thread separada dentro do peer coordenador(somente o peer coordenador ouve o canal de multicast)
        #Seu objetivo é ouvir as mensagens do canal de multicast to tipo 0(pedidos de entrada)

        #Se recebeu uma mensagem do tipo 0, verifica em self.peers se o nome requerido pelo usuário já está em uso.
        #Envia 1 caso o nome esteja livre, e adiciona o novo peer no dicionário self.peers junto com o endereço IP.
        #   Além disso, envia por meio a função de repassar uma mensagem avisando todos os peers da rede sobre a entrada de um novo peer
        #Envia 2 caso o nome já esteja em uso, não faz nada com a informação.

        #O socket usado para ouvir Multicast possui um timeout, pois caso contrário, o recvfrom pode impedir a thread de acabar

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
    
    def rede_p2p(self):
        #Inicia o Peer comum, que possui no programa principal executa ouvir_peers()
        #Em uma thread separada, todo peer pode escrever mensagens no chat
        #Se entrou nesta função, então o peer está pronto
        print("Conectado a rede")
        try:
            self.Chat = threading.Thread(target = self.chat, daemon = True)
            self.Chat.start()
            self.ouvir_peers()
        except:
            return

    def chat(self):
        #Na Thread de Chat, é aguardado o input do usuário(a mensagem a ser enviada) e é mandada com o código 1 para o coordenador
        #O coordenador vai repassar a mensagem para todos os peers(incluindo quem enviou), e assim os peers sabem que é para imprimir a mensagem na tela
        #A mensagem é escrita no formato "{self.nome}:{msg}"
        #Em caso de falha ao se comunicar com o coordenador, muda o valor de self.coord_existe, que é utilizado na função ouvir_peers para chamar uma eleição
        while self.active:
            try:
                msg = input("")
                msg = f"1\x1f{self.id}\x1f{self.nome}:{msg}".encode()
                self.enviar_para_coordenador(msg)
            except KeyboardInterrupt:
                self.active = False
            except:
                self.coord_existe = False
                while(not self.coord_existe):
                    continue
                
    def ouvir_peers(self):
        #Esta Função reage aos 6 tipos de mensagens definidos para a comunicação entre peers, que são:
        #1: Mensagem do chat
        #    Coordenador: Recebe a mensagem de um peer, envia para todos os peers e escreve na própria tela
        #        -> garante ordenação
        #    Peer: Imprime na tela as mensagens do coordenador
        #2: Mensagem de Remoção
        #    Coordenador: Não Recebe este tipo de mensagem, só envia a medida que descobre
        #    Peer: Remove o peer de seu dicionário
        #3: Mensagem de Heartbeat
        #        -> Nota: Qualquer mensagem do coordenador é prova da atividade do coordenador, 
        #        logo, todas as mensagens são consideradas Heartbeat
        #    Coordenador: Não Recebe este tipo de mensagem, envia a cada 1 segundo sem repassar mensagens
        #    Peer: Reinicia o tempo de espera do peer(5 segundos)
        #4: Mensagem de Inicio de Eleição
        #        -> Nota: Eleição Feita em Bully
        #    Coordenador: Assume-se que não existe caso esta mensagem chegue
        #    Peer: verifica o próprio ID e compara com o candidato para ver se ele vai para
        #        -> Comecar_Eleição: envia mensagem de candidatura para todos antes de entrar na função Eleição
        #        -> Eleição(1): entra no modo eleição já sabendo que seu ID não é o maior, só espera mensagens
        #5: Mensagem de Vitória na Eleição
        #        -> Não recebida nesta função
        #6: Mensagem de Adição
        #    Coordenador: Não Recebe esta mensagem, só envia toda vez que um novo peer é adicionado
        #    Peer: Adiciona um novo peer para o dicionário de peers

        while self.active:
            try:
                if(not self.coord_existe):
                    raise socket.timeout
                self.sock.settimeout(self.espera_padrao)
                client_socket, _ = self.sock.accept()
                client_socket.settimeout(self.espera_padrao)
                data = client_socket.recv(4096).decode().split("\x1f")
                client_socket.close()
                match (int(data[0])):
                    case 1:#recebeu uma mensagem
                        if self.coord:
                            msg = f"1\x1f{self.id}\x1f{data[2]}".encode()
                            self.repassar_mensagem(msg)
                        print(data[2])
                    case 2:#mensagem de remoção
                        if int(data[1])== self.coord_id:
                            try:
                                del self.peers[data[2]]
                            except KeyError:
                                continue
                    case 3:#Mensagem de Heartbeat do servidor, somente o servidor envia esta mensagem
                        continue
                    case 4:#Mensagem de Candidato para Eleição
                        if self.id > int(data[1]):
                            self.peers[data[2]] = (data[3],int(data[4]))
                            self.Comecar_Eleicao()
                        else:
                            self.Eleicao(1)
                    case 6:#Mensagem de adição
                        if int(data[1])==self.coord_id:
                            self.peers[data[2]] = (data[3],int(data[4]))
            except TimeoutError:
                if self.coord:#se sou
                    self.Heartbeat()
                else:
                    self.Comecar_Eleicao()
            except KeyboardInterrupt:
                self.active = False
        self.sock.close()

    def repassar_mensagem(self,msg):#Repassa Mensagem para todos os peers e detecta quando um peer não responde
        #Cria uma Thread para repassar mensagens
        #Esta ideia foi feita pois ao estar no programa principal prejudicava a comunicação dos peers entre si

        threading.Thread(target = self._repassar,args = (msg,),daemon = True).start()
        
    def _repassar(self,msg):
        #Função usada em thread para enviar uma mensagem para todos os peers conhecidos
        #Também faz a função de detectar quais peers não estão mais ativos na rede P2P
        #Para cada Peer no dicionário, exceto o Peer que lançou a thread, envia a mensagem por TCP
        #Qualquer erro, se supõe que a causa é pelo peer estar desconexo e adicionamos o nome na lista elimina

        #Somente o coordenador tem o poder de apagar peers, e além disso, é o nó que mais usa a função de repassar
        #O coordenador elimina os peers da lista de eliminação do próprio dicionário e envia mensagens de remoção para cada peer restante
        #Erros no momento de repassar as mensagens de remoção são ignorados.

        #Durante a execução do coordenador, várias threads podem reportar o KeyError devido a edição simultânea dos dicionários,
        #Este erro é ignorado pela thread atual, pois se um peer foi removido por outra thread de repassar
        #então este peer sería também detectado por esta como inativo

        #Os Peers comuns só chamam a função de repassar em contexto de eleição, no qual o self.sock de todos está mais ocupado,
        #Por esta razão, apesar das falhas de comunicação, são ignorados, pois só o coordenador pode retirar peers
        elimina = []
        temp = list(self.peers.items())
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
                elimina.append(nome)#adiciona na lista de peers caídos

        if not self.coord:#somente o coordenador pode eliminar peers
            return

        for nome in elimina:#elimina peers ausentes
            try:
                del self.peers[nome]
            except KeyError:
                continue

        if elimina:#envia mensagens para eliminar mais peers
            for nome_el in elimina:
                msg2 = f"2\x1f{self.id}\x1f{nome_el}".encode()
                for nome in self.peers:#Envia para todos os peers restantes
                    if nome == self.nome:
                        continue
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(3.0)
                        sock.connect(tuple(self.peers[nome]))
                        sock.send(msg2)
                        sock.close()
                    except:
                        continue
    
    def enviar_para_coordenador(self,msg):
        while(self.active):
            try:
                sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect(self.coord_address)
                sock.send(msg)
                break
            except (ConnectionRefusedError,socket.timeout):
                self.coord_existe = False
                while(not self.coord_existe and self.active):
                    continue
            finally:
                sock.close()

    def Heartbeat(self):
        #Envia uma mensagem para todos os peers sem muitas informações
        #É enviado períodicamente

        self.repassar_mensagem(f"3\x1f{self.id}".encode())

    def Comecar_Eleicao(self):
        #Ao detectar falha ao se conectar ao servidor ou heartbeat ausente por muito tempo, pode ser iniciada partindo de 2 estados
        #0 -> Peer sabe até agora que é o candidato com maior id
        #1 -> Peer sabe que a eleição não acabou, mas ele não é o melhor candidato

        #Caso tenha começado a eleição, assume que é o peer de maior id
        ip,port = self.address
        self.repassar_mensagem(f"4\x1f{self.id}\x1f{self.nome}\x1f{ip}\x1f{port}".encode())
        self.Eleicao(0)

    def Eleicao(self, estado = 0):
        #Espera mensagens do tipo 4 ou 5
        #Se recebe uma mensagem do tipo 5, já atualiza o coordenador e aceita ele como vencedor
        #Se recebe uma mensagem do tipo 4 com id maior que o próprio entra no estado 1, adicionalmente é usada para garantir que os peers estejam na lista de peers
        #Se der timeout na espera e o estado for 0, assume que é o coordenador, envia 5
        #Se der timeout na espera e o estado for 1, inicia uma nova eleição, envia 4 e muda o estado para 0
        while self.active:
            try:
                self.sock.settimeout(3+estado*3)#quem acredita ser o coordenador é mais 'impaciente' do que aqueles que sabem que não são

                client_socket, _ = self.sock.accept()
                data = client_socket.recv(4096).decode().split("\x1f")
                match int(data[0]):
                    case 4:#mensagem de eleição
                        self.peers[data[2]] = (data[3],int(data[4]))
                        if self.id < int(data[1]):
                            estado = 1
                    case 5:#mensagem de confirmação do novo coordenador
                        self.coord_id = int(data[1])
                        self.coord_address = (data[2],int(data[3]))
                        self.coord_existe = True
                        break
            except socket.timeout:
                if estado == 0:#se o tempo passou, então mandar mensagem confirmando ser o novo coordenador
                    ip,port = self.address
                    self.virar_coordenador()
                    self.repassar_mensagem(f"5\x1f{self.id}\x1f{ip}\x1f{port}".encode())
                    break
                else:#inicia nova eleição
                    estado = 0
                    ip,port = self.address
                    self.repassar_mensagem(f"4\x1f{self.id}\x1f{self.nome}\x1f{ip}\x1f{port}".encode())
            except KeyboardInterrupt:
                self.active = False
        
    def virar_coordenador(self):
        #Ao virar coordenador inicia uma thread para ouvir multicast e inicia suas variáveis
        self.coord_id = self.id
        self.coord = True
        self.coord_existe = True
        self.coord_address = self.address
        self.MC_listener = threading.Thread(target = self.ouvir_Multicast,daemon = True)
        self.peers[self.nome] = self.address
        self.MC_listener.start()#inicia thread
        self.espera_padrao = 1.0 #tempo de heartbeat do servidor

Peer()