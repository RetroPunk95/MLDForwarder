MLDForwarder — Instalador Windows
================================

ARQUITETURA

O instalador coloca os três executáveis em:

    %LOCALAPPDATA%\MLDForwarder

Isso evita exigir permissões administrativas e permite que o programa
mantenha seus arquivos locais na mesma pasta.

O INSTALADOR INCLUI

- MLDForwarder.exe
- MLDForwarderSync.exe
- MLDForwarderRetro.exe
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

Quando uma versão futura do instalador for executada sobre uma instalação
existente, os executáveis podem ser atualizados sem substituir os dados
locais do usuário, pois esses dados não fazem parte do pacote de instalação.

DESINSTALAÇÃO

O desinstalador remove os arquivos do aplicativo que foram instalados,
mas deixa intencionalmente dados gerados pelo usuário, como:
- credenciais locais
- sessão Telegram
- configuração de rotas
- progresso

Isso reduz o risco de perder a configuração ao reinstalar o MLDForwarder.

BUILD

1. Execute build_exe.bat.
2. Instale Inno Setup.
3. Execute build_installer.bat.

Ou execute build_release.bat para fazer as duas etapas.
