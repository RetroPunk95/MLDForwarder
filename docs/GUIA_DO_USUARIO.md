# MLD Tools 3.0.0 — Guia completo do usuário

## Sincronize canais, grupos e tópicos do Telegram sem assinatura de encaminhamento

O **MLD Tools** é uma ferramenta para Windows que copia mensagens entre canais e grupos do Telegram usando a sua própria conta. As mensagens chegam ao destino como novas publicações, sem a indicação “Encaminhada de”.

O programa suporta textos, fotos, vídeos, documentos, legendas e álbuns. A versão 3.0.0 preserva as formatações compatíveis do Telegram, permite baixar e reenviar arquivos quando a origem bloqueia o encaminhamento, oferece controle sobre o armazenamento temporário e permite escolher quais rotas iniciar.

Também é possível criar várias rotas, usar tópicos tanto na origem quanto no destino e importar mensagens antigas. Em álbuns, a formatação de cada legenda é tratada separadamente.

Com ele, você pode criar rotas como canal → canal, canal → grupo, canal → tópico, grupo → grupo, grupo → tópico e tópico → tópico.

Este guia foi preparado para o **MLD Tools 3.0.0**.

> Use o programa apenas em canais e grupos aos quais você tem acesso e respeite as regras e os Termos de Serviço do Telegram. O MLD Tools não é uma ferramenta de spam.

---

## 1. Antes de começar

Você precisará de:

- Windows 10 ou Windows 11;
- uma conta ativa do Telegram;
- acesso de leitura ao canal ou grupo de origem;
- permissão para publicar no canal, grupo ou tópico de destino;
- um **API ID** e um **API Hash** próprios do Telegram.

Não é necessário instalar Python.

> A conta conectada ao MLD Tools precisa conseguir visualizar a origem e publicar no destino. Se a conta não tiver essas permissões, a sincronização não poderá ser concluída.

---

## 2. Instalando ou usando a versão portátil

### Versão com instalador

1. Baixe o arquivo `MLDTools_Setup_v3.0.0.exe`.
2. Abra o instalador e siga as instruções exibidas.
3. Depois da instalação, abra o MLD Tools pelo atalho criado no Windows.

### Versão portátil

1. Baixe o arquivo `MLDTools_Portable.zip`.
2. Clique com o botão direito sobre o ZIP e selecione **Extrair tudo**.
3. Abra a pasta extraída.
4. Execute `MLDTools.exe`.

Não execute o programa diretamente de dentro do ZIP. Os componentes abaixo devem permanecer juntos na mesma pasta:

- `MLDTools.exe` — interface gráfica;
- `MLDToolsSync.exe` — sincronização contínua;
- `MLDToolsRetro.exe` — importação retroativa.
- `MLDToolsMedia.exe` — downloads, exportações, uploads, fila e histórico;
- `MLDToolsAlbum.exe` — motor de upload agrupado em álbuns;
- `engine\tdl.exe` — motor das demais ferramentas de mídia.

Você não precisa abrir os motores manualmente. O `MLDTools.exe` inicia cada componente quando necessário.

> A versão 3.0.0 ainda não possui assinatura digital. Por isso, o Windows pode exibir um aviso do SmartScreen. Se o arquivo veio da fonte oficial do projeto, clique em **Mais informações** e depois em **Executar assim mesmo**.

![Arquivos da versão portátil dentro da pasta extraída](images/01-pasta-portatil.png)

---

## 3. Criando suas credenciais do Telegram

O Telegram exige que cada usuário crie suas próprias credenciais de API. Elas identificam a aplicação usada para conectar a conta.

1. Abra o MLD Tools.
2. No menu lateral, entre em **Telegram**.
3. Clique em **Obter API ID e API Hash em my.telegram.org ↗**.
4. Informe seu número com código do país. No Brasil, use o formato `+55 DDD NÚMERO`.
5. O Telegram enviará um código de confirmação pelo próprio aplicativo, e não por SMS.
6. Depois de entrar no portal, abra **API development tools**.
7. Preencha o formulário de criação da aplicação.
8. Copie os valores de **api_id** e **api_hash** apresentados.

Cada número do Telegram pode ter somente um API ID associado no portal. Guarde essas credenciais em segurança.

Link direto: https://my.telegram.org/

![Atalho para obter o API ID e o API Hash](images/02-api-telegram.png)

---

## 4. Salvando as credenciais no MLD Tools

