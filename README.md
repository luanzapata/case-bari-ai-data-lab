# Case Técnico — Bari AI & Data Lab

Solução desenvolvida para o processo seletivo do **Bari AI & Data Lab**, com foco em análise do funil de crédito, automação de relatórios e extração estruturada de informações de laudos imobiliários utilizando IA.

## Estrutura do projeto

```text
case-bari/
├── data/
│   ├── propostas_credito.csv
│   ├── gabarito_laudos.json
│   └── laudos_avaliacao/
│
├── notebooks/
│   └── parte1_diagnostico_funil.ipynb
│
├── src/
│   ├── parte2_relatorio_semanal.py
│   ├── relatorio_html.py
│   ├── parte3_extracao_laudos.py
│   └── avaliar_extracao_laudos.py
│
├── reports/
│   ├── parte2/
│   │   ├── relatorio_semanal.html
│   │   └── assets/
│   │       ├── conversao_canal.png
│   │       ├── conversao_mensal.png
│   │       └── perdas_etapa.png
│   │
│   ├── parte3/
│   │   ├── extracao_laudos.json
│   │   ├── extracao_laudos.csv
│   │   ├── extracao_laudos_bruta.json
│   │   ├── erros_extracao_laudos.json
│   │   ├── avaliacao_extracao_laudos.csv
│   │   └── metricas_extracao_laudos.json
│   │
│   └── resumo_executivo.pdf
│
├── logs/
│   ├── parte2/
│   │   └── exemplos/
│   └── parte3/
│       └── exemplos/
│
├── scripts/
│   └── executar_relatorio.bat
│
├── DIARIO.md
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
└── RESUMO_EXECUTIVO.md
```

## Como executar

### 1. Criar o ambiente virtual

No Windows:

```powershell
python -m venv .venv
```

Ativar o ambiente:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Instalar as dependências

```powershell
pip install -r requirements.txt
```

### 3. Configurar a API do Gemini

Crie um arquivo `.env` na raiz do projeto utilizando o `.env.example` como referência:

```env
GEMINI_API_KEY=sua_chave_aqui
GEMINI_MODEL=gemini-3.5-flash-lite
```

O arquivo `.env` contém a chave da API e não é versionado no Git.

---

## Parte 1 — Diagnóstico do funil

A análise exploratória e o diagnóstico do funil estão disponíveis no notebook:

```text
notebooks/parte1_diagnostico_funil.ipynb
```

Para abrir:

```powershell
jupyter notebook notebooks/parte1_diagnostico_funil.ipynb
```

A análise considera as etapas:

```text
Simulação
→ Lead
→ Análise de crédito
→ Avaliação do imóvel
→ Formalização
→ Contratação
```

Conforme solicitado no case, imóveis classificados como `Terreno` foram removidos da análise da base de propostas.

O tratamento foi construído preservando a base original sempre que possível e evitando transformar a limpeza em um **abacaxi de regras arbitrárias**.

As conclusões detalhadas, hipóteses e recomendações estão documentadas no próprio notebook.

---

## Parte 2 — Relatório semanal automatizado

A automação lê a base de propostas, aplica os tratamentos, calcula as principais métricas do funil, gera gráficos e produz um relatório HTML para acompanhamento da liderança.

### Executar diretamente

```powershell
python src/parte2_relatorio_semanal.py
```

### Executar pelo script de automação

```powershell
.\scripts\executar_relatorio.bat
```

O `.bat` foi criado para facilitar a configuração no **Agendador de Tarefas do Windows**, permitindo a execução automática semanal.

### Saída principal

```text
reports/parte2/relatorio_semanal.html
```

### Gráficos gerados

```text
reports/parte2/assets/conversao_canal.png
reports/parte2/assets/conversao_mensal.png
reports/parte2/assets/perdas_etapa.png
```

Os relatórios e gráficos possuem nomes fixos e são atualizados a cada nova execução.

Os logs, por outro lado, mantêm histórico das execuções:

```text
logs/parte2/
```

A automação também possui validações para situações como:

- ausência de colunas obrigatórias;
- presença de novas colunas;
- formatos de entrada suportados;
- datas inválidas;
- registros fora das regras esperadas;
- inconsistências preservadas para auditoria.

Alguns exemplos de logs foram mantidos em:

```text
logs/parte2/exemplos/
```

---

## Parte 3 — Extração de laudos com IA

A Parte 3 processa automaticamente os arquivos `.txt` disponíveis em:

```text
data/laudos_avaliacao/
```

Para executar:

```powershell
python src/parte3_extracao_laudos.py
```

A solução utiliza uma arquitetura híbrida:

