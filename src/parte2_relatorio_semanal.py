from relatorio_html import gerar_relatorio_html
from pathlib import Path
from datetime import datetime
import argparse
import logging
import sys
import pandas as pd
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

# ==========================================================
# CONFIGURAÇÃO DE CAMINHOS
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

CAMINHO_DADOS = (
    BASE_DIR
    / "data"
    / "propostas_credito.csv"
)

PASTA_RELATORIOS = (
    BASE_DIR
    / "reports"
    / "parte2"
)

PASTA_GRAFICOS = (
    PASTA_RELATORIOS
    / "assets"
)

PASTA_LOGS = (
    BASE_DIR
    / "logs"
    / "parte2"
)

PASTA_RELATORIOS.mkdir(
    parents=True,
    exist_ok=True
)

PASTA_GRAFICOS.mkdir(
    parents=True,
    exist_ok=True
)

PASTA_LOGS.mkdir(
    parents=True,
    exist_ok=True
)


# ==========================================================
# CONFIGURAÇÃO DE LOG
# ==========================================================

momento_execucao = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

arquivo_log = (
    PASTA_LOGS
    / f"relatorio_semanal_{momento_execucao}.log"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(
            arquivo_log,
            encoding="utf-8"
        ),
        logging.StreamHandler(
            sys.stdout
        )
    ]
)

logger = logging.getLogger(__name__)

# Evita mensagens internas do Matplotlib no log da automação
logging.getLogger(
    "matplotlib"
).setLevel(
    logging.WARNING
)

# ==========================================================
# LEITURA DO ARQUIVO
# ==========================================================

def carregar_dados(caminho):
    logger.info(f"Iniciando leitura do arquivo: {caminho}")

    if not caminho.exists():
        logger.error(f"Arquivo não encontrado: {caminho}")
        raise FileNotFoundError(
            f"O arquivo de entrada não foi encontrado: {caminho}"
        )

    extensao = caminho.suffix.lower()

    try:
        if extensao == ".csv":
            df = pd.read_csv(caminho)

        elif extensao in [".xlsx", ".xls"]:
            df = pd.read_excel(caminho)

        else:
            raise ValueError(
                f"Formato não suportado: {extensao}"
            )

    except Exception as erro:
        logger.exception(
            f"Erro durante a leitura do arquivo: {erro}"
        )
        raise

    logger.info(
        f"Arquivo carregado com sucesso: "
        f"{len(df)} linhas e {len(df.columns)} colunas."
    )

    return df

# ==========================================================
# VALIDAÇÃO DA ESTRUTURA DO ARQUIVO
# ==========================================================

COLUNAS_OBRIGATORIAS = {
    "id_proposta",
    "data_entrada",
    "canal_origem",
    "tipo_imovel",
    "valor_imovel",
    "valor_solicitado",
    "etapa_max_funil",
    "status_final"
}

COLUNAS_ESPERADAS = {
    "id_proposta",
    "data_entrada",
    "canal_origem",
    "cidade",
    "uf",
    "tipo_imovel",
    "valor_imovel",
    "valor_solicitado",
    "prazo_meses",
    "score_credito",
    "idade_cliente",
    "renda_mensal_declarada",
    "flag_cliente_recorrente",
    "consultor_id",
    "etapa_max_funil",
    "status_final",
    "tempo_analise_dias",
    "data_assinatura_contrato",
    "taxa_juros_aa"
}


def validar_estrutura(df):
    logger.info("Validando estrutura do arquivo.")

    colunas_recebidas = set(df.columns)

    # Colunas essenciais que estão faltando
    faltantes_obrigatorias = (
        COLUNAS_OBRIGATORIAS - colunas_recebidas
    )

    if faltantes_obrigatorias:
        mensagem = (
            "Arquivo inválido. Colunas obrigatórias ausentes: "
            + ", ".join(sorted(faltantes_obrigatorias))
        )

        logger.error(mensagem)
        raise ValueError(mensagem)

    # Colunas esperadas, mas não essenciais
    faltantes_opcionais = (
        COLUNAS_ESPERADAS
        - COLUNAS_OBRIGATORIAS
        - colunas_recebidas
    )

    if faltantes_opcionais:
        logger.warning(
            "Colunas opcionais ausentes: "
            + ", ".join(sorted(faltantes_opcionais))
        )

    # Colunas novas/desconhecidas
    colunas_novas = colunas_recebidas - COLUNAS_ESPERADAS

    if colunas_novas:
        logger.warning(
            "Novas colunas identificadas: "
            + ", ".join(sorted(colunas_novas))
            + ". Elas serão preservadas."
        )

    logger.info("Estrutura do arquivo validada com sucesso.")

    