Na página **Telegram**, preencha:

### API ID

O número fornecido pelo portal do Telegram.

### API Hash

O código secreto exibido junto do API ID.

### Nome da sessão

Nome do arquivo usado para manter sua conta conectada. O padrão é `user_session` e normalmente não precisa ser alterado.

Clique em **SALVAR CREDENCIAIS**.

As informações ficam armazenadas localmente na pasta do programa. Elas não são enviadas para um servidor do MLD Tools.

> Nunca publique seu API Hash, o arquivo `.env` ou o arquivo `user_session.session`.

![Campos API ID, API Hash e Nome da sessão](images/03-credenciais.png)

---

## 5. Conectando sua conta

Ainda na página **Telegram**:

1. Digite seu número no campo **Telefone**, incluindo `+55` e o DDD.
2. Clique em **Enviar código**.
3. Abra o Telegram e localize o código recebido.
4. Digite-o no campo **Código recebido**.
5. Clique em **Confirmar código**.

Se a conta usa verificação em duas etapas, o MLD Tools mostrará **Senha 2FA necessária**. Digite a senha no campo **Senha 2FA** e clique em **Confirmar senha**.

Quando a autenticação terminar, o status mudará para conectado. O botão **Verificar sessão** pode ser usado a qualquer momento para confirmar se a sessão ainda é válida.

O botão **Sair da conta** encerra a sessão local. Na próxima utilização, será necessário autenticar novamente.

![Área de autenticação e status da sessão do Telegram](images/04-sessao-telegram.png)

---

## 6. Conhecendo a interface

O menu lateral possui sete áreas:

### Dashboard

Mostra o estado do Telegram, a quantidade de rotas, os processos normal e retroativo e o número de pendências. É também onde você inicia ou interrompe a sincronização contínua.

### Rotas

Gerencia as ligações entre origens e destinos. Uma rota informa ao programa de onde copiar e para onde enviar.

### Retroativo

Importa mensagens antigas de uma rota específica ou de todas as rotas.

### Central de mídia

Abre a suíte de downloads, exportações, upload para o Telegram, fila e histórico em uma janela independente.

### Telegram

Guarda as credenciais e controla a autenticação da conta.

### Configurações

Define o tamanho dos lotes e o intervalo da sincronização normal.

### Log

Exibe o que o programa está fazendo, incluindo mensagens processadas, pausas, avisos e erros.

### Usando a Central de mídia

Abra **Central de mídia** e escolha uma ação:

- **Novo download:** selecione links de mensagens, arquivos JSON ou um canal, grupo ou tópico. A tarefa entra na fila e aguarda o seu comando para iniciar;
- **Central de exportação:** exporta mensagens, membros ou inscritos para JSON;
- **Upload para Telegram:** adiciona arquivos ou pastas, escolhe o destino e cria uma tarefa sem iniciar o envio;
- **Fila e Histórico:** ordena downloads e uploads juntos e permite iniciar, pausar, retomar, cancelar ou repetir tarefas.

A Central de mídia usa o `tdl`, que possui uma autenticação própria na página **Telegram** dessa janela. Recomenda-se conectar a mesma conta usada na interface principal.

Em **Novo download**, marque **Manter nome original** para salvar o arquivo sem os IDs da conversa e da mensagem no início. O programa preserva o nome fornecido pelo Telegram e substitui somente caracteres incompatíveis com o Windows. Se dois arquivos diferentes tiverem exatamente o mesmo nome no mesmo destino, desmarque essa opção para que os IDs evitem colisões.

Para enviar imagens, vídeos ou documentos como álbum, abra **Upload para Telegram** e marque **Enviar arquivos agrupados em álbuns**. Em **Agrupar por**, escolha:

- **Seleção atual:** todos os arquivos selecionados formam uma sequência de álbuns;
- **Cada pasta:** cada pasta e subpasta forma seu próprio conjunto.

Os arquivos são ordenados naturalmente (`2` antes de `10`) e divididos automaticamente quando a seleção ultrapassa o limite de um álbum. A legenda é aplicada ao primeiro arquivo de cada conjunto. Essa função usa a sessão autenticada na página **Telegram** da interface principal.

Depois de configurar o upload, clique em **Adicionar à fila**. Nada será enviado imediatamente. Na página **Fila**, clique em **Iniciar fila** para processar downloads e uploads na ordem em que foram criados.

