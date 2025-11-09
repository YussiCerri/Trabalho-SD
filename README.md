# Trabalho-SD
Trabalho de universidade chat P2P

Qualquer Peer pode ser iniciado ao chamar a classe Peer em um chat.
Escreva "python peer.py" e o usuário entra em modo de inicialização,
responda escrevendo um socket válido e um nome de usuário novo na rede.
Cntl C para sair

## Peer comum

Todo peer têm um socket **self.sock** utilizado para receber mensagens de outros peers. Este é o socket que o usuário insere.
O  peer manda uma mensagem tipo 0 para o endereço de multicast, pedindo para entrar na rede.
Um peer comum executa 2 funções simultaneamente:

1. ouvir_peers(programa principal): recebe mensagens da rede P2P e reage de acordo

2. chat(thread):lê a entrada do usuário e manda as mensagens do chat para o coordenador

Os peers esperam 5 segundos por qualquer mensagem do Coordenador, considerando todas como evidência da presença do servidor

## Coordenador

O coordenador executa o heartbeat a cada segundo caso não receba uma mensagem.

O coordenador têm 1 thread adicional em relação aos peers:

MC_Listener: ouve as mensagens no canal de multicast para aprovar ou não o nome de um usuário e adicioná-lo à rede