# ==========================================================
# TRATAMENTO DOS DADOS
# ==========================================================

def tratar_dados(df):
    logger.info("Iniciando tratamento dos dados.")

    # Trabalhamos em uma cópia para preservar o DataFrame bruto
    dados = df.copy()

    linhas_iniciais = len(dados)

    # ------------------------------------------------------
    # 1. Remoção de Terrenos
    # ------------------------------------------------------

    dados["tipo_imovel"] = (
        dados["tipo_imovel"]
        .astype("string")
        .str.strip()
    )

    quantidade_terrenos = (
        dados["tipo_imovel"] == "Terreno"
    ).sum()

    dados = dados[
        dados["tipo_imovel"] != "Terreno"
    ].copy()

    logger.info(
        f"Terrenos removidos: {quantidade_terrenos}. "
        f"Registros restantes: {len(dados)}."
    )

    # ------------------------------------------------------
    # 2. Conversão de valores monetários
    # ------------------------------------------------------

    def converter_valor(valor):
        if pd.isna(valor):
            return pd.NA

        texto = str(valor).strip()

        texto = (
            texto
            .replace("R$", "")
            .replace(" ", "")
        )

        # Formato brasileiro: 574.857,06
        if "." in texto and "," in texto:
            texto = (
                texto
                .replace(".", "")
                .replace(",", ".")
            )

        # Exemplo: 574857,06
        elif "," in texto:
            texto = texto.replace(",", ".")

        try:
            return float(texto)

        except ValueError:
            return pd.NA

    dados["valor_imovel"] = (
        dados["valor_imovel"]
        .apply(converter_valor)
    )

    dados["valor_solicitado"] = (
        dados["valor_solicitado"]
        .apply(converter_valor)
    )

    valores_imovel_invalidos = (
        dados["valor_imovel"].isna().sum()
    )

    valores_solicitados_invalidos = (
        dados["valor_solicitado"].isna().sum()
    )

    if valores_imovel_invalidos > 0:
        logger.warning(
            f"{valores_imovel_invalidos} registro(s) possuem "
            "valor_imovel inválido após a conversão."
        )

    if valores_solicitados_invalidos > 0:
        logger.warning(
            f"{valores_solicitados_invalidos} registro(s) possuem "
            "valor_solicitado inválido após a conversão."
        )

    # ------------------------------------------------------
    # 3. Padronização dos canais
    # ------------------------------------------------------

    mapa_canais = {
        "correspondente": "Correspondente",
        "indicação": "Indicação",
        "indicacao": "Indicação",
        "mídia paga": "Mídia paga",
        "midia paga": "Mídia paga",
        "organico": "Organico",
        "orgânico": "Organico",
        "parceria": "Parceria"
    }

    dados["canal_origem"] = (
        dados["canal_origem"]
        .astype("string")
        .str.strip()
        .str.lower()
        .replace(mapa_canais)
    )

    # ------------------------------------------------------
    # 4. Conversão da data de entrada
    # ------------------------------------------------------

    def converter_data_entrada(valor):
        if pd.isna(valor):
            return pd.NaT

        texto = str(valor).strip()

        formatos = [
            "%Y-%m-%d",
            "%d/%m/%Y"
        ]

        for formato in formatos:
            try:
                return pd.to_datetime(
                    texto,
                    format=formato
                )
            except (ValueError, TypeError):
                continue

        return pd.NaT

    dados["data_entrada"] = (
        dados["data_entrada"]
        .apply(converter_data_entrada)
    )

    datas_entrada_invalidas = (
        dados["data_entrada"].isna().sum()
    )

    logger.info(
        f"Datas de entrada inválidas: "
        f"{datas_entrada_invalidas}."
    )

    # ------------------------------------------------------
    # 5. Etapa do funil
    # ------------------------------------------------------

    dados["etapa_max_funil"] = pd.to_numeric(
        dados["etapa_max_funil"],
        errors="coerce"
    )

    # Preserva a coluna original
    dados["etapa_funil_analise"] = (
        dados["etapa_max_funil"].copy()
    )

    etapas_acima_6 = (
        dados["etapa_funil_analise"] > 6
    ).sum()

    if etapas_acima_6 > 0:
        logger.warning(
            f"{etapas_acima_6} registro(s) com etapa acima de 6. "
            "Para a análise do funil, foram mapeados para a etapa 6."
        )

        dados.loc[
            dados["etapa_funil_analise"] > 6,
            "etapa_funil_analise"
        ] = 6

    etapas_abaixo_1 = (
        dados["etapa_funil_analise"] < 1
    ).sum()

    if etapas_abaixo_1 > 0:
        logger.warning(
            f"{etapas_abaixo_1} registro(s) possuem "
            "etapa abaixo de 1."
        )

        dados.loc[
            dados["etapa_funil_analise"] < 1,
            "etapa_funil_analise"
        ] = pd.NA

    # ------------------------------------------------------
    # 6. Cálculo do LTV
    # ------------------------------------------------------

    dados["ltv_calculado"] = pd.NA

    imovel_valido = (
        dados["valor_imovel"].notna()
        & (dados["valor_imovel"] > 0)
    )

    dados.loc[
        imovel_valido,
        "ltv_calculado"
    ] = (
        dados.loc[
            imovel_valido,
            "valor_solicitado"
        ]
        / dados.loc[
            imovel_valido,
            "valor_imovel"
        ]
    )

    dados["ltv_calculado"] = pd.to_numeric(
        dados["ltv_calculado"],
        errors="coerce"
    )

    dados["flag_ltv_acima_60"] = (
        dados["ltv_calculado"] > 0.60
    )

    logger.info(
        f"Propostas com LTV solicitado acima de 60%: "
        f"{dados['flag_ltv_acima_60'].sum()}."
    )

    # ------------------------------------------------------
    # 7. Idade anômala
    # ------------------------------------------------------

    if "idade_cliente" in dados.columns:

        dados["idade_cliente"] = pd.to_numeric(
            dados["idade_cliente"],
            errors="coerce"
        )

        dados["flag_idade_anomala"] = (
            dados["idade_cliente"] < 18
        )

        quantidade_idades_anomalas = (
            dados["flag_idade_anomala"].sum()
        )

        if quantidade_idades_anomalas > 0:
            logger.warning(
                f"{quantidade_idades_anomalas} registro(s) "
                "com idade inferior a 18 anos. "
                "Os registros foram preservados."
            )

    # ------------------------------------------------------
    # 8. Data de assinatura
    # ------------------------------------------------------

    if "data_assinatura_contrato" in dados.columns:

        assinatura_original = (
            dados["data_assinatura_contrato"].copy()
        )

        dados["data_assinatura_contrato"] = pd.to_datetime(
            dados["data_assinatura_contrato"],
            format="%Y-%m-%d",
            errors="coerce"
        )

        # Campo preenchido, mas impossível de interpretar
        assinatura_preenchida = (
            assinatura_original.notna()
            & assinatura_original
            .astype(str)
            .str.strip()
            .ne("")
        )

        formato_assinatura_invalido = (
            assinatura_preenchida
            & dados["data_assinatura_contrato"].isna()
        )

        qtd_formato_invalido = (
            formato_assinatura_invalido.sum()
        )

        if qtd_formato_invalido > 0:
            logger.warning(
                f"{qtd_formato_invalido} registro(s) possuem "
                "formato inválido em data_assinatura_contrato."
            )

        # Data interpretável, mas cronologicamente impossível
        dados["flag_data_assinatura_invalida"] = (
            dados["data_assinatura_contrato"].notna()
            & dados["data_entrada"].notna()
            & (
                dados["data_assinatura_contrato"]
                < dados["data_entrada"]
            )
        )

        assinaturas_invalidas = (
            dados["flag_data_assinatura_invalida"].sum()
        )

        logger.info(
            f"Datas de assinatura anteriores à entrada: "
            f"{assinaturas_invalidas}."
        )

        if assinaturas_invalidas > 0:
            logger.warning(
                f"{assinaturas_invalidas} registro(s) possuem "
                "data de assinatura anterior à data de entrada. "
                "Os registros foram preservados."
            )

    # ------------------------------------------------------
    # 9. Duplicidades
    # ------------------------------------------------------

    duplicados = (
        dados["id_proposta"]
        .duplicated()
        .sum()
    )

    if duplicados > 0:
        logger.warning(
            f"{duplicados} ID(s) de proposta duplicados encontrados. "
            "Nenhum registro foi removido automaticamente."
        )

    # ------------------------------------------------------
    # 10. Flag de contratação
    # ------------------------------------------------------

    dados["contratada"] = (
        dados["etapa_funil_analise"] == 6
    )

    logger.info(
        f"Tratamento concluído. "
        f"Linhas recebidas: {linhas_iniciais}. "
        f"Linhas utilizadas: {len(dados)}."
    )

    return dados