Durante o envio, **Cancelar** interrompe o upload ativo. Arquivos locais não são alterados; álbuns ou arquivos concluídos antes do cancelamento permanecem no Telegram. Como o Telegram não oferece retomada real de upload, uma tarefa pausada reinicia do começo e pode duplicar itens já publicados; o programa avisa antes de pausar.

### Perfis de desempenho e rede

Em **Configurações > Desempenho e rede**, três valores controlam o paralelismo das novas tarefas executadas pelo `tdl`:

- **Conexões por arquivo** — quantidade máxima de partes transferidas em paralelo dentro de um único arquivo. Ajuda principalmente com arquivos grandes;
- **Transferências simultâneas** — quantidade máxima de arquivos diferentes processados ao mesmo tempo;
- **Pool de conexões** — tamanho do conjunto de conexões compartilhadas com os datacenters do Telegram.

Use os perfis como ponto de partida:

| Perfil | Valores | Indicação |
|---|---:|---|
| **Equilibrado** | `8 / 4 / 8` | Maior estabilidade, menor uso de disco e rede. Recomendado para HDD, Wi-Fi instável ou quando ocorrerem desconexões. |
| **Rápido** | `16 / 6 / 12` | Melhor escolha geral para conta Premium, SSD e conexão estável. Oferece bom ganho sem elevar demais a carga. |
| **Agressivo** | `24 / 8 / 16` | Para testar em conexão rápida e SSD quando o perfil Rápido ainda não utiliza toda a banda disponível. Pode antecipar limites temporários do Telegram. |

A interface aceita manualmente até `32 / 16 / 32`, mas essa combinação não é um perfil recomendado. Valores maiores não garantem mais velocidade: podem aumentar uso de memória, CPU e disco, causar oscilações, desconexões ou esperas do Telegram. Se o desempenho piorar, volte para **Rápido**; se aparecerem erros recorrentes, use **Equilibrado**.

Depois de selecionar um perfil, clique em **Salvar configurações** antes de adicionar ou iniciar as próximas tarefas. A mudança não reconfigura uma transferência que já esteja em andamento.

> Esses perfis afetam principalmente downloads e uploads comuns da Central de mídia. O upload de documentos em álbuns usa **Transferências simultâneas** como referência, limitado a quatro arquivos. Já o modo **Baixar e reenviar arquivos** das rotas possui uma aceleração própria do Telethon e não utiliza esses três valores.

![Menu lateral do MLD Tools](images/05-menu-lateral.png)

---

## 7. Criando uma rota

1. Entre em **Rotas**.
2. Clique em **+ Adicionar**.
3. Aguarde a lista de canais e grupos ser carregada.
4. Escolha a origem e o destino e preencha os demais campos da nova rota.

Os campos **Canal ou grupo** de origem e destino mostram as conversas acessíveis à conta conectada no formato `nome — tipo (ID)`. Se uma conversa nova ainda não aparecer, clique em **Atualizar lista**. Os campos continuam editáveis, então também é possível informar manualmente um ID ou `@username`.

### Canal ou grupo de origem

É o local de onde as mensagens serão copiadas. Escolha um canal ou grupo da lista. Como alternativa, informe o ID numérico ou o `@username` acessível pela conta conectada.

Exemplo de ID:

`-1001234567890`

### ID do tópico de origem — opcional

Use este campo quando quiser sincronizar somente um tópico de um grupo com fórum ativado.

Deixe vazio para sincronizar o canal ou grupo inteiro.

### Canal ou grupo de destino

É o local que receberá as novas mensagens. Escolha um canal ou grupo da lista ou informe manualmente o ID numérico ou o `@username`. A conta conectada precisa ter permissão para publicar nele.

### ID do tópico de destino — opcional

Use este campo quando as mensagens precisarem ser publicadas dentro de um tópico específico do grupo de destino.

Deixe vazio para enviar ao canal, grupo ou tópico principal.

### Nome da rota

Um nome de identificação exibido na interface, como:

- Filmes → Backup;
- Novidades → Arquivo;
- Tópico Dublagens → Canal Dublagens;
- Canal Filmes → Tópico Lançamentos;
- Tópico Séries → Tópico Séries MLD.

### Baixar e reenviar arquivos — opcional

Ative essa opção quando a origem permitir baixar os arquivos, mas não aceitar o encaminhamento ou a cópia direta da mídia.

