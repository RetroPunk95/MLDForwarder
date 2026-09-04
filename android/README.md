# MLDForwarder Android 1.1.6

Versão Android do núcleo do MLDForwarder, direcionada à sincronização normal e
retroativa de canais, grupos, conversas e tópicos do Telegram. Compatível com Android 7 ou
superior e validada inicialmente no Android 12.

## Funcionalidades

- autenticação por telefone, código e senha 2FA;
- sessão Telethon persistente no armazenamento privado do aplicativo;
- API ID, API Hash e telefone protegidos com AES-GCM pelo Android Keystore;
- seletores personalizados com busca para canais, grupos, conversas privadas, Mensagens salvas e tópicos;\n- nomes legíveis de origem, destino e tópicos preservados nas rotas;\n- verificação de sessão diretamente pela tela inicial;\n- acesso às rotas salvas pelo card da tela inicial e exclusão segura por item;
- múltiplas rotas salvas e executadas na mesma sincronização;
- origem e destino em canal, grupo inteiro ou tópico;
- sincronização normal com progresso independente por rota;
- sincronização retroativa com limite e ID inicial por rota;
- textos formatados, previews, mídias e álbuns;
- pausa cooperativa, retomada e tratamento de FloodWait;
- recuperação de referências de mídia e fallback seletivo de emojis personalizados;
- pendências persistentes por conta, modo e rota, com nova tentativa na próxima execução;
- confirmação por etapa para retomar legendas longas sem repetir a mídia já confirmada;
- serviço em primeiro plano com notificação permanente;
- suporte a `arm64-v8a` e `armeabi-v7a`.

## Fluxo de uso

1. Informe API ID, API Hash e telefone.
2. Envie o código e conclua o login. Se necessário, informe a senha 2FA.
3. Use **Selecionar origem na lista** e escolha um canal, grupo ou conversa.
4. Se necessário, use **Selecionar tópico de origem**.
5. Repita o processo para o destino.
6. Defina nome, limite retroativo e ID inicial; depois toque em **Salvar**.
7. Use **Nova** para cadastrar outras rotas.
8. Inicie a sincronização normal ou retroativa. Todas as rotas salvas serão
   processadas pelo mesmo serviço.

Os IDs continuam visíveis e editáveis para permitir configurações avançadas e
uso de `@username` quando necessário.

### Limite e ID inicial: comportamento real

- **Limite de mensagens:** quantidade buscada por execução/rota, mínimo 1.
  Tanto na v1.1.1 quanto na v1.1.2, **digitar 0 resulta em 1**, não em busca ilimitada.
  O lote pode exceder ligeiramente o limite para completar um álbum.
- **ID inicial:** ponto exclusivo de partida. O app busca IDs maiores que
  `max(ID inicial configurado, progresso salvo)`, em ordem crescente.
  `0` retoma o progresso salvo; sem progresso, começa no histórico mais antigo disponível.
- Alterar o limite não muda a velocidade nem corrige uma mídia rejeitada.
  Reduzir o ID inicial também não rebobina um progresso maior já salvo.

### Recuperação e pendências (v1.1.2)

O envio mantém a formatação original na primeira tentativa. Se houver rejeição
de mídia/referência, o motor busca novamente a mensagem para renovar a mídia.
Se `DOCUMENT_INVALID` ou exigência de Premium persistir e houver entidades de
emoji personalizado, tenta uma versão de compatibilidade: remove somente as
entidades `MessageEntityCustomEmoji`. O texto permanece intacto, incluindo o
emoji Unicode correspondente; negrito, itálico, links e citações são preservados.
Os ícones personalizados podem, portanto, aparecer como emojis comuns no destino.
Isso é uma estratégia de recuperação, não prova da causa de todos os erros.

Caso a rejeição de mídia persista, a mensagem/álbum fica **pendente** e a rota
continua. IDs, tipo de mídia e contagem de emojis aparecem na Atividade. Um erro
de álbum identifica todos os IDs envolvidos, não necessariamente o item exato
rejeitado pelo servidor. O álbum não é desmembrado silenciosamente.