# ==========================================================
# CÁLCULO DAS MÉTRICAS
# ==========================================================

def calcular_metricas(df):
    logger.info("Iniciando cálculo das métricas.")

    nomes_etapas = {
        1: "Simulação",
        2: "Lead",
        3: "Análise de crédito",
        4: "Avaliação do imóvel",
        5: "Formalização",
        6: "Contratação"
    }

    # ------------------------------------------------------
    # 1. Métricas gerais
    # ------------------------------------------------------

    total_propostas = len(df)

    total_contratadas = df["contratada"].sum()

    taxa_conversao = (
        total_contratadas / total_propostas * 100
        if total_propostas > 0
        else 0
    )

    volume_total = df["valor_solicitado"].sum()

    volume_contratado_proxy = (
        df.loc[
            df["contratada"],
            "valor_solicitado"
        ].sum()
    )

    volume_perdido = (
        df.loc[
            ~df["contratada"],
            "valor_solicitado"
        ].sum()
    )

    periodo_inicio = df["data_entrada"].min()
    periodo_fim = df["data_entrada"].max()

    metricas_gerais = {
        "total_propostas": total_propostas,
        "total_contratadas": int(total_contratadas),
        "taxa_conversao": taxa_conversao,
        "volume_total": volume_total,
        "volume_contratado_proxy": volume_contratado_proxy,
        "volume_perdido": volume_perdido,
        "periodo_inicio": periodo_inicio,
        "periodo_fim": periodo_fim
    }


    # ------------------------------------------------------
    # 2. Perdas por etapa
    # ------------------------------------------------------

    perdas = df[
        df["etapa_funil_analise"] < 6
    ].copy()

    perdas_por_etapa = (
        perdas
        .groupby("etapa_funil_analise")
        .agg(
            propostas_perdidas=("id_proposta", "count"),
            valor_perdido=("valor_solicitado", "sum")
        )
        .reset_index()
    )

    perdas_por_etapa["etapa"] = (
        perdas_por_etapa["etapa_funil_analise"]
        .map(nomes_etapas)
    )

    total_perdido = (
        perdas_por_etapa["valor_perdido"].sum()
    )

    perdas_por_etapa["percentual_valor_perdido"] = (
        perdas_por_etapa["valor_perdido"]
        / total_perdido
        * 100
    )


    # ------------------------------------------------------
    # 3. Conversão por canal
    # ------------------------------------------------------

    conversao_canal = (
        df
        .groupby("canal_origem")
        .agg(
            propostas=("id_proposta", "count"),
            contratadas=("contratada", "sum"),
            valor_solicitado=("valor_solicitado", "sum")
        )
        .reset_index()
    )

    conversao_canal["taxa_conversao"] = (
        conversao_canal["contratadas"]
        / conversao_canal["propostas"]
        * 100
    )

    # Volume solicitado das propostas contratadas por canal
    volume_contratado_canal = (
        df[df["contratada"]]
        .groupby("canal_origem")["valor_solicitado"]
        .sum()
    )

    conversao_canal["volume_contratado_proxy"] = (
        conversao_canal["canal_origem"]
        .map(volume_contratado_canal)
        .fillna(0)
    )

    conversao_canal["conversao_valor"] = (
        conversao_canal["volume_contratado_proxy"]
        / conversao_canal["valor_solicitado"]
        * 100
    )

    conversao_canal = conversao_canal.sort_values(
        "taxa_conversao",
        ascending=False
    )


    # ------------------------------------------------------
    # 4. Conversão mensal
    # ------------------------------------------------------

    dados_com_data = df[
        df["data_entrada"].notna()
    ].copy()

    dados_com_data["mes_entrada"] = (
        dados_com_data["data_entrada"]
        .dt.to_period("M")
    )

    conversao_mensal = (
        dados_com_data
        .groupby("mes_entrada")
        .agg(
            propostas=("id_proposta", "count"),
            contratadas=("contratada", "sum")
        )
        .reset_index()
    )

    conversao_mensal["taxa_conversao"] = (
        conversao_mensal["contratadas"]
        / conversao_mensal["propostas"]
        * 100
    )

    # Converte Period para texto para facilitar HTML/gráficos depois
    conversao_mensal["mes_entrada"] = (
        conversao_mensal["mes_entrada"]
        .astype(str)
    )


    # ------------------------------------------------------
    # 5. Motivos das perdas
    # ------------------------------------------------------

    motivos_perda = (
        perdas
        .groupby("status_final")
        .agg(
            propostas=("id_proposta", "count"),
            valor_perdido=("valor_solicitado", "sum")
        )
        .reset_index()
        .sort_values(
            "valor_perdido",
            ascending=False
        )
    )


    # ------------------------------------------------------
    # 6. Qualidade / alertas relevantes
    # ------------------------------------------------------

    alertas = {
        "ltv_acima_60": int(
            df["flag_ltv_acima_60"].sum()
        ),
        "ids_duplicados": int(
            df["id_proposta"].duplicated().sum()
        )
    }

    if "flag_idade_anomala" in df.columns:
        alertas["idades_anomalas"] = int(
            df["flag_idade_anomala"].sum()
        )

    if "flag_data_assinatura_invalida" in df.columns:
        alertas["datas_assinatura_invalidas"] = int(
            df["flag_data_assinatura_invalida"].sum()
        )


    logger.info(
        f"Métricas calculadas com sucesso. "
        f"Conversão geral: {taxa_conversao:.2f}%."
    )

    return {
        "gerais": metricas_gerais,
        "perdas_por_etapa": perdas_por_etapa,
        "conversao_canal": conversao_canal,
        "conversao_mensal": conversao_mensal,
        "motivos_perda": motivos_perda,
        "alertas": alertas
    }