Nesse modo, o MLD Tools baixa cada mídia para uma pasta temporária, envia como um arquivo novo e remove o temporário depois que o Telegram confirma o envio. Isso elimina a assinatura de encaminhamento, mas utiliza espaço em disco e consome tanto download quanto upload.

Downloads interrompidos são guardados com extensão `.part` e retomados na próxima execução. Se o download terminou e apenas o upload falhou, o arquivo completo será reutilizado.

Arquivos acima de 2 GB exigem Telegram Premium na conta conectada para serem reenviados. O limite de upload Premium é 4 GB.

Clique em **Salvar** para concluir.

Você pode cadastrar várias rotas e vários tópicos do mesmo grupo. Cada combinação de origem e tópico mantém seu próprio progresso.

![Janela Adicionar rota com origem e destino](images/06-adicionar-rota.png)

---

## 8. Encontrando o ID de um tópico automaticamente

O botão **Buscar tópicos** está disponível nos dois lados da rota. Ele pode localizar tanto o tópico de origem quanto o tópico de destino.

Para selecionar um tópico:

1. Abra a janela de criação ou edição de rota.
2. Informe o grupo no campo **Canal ou grupo** do lado desejado.
3. Clique em **Buscar tópicos**.
4. Aguarde a consulta ao Telegram.
5. Abra a lista **Tópicos encontrados**.
6. Selecione a opção desejada, exibida como `ID — nome do tópico`.

O campo **ID do tópico** correspondente será preenchido automaticamente.

Repita o processo no outro lado quando quiser criar uma rota de tópico para tópico. Se o grupo informado não tiver tópicos ativados, o programa avisará que ele não é um fórum. O preenchimento manual do ID continua disponível.

> Para buscar tópicos, as credenciais precisam estar salvas e a sessão do Telegram deve estar autenticada.

![Seleção automática de tópico na origem ou no destino](images/07-selecao-topico.png)

---

## 9. Sincronização normal

O sincronizador normal monitora as rotas selecionadas no Dashboard e copia continuamente as mensagens novas. Todas ficam selecionadas por padrão.

Para iniciar:

1. Verifique se o Telegram está conectado.
2. Confirme se pelo menos uma rota foi cadastrada.
3. Volte ao **Dashboard**.
4. Marque uma, várias ou todas as rotas em **Rotas desta execução**.
5. Clique em **INICIAR SINCRONIZADOR**.

Os botões **Selecionar todas** e **Limpar seleção** ajudam quando há muitas rotas. A seleção vale apenas para a execução atual: não remove configurações, não mistura os progressos e não altera se uma rota usa transferência direta ou **Baixar e reenviar arquivos**.

Na primeira execução de cada rota, o programa registra o ID mais recente da origem. As mensagens que já existiam antes desse ponto não são copiadas pelo modo normal. A partir daí, novas mensagens são enviadas ao destino.

Esse comportamento evita que todo o histórico seja duplicado acidentalmente. Para copiar mensagens antigas, use o modo **Retroativo**.

Enquanto estiver ativo, o sincronizador verifica novas mensagens de acordo com o intervalo configurado. Use **PARAR** antes de fechar o programa ou alterar arquivos da pasta.

> O MLD Tools precisa continuar aberto e o computador precisa permanecer ligado e conectado à internet. Ele não funciona como um serviço hospedado na nuvem.

![Dashboard com o sincronizador normal ativo](images/08-dashboard.png)

---

## 10. Configurações da sincronização normal

Entre em **Configurações** para ajustar:

### Tamanho do lote

Quantidade máxima de mensagens processadas em cada ciclo.

- Valores maiores ajudam quando há muitas mensagens acumuladas, mas aumentam o uso da API.
- Valores menores reduzem o volume processado em cada ciclo.
- Padrão: **100**.

### Intervalo entre verificações

Tempo de espera, em segundos, antes de procurar novas mensagens novamente.

- Um valor menor sincroniza mais rapidamente e faz mais consultas ao Telegram.
- Um valor maior reduz a frequência das consultas.
- Padrão: **5 segundos**.

### Armazenamento temporário

Essa seção controla os downloads usados somente nas rotas com **Baixar e reenviar arquivos**:

- **Pasta-pai** — escolha uma unidade ou pasta com espaço suficiente. O programa cria e administra apenas a subpasta `temp_transferencias` dentro dela.
- **Limite temporário (GB)** — impede que arquivos completos, parciais e novos downloads ultrapassem o teto escolhido. Use `0` para não definir um teto adicional.
- **Em uso / Livre no disco** — mostra quanto os temporários ocupam e quanto ainda está disponível na unidade.
- **Limpar temporários** — remove downloads parciais e arquivos retidos, após confirmação. O botão exige que os modos normal e retroativo estejam parados.