Ao iniciar novamente o mesmo modo, as pendências das rotas selecionadas são
tentadas antes do histórico novo. Cada item recebe uma sequência limitada de
recuperação por execução; FloodWait respeita o tempo solicitado pelo Telegram.
Uma mensagem recuperada depois pode aparecer fora da ordem original no destino.
Mensagem removida/inacessível na origem permanece pendente, sem indicação falsa
de sucesso. Pendências de uma rota cujo destino foi alterado não são redirecionadas.

Os arquivos privados `retro_delivery_<conta>.json` e
`normal_delivery_<conta>.json` guardam as pendências e etapas confirmadas.
Os arquivos de progresso antigos são preservados; a partir desta versão, o
cursor indica o último item **examinado**, não que todas as mensagens anteriores
foram entregues. A pendência é salva antes de avançar esse cursor.

Timeout, erro de rede ou encerramento durante um envio podem deixar o resultado
incerto. Nesse caso, a pendência exige **conferência manual no destino** e não
é reenviada automaticamente. O mesmo vale se o texto de origem mudar após um
envio parcial. Esta versão informa a situação na Atividade; não inclui uma tela
para resolver essas pendências manualmente. Não apague os dados do app nem altere
o journal sem verificar o que já foi entregue.

Erros de permissão/autenticação pausam a rota afetada nesta execução; não são
tratados como uma sucessão de mídias inválidas. Falha ao salvar progresso/journal
interrompe o motor para evitar perdas. Não há promessa de entrega exatamente
uma vez em caso de perda de dados ou interrupções abruptas do aparelho.

O botão de parar aguarda a operação em andamento terminar; somente depois o
serviço encerra. Aguarde a indicação de encerramento antes de iniciar de novo.

## Segurança e migração do alpha

API ID, API Hash e telefone são cifrados com uma chave AES-GCM protegida pelo
Android Keystore. A senha 2FA e o código de login não são armazenados.

O alpha usava uma assinatura temporária do GitHub Actions. Por isso, ele deve
ser desinstalado antes da instalação estável, o que exige um novo login. A
partir da v1.0.0, todas as versões oficiais usam a mesma chave definitiva e
podem ser atualizadas normalmente sem apagar os dados.

## Compilar

1. Instale Android SDK 35, JDK 17, Python 3.11 e Gradle 8.11.1.
2. Abra esta pasta no Android Studio ou execute `gradle :app:assembleDebug`.
3. A primeira compilação baixa o runtime Python, Telethon e dependências.

O projeto usa Chaquopy 17.0, Python 3.11, Telethon 1.40.0 e Android Gradle
Plugin 8.9.2. O workflow da branch `android-stable` gera o APK release sem
assinatura; a assinatura é aplicada fora do repositório com a chave privada do
projeto.

### Testes automatizados

```sh
python -m pip install telethon==1.40.0
python -m unittest discover -s tests -v
```

Os testes usam tipos reais do Telethon e clientes simulados: não acessam contas
nem enviam mensagens. O workflow executa esses testes antes de compilar.
Veja [VALIDACAO.md](VALIDACAO.md) para resultados, limitações e teste no aparelho.

### Atualizar com segurança

O código usa `versionName 1.1.2` e `versionCode 7`, mantendo o applicationId
de release. O APK deve ser assinado com a **mesma chave** da versão instalada.
Não desinstale a versão atual para contornar erro de assinatura: isso apaga os
dados privados. O APK debug tem outro applicationId e não testa a migração dos
dados da versão oficial. Nenhuma chave de assinatura é incluída neste projeto.

Não volte à v1.1.1 enquanto existirem pendências: ela não conhece o journal e
usaria o cursor avançado sem tentar novamente os itens que ficaram pendentes.
Pendências criadas antes desta atualização ou puladas manualmente não podem ser
reconstruídas apenas pelos prints. Para testar um post antigo, use uma rota e
um destino de teste novos, sem alterar o progresso da rota de produção.

## Limites atuais

- o modo de baixar e reenviar mídias protegidas não faz parte do app Android;
- o serviço pode ser interrompido por otimizações agressivas de bateria do
  fabricante;
- a otimização de bateria deve ser desativada para o MLDForwarder em aparelhos
  que encerram serviços em segundo plano de forma agressiva.

Não execute a mesma rota simultaneamente no Windows e no Android: cada
instalação mantém seu próprio progresso e as mensagens podem ser duplicadas.
