# MLDForwarder

![Ícone do MLDForwarder](docs/images/icon.png)

**Sincronização de canais, grupos e tópicos do Telegram em uma interface para Windows.**

O MLDForwarder copia mensagens entre conversas às quais a sua conta tem acesso. O conteúdo chega ao destino como uma nova publicação, sem a assinatura “Encaminhada de”.

![Dashboard do MLDForwarder](docs/images/08-dashboard.png)

## Recursos

- sincronização contínua de mensagens novas;
- importação retroativa de mensagens antigas;
- múltiplas rotas independentes;
- canal, grupo ou tópico na origem e no destino;
- busca de tópicos diretamente pela interface;
- suporte a textos, fotos, vídeos, documentos, legendas e álbuns;
- preservação de formatações compatíveis do Telegram;
- progresso salvo para continuar de onde parou;
- versão portátil e instalador para Windows.

## Download

Baixe a versão mais recente na página de [Releases](../../releases/latest).

| Opção | Indicação |
|---|---|
| `MLDForwarder_Setup_v2.8.0.exe` | Instalação comum no Windows, com atalhos e desinstalador. |
| `MLDForwarder_Portable.zip` | Uso sem instalação. Extraia o ZIP antes de executar. |

> O projeto ainda não possui assinatura digital. O Windows SmartScreen pode exibir um aviso de editor desconhecido. Confira se o arquivo veio desta página e valide o SHA-256 publicado na Release.

## Requisitos

- Windows 10 ou Windows 11 de 64 bits;
- conta ativa do Telegram;
- acesso de leitura às origens configuradas;
- permissão para publicar nos destinos;
- API ID e API Hash obtidos em [my.telegram.org](https://my.telegram.org/).

O usuário da versão compilada não precisa instalar Python.

## Primeiros passos

1. Instale o programa ou extraia a versão portátil.
2. Abra `MLDForwarder.exe`.
3. Entre em **Telegram** e informe seu API ID e API Hash.
4. Autentique sua conta com telefone, código e senha 2FA, quando solicitada.
5. Entre em **Rotas** e cadastre uma origem e um destino.
6. Use o **Dashboard** para iniciar a sincronização normal.
7. Use **Retroativo** somente quando quiser importar mensagens antigas.

O passo a passo completo está no [Guia do Usuário](docs/GUIA_DO_USUARIO.md).

## Formatação preservada

A versão 2.8.0 preserva, quando suportados pelo Telegram:

- negrito, itálico, sublinhado e tachado;
- spoiler e código;
- links, menções e citações;
- emojis personalizados compatíveis;
- formatação individual das legendas de álbuns.

## Dados locais e segurança

As credenciais e a sessão são armazenadas localmente na pasta do programa. O MLDForwarder não possui servidor próprio para receber esses dados.

Nunca compartilhe:

- `.env`;
- `*.session` ou `*.session-journal`;
- configurações contendo IDs que você prefira manter privados;
- logs e arquivos de progresso com informações pessoais.

Os modelos incluídos no repositório não contêm credenciais ou rotas reais.

## Compilando pelo código-fonte

Requisitos de build:

- Windows;
- Python 3.12;
- Inno Setup 6 ou 7, caso queira gerar o instalador.

Para gerar os executáveis e o pacote portátil:

```bat
build_exe.bat
```

Para gerar executáveis, portátil e instalador:

```bat
build_release.bat
```

Consulte também `README_BUILD.txt` e `README_INSTALLER.txt`.

## Limitações atuais

- o computador e o MLDForwarder precisam permanecer ligados durante a sincronização;
- edições e exclusões posteriores na origem não alteram a cópia já publicada;
- rotas novas começam nas mensagens mais recentes; use o modo retroativo para o histórico;
- limites e bloqueios temporários aplicados pelo Telegram continuam valendo.

## Uso responsável

Use o programa somente em canais e grupos aos quais você tem acesso. Respeite permissões, direitos autorais, privacidade e os Termos de Serviço do Telegram. O MLDForwarder não deve ser usado para spam.

MLDForwarder é um projeto independente e não possui vínculo, patrocínio ou aprovação oficial do Telegram.

## Licença

O projeto é distribuído sob a licença descrita em [LICENSE](LICENSE). O código pode ser consultado para auditoria, mas redistribuição, modificação, reempacotamento e comercialização exigem autorização prévia do autor.