Antes do primeiro download de um álbum, o MLD Tools soma os tamanhos conhecidos de todos os arquivos. Se o álbum inteiro não couber no disco ou ultrapassar o limite configurado, nenhum item do álbum começa a baixar. Arquivos mantidos depois de falhas anteriores também entram no cálculo do limite.

> Selecionar `D:\TelegramTemp`, por exemplo, faz o programa usar `D:\TelegramTemp\temp_transferencias`. Os demais arquivos existentes em `D:\TelegramTemp` não são administrados nem apagados.

Para a maioria dos usuários, os valores padrão são a melhor escolha. Depois de alterar os campos, clique em **SALVAR CONFIGURAÇÕES**.

![Configurações da sincronização normal](images/09-configuracoes-normal.png)

---

## 11. Importando mensagens antigas

O modo **Retroativo** serve para copiar o histórico que existia antes do início da sincronização normal.

1. Pare o sincronizador normal, caso esteja ativo.
2. Entre em **Retroativo**.
3. Escolha uma rota ou selecione **Todas as rotas**.
4. Revise as opções de importação.
5. Clique em **INICIAR RETROATIVO**.

O progresso é salvo automaticamente. Se o processo for interrompido, ele poderá continuar do ponto registrado na próxima execução.

Os modos normal e retroativo não funcionam simultaneamente. Isso evita conflitos entre os dois processos.

### Limite — 0 significa todo o histórico

Quantidade máxima de mensagens antigas importadas por rota.

- `1000` importa até mil mensagens;
- `5000` importa até cinco mil;
- `0` importa todo o histórico disponível.

Padrão: **1000**.

### Começar pelo ID

Ignora mensagens com ID menor ou igual ao valor informado.

- Use `0` para começar pela mensagem mais antiga disponível.
- Use um ID específico quando quiser iniciar a importação depois de determinado ponto.

Padrão: **0**.

### Tamanho do lote

Número de mensagens preparado em cada etapa. Um lote maior pode acelerar a importação, mas também aumenta o uso da API.

Padrão: **100**.

### Tentativas em caso de erro

Quantidade máxima de tentativas de envio para cada mensagem que apresentar erro. Quando o limite é atingido, a mensagem permanece registrada nas pendências.

Padrão: **3**.

> Ao usar `0` para importar todo o histórico, o tempo total dependerá da quantidade de mensagens, do tamanho das mídias e dos limites aplicados pelo Telegram.

![Configurações da sincronização retroativa](images/10-sincronizacao-retroativa.png)

---

## 12. Acompanhando rotas, progresso e pendências

A tabela da página **Rotas** mostra:

- nome da rota;
- origem;
- tópico de origem;
- destino;
- tópico de destino;
- modo de transferência — direta ou baixar + reupar;
- último ID do modo normal;
- último ID do retroativo;
- número de pendências.

Use **Atualizar** para recarregar os dados exibidos.

### Editar

Altera a origem, o tópico de origem, o destino, o tópico de destino ou o nome da rota. Ao mudar a identificação da rota, o programa remove o progresso associado à configuração anterior para evitar inconsistências.

### Remover

Exclui a rota da configuração. O programa também perguntará se você deseja remover os registros de progresso dela. Nenhuma mensagem já enviada será apagada do Telegram.

### Limpar progresso

Apaga o ponto salvo da rota selecionada.

- No modo normal, a rota será reinicializada no ID mais recente e o histórico existente não será reenviado.
- No retroativo, a rota voltará ao ID inicial configurado.

Use essa opção com atenção.

![Tabela de rotas, tópicos, progresso e pendências](images/11-lista-rotas.png)

---

## 13. Entendendo o Log

A página **Log** mostra as atividades da sessão atual do programa. Consulte-a quando quiser:

- confirmar que uma mensagem foi processada;
- verificar a inicialização de uma rota;
- acompanhar a importação retroativa;
- identificar um erro de permissão ou conexão;
- saber se o Telegram solicitou uma pausa temporária.

O botão **Limpar log** remove apenas o texto exibido na tela. Ele não apaga mensagens, rotas ou arquivos de progresso.