# ==========================================================
# GERAÇÃO DOS GRÁFICOS
# ==========================================================

def gerar_graficos(metricas):
    logger.info("Iniciando geração dos gráficos.")

    graficos = {}

        # ------------------------------------------------------
    # 1. Perdas por etapa
    # ------------------------------------------------------

    perdas = metricas["perdas_por_etapa"].copy()

    perdas["valor_milhoes"] = (
        perdas["valor_perdido"] / 1_000_000
    )

    caminho_perdas = (
        PASTA_GRAFICOS
        / "perdas_etapa.png"
    )

    plt.figure(figsize=(10, 5))

    barras = plt.bar(
        perdas["etapa"],
        perdas["valor_milhoes"]
    )

    plt.title(
        "Volume potencial perdido por etapa"
    )
    plt.ylabel(
        "Valor solicitado (R$ milhões)"
    )
    plt.xlabel("Última etapa atingida")
    plt.xticks(rotation=20)

    for barra in barras:
        valor = barra.get_height()

        plt.text(
            barra.get_x()
            + barra.get_width() / 2,
            valor + 5,
            f"R$ {valor:.1f} mi",
            ha="center"
        )

    plt.tight_layout()
    plt.savefig(
        caminho_perdas,
        dpi=150,
        bbox_inches="tight"
    )
    plt.close()

    graficos["perdas_etapa"] = caminho_perdas


    # ------------------------------------------------------
    # 2. Conversão por canal
    # ------------------------------------------------------

    canais = (
        metricas["conversao_canal"]
        .sort_values("taxa_conversao")
        .copy()
    )

    caminho_canais = (
        PASTA_GRAFICOS
        / "conversao_canal.png"
    )

    plt.figure(figsize=(9, 5))

    barras = plt.bar(
        canais["canal_origem"],
        canais["taxa_conversao"]
    )

    plt.title(
        "Taxa de conversão por canal"
    )
    plt.ylabel("Conversão (%)")
    plt.xlabel("Canal de origem")

    for barra in barras:
        valor = barra.get_height()

        plt.text(
            barra.get_x()
            + barra.get_width() / 2,
            valor + 0.3,
            f"{valor:.1f}%",
            ha="center"
        )

    plt.tight_layout()
    plt.savefig(
        caminho_canais,
        dpi=150,
        bbox_inches="tight"
    )
    plt.close()

    graficos["conversao_canal"] = caminho_canais


    # ------------------------------------------------------
    # 3. Evolução mensal da conversão
    # ------------------------------------------------------

    mensal = metricas["conversao_mensal"].copy()

    caminho_mensal = (
        PASTA_GRAFICOS
        / "conversao_mensal.png"
    )

    plt.figure(figsize=(11, 5))

    plt.plot(
        mensal["mes_entrada"],
        mensal["taxa_conversao"],
        marker="o"
    )

    plt.title(
        "Evolução mensal da taxa de conversão"
    )
    plt.ylabel("Conversão (%)")
    plt.xlabel("Mês de entrada")
    plt.xticks(rotation=45)

    plt.grid(
        axis="y",
        alpha=0.3
    )

    plt.tight_layout()
    plt.savefig(
        caminho_mensal,
        dpi=150,
        bbox_inches="tight"
    )
    plt.close()

    graficos["conversao_mensal"] = caminho_mensal


    logger.info(
        f"{len(graficos)} gráficos gerados com sucesso."
    )

    return graficos

