# Validação — MLDForwarder Android 1.1.2

## Resultado executado

**34 testes passaram** em `python -m unittest discover -s tests -v`.
A biblioteca utilizada foi a mesma do app: Telethon **1.40.0**.
Compilação sintática dos módulos Python e leitura dos XMLs também verificadas.

Os testes simulam respostas do Telegram; não são testes de integração com uma
conta real. Nenhuma sessão, API Hash pessoal ou chave de assinatura foi utilizada.

| Área | Cobertura |
| --- | --- |
| Legendas dos exemplos | Documento rejeitado com custom emoji; preservação de Unicode, negrito e citação expansível |
| Referência expirada | Refetch e envio sem remover os estilos originais |
| Pendência persistente | Salva antes de avançar cursor, reabertura e nova tentativa sem rebobinar histórico |
| Álbuns | Agrupamento preservado e retomada de legendas sem repetir álbum/trechos confirmados |
| Fluxo normal e retroativo | Continuidade após mídia inválida e execução das demais rotas |
| Permissões | Pausa somente da rota afetada, sem loop de requisições |
| FloodWait/parada | Retomada da operação atual, cancelamento da espera/coleta e proteção de execução única |
| Rede/interrupção | Resultado incerto mantido para conferência, sem reenvio automático |
| Armazenamento | Journal corrompido não apagado; falha ao salvar interrompe; recibo protege retomada |
| Compatibilidade | Progresso v1.1.1, ID inicial exclusivo/crescente, limite mínimo 1, extensão para concluir álbum |
| Isolamento | Pendências separadas por conta, modo e identidade completa da rota |

## O que o material recebido permite concluir

- O código v1.1.1 tratava `FloodWait` por grupo, mas não `DocumentInvalidError`.
  A exceção abandonava o restante da rota; outras rotas posteriores ainda seriam
  executadas. Nos prints, a rota problemática era a última das quatro.
- O código reutiliza tanto a mídia quanto todas as entidades originais da legenda.
- As capturas mostram ícones personalizados nas legendas. É plausível que uma
  entidade custom emoji esteja envolvida, pois essas entidades referenciam documentos.
  Isso **não foi comprovado**: screenshots não contêm os objetos MTProto originais
  nem demonstram a resposta a uma tentativa sem aquelas entidades.
- A descrição genérica do erro menciona inline, mas isso não prova que o app
  esteja usando um bot inline. A chamada observada é `SendMediaRequest`.
- Referência: [documentação de emojis personalizados do Telegram](https://core.telegram.org/api/custom-emoji).

## Pendente antes de distribuir

1. Compilar no ambiente Android: `gradle :app:assembleDebug` para teste isolado
   ou `gradle :app:assembleRelease` para release sem assinatura. O ambiente desta
   entrega não tinha SDK/Gradle e a obtenção das ferramentas foi bloqueada;
   **nenhum APK foi gerado ou validado**.
2. Assinar o release com a mesma chave da v1.1.1. A chave privada não veio no ZIP
   e não deve ser publicada no repositório.
3. Instalar sobre a versão oficial sem desinstalar; confirmar conta e rotas mantidas.
4. Criar uma rota de teste com destino novo e usar o ID imediatamente anterior ao
   post rejeitado, com limite pequeno. Não reduzir o ID de uma rota de produção:
   o maior progresso salvo prevalece e não há rebobinagem automática.
5. Testar separadamente os dois posts fornecidos e um álbum com legenda longa.
6. Conferir mídia, texto, formatação, tópicos, posição dos emojis e ausência de
   duplicação. Guardar as linhas da Atividade que identifiquem a tentativa usada.
7. Se algum post ficar pendente, confirmar que os seguintes e outras rotas seguem;
   reiniciar o mesmo modo para testar a nova tentativa e conferir o resumo final.
8. Testar parar durante envio e FloodWait; aguardar encerramento antes de reiniciar.

## Limitações importantes

- A solução não baixa arquivos grandes nem contorna proteção de conteúdo.
- Não há tela nova de pendências nesta atualização: diagnóstico e resumo ficam
  na Atividade; os registros persistem no armazenamento privado.
- Pendências de resultado incerto não são resolvidas automaticamente. É necessário
  conferir o destino antes de decidir por qualquer reenvio.
- Mensagens recuperadas depois podem chegar fora de ordem. A preservação rigorosa
  da ordem exigiria pausar a rota, em vez de seguir após a falha.
- Os cursores legados continuam com seu modelo original de armazenamento; só os
  novos journals de entrega são isolados por conta. Não use troca de conta como
  forma de reiniciar uma rota ou reconstruir pendências.
- A suíte offline não comprova que os dois posts reais serão aceitos. Ela comprova
  os caminhos de tratamento simulados e deve ser complementada pelo teste acima.