Quando o Telegram aplica um `FloodWait`, o motor aguarda o período solicitado e tenta continuar. Evite reduzir demais o intervalo ou usar lotes exageradamente grandes.

![Log durante uma sincronização retroativa](images/12-log-atividade.png)

---

## 14. Arquivos importantes e segurança

O MLD Tools usa arquivos locais para manter credenciais, rotas e progresso:

- `.env` — API ID e API Hash;
- `user_session.session` — sessão autenticada do Telegram;
- `channels.json` — rotas cadastradas;
- `sync_progress.json` — progresso da sincronização normal;
- `historico_progress.json` — progresso e pendências do retroativo;
- `normal_config.json` — opções do modo normal;
- `retro_config.json` — opções do retroativo;
- `app_config.json` — preferências gerais, inclusive pasta-pai e limite temporário;
- `temp_transferencias` — subpasta administrada com arquivos usados pelo modo de download e reenvio.

Não compartilhe `.env` nem `user_session.session`. Quem tiver acesso válido ao arquivo de sessão poderá tentar usar a conta conectada.

Na versão portátil, esses arquivos ficam junto da pasta do programa por padrão. A pasta temporária pode ficar em outra unidade quando uma pasta-pai personalizada for selecionada. Se você mover a pasta do programa para outro computador ou dispositivo USB, trate os dados locais como informação privada.

A subpasta `temp_transferencias` normalmente desaparece depois de um envio bem-sucedido. Se uma operação for interrompida ou falhar, ela será mantida para permitir retomada. Não a limpe enquanto pretende continuar a transferência.

Para criar um backup da configuração, feche o MLD Tools e copie a pasta inteira para um local seguro.

---

## 15. Solução de problemas

### O Windows bloqueou a abertura

A versão atual não possui assinatura digital. Se o arquivo foi obtido da fonte oficial, abra **Mais informações** e escolha **Executar assim mesmo**.

### O código de autenticação não chegou por SMS

O portal e o login da API normalmente enviam o código pelo próprio Telegram. Verifique a conversa de serviço do Telegram nos aplicativos já conectados.

### O programa pede uma senha 2FA

Sua conta usa verificação em duas etapas. Digite a senha criada nas configurações de segurança do Telegram — não o código recebido na conversa.

### A busca de tópicos não funciona

Confirme se:

- API ID e API Hash foram salvos;
- a sessão está autenticada;
- o grupo informado está acessível pela conta;
- o grupo possui tópicos ativados;
- o ID ou `@username` do grupo está correto;
- você clicou em **Buscar tópicos** no lado correto da rota.

### A mensagem não chegou ao destino

Verifique o **Log** e confirme se a conta tem permissão para publicar no destino. Confira também os IDs da origem, do tópico de origem, do destino e do tópico de destino.

Se a origem permite baixar o arquivo no Telegram, mas rejeita a cópia direta, edite a rota e marque **Baixar e reenviar arquivos**.

### O arquivo foi baixado, mas não pôde ser reenviado

Confira o tamanho mostrado no Telegram. Arquivos acima de 2 GB precisam ser enviados por uma conta Telegram Premium. Verifique também o espaço livre em disco e a permissão da conta para publicar no destino.

Quando o upload falha, o arquivo completo permanece em `temp_transferencias` e será reutilizado na próxima tentativa.

### Não há espaço suficiente para o download

Entre em **Configurações > Armazenamento temporário** e confira **Em uso**, **Livre no disco** e o limite em GB. Você pode escolher outra unidade, aumentar o limite ou usar **Limpar temporários** com os sincronizadores parados. Se o espaço for insuficiente, o download não é concluído; no caso de um álbum com tamanhos conhecidos, nenhum arquivo do conjunto começa a baixar.

### Mensagens antigas não foram copiadas pelo modo normal

Isso é esperado. Rotas novas começam no ID mais recente para evitar duplicação. Use **Retroativo** para importar o histórico.

### O retroativo parou antes de terminar

Inicie o modo novamente. O programa usa o progresso salvo para continuar. Mensagens que atingirem o limite de tentativas permanecerão nas pendências.

### O sincronizador normal não inicia

Confira se:

- as credenciais foram salvas;
- a conta está autenticada;
- existe pelo menos uma rota;
- o retroativo está parado;
- os três executáveis da versão portátil continuam na mesma pasta.

### Posso fechar a interface depois de iniciar?

