# Histórico de versões

## 2.8.1 — Hotfix de compatibilidade

- Corrige o envio de mídias cuja legenda ultrapassa o limite da conta no Telegram.
- Envia a mídia sem legenda e publica o texto completo logo depois, sem perder conteúdo ou formatação.
- Aplica o mesmo tratamento de legendas longas a álbuns.
- Corrige mensagens com `MessageMediaWebPage`, que agora são recriadas como texto com prévia de link.
- Aplica as correções à sincronização normal, retroativa e às retentativas.
- Mantém compatibilidade com rotas, sessão, configurações e progresso da versão 2.8.0.

## 2.8.0 — Release Kit v1.9

- Preserva a formatação original de textos e legendas no destino.
- Mantém negrito, itálico, sublinhado, tachado, spoiler e código.
- Mantém links, menções, citações e emojis personalizados compatíveis.
- Preserva separadamente a formatação de cada legenda em álbuns.
- Aplica a melhoria à sincronização normal, retroativa e às retentativas.
- Mantém o tema azul `#0083E8`, o ícone e todas as rotas da versão 2.7.0.

## 2.7.0 — Release Kit v1.8

- Adiciona destino opcional em tópico de grupo.
- Permite canal para tópico, grupo para tópico e tópico para tópico.
- Inclui busca e seleção de tópicos também no destino.
- Aplica o tópico de destino a textos, fotos, vídeos, documentos e álbuns.
- Atualiza a sincronização normal, retroativa e as retentativas de falhas.
- Adiciona a coluna “Tópico destino” à lista de rotas.
- Mantém compatibilidade com rotas antigas sem `target_topic_id`.

## 2.6.1 — Release Kit v1.7

- Corrige a inicialização do retroativo em rotas com ID negativo e tópico.
- Passa a chave da rota no formato seguro `--canal=<origem>:<tópico>`.
- Mantém compatibilidade com configurações, rotas e progressos da versão 2.6.0.

## 2.6.0 — Release Kit v1.6

- Adiciona descrições às configurações da sincronização normal.
- Explica o efeito de alterar o lote e o intervalo.
- Adiciona explicações aos campos do modo retroativo.
- Informa os valores padrão diretamente na interface.

## 2.5.0 — Release Kit v1.5

- Renomeia o programa de TGForwarder para MLDForwarder.
- Atualiza interface, executáveis, instalador e pacotes portáteis.
- Adiciona um link para [my.telegram.org](https://my.telegram.org/) na área da API.
- Preserva compatibilidade com rotas e progressos anteriores.

## 2.4.0 — Release Kit v1.4

- Adiciona busca e seleção de tópicos ao criar ou editar uma rota.
- Exibe cada tópico como `ID — nome do tópico`.
- Mantém o preenchimento manual do ID como alternativa.
- Pagina consultas em grupos com mais de 100 tópicos.

## 2.3.0 — Release Kit v1.3

- Adiciona rotas de tópico de grupo para canal.
- Permite vários tópicos do mesmo grupo.
- Mantém progresso normal e retroativo separado por rota.
- Reenvia como nova mensagem, sem assinatura de encaminhamento.
- Mantém suporte a textos, fotos, vídeos, documentos, legendas e álbuns.
