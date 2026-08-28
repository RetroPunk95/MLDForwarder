# MLDForwarder Android 1.0.0-rc1

Versão Android do núcleo do MLDForwarder, direcionada à sincronização normal e
retroativa de canais, grupos e tópicos do Telegram. Compatível com Android 7 ou
superior e validada inicialmente no Android 12.

## Funcionalidades

- autenticação por telefone, código e senha 2FA;
- sessão Telethon persistente no armazenamento privado do aplicativo;
- API ID, API Hash e telefone protegidos com AES-GCM pelo Android Keystore;
- seleção visual de canais, grupos e tópicos;
- múltiplas rotas salvas e executadas na mesma sincronização;
- origem e destino em canal, grupo inteiro ou tópico;
- sincronização normal com progresso independente por rota;
- sincronização retroativa com limite e ID inicial por rota;
- textos formatados, previews, mídias e álbuns;
- pausa cooperativa, retomada e tratamento de FloodWait;
- serviço em primeiro plano com notificação permanente;
- suporte a `arm64-v8a` e `armeabi-v7a`.

## Fluxo de uso

1. Informe API ID, API Hash e telefone.
2. Envie o código e conclua o login. Se necessário, informe a senha 2FA.
3. Use **Selecionar origem na lista** e escolha um canal ou grupo.
4. Se necessário, use **Selecionar tópico de origem**.
5. Repita o processo para o destino.
6. Defina nome, limite retroativo e ID inicial; depois toque em **Salvar**.
7. Use **Nova** para cadastrar outras rotas.
8. Inicie a sincronização normal ou retroativa. Todas as rotas salvas serão
   processadas pelo mesmo serviço.

Os IDs continuam visíveis e editáveis para permitir configurações avançadas e
uso de `@username` quando necessário.

## Segurança e atualização do alpha

As credenciais que estavam no armazenamento comum da versão alpha são migradas
automaticamente para dados cifrados na primeira abertura da nova versão. A
senha 2FA e o código de login não são armazenados.

O build de teste usa o identificador `com.retropunk.mldforwarder.rc` e o nome
**MLDForwarder RC**. Ele pode ser instalado ao lado do alpha aprovado sem
substituir o aplicativo, a sessão ou as rotas atuais. Por ser uma instalação
separada, o RC exige um novo login no Telegram.

## Compilar

1. Instale Android SDK 35, JDK 17, Python 3.11 e Gradle 8.11.1.
2. Abra esta pasta no Android Studio ou execute `gradle :app:assembleDebug`.
3. A primeira compilação baixa o runtime Python, Telethon e dependências.

O projeto usa Chaquopy 17.0, Python 3.11, Telethon 1.40.0 e Android Gradle
Plugin 8.9.2. O workflow compila as branches `android-alpha` e `android-v1` e
publica o artefato `MLDForwarder-Android-v1-debug`.

## Limites atuais

- o modo de baixar e reenviar mídias protegidas não faz parte do app Android;
- o serviço pode ser interrompido por otimizações agressivas de bateria do
  fabricante;
- o APK RC ainda usa assinatura de teste; a chave de distribuição definitiva
  deve ser criada e guardada pelo responsável pelo projeto.

Não execute a mesma rota simultaneamente no Windows e no Android: cada
instalação mantém seu próprio progresso e as mensagens podem ser duplicadas.