Não. O MLD Tools precisa permanecer aberto. Se houver um processo em andamento, a interface perguntará se deseja solicitar a parada antes de fechar.

---

## 16. Perguntas frequentes

### As mensagens aparecem como encaminhadas?

Não. O conteúdo é reenviado como uma nova mensagem, sem assinatura de encaminhamento.

### A formatação original dos textos é preservada?

Sim. O MLD Tools 3.0.0 preserva as formatações compatíveis de textos e legendas, como negrito, itálico, sublinhado, tachado, spoiler, código, links, menções, citações e emojis personalizados compatíveis. Em álbuns, cada legenda mantém sua própria formatação. Se uma legenda ultrapassar o limite aceito pela conta, a mídia será enviada primeiro e o texto completo aparecerá logo depois.

### Posso sincronizar uma origem que bloqueia o encaminhamento?

Sim, quando a conta consegue baixar livremente a mídia e você possui autorização para reutilizá-la. Edite a rota, ative **Baixar e reenviar arquivos** e faça primeiro um teste com um arquivo pequeno. Se a API do Telegram também impedir o download, o programa não poderá completar a transferência.

### O que acontece com mensagens que possuem prévia de link?

Elas são reenviadas como texto e o Telegram recria a prévia da página no destino. A aparência pode mudar caso o site tenha atualizado sua imagem ou seus metadados.

### Posso sincronizar vários canais?

Sim. Cadastre quantas rotas forem necessárias, considerando os limites e permissões da sua conta no Telegram.

### Posso sincronizar vários tópicos do mesmo grupo?

Sim. Crie uma rota separada para cada tópico. Cada uma terá progresso próprio.

### Posso enviar as mensagens diretamente para um tópico?

Sim. Informe o grupo no lado **DESTINO** e selecione o tópico desejado. Se o campo **ID do tópico** do destino ficar vazio, a mensagem será enviada ao canal, grupo ou tópico principal.

### Posso criar uma rota de tópico para tópico?

Sim. Selecione um tópico no lado **ORIGEM** e outro no lado **DESTINO**. O MLD Tools também aceita rotas de canal ou grupo para tópico.

### Posso sincronizar o grupo inteiro?

Sim. Deixe o campo **ID do tópico** da origem vazio. Para enviar ao grupo principal, deixe também vazio o tópico do destino.

### O programa copia todo o histórico automaticamente?

Não. O modo normal copia mensagens novas. O histórico só é importado quando você inicia o modo retroativo.

### Posso escolher onde os arquivos temporários ficam?

Sim. Entre em **Configurações > Armazenamento temporário** e escolha a pasta-pai. O MLD Tools usará somente a subpasta `temp_transferencias` dentro do local selecionado. Na versão portátil, você também pode escolher uma unidade diferente daquela em que o programa está salvo.

### O retroativo baixa o canal inteiro de uma vez?

Não. O limite do retroativo define quantas mensagens serão processadas; `0` significa todo o histórico disponível. O trabalho ocorre progressivamente. Um arquivo isolado é removido após o envio confirmado, mas os itens de um mesmo álbum precisam coexistir temporariamente para que o álbum seja recriado corretamente.

### Edições e exclusões também são espelhadas?

Não. O MLD Tools trabalha com o envio de mensagens como novas publicações. Alterações ou exclusões feitas posteriormente na origem não modificam automaticamente a cópia já enviada.

### Preciso deixar o computador ligado?

Sim. A sincronização acontece localmente no seu computador.

### Preciso instalar Python?

Não. Os executáveis já incluem os componentes necessários.

### Posso usar a mesma configuração depois de atualizar?

Sim. A versão 3.0.0 mantém compatibilidade com as rotas, a sessão e os arquivos de progresso das versões recentes anteriores do projeto. Rotas antigas permanecem no modo direto até que a opção de baixar e reenviar seja ativada manualmente.

---

## Comece com uma rota de teste

Antes de configurar canais importantes, crie uma origem e um destino de teste. Envie uma mensagem de texto, uma foto com legenda e um pequeno álbum. Verifique o resultado e consulte o Log.

Depois do teste, você já pode cadastrar as rotas definitivas e manter o MLD Tools trabalhando no Dashboard.

**MLD Tools 3.0.0 — sincronização organizada, histórico preservado e controle em uma única interface.**

---

## Download e atualizações

Consulte a página de [Releases](../../../releases/latest) para baixar a versão mais recente e conferir as notas de atualização.
