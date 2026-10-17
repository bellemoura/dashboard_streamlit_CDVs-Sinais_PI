# Diagnóstico de Sinalização Ferroviária — Projeto Integrador

Dashboard interativo desenvolvido com **Python, Pandas, Plotly e Streamlit**, com base nos arquivos de levantamento de BD de **CDVs e Sinais (Vias 1 e 2)**. Usa o dashboard de outro grupo como referência do problema e das categorias de análise, mas tem organização, interface e processamento próprios.

## 1. Como executar — passo a passo

1. Extraia o ZIP para uma pasta no computador.
2. Abra **essa pasta** no Visual Studio Code (Arquivo > Abrir Pasta).
3. Abra um terminal do VS Code.
4. Opcional: crie e ative um ambiente virtual, para separar as bibliotecas do projeto:

   **Windows (PowerShell):**
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **Windows (Prompt de Comando):**
   ```cmd
   py -m venv .venv
   .venv\Scripts\activate.bat
   ```

   Se você já tem um ambiente Conda com Python e prefere utilizá-lo, pode usar esse ambiente, sem criar `.venv`.
5. Instale as bibliotecas (uma única vez por ambiente):
   ```bash
   python -m pip install -r requirements.txt
   ```
6. Inicie o painel:
   ```bash
   python -m streamlit run app.py
   ```
7. Abra no navegador o endereço local que aparecer no terminal (geralmente `http://localhost:8501`).

**Dica:** as planilhas acompanham esta pasta; não é necessário indicar caminhos absolutos. Se trocar os arquivos pelos uploads da barra lateral, o painel usará os arquivos enviados.

### Arquivos incluídos

| Arquivo | Para que serve |
|---|---|
| `app.py` | Interface, filtros, indicadores, gráficos, tabelas e exportações. |
| `processamento.py` | Leitura, extração dos blocos da planilha, classificação e métricas. |
| `requirements.txt` | Bibliotecas a instalar. |
| `levantamento BD CDVs via 1 e 2.xlsx` | Planilha original de circuitos de via. |
| `levantamento BD Sinais via 1 e 2.xlsx` | Planilha original de sinais. |
| `LEIA-ME.md` | Este documento explicativo. |

## 2. Qual é a pergunta do projeto?

**Como organizar e visualizar o levantamento de registros de CDVs e Sinais, identificar a distribuição por funções e locais e encontrar campos que mereçam revisão?**

Os arquivos não são tabelas prontas para gráficos: cada equipamento aparece em um **bloco**, com funções em colunas. O principal trabalho de preparação é converter esses blocos em uma tabela estruturada, em que cada linha contém:

- Tipo de ativo: CDV ou Sinal;
- Nome do equipamento e identificação do bloco;
- Via e sentido, quando podem ser extraídos do nome do CDV;
- Local e tipo de local;
- Categoria/função, código e valor do ponto;
- Status, família, indicador de possível inconsistência de escrita;
- Endereço de origem (`linha_excel` e `coluna_excel`) para facilitar a conferência.

**A unidade das métricas de pontos é a célula de função por local.** Isso não representa necessariamente uma conexão ou um local físico único. Uma célula que contém `LB A-23 / LB B-22` conta como **um registro preenchido**, embora contenha duas referências.

## 3. Como as planilhas são transformadas?

### Etapa A — Ler os arquivos

Em `processamento.py`, `pd.read_excel(..., header=None)` lê a planilha sem transformar a primeira linha em nomes de colunas. Isso importa porque as planilhas têm muitos blocos e cabeçalhos internos, não uma única tabela com cabeçalho na linha 1.

### Etapa B — Localizar os blocos

A função `transformar_planilha()` procura cabeçalhos como `CDV 1N08T LUZ` e `SINAL 4 LUZ`, percorrendo as colunas. A detecção não depende de cada bloco estar sempre na mesma coluna.

O início dos dados é deslocado em relação ao cabeçalho: **4 linhas** nos CDVs e **5 linhas** nos Sinais, porque a estrutura de cabeçalhos é diferente.

### Etapa C — Converter a tabela para formato longo

Cada local dentro do bloco tem 5 funções para CDVs, ou 4 funções para Sinais. O algoritmo gera **uma linha para cada combinação de local e função**. Esse formato é chamado *long* ou *tidy data* e facilita os agrupamentos (`groupby`), filtros e gráficos.