```text
Laudo em texto livre
→ Gemini para interpretação semântica
→ Structured Output validado com Pydantic
→ Python para normalização e validação
→ tratamento de inconsistências
→ JSON e CSV
```

O modelo de linguagem é utilizado principalmente para interpretar o texto livre.

As regras determinísticas, normalizações, conversões, identificação de conflitos e definição do status final ficam sob responsabilidade da aplicação Python.

Isso reduz a quantidade de decisões deixadas abertas à interpretação do modelo.

### Informações extraídas

A solução procura estruturar:

- tipo do imóvel;
- endereço;
- áreas;
- ano;
- valor da avaliação;
- matrícula;
- ônus;
- data da vistoria;
- responsável técnico.

Quando uma informação não está disponível, a aplicação evita inferir ou inventar o valor.

Quando existem informações contraditórias, a divergência é registrada em vez de escolher arbitrariamente um dos valores.

### Saídas

```text
reports/parte3/extracao_laudos.json
reports/parte3/extracao_laudos_bruta.json
reports/parte3/extracao_laudos.csv
reports/parte3/erros_extracao_laudos.json
```

`extracao_laudos_bruta.json` preserva a extração retornada pela IA e suas evidências.

`extracao_laudos.json` contém o resultado após as regras e validações realizadas pelo Python.

Os logs de execução ficam em:

```text
logs/parte3/
```

A aplicação também possui retry para indisponibilidade temporária do serviço e controle de intervalo entre as chamadas à API.

---

## Avaliação da extração dos laudos

Foi criado um gabarito manual para avaliar a qualidade da automação:

```text
data/gabarito_laudos.json
```

O gabarito é utilizado exclusivamente para avaliação e **não participa da extração**.

Para executar a avaliação:

```powershell
python src/avaliar_extracao_laudos.py
```

O critério considera os 9 macrocampos solicitados no case:

```text
1. tipo do imóvel
2. endereço
3. áreas
4. ano
5. valor da avaliação
6. matrícula
7. ônus
8. data da vistoria
9. responsável técnico
```

Na execução utilizada para avaliação, 16 dos 17 laudos foram efetivamente processados pela API.

Foram obtidos:

```text
136 acertos em 144 macrocampos processados
Acurácia nos documentos processados: 94,44%

Taxa de alucinação: 0,00%
Identificação correta dos casos de campos ausentes: 100%
```

O 17º documento não foi processado naquela execução por limite de requisições da API. Quando contabilizado como nove campos não processados, o avaliador apresenta uma acurácia global de 88,89%.

Os resultados detalhados são gravados em:

```text
reports/parte3/avaliacao_extracao_laudos.csv
reports/parte3/metricas_extracao_laudos.json
```

---

## Tratamento de erros e logs

Os logs foram organizados por parte da solução:

```text
logs/
├── parte2/
└── parte3/
```

Os logs normais de execução utilizam timestamp para preservar histórico.

Eles não são enviados ao repositório por padrão.

Alguns exemplos relevantes foram preservados em:

```text
logs/parte2/exemplos/
logs/parte3/exemplos/
```

Entre os casos documentados estão:

- correção do tratamento de datas;
- ausência de coluna obrigatória;
- nova coluna recebida pela automação;
- execução normal da extração dos laudos;
- limite de requisições da API.

---

## Arquivos principais

| Arquivo | Função |
|---|---|
| `notebooks/parte1_diagnostico_funil.ipynb` | Diagnóstico e análise do funil |
| `src/parte2_relatorio_semanal.py` | Automação do relatório semanal |
| `src/relatorio_html.py` | Construção do relatório HTML |
| `src/parte3_extracao_laudos.py` | Extração estruturada dos laudos |
| `src/avaliar_extracao_laudos.py` | Avaliação da qualidade da extração |
| `data/gabarito_laudos.json` | Referência manual para avaliação |
| `scripts/executar_relatorio.bat` | Execução automatizável da Parte 2 |
| `DIARIO.md` | Diário de desenvolvimento e autocrítica |

---

## Dependências

As dependências utilizadas estão registradas em:

```text
requirements.txt
```

A instalação pode ser feita com:

```powershell
pip install -r requirements.txt
```

---

## Diário de desenvolvimento

O uso de IA durante o desenvolvimento, erros encontrados, mudanças de arquitetura, aprendizados e autocrítica estão documentados em:

```text
DIARIO.md
```

---

## Resumo executivo

A versão executiva de 1 página, preparada para liderança comercial, está disponível em:

`reports/resumo_executivo.pdf`

A versão textual/editável está em:

`RESUMO_EXECUTIVO.md`

## Tempo de desenvolvimento

Tempo aproximado dedicado ao desenvolvimento do case:

**16 horas**