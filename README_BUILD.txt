MLDForwarder — Release Kit v1.9.1
================================

OBJETIVO

Gerar uma versão portátil do MLDForwarder que não exige Python
na máquina do usuário final.

ARQUITETURA DO RELEASE

MLDForwarder.exe
    GUI sem janela de console.

MLDForwarderSync.exe
    Helper do modo normal.

MLDForwarderRetro.exe
    Helper do modo retroativo.

Os helpers continuam separados para preservar a arquitetura
que já foi validada no projeto.

COMO COMPILAR

REQUISITO DO COMPUTADOR DE BUILD:
- Windows
- Python 3.12

PASSOS:

1. Extraia este kit em uma pasta.
2. Se você está atualizando o seu projeto atual, pode copiar para
   cá seus JSONs/.env/session antes do teste.
3. Execute:
      build_exe.bat
4. Aguarde a compilação.
5. O resultado ficará em:
      release\MLDForwarder_Portable
6. Também será criado:
      release\MLDForwarder_Portable.zip

TESTE COM SUA CONFIGURAÇÃO ATUAL

Depois do build:

1. Abra a pasta:
      release\MLDForwarder_Portable
2. Copie manualmente para ela somente os arquivos locais necessários
   ao seu teste, como .env, configuração e sessão.
3. Abra:
      release\MLDForwarder_Portable\MLDForwarder.exe

ATENÇÃO:
Depois que dados locais forem copiados para MLDForwarder_Portable,
essa pasta deixa de ser um pacote público limpo. NÃO a compartilhe.
Execute build_exe.bat novamente antes de gerar uma distribuição pública.

PACOTE PARA DISTRIBUIÇÃO

MLDForwarder_Portable é criado limpo:
- sem .env real
- sem sessão
- sem progresso
- channels.json vazio

Assim ele pode ser entregue a outro usuário.

ÍCONE OPCIONAL

Se você colocar um arquivo:
    icon.ico

na mesma pasta do build_exe.bat antes de compilar, ele será
aplicado ao MLDForwarder.exe.

O QUE FOI ADAPTADO PARA O EXE

- Caminhos persistentes usam a pasta do executável.
- A GUI detecta quando está congelada pelo PyInstaller.
- No modo congelado, a GUI chama MLDForwarderSync.exe e
  MLDForwarderRetro.exe.
- No modo Python, a mesma GUI continua chamando os scripts .py.
- Os helpers têm saída line-buffered para o log continuar em tempo real.
- Os helpers são iniciados no Windows sem abrir janelas de console.

A versão Python continua utilizável normalmente.


CREDENCIAIS DA API

Na aba "Telegram", o link "Obter API ID e API Hash em my.telegram.org"
abre o portal oficial no navegador padrão. O endereço usado é:

    https://my.telegram.org/


ROTAS COM TÓPICOS

A versão 2.8.1 aceita canais, grupos e tópicos tanto na origem quanto no destino:
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


PROTEÇÃO DO PACOTE PÚBLICO

O build_exe.bat NÃO copia channels.json, .env, sessão ou progresso
da sua pasta de trabalho para MLDForwarder_Portable.

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

    MLDForwarder_Setup_v2.8.1.exe

O instalador:
- instala por usuário em %LOCALAPPDATA%\MLDForwarder
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
