MLD Tools — Versão Portátil para Windows
===========================================

ARQUIVOS PRINCIPAIS

MLDTools.exe
    Interface gráfica.

MLDToolsSync.exe
    Motor da sincronização contínua.

MLDToolsRetro.exe
    Motor da sincronização retroativa.

MLDToolsMedia.exe
    Central de downloads, exportações, uploads, fila e histórico.

MLDToolsAlbum.exe
    Motor de upload agrupado em álbuns.

engine\tdl.exe
    Motor de downloads, exportações e uploads comuns.

Todos os executáveis e a pasta engine devem permanecer juntos.

PRIMEIRO USO

1. Abra MLDTools.exe.
2. Entre em "Telegram".
3. Use o link para my.telegram.org se ainda não possuir API ID e API Hash.
4. Informe API ID e API Hash.
5. Salve as credenciais.
6. Faça a autenticação pelo telefone/código/2FA, se necessário.
7. Entre em "Rotas" e configure suas origens e destinos.
8. Use o Dashboard para iniciar a sincronização.
9. Abra "Central de mídia" para baixar, exportar ou enviar arquivos.

UPLOAD EM ÁLBUNS

Na Central de mídia, abra "Upload para Telegram" e ative
"Enviar arquivos agrupados em álbuns". Selecione "Seleção atual" para
agrupar todos os itens escolhidos ou "Cada pasta" para criar conjuntos
separados. A sessão da tela principal Telegram precisa estar autenticada.

Os uploads também aparecem em "Atividade recente" e no histórico da Central
de mídia. O botão "Adicionar à fila" não inicia o envio: downloads e uploads
aguardam juntos até o comando "Iniciar fila" e seguem a ordem de criação.
Para transferências comuns, abra "Configurações > Desempenho e rede". O perfil
Equilibrado (8/4/8) prioriza estabilidade; Rápido (16/6/12) é recomendado para
uso geral; Agressivo (24/8/16) serve para testar conexões rápidas com SSD e
pode antecipar limites temporários do Telegram. Escolha o perfil e salve.
Álbuns de documentos fazem pré-upload paralelo de até quatro arquivos e mantêm
a ordem selecionada.

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

BAIXAR E REENVIAR ARQUIVOS

Ao adicionar ou editar uma rota, ative "Baixar e reenviar arquivos" quando
a origem permitir o download, mas bloquear o encaminhamento ou a cópia
direta da mídia.

Nesse modo, o programa baixa os arquivos para temp_transferencias, reenvia
como novas publicações e apaga cada temporário depois da confirmação.
Downloads interrompidos ficam com extensão .part e são retomados. Se apenas
o upload falhar, o arquivo completo será reutilizado na próxima tentativa.

Cada arquivo usa partes de 512 KB com até quatro requisições em voo. Em
álbuns, vários arquivos podem avançar ao mesmo tempo dentro desse mesmo
limite, sem alterar a ordem da publicação. A velocidade final continua
dependendo da conexão e dos limites do Telegram.

Em "Configurações > Armazenamento temporário", escolha a pasta-pai, consulte
o espaço disponível e defina um limite em GB. O programa usa somente a
subpasta temp_transferencias dentro da pasta escolhida. Use 0 para não impor
um teto adicional. Álbuns são verificados como um conjunto antes do primeiro
download. O botão "Limpar temporários" só funciona com os motores parados e
pede confirmação antes de remover downloads parciais ou retidos.

Arquivos acima de 2 GB exigem Telegram Premium na conta conectada para o
reenvio. O limite de upload Premium é 4 GB. Reserve espaço em disco pelo
menos igual ao álbum completo que estiver sendo processado, além de uma
margem de segurança.

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

temp_transferencias
    Subpasta administrada dentro da pasta-pai escolhida. É removida
    automaticamente quando todas as transferências terminam com sucesso.

SEGURANÇA

Não compartilhe:
- .env
- user_session.session
- arquivos de progresso se contiverem informações que você prefira manter privadas.

O usuário final não precisa instalar Python.
