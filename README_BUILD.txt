MLD Tools — Release Kit 3.0.0
================================

OBJETIVO

Gerar uma versão portátil do MLD Tools que não exige Python
na máquina do usuário final.

ARQUITETURA DO RELEASE

MLDTools.exe
    GUI sem janela de console.

MLDToolsSync.exe
    Helper do modo normal.

MLDToolsRetro.exe
    Helper do modo retroativo.

MLDToolsMedia.exe
    Central de downloads, exportações, uploads, fila e histórico.

MLDToolsAlbum.exe
    Helper do upload agrupado em álbuns.

engine\tdl.exe
    Motor de downloads, exportações e uploads comuns.

Os helpers continuam separados para preservar a arquitetura
que já foi validada no projeto.

COMO COMPILAR

REQUISITO DO COMPUTADOR DE BUILD:
- Windows
- Python 3.12

PASSOS:

1. Extraia este kit em uma pasta.
2. Se engine\tdl.exe não estiver presente, execute:
      download_tdl.bat
   O script baixa a versão oficial e valida o checksum antes de instalar.
3. Se você está atualizando o seu projeto atual, pode copiar para
   cá seus JSONs/.env/session antes do teste.
4. Execute:
      build_exe.bat
5. Aguarde a compilação.
6. O resultado ficará em:
      release\MLDTools_Portable
7. Também será criado:
      release\MLDTools_Portable.zip

TESTE COM SUA CONFIGURAÇÃO ATUAL

Depois do build:

1. Abra a pasta:
      release\MLDTools_Portable
2. Copie manualmente para ela somente os arquivos locais necessários
   ao seu teste, como .env, configuração e sessão.
3. Abra:
      release\MLDTools_Portable\MLDTools.exe

ATENÇÃO:
Depois que dados locais forem copiados para MLDTools_Portable,
essa pasta deixa de ser um pacote público limpo. NÃO a compartilhe.
Execute build_exe.bat novamente antes de gerar uma distribuição pública.

PACOTE PARA DISTRIBUIÇÃO

MLDTools_Portable é criado limpo:
- sem .env real
- sem sessão
- sem progresso
- channels.json vazio

Assim ele pode ser entregue a outro usuário.

RECURSOS VISUAIS OBRIGATÓRIOS

Mantenha estes itens na pasta do projeto:
    Icon.ico
    assets\app_icon_64.png

O build aplica o ícone aos executáveis e inclui os dois recursos dentro das
interfaces one-file. Se algum deles estiver ausente, o build é interrompido
antes da compilação.

O visual moderno usa CustomTkinter. O build instala automaticamente a versão
fixada em requirements.txt e inclui seus temas e fontes internas nos dois
executáveis de interface; não é necessário copiar essa biblioteca à mão.

O QUE FOI ADAPTADO PARA O EXE

- Caminhos persistentes usam a pasta do executável.
- A GUI detecta quando está congelada pelo PyInstaller.
- No modo congelado, a GUI chama MLDToolsSync.exe e
  MLDToolsRetro.exe e abre MLDToolsMedia.exe quando necessário.
- A Central de mídia chama MLDToolsAlbum.exe para álbuns e engine\tdl.exe
  para as demais operações.
- No modo Python, a mesma GUI continua chamando os scripts .py.
- Os helpers têm saída line-buffered para o log continuar em tempo real.
- Os helpers são iniciados no Windows sem abrir janelas de console.

A versão Python continua utilizável normalmente.


CREDENCIAIS DA API

Na aba "Telegram", o link "Obter API ID e API Hash em my.telegram.org"
abre o portal oficial no navegador padrão. O endereço usado é:

    https://my.telegram.org/


ROTAS COM TÓPICOS

A versão 3.0.0 aceita canais, grupos e tópicos tanto na origem quanto no destino:
- canal ou grupo inteiro
- tópico específico dentro de um grupo com fórum

Na tela "Rotas", informe o grupo no campo de origem e clique em
"Buscar tópicos". Selecione uma opção da lista para preencher o ID.
O preenchimento manual continua disponível. Deixe esse campo vazio
para sincronizar a origem inteira.

Para publicar dentro de um tópico, repita o processo no painel DESTINO.
O campo target_topic_id fica vazio nas rotas que publicam diretamente
em canais ou no grupo principal.

Vários tópicos do mesmo grupo podem ser cadastrados ao mesmo tempo.
Cada rota possui progresso normal e retroativo independentes.


DOWNLOAD E REENVIO LOCAL

Cada rota pode salvar download_reupload=true em channels.json. Quando essa
opção está ativa, os dois helpers usam media_transfer.py para baixar a mídia,
reenviar o arquivo e limpar o temporário após a confirmação.

O fluxo usa partes de 512 KB e mantém até quatro requisições em voo. Em
álbuns, o limite é compartilhado entre os arquivos e a ordem final é
preservada. O build inclui explicitamente cryptg nos helpers normal e
retroativo para acelerar a criptografia do Telethon.

O módulo é importado automaticamente pelo PyInstaller. Por padrão, a pasta
temp_transferencias é criada em tempo de execução ao lado dos executáveis.
O usuário também pode escolher outra pasta-pai e definir um limite de uso em
GB. O programa administra somente a subpasta temp_transferencias, valida o
tamanho completo de álbuns antes do primeiro download e não inclui temporários
no pacote público.


PROTEÇÃO DO PACOTE PÚBLICO

O build_exe.bat NÃO copia channels.json, .env, sessão ou progresso
da sua pasta de trabalho para MLDTools_Portable.

O release público usa:
- channels.default.json
- normal_config.default.json
- retro_config.default.json
- app_config.default.json

Portanto, você pode manter sua configuração local na pasta do kit
para testar sem contaminar o ZIP público com suas rotas.


INSTALLER WINDOWS
=================

Depois de validar os executáveis, este kit também pode gerar:

    MLDTools_Setup_v3.0.0.exe

O instalador:
- instala por usuário em %LOCALAPPDATA%\MLDTools
- é reconhecido como atualização do MLDForwarder pelo mesmo AppId
- reutiliza o diretório anterior e remove somente executáveis/atalhos antigos
- não exige privilégios de administrador
- cria atalho no Menu Iniciar
- pode criar atalho opcional na Área de Trabalho
- não instala .env real, sessão Telegram ou progresso
- não sobrescreve dados pessoais do usuário
- mantém arquivos gerados pelo usuário quando o programa é desinstalado

Para gerar o instalador, instale o Inno Setup e execute:

    build_installer.bat

Ou use:

    build_release.bat

para gerar executáveis + instalador em uma única sequência.
