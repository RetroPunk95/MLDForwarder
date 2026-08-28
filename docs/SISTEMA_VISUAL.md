# Sistema visual do MLD Tools v3

O painel principal e a Central de mídia compartilham o tema definido em
`ui_theme.py`. Alterações futuras de cor ou acabamento devem ser feitas nesse
arquivo para evitar divergências entre os dois executáveis.

## Direção

- base navy escura inspirada em interfaces SaaS;
- azul elétrico para navegação e ações principais;
- violeta para a Central de mídia e elementos de identidade;
- verde, amarelo e coral reservados para sucesso, atenção e erro;
- Segoe UI como tipografia nativa do Windows;
- hierarquia construída com overlines, títulos contextuais, cards e superfícies.

## Paleta principal

| Uso | Cor |
|---|---|
| Fundo | `#080D18` |
| Sidebar | `#0A1020` |
| Superfície | `#101827` |
| Campo / superfície elevada | `#182338` |
| Borda | `#26324A` |
| Texto principal | `#F6F8FC` |
| Texto secundário | `#91A0B8` |
| Azul principal | `#168BFF` |
| Violeta | `#7C5CFF` |
| Sucesso | `#4ADE80` |
| Alerta | `#F7C75C` |
| Erro | `#FF657A` |

## Recursos

- `Icon.ico`: ícone multirresolução usado pela janela, executáveis e instalador;
- `assets/app_icon_64.png`: versão compacta exibida na sidebar;
- `docs/images/redesign-dashboard.png`: prévia do dashboard redesenhado.

O `build_exe.bat` valida e inclui os recursos necessários nos executáveis
one-file. A camada moderna usa `customtkinter==5.2.2` para cantos arredondados,
botões com estados consistentes e escala mais legível; tabelas e campos densos
continuam em Tk/ttk.

## Responsividade

- sidebar e cabeçalho permanecem fixos para preservar a navegação;
- o conteúdo de cada página possui uma viewport própria com rolagem vertical automática;
- cards, campos, opções e barras de ações mudam de quantidade de colunas conforme a largura disponível;
- textos auxiliares recalculam a quebra de linha durante o redimensionamento;
- ao trocar de página, a viewport volta ao topo para não esconder o início do conteúdo;
- a última geometria normal e o estado maximizado continuam sendo restaurados na próxima abertura.
