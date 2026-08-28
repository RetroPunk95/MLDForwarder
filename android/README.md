# MLDForwarder Android — prova técnica 0.1.0-alpha

Prova técnica independente da versão Windows, direcionada ao Android 12. O
objetivo desta etapa é validar Telethon dentro de um serviço Android antes da
construção da interface e do gerenciador completo de rotas.

## Incluído nesta etapa

- autenticação por telefone, código e senha 2FA;
- sessão persistente no armazenamento privado do aplicativo;
- listagem de canais, grupos e tópicos;
- uma rota por execução, com canal ou tópico na origem e no destino;
- sincronização normal a partir das mensagens novas;
- sincronização retroativa com limite e ID inicial;
- textos formatados, previews, mídias e álbuns;
- progresso separado para normal e retroativa;
- pausa cooperativa e retomada;
- serviço em primeiro plano com notificação permanente;
- suporte a `arm64-v8a` e `armeabi-v7a`, Android 7 ou superior.

## Limites conhecidos da prova

- a interface ainda usa IDs digitados; a seleção visual de origem e destino é
  parte da próxima etapa;
- executa uma rota por vez;
- o modo de baixar e reenviar mídia protegida ainda não foi portado;
- as credenciais são mantidas no armazenamento privado comum do aplicativo;
- o Android pode limitar serviços longos de sincronização em versões recentes;
- o ícone e o refinamento visual final ainda não foram aplicados.

## Abrir e compilar

1. Instale o Android Studio com Android SDK 35 e JDK 17.
2. Abra esta pasta como projeto.
3. Se o projeto solicitar o Gradle Wrapper, execute `gradle wrapper` usando
   Gradle 8.11.1 ou deixe o Android Studio criar o wrapper.
4. Aguarde a sincronização. A primeira compilação baixa o runtime Python,
   Telethon e dependências.
5. Conecte um aparelho Android 12 com depuração USB e execute a variante
   `debug`.

O projeto usa Chaquopy 17.0, Python 3.11, Telethon 1.40.0, Android Gradle Plugin
8.9.2, `minSdk 24` e `targetSdk 35`.

## Compilação automática no GitHub

O workflow `.github/workflows/android-build.yml` compila um APK de depuração
quando o projeto é enviado para a branch `android-alpha`. Também pode ser
iniciado manualmente em **Actions → Android alpha build → Run workflow**. O APK
fica disponível como artefato `MLDForwarder-Android-alpha-debug` por 14 dias.

## Roteiro de teste no aparelho

1. Informe API ID, API Hash e telefone.
2. Envie o código e conclua o login.
3. Use **Listar canais e grupos no log** para obter os IDs.
4. Se a origem for um fórum, informe seu ID e liste os tópicos.
5. Configure uma rota pequena de teste.
6. Inicie o modo normal. No primeiro uso ele registra a mensagem mais recente e
   passa a observar somente mensagens novas.
7. Envie uma mensagem na origem e confirme o recebimento no destino.
8. Pare o serviço e teste a retroativa com limite baixo, preferencialmente 5.

Não execute a mesma rota simultaneamente no Windows e no Android durante os
testes, pois cada instalação mantém seu próprio progresso e ambas podem enviar
a mesma mensagem.
