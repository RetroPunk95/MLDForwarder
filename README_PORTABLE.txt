MLDForwarder — Versão Portátil para Windows
===========================================

ARQUIVOS PRINCIPAIS

MLDForwarder.exe
    Interface gráfica.

MLDForwarderSync.exe
    Motor da sincronização contínua.

MLDForwarderRetro.exe
    Motor da sincronização retroativa.

Os três executáveis devem permanecer na mesma pasta.

PRIMEIRO USO

1. Abra MLDForwarder.exe.
2. Entre em "Telegram".
3. Use o link para my.telegram.org se ainda não possuir API ID e API Hash.
4. Informe API ID e API Hash.
5. Salve as credenciais.
6. Faça a autenticação pelo telefone/código/2FA, se necessário.
7. Entre em "Rotas" e configure suas origens e destinos.
8. Use o Dashboard para iniciar a sincronização.

AJUDA NAS CONFIGURAÇÕES

As telas "Configurações" e "Retroativo" explicam abaixo de cada campo
o que a opção controla, o efeito de alterar o valor e qual é o padrão.

Para sincronizar um tópico de grupo:
- use o ID do grupo no campo de origem;
- clique em "Buscar tópicos";
- selecione o tópico pelo nome e ID;
- use o ID do canal no campo de destino.

O ID será preenchido automaticamente. O preenchimento manual continua
disponível. Deixe o ID do tópico vazio para sincronizar o canal ou grupo
inteiro.

Para enviar a um tópico de grupo:
- use o ID do grupo no campo de destino;
- clique em "Buscar tópicos" no painel DESTINO;
- selecione o tópico pelo nome e ID.

As duas opções podem ser combinadas. Assim, o programa aceita canal para
tópico, tópico para canal e tópico para tópico. Deixe o tópico de destino
vazio para publicar no canal ou no grupo principal.

FORMATAÇÃO DAS MENSAGENS

Textos e legendas são recriados preservando a formatação original sempre
que ela for suportada pelo Telegram. Isso inclui negrito, itálico,
sublinhado, tachado, spoiler, código, links, menções, citações e emojis
personalizados. Em álbuns, cada arquivo mantém a formatação da própria
legenda.

ARQUIVOS CRIADOS/USADOS LOCALMENTE

.env
    API ID e API Hash.

user_session.session
    Sessão do Telegram.

channels.json
    Rotas de canais, grupos e tópicos.

sync_progress.json
    Progresso da sincronização normal.

historico_progress.json
    Progresso do retroativo.

normal_config.json
retro_config.json
app_config.json
    Preferências do programa.

SEGURANÇA

Não compartilhe:
- .env
- user_session.session
- arquivos de progresso se contiverem informações que você prefira manter privadas.

O usuário final não precisa instalar Python.
