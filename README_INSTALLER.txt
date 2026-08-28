MLD Tools — Instalador Windows
================================

ARQUITETURA

O instalador coloca os executáveis em:

    %LOCALAPPDATA%\MLDTools

Isso evita exigir permissões administrativas e permite que o programa
mantenha seus arquivos locais na mesma pasta.

O INSTALADOR INCLUI

- MLDTools.exe
- MLDToolsSync.exe
- MLDToolsRetro.exe
- MLDToolsMedia.exe
- MLDToolsAlbum.exe
- engine\tdl.exe e seus avisos de licença
- .env.example
- README.txt

O INSTALADOR NÃO INCLUI

- .env real
- user_session.session
- channels.json com rotas pessoais
- sync_progress.json
- historico_progress.json

Esses arquivos são criados pelo próprio usuário/aplicativo.

ATUALIZAÇÕES

O MLDTools_Setup_v3.0.0.exe usa o mesmo identificador do MLDForwarder e é
reconhecido como uma atualização. Feche o MLDForwarder e seus motores antes
de executar o instalador. Ele reutiliza a pasta instalada anteriormente,
mesmo que ela ainda se chame MLDForwarder.

Durante a atualização, o instalador remove somente:
- MLDForwarder.exe
- MLDForwarderSync.exe
- MLDForwarderRetro.exe
- atalhos antigos chamados MLDForwarder

Credenciais, sessão, rotas, progresso, configurações e demais dados locais
permanecem intactos. Os novos atalhos usam o nome MLD Tools.

DESINSTALAÇÃO

O desinstalador remove os arquivos do aplicativo que foram instalados,
mas deixa intencionalmente dados gerados pelo usuário, como:
- credenciais locais
- sessão Telegram
- configuração de rotas
- progresso

Isso reduz o risco de perder a configuração ao reinstalar o MLD Tools.
Arquivos incompletos ou temporários da pasta temp_transferencias são removidos
na desinstalação quando estiverem dentro da pasta padrão do aplicativo. Uma
pasta-pai personalizada fica fora do alcance do desinstalador e pode ser limpa
antes pela interface em "Configurações > Armazenamento temporário".

BUILD

1. Execute build_exe.bat.
2. Instale Inno Setup.
3. Execute build_installer.bat.

Ou execute build_release.bat para fazer as duas etapas.