### Etapa D — Criar categorias

A função `classificar_status()` aplica a mesma regra de análise que foi adotada como referência pelo outro grupo:

| Valor na célula | Status atribuído |
|---|---|
| vazio | `Pendente` |
| `-` | `Não utilizado` |
| outro valor | `Preenchido` |

A definição é útil para o **levantamento documental**. Ela **não prova** que um campo vazio seja uma falha real de campo. Consulte a documentação da disciplina ou o professor para confirmar a interpretação esperada.

A função `identificar_local()` categoriza rótulos como `Locação 1`, `Armario TB`, `Interface 2` e `Bastidor DCC1`, preservando o nome completo em outra coluna.

A função `extrair_familia()` procura grupos como `LB`, `LC`, `TB2`, `TB3` etc., para permitir análises hierárquicas.

A função `verificar_escrita()` procura valores cuja formatação difere dos padrões mais frequentes da planilha, como `TB3-46` ou `B3028`. São **alertas para revisão, não erros comprovados**.

## 4. Entendendo os cálculos

### Indicadores principais

- **CDVs distintos** = quantidade de nomes diferentes na coluna `equipamento`, filtrados como CDV;
- **Sinais distintos** = mesma contagem para sinais;
- **Pontos preenchidos** = número de linhas com `status == "Preenchido"`;
- **Células pendentes** = número de linhas com `status == "Pendente"`;
- **Não utilizados** = número de linhas com `status == "Não utilizado"`;
- **Taxa de preenchimento** = `Preenchidos / (Preenchidos + Pendentes) × 100`.

**Por que `Não utilizado` fica fora da taxa?** Porque o hífen informa, sob a regra escolhida, que o registro não se aplica; tratá-lo como pendência distorceria a proporção. Se o professor pedir outra definição, basta alterar `calcular_resumo()`.

**Por que existem nomes repetidos?** Em alguns casos, o mesmo CDV está identificado em mais de um bloco da planilha. A métrica conta o nome **uma vez**, enquanto os registros dos blocos permanecem disponíveis para auditoria. Não se deve apagar automaticamente blocos repetidos: eles podem registrar posições diferentes.

## 5. Por que escolhemos cada visualização?

| Visualização | Por que faz sentido |
|---|---|
| **Cartões KPI** | Mostram rapidamente os números principais. |
| **Barras empilhadas por ativo / via / sentido** | Permitem comparar volumes e estados (preenchido, pendente e não utilizado). |
| **Barras por função** | Mostram quais funções concentram mais registros preenchidos. |
| **Mapa de calor CDV × função** | Facilita encontrar diferenças de volume entre equipamentos e funções. Não representa temperatura ou risco. |
| **Gráfico de rosca (Sinais × local)** | Mostra a composição percentual dos registros preenchidos. |
| **Ranking de pendências** | Direciona a revisão para equipamentos que têm mais células vazias. |
| **Tabelas de auditoria** | Exibem os detalhes exatos para investigar casos específicos. |
| **Download de CSV** | Permite continuar a análise fora do Streamlit. |

**Por que não usar gráfico de linhas?** A fonte não fornece uma sequência temporal de medições. Um gráfico de linhas sugeriria uma evolução no tempo que os dados não comprovam.

## 6. Entendendo as bibliotecas e comandos usados

- **Pandas (`pd`)**: lê os Excel, organiza registros com `DataFrame`, filtra linhas e resume contagens com `groupby()` e `value_counts()`.
- **Plotly Express (`px`)**: desenha os gráficos interativos, com destaque ao passar o cursor e legenda.
- **Streamlit (`st`)**: transforma o programa Python em uma página web, sem precisar escrever HTML/JavaScript para a interface.
- **`st.multiselect()`**: cria filtros para ativos, via e tipo de local.
- **`st.metric()`**: destaca indicadores.
- **`st.tabs()`**: separa o painel por objetivos analíticos.
- **`st.dataframe()`**: exibe uma tabela navegável.
- **`st.download_button()`**: permite baixar a tabela normalizada e os alertas.
- **`@st.cache_data`**: evita reler e reprocessar os mesmos arquivos a cada alteração de filtro; recalcula se o conteúdo dos arquivos mudar.
- **`Path(__file__).resolve().parent`**: localiza a pasta do código. Evita dependência de caminhos pessoais do Windows.