# ==========================================================
# ARGUMENTOS DE EXECUÇÃO
# ==========================================================

def obter_argumentos():
    parser = argparse.ArgumentParser(
        description="Gera o relatório semanal do funil de crédito."
    )

    parser.add_argument(
        "arquivo",
        nargs="?",
        default=str(CAMINHO_DADOS),
        help=(
            "Caminho do arquivo de entrada. "
            "Se não informado, utiliza data/propostas_credito.csv."
        )
    )

    return parser.parse_args()


# ==========================================================
# EXECUÇÃO
# ==========================================================
if __name__ == "__main__":
    logger.info("=== INÍCIO DA AUTOMAÇÃO ===")

    try:
        argumentos = obter_argumentos()

        caminho_entrada = Path(argumentos.arquivo)

        # 1. Leitura
        dados_brutos = carregar_dados(
            caminho_entrada
        )

        # 2. Validação
        validar_estrutura(
            dados_brutos
        )

        # 3. Tratamento
        dados_tratados = tratar_dados(
            dados_brutos
        )

        # 4. Métricas
        metricas = calcular_metricas(
            dados_tratados
        )

        # 5. Gráficos
        graficos = gerar_graficos(
            metricas
        )

        # 6. Relatório HTML
        relatorio = gerar_relatorio_html(
            metricas,
            graficos,
            PASTA_RELATORIOS,
            momento_execucao,
            logger
        )

        print("\n================================")
        print("RELATÓRIO GERADO COM SUCESSO")
        print("================================")
        print(f"Arquivo: {relatorio}")

        logger.info(
            "=== AUTOMAÇÃO CONCLUÍDA COM SUCESSO ==="
        )

    except Exception as erro:
        logger.exception(
            f"A automação foi interrompida: {erro}"
        )

        sys.exit(1)