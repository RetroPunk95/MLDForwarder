# Segurança

## Dados que nunca devem ser publicados

- `.env` com API ID e API Hash reais;
- arquivos `*.session` e `*.session-journal`;
- telefone, código de autenticação ou senha 2FA;
- rotas, logs e progressos que contenham informações privadas.

Os arquivos `.default.json` e `.env.example` deste repositório são apenas modelos públicos.

## Relatando uma vulnerabilidade

Não publique credenciais, sessões ou detalhes exploráveis em uma Issue pública. Prefira o recurso **Report a vulnerability** na aba **Security** do repositório, quando disponível.

Inclua uma descrição do problema, versão afetada e passos mínimos para reprodução, sempre removendo dados pessoais.

