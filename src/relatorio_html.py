import pandas as pd


# ==========================================================
# GERAÇÃO DO RELATÓRIO HTML
# ==========================================================

def gerar_relatorio_html(
    metricas,
    graficos,
    pasta_relatorios,
    momento_execucao,
    logger
):
    logger.info("Iniciando geração do relatório HTML.")

    gerais = metricas["gerais"]

    # ------------------------------------------------------
    # Função auxiliar de formatação
    # ------------------------------------------------------

    def formatar_milhoes(valor):
        return (
            f"R$ {valor / 1_000_000:.1f} mi"
            .replace(".", ",")
        )

    # ------------------------------------------------------
    # Período analisado
    # ------------------------------------------------------

    periodo_inicio = (
        gerais["periodo_inicio"].strftime("%d/%m/%Y")
        if pd.notna(gerais["periodo_inicio"])
        else "Não disponível"
    )

    periodo_fim = (
        gerais["periodo_fim"].strftime("%d/%m/%Y")
        if pd.notna(gerais["periodo_fim"])
        else "Não disponível"
    )

    # ------------------------------------------------------
    # Tabela de perdas por etapa
    # ------------------------------------------------------

    tabela_perdas = (
        metricas["perdas_por_etapa"][
            [
                "etapa",
                "propostas_perdidas",
                "valor_perdido",
                "percentual_valor_perdido"
            ]
        ]
        .copy()
    )

    tabela_perdas.columns = [
        "Etapa",
        "Propostas perdidas",
        "Volume potencial perdido",
        "% do volume perdido"
    ]

    tabela_perdas["Volume potencial perdido"] = (
        tabela_perdas["Volume potencial perdido"]
        .apply(formatar_milhoes)
    )

    tabela_perdas["% do volume perdido"] = (
        tabela_perdas["% do volume perdido"]
        .apply(lambda x: f"{x:.1f}%")
    )

    # ------------------------------------------------------
    # Tabela de canais
    # ------------------------------------------------------

    tabela_canais = (
        metricas["conversao_canal"][
            [
                "canal_origem",
                "propostas",
                "contratadas",
                "taxa_conversao",
                "conversao_valor"
            ]
        ]
        .copy()
    )

    tabela_canais.columns = [
        "Canal",
        "Propostas",
        "Contratadas",
        "Conversão",
        "Conversão em volume"
    ]

    tabela_canais["Conversão"] = (
        tabela_canais["Conversão"]
        .apply(lambda x: f"{x:.1f}%")
    )

    tabela_canais["Conversão em volume"] = (
        tabela_canais["Conversão em volume"]
        .apply(lambda x: f"{x:.1f}%")
    )

    # ------------------------------------------------------
    # Tabela de motivos de perda
    # ------------------------------------------------------

    tabela_motivos = (
        metricas["motivos_perda"][
            [
                "status_final",
                "propostas",
                "valor_perdido"
            ]
        ]
        .copy()
    )

    tabela_motivos.columns = [
        "Motivo",
        "Propostas",
        "Volume potencial perdido"
    ]

    tabela_motivos["Volume potencial perdido"] = (
        tabela_motivos["Volume potencial perdido"]
        .apply(formatar_milhoes)
    )

    # ------------------------------------------------------
    # Caminhos relativos dos gráficos
    # ------------------------------------------------------

    grafico_perdas = (
        graficos["perdas_etapa"]
        .relative_to(pasta_relatorios)
        .as_posix()
    )

    grafico_canais = (
        graficos["conversao_canal"]
        .relative_to(pasta_relatorios)
        .as_posix()
    )

    grafico_mensal = (
        graficos["conversao_mensal"]
        .relative_to(pasta_relatorios)
        .as_posix()
    )

    # ------------------------------------------------------
    # Alertas de qualidade
    # ------------------------------------------------------

    alertas = metricas["alertas"]

    texto_alertas = f"""
        <li>
            LTV solicitado acima de 60%:
            <strong>{alertas.get("ltv_acima_60", 0)}</strong>
        </li>

        <li>
            IDs duplicados:
            <strong>{alertas.get("ids_duplicados", 0)}</strong>
        </li>

        <li>
            Idades inferiores a 18 anos:
            <strong>{alertas.get("idades_anomalas", 0)}</strong>
        </li>

        <li>
            Datas de assinatura inconsistentes:
            <strong>{alertas.get("datas_assinatura_invalidas", 0)}</strong>
        </li>
    """

    # ------------------------------------------------------
    # Conteúdo HTML
    # ------------------------------------------------------

    html = f"""
<!DOCTYPE html>

<html lang="pt-BR">

<head>

<meta charset="UTF-8">

<title>Relatório Semanal do Funil</title>

<style>

body {{
    font-family: Arial, sans-serif;
    background-color: #f5f6f8;
    color: #222;
    margin: 0;
    padding: 30px;
}}

.container {{
    max-width: 1100px;
    margin: auto;
    background-color: white;
    padding: 40px;
}}

h1 {{
    margin-bottom: 5px;
}}

h2 {{
    margin-top: 45px;
    border-bottom: 1px solid #ddd;
    padding-bottom: 8px;
}}

.subtitulo {{
    color: #666;
    margin-bottom: 30px;
}}

.cards {{
    display: grid;
    grid-template-columns: repeat(
        auto-fit,
        minmax(180px, 1fr)
    );
    gap: 15px;
}}

.card {{
    border: 1px solid #ddd;
    padding: 20px;
    border-radius: 8px;
}}

.card .valor {{
    font-size: 24px;
    font-weight: bold;
    margin-top: 8px;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 20px;
}}

th,
td {{
    border-bottom: 1px solid #ddd;
    padding: 10px;
    text-align: left;
}}

th {{
    background-color: #f1f2f4;
}}

img {{
    max-width: 100%;
    margin-top: 20px;
}}

.alerta {{
    background-color: #fafafa;
    border-left: 4px solid #888;
    padding: 15px 20px;
}}

.fonte {{
    color: #666;
    font-size: 13px;
    margin-top: 50px;
}}

</style>

</head>

<body>

<div class="container">

<h1>Relatório semanal do funil de crédito</h1>

<p class="subtitulo">
Período analisado:
<strong>{periodo_inicio}</strong>
a
<strong>{periodo_fim}</strong>
</p>


<div class="cards">

<div class="card">
Propostas analisadas

<div class="valor">
{gerais["total_propostas"]:,}
</div>

</div>


<div class="card">
Contratações

<div class="valor">
{gerais["total_contratadas"]:,}
</div>

</div>


<div class="card">
Taxa de conversão

<div class="valor">
{gerais["taxa_conversao"]:.1f}%
</div>

</div>


<div class="card">
Volume solicitado

<div class="valor">
{formatar_milhoes(gerais["volume_total"])}
</div>

</div>


<div class="card">
Volume potencial perdido

<div class="valor">
{formatar_milhoes(gerais["volume_perdido"])}
</div>

</div>

</div>


<h2>Perdas por etapa</h2>

<p>
O valor apresentado representa o volume solicitado das propostas
que não chegaram à contratação, e não receita ou lucro perdido pelo Bari.
</p>

<img
    src="{grafico_perdas}"
    alt="Volume potencial perdido por etapa"
>

{tabela_perdas.to_html(
    index=False,
    border=0,
    escape=True
)}


<h2>Conversão por canal</h2>

<img
    src="{grafico_canais}"
    alt="Taxa de conversão por canal"
>

{tabela_canais.to_html(
    index=False,
    border=0,
    escape=True
)}


<h2>Evolução da conversão</h2>

<img
    src="{grafico_mensal}"
    alt="Evolução mensal da conversão"
>


<h2>Principais motivos de perda</h2>

{tabela_motivos.to_html(
    index=False,
    border=0,
    escape=True
)}


<h2>Alertas de qualidade dos dados</h2>

<div class="alerta">

<ul>
{texto_alertas}
</ul>

<p>
Os alertas acima não significam que os registros foram
automaticamente removidos. Situações sem correção evidente foram
preservadas para evitar alterações arbitrárias nos dados.
</p>

</div>


<p class="fonte">

<strong>Fonte:</strong>
elaboração própria a partir do arquivo
<code>propostas_credito.csv</code>
fornecido no desafio prático.

<br><br>

Valores financeiros utilizam o valor solicitado
como proxy de volume potencial.

</p>

</div>

</body>

</html>
"""

    # ------------------------------------------------------
    # Salvar relatório
    # ------------------------------------------------------

    caminho_relatorio = (
        pasta_relatorios
        / "relatorio_semanal.html"
    )

    caminho_relatorio.write_text(
        html,
        encoding="utf-8"
    )

    logger.info(
        f"Relatório HTML gerado com sucesso: "
        f"{caminho_relatorio}"
    )

    return caminho_relatorio