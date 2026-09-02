# Histórico de alterações

## 1.1.2 — estabilidade de envio

- Rejeições `DOCUMENT_INVALID` e erros específicos de mídia não abandonam mais
  o restante da rota: há recuperação limitada e registro persistente de pendência.
- Nova tentativa com referência de mídia renovada; fallback seletivo para emoji
  Unicode em vez de emoji personalizado quando a rejeição justificar essa tentativa.
- Formatação textual e álbum mantidos, sem download/reupload automático nem mudança
  de autoria por encaminhamento nativo.
- IDs da mensagem/álbum, classe do erro e diagnóstico de entidades na Atividade.
- Reprocessamento das pendências ao iniciar o mesmo modo e a mesma rota/conta.
- Etapas confirmadas de mídia, álbuns e textos longos não são repetidas durante
  a recuperação. Resultados incertos exigem conferência manual.
- Parada cooperativa durante coleta/FloodWait, proteção contra execução simultânea
  e remoção da destruição imediata do serviço no botão de parar.
- Erros de permissão pausam a rota; falhas de armazenamento param o motor.
- Rótulo do limite esclarecido: mínimo 1. A semântica original de `0 → 1` não mudou.
- 34 testes offline com Telethon 1.40.0 adicionados ao workflow de build.

Status: código-fonte validado por testes offline. Compilação Android, assinatura
de release e validação com as mensagens reais ainda pendentes; não é uma release publicada.
