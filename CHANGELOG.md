# Histórico de versões

## Correção do pacote v3.0.0

- Torna as duas interfaces responsivas durante o redimensionamento, reorganizando cards, campos, opções e grupos de ações por pontos de quebra.
- Adiciona rolagem vertical automática em cada página quando a altura disponível não comporta todo o conteúdo.
- Ajusta textos explicativos à largura disponível e mantém sidebar e cabeçalho fixos durante a rolagem.
- Aumenta a altura inicial da Central de mídia e restaura automaticamente o último tamanho, posição e estado maximizado das duas janelas.
- Corrige a abertura do portátil após a migração para CustomTkinter, encaminhando corretamente as opções de geometria dos painéis arredondados.
- Redesenha integralmente o painel principal e a Central de mídia com uma interface escura inspirada em produtos SaaS.
- Adota a paleta navy, azul elétrico e violeta do novo ícone oficial, preservando cores semânticas para sucesso, alerta e erro.
- Adiciona o ícone à sidebar, cabeçalhos contextuais, navegação com marcador lateral, cards de estado e acabamento escuro da janela no Windows.
- Centraliza o sistema visual em `ui_theme.py` e migra superfícies, badges, navegação e ações para CustomTkinter, com cantos arredondados reais e escala mais legível.
- Mantém tabelas e campos em Tk/ttk para preservar o comportamento existente e fixa `customtkinter==5.2.2` no build.
- Inclui os recursos visuais automaticamente nos executáveis `MLDTools.exe` e `MLDToolsMedia.exe`.
- Restaura a lista automática de canais e grupos nos campos de origem e destino ao adicionar ou editar uma rota.
- Exibe cada opção como `nome — tipo (ID)`, permite atualizar a consulta e mantém o preenchimento manual por ID ou `@username`.
- Unifica downloads e uploads na mesma fila persistente e preserva a ordem de criação.
- Substitui o início imediato do upload por **Adicionar à fila**; o envio só começa após **Iniciar fila**.
- Adiciona pausa, cancelamento, nova tentativa e recuperação após fechamento também aos uploads, reiniciando-os do começo quando necessário.
- Registra uploads na atividade recente e no histórico persistente, incluindo progresso, velocidade, destino e resultado final.
- Adiciona perfis **Equilibrado**, **Rápido** e **Agressivo** para os parâmetros de transferência do `tdl`.
- Explica no Guia do Usuário o significado, a indicação e os riscos de cada perfil de desempenho.
- Acelera documentos enviados como álbum com `cryptg`, partes de 512 KB e pré-upload paralelo de até quatro arquivos, preservando a ordem do álbum.
- Acelera o modo **Baixar e reenviar arquivos** com quatro partes de 512 KB em voo no download e no upload.
- Processa as mídias de um álbum em paralelo com um limite global conservador, preservando a ordem e a retomada dos temporários.
- Garante a inclusão do `cryptg` nos motores compilados de sincronização normal e retroativa.
- Corrige o botão **Cancelar** durante uploads, encerrando também o processo real do uploader compilado em modo `onefile`.
- Adiciona cancelamento cooperativo, encerramento forçado como fallback e limpeza dos arquivos temporários da tarefa.
- Adiciona a opção **Manter nome original** aos downloads, removendo os IDs da conversa e da mensagem do início do arquivo.
- Permite salvar essa escolha como comportamento padrão nas configurações.
- Corrige o upload em álbuns para destinos escolhidos pela lista do `tdl`, convertendo IDs de canais e grupos para o formato esperado pelo Telethon.
- Atualiza automaticamente o cache de conversas da sessão de álbuns quando o destino ainda não foi localizado.
- Corrige acentos e reticências nos logs do motor de upload no Windows.

## 3.0.0 — MLD Tools

- Renomeia o MLDForwarder para **MLD Tools — Telegram Media Suite**.
- Integra a Central de mídia do MLD Fetch em uma janela própria iniciada pela interface principal.
- Adiciona downloads por links, JSON, canal, grupo ou tópico, sempre com início manual pela fila.
- Adiciona exportação de mensagens, membros e inscritos para JSON.
- Adiciona upload de arquivos e pastas para Mensagens Salvas, conversas, canais, grupos e tópicos.
- Adiciona upload agrupado em álbuns, por seleção ou por pasta.
- Divide seleções grandes em álbuns compatíveis e usa ordenação natural de nomes.
- Usa a sessão Telethon autenticada do MLD Tools para álbuns e mantém o `tdl` nas demais ferramentas de mídia.
- Inclui motores independentes para sincronização, retroativo, Central de mídia e upload de álbuns.
- Mantém compatibilidade com rotas, progresso, sessão e configurações da versão 2.10.1.
- Atualiza a instalação existente no mesmo diretório, removendo apenas executáveis e atalhos antigos do MLDForwarder.

## 2.10.1 — Seleção de rotas no modo normal

- Permite iniciar uma, várias ou todas as rotas pelo Dashboard.
- Mantém todas as rotas selecionadas por padrão, preservando o comportamento anterior.
- Exibe a quantidade de rotas ativas durante a execução.
- Mantém progresso independente e rejeita chaves de rota desconhecidas.
- Preserva o download/reupload e o controle de armazenamento temporário da versão 2.10.0.

## 2.10.0 — Controle de armazenamento temporário

- Permite escolher a pasta-pai dos downloads temporários pela interface.
- Administra somente a subpasta marcada `temp_transferencias`, protegendo os demais arquivos da pasta escolhida.
- Exibe espaço livre, uso atual e limite configurado.
- Adiciona limite temporário em GB; `0` mantém apenas a verificação do espaço real do disco.
- Valida o tamanho total conhecido de um álbum antes de iniciar o primeiro download.
- Considera arquivos completos e parciais retidos de tentativas anteriores no limite configurado.
- Adiciona o botão **Limpar temporários**, disponível apenas com os sincronizadores parados e mediante confirmação.
- Mantém compatibilidade com a pasta padrão e com temporários da versão 2.9.0.

## 2.9.0 — Download e reenvio local

- Adiciona a opção **Baixar e reenviar arquivos** individualmente por rota.
- Permite recriar arquivos como novas publicações quando a origem aceita download, mas bloqueia o encaminhamento ou a cópia direta.
- Aplica o modo à sincronização normal, retroativa e às retentativas de falhas.
- Retoma downloads parciais armazenados com extensão `.part`.
- Reutiliza o arquivo completo quando o upload falha, evitando baixá-lo novamente.
- Valida espaço livre antes do download e mantém uma margem de segurança.
- Verifica o limite de 2 GB antes do download e informa quando a conta precisa de Telegram Premium.
- Preserva nome, tipo, atributos, legenda e formatação compatível das mídias reenviadas.
- Mantém álbuns agrupados e preserva os metadados disponíveis de cada arquivo.
- Apaga o temporário somente depois que o envio é confirmado.
- Mantém todas as rotas antigas no modo direto por padrão.
- Adiciona a coluna **Transferência** à lista de rotas.

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