## 7. Resultados de referência — sem filtros

Leitura das planilhas originais incluídas no ZIP, usando as regras descritas acima:

| Medida | CDVs | Sinais | Total |
|---|---:|---:|---:|
| Equipamentos distintos | 21 | 19 | 40 |
| Registros preenchidos | 478 | 247 | 725 |
| Células pendentes | 2 | 13 | 15 |
| Registros com `-` | 195 | 0 | 195 |
| Total de registros | 675 | 260 | 935 |
| Taxa de preenchimento | 99,6% | 95,0% | 98,0% |

O programa encontra, usando **heurísticas de escrita**, 13 registros para revisão na planilha de CDVs e 7 na de Sinais. Há dois **nomes de CDV que aparecem em mais de um bloco** na fonte. Essas ocorrências não devem ser tratadas como erros sem verificação.

## 8. Limitações e interpretação responsável

1. A base de **Sinais não identifica a via** de cada sinal. O filtro de Via atua apenas nos CDVs; não se deve atribuir arbitrariamente Via 1 ou Via 2 aos Sinais.
2. Não há informação temporal, portanto não é possível avaliar tendência ou evolução.
3. O formato predominante de códigos não equivale a uma norma técnica validada. Os alertas de formatação são sugestões de revisão.
4. As regras para `Pendente` e `Não utilizado` devem ser confirmadas com o professor, se houver convenções próprias para o exercício.
5. Este é um **diagnóstico documental**, não uma avaliação de funcionamento ou segurança ferroviária.
6. Se as planilhas mudarem de estrutura (por exemplo, número de linhas de cabeçalho ou funções), talvez seja necessário ajustar `transformar_planilha()`.

## 9. Roteiro para apresentar o trabalho

Você pode explicar nessa ordem:

1. **Problema:** os dados estão em planilhas de blocos, difíceis de comparar diretamente.
2. **Preparação:** leitura em Pandas, busca de blocos e conversão para tabela normalizada.
3. **Classificação:** definição explícita dos três status; identificação de via nos CDVs e tipos de local.
4. **Visualização:** KPIs de resumo, comparação por ativo, detalhamento de CDVs e Sinais.
5. **Qualidade:** registros vazios, valores com grafia fora do padrão e blocos repetidos com referência à linha/coluna de origem.
6. **Limitações:** sem cronologia, sem via dos Sinais e sem confirmação dos padrões por norma de engenharia.

### Perguntas que o professor pode fazer

**"Por que usar Streamlit?"** Para construir uma interface interativa em Python, com filtros e gráficos acessíveis em navegador.

**"Por que tratar os dados antes de criar gráficos?"** Porque a estrutura em blocos não permite agrupamentos simples; precisamos de uma linha por observação para que cada gráfico represente a mesma unidade de análise.

**"O que acontece quando aplicamos um filtro?"** O Streamlit executa o script novamente, o Pandas seleciona o subconjunto e todos os números/gráficos são recalculados. O cache evita reler os arquivos sem necessidade.

**"Por que a taxa de preenchimento pode ser diferente do percentual de células não vazias?"** Porque o denominador exclui registros com hífen, definidos como não utilizados.

**"Por que nem todos os registros 'diferentes' são erros?"** Porque não temos a norma técnica dos códigos: usamos padrões recorrentes como sinais de alerta, não como critério definitivo de correção.

## 10. Publicar no Streamlit Community Cloud

1. Crie um repositório no GitHub com `app.py`, `processamento.py`, `requirements.txt` e as duas planilhas (se for autorizado compartilhar as bases).
2. No Streamlit Community Cloud, crie um app vinculado ao repositório.
3. Selecione `app.py` como arquivo principal.
4. O serviço instalará as bibliotecas de `requirements.txt`.
5. Se as planilhas não puderem ser publicadas, deixe-as fora do GitHub e faça upload pela barra lateral após abrir o app; nesse caso, elas não estarão pré-carregadas para outros usuários.

Não coloque caminhos `C:\Users\...` no código publicado. Os caminhos deste projeto já são relativos à pasta.
