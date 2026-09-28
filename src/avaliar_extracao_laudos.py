import json
import re
import unicodedata
from pathlib import Path

import pandas as pd


# =========================================================
# CAMINHOS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

PASTA_RELATORIOS = (
    BASE_DIR
    / "reports"
    / "parte3"
)

PASTA_RELATORIOS.mkdir(
    parents=True,
    exist_ok=True
)

CAMINHO_GABARITO = (
    BASE_DIR
    / "data"
    / "gabarito_laudos.json"
)

CAMINHO_EXTRACAO = (
     PASTA_RELATORIOS
    / "extracao_laudos.json"
)

CAMINHO_DETALHES = (
    PASTA_RELATORIOS
    / "avaliacao_extracao_laudos.csv"
)

CAMINHO_METRICAS = (
    PASTA_RELATORIOS
    / "metricas_extracao_laudos.json"
)

# =========================================================
# CAMPOS AVALIADOS
#
# São exatamente os 9 macrocampos pedidos no case.
# =========================================================

CAMPOS_AVALIADOS = [
    "tipo_imovel",
    "endereco",
    "areas",
    "ano",
    "valor_avaliacao_brl",
    "matricula",
    "onus",
    "data_vistoria",
    "responsavel_tecnico"
]


# =========================================================
# LEITURA
# =========================================================

def carregar_json(caminho: Path):

    if not caminho.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {caminho}"
        )

    with open(
        caminho,
        "r",
        encoding="utf-8"
    ) as arquivo:

        return json.load(arquivo)


# =========================================================
# NORMALIZAÇÕES PARA COMPARAÇÃO
# =========================================================

def remover_acentos(texto: str) -> str:

    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    return "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(
            caractere
        )
    )


def normalizar_texto(valor):

    if valor is None:
        return None

    texto = str(valor).strip().lower()

    texto = remover_acentos(
        texto
    )

    # Espaços duplicados
    texto = " ".join(
        texto.split()
    )

    # Padroniza pequenos detalhes de pontuação
    texto = re.sub(
        r"\s*([,;/\-])\s*",
        r"\1",
        texto
    )

    return texto


def numeros_iguais(
    esperado,
    obtido,
    tolerancia=0.01
):

    if esperado is None and obtido is None:
        return True

    if esperado is None or obtido is None:
        return False

    try:

        return abs(
            float(esperado)
            - float(obtido)
        ) <= tolerancia

    except (
        TypeError,
        ValueError
    ):

        return False


# =========================================================
# COMPARAÇÃO DOS MACROCAMPOS
# =========================================================

def comparar_texto(
    esperado,
    obtido
):

    return (
        normalizar_texto(esperado)
        ==
        normalizar_texto(obtido)
    )


def comparar_areas(
    esperado: dict,
    obtido: dict
):

    campos_area = [
        "terreno_m2",
        "construida_m2",
        "coberta_m2",
        "privativa_m2",
        "total_m2",
        "util_m2",
        "comum_m2"
    ]

    for campo in campos_area:

        valor_esperado = esperado.get(
            campo
        )

        valor_obtido = obtido.get(
            campo
        )

        if not numeros_iguais(
            valor_esperado,
            valor_obtido
        ):

            return False

    return True


def comparar_responsavel(
    esperado: dict,
    obtido: dict
):

    nome_correto = comparar_texto(
        esperado.get("nome"),
        obtido.get("nome")
    )

    registro_correto = comparar_texto(
        esperado.get("registro"),
        obtido.get("registro")
    )

    return (
        nome_correto
        and registro_correto
    )


def comparar_campo(
    campo,
    esperado,
    obtido
):

    if campo in {
        "tipo_imovel",
        "endereco",
        "matricula",
        "data_vistoria"
    }:

        return comparar_texto(
            esperado,
            obtido
        )


    if campo in {
        "ano",
        "valor_avaliacao_brl"
    }:

        return numeros_iguais(
            esperado,
            obtido
        )


    if campo == "areas":

        return comparar_areas(
            esperado,
            obtido
        )


    if campo == "onus":

        # No gabarito avaliamos a classificação,
        # não a redação da descrição.
        return comparar_texto(
            esperado,
            obtido.get("status")
        )


    if campo == "responsavel_tecnico":

        return comparar_responsavel(
            esperado,
            obtido
        )


    return False


# =========================================================
# PREPARAÇÃO DO RESULTADO PARA COMPARAÇÃO
# =========================================================

def obter_valor_esperado(
    registro,
    campo
):

    if campo == "onus":

        return registro.get(
            "onus_status"
        )

    return registro.get(
        campo
    )


def obter_valor_obtido(
    registro,
    campo
):

    return registro.get(
        campo
    )


# =========================================================
# MÉTRICA DE ALUCINAÇÃO
#
# Avaliamos campos atômicos que deveriam permanecer null.
#
# Exemplo:
# gabarito: area_total_m2 = null
# extrator: area_total_m2 = 95
#
# Isso conta como preenchimento sem suporte.
# =========================================================

def contar_alucinacoes(
    esperado,
    obtido
):

    oportunidades = 0
    alucinacoes = 0

    # Áreas
    areas_esperadas = esperado.get(
        "areas",
        {}
    )

    areas_obtidas = obtido.get(
        "areas",
        {}
    )

    for campo, valor_esperado in (
        areas_esperadas.items()
    ):

        if valor_esperado is None:

            oportunidades += 1

            if (
                areas_obtidas.get(campo)
                is not None
            ):
                alucinacoes += 1


    # Ano
    if esperado.get("ano") is None:

        oportunidades += 1

        if obtido.get("ano") is not None:
            alucinacoes += 1


    # Matrícula
    if esperado.get("matricula") is None:

        oportunidades += 1

        if (
            obtido.get("matricula")
            is not None
        ):
            alucinacoes += 1


    return (
        alucinacoes,
        oportunidades
    )


# =========================================================
# AVALIAÇÃO
# =========================================================

def avaliar():

    gabarito = carregar_json(
        CAMINHO_GABARITO
    )

    extracoes = carregar_json(
        CAMINHO_EXTRACAO
    )


    # Indexa pelo nome do arquivo
    gabarito_por_arquivo = {
        item["arquivo"]: item
        for item in gabarito
    }

    extracao_por_arquivo = {
        item["arquivo"]: item
        for item in extracoes
    }


    detalhes = []

    acertos_por_campo = {
        campo: 0
        for campo in CAMPOS_AVALIADOS
    }

    total_por_campo = {
        campo: 0
        for campo in CAMPOS_AVALIADOS
    }

    total_acertos = 0
    total_avaliacoes = 0

    total_alucinacoes = 0
    total_oportunidades_alucinacao = 0

    ausencias_corretas = 0
    total_ausencias = 0

    divergencias_corretas = 0
    total_divergencias = 0


    # =====================================================
    # PERCORRE O GABARITO
    # =====================================================

    for nome_arquivo, esperado in (
        gabarito_por_arquivo.items()
    ):

        obtido = extracao_por_arquivo.get(
            nome_arquivo
        )


        # Se o laudo nem foi processado,
        # todos os nove macrocampos contam como erro.
        if obtido is None:

            for campo in CAMPOS_AVALIADOS:

                detalhes.append({
                    "arquivo":
                        nome_arquivo,

                    "campo":
                        campo,

                    "correto":
                        False,

                    "esperado":
                        json.dumps(
                            obter_valor_esperado(
                                esperado,
                                campo
                            ),
                            ensure_ascii=False
                        ),

                    "obtido":
                        "LAUDO NÃO PROCESSADO"
                })

                total_por_campo[campo] += 1

                total_avaliacoes += 1

            continue


        # =================================================
        # 9 MACROCAMPOS
        # =================================================

        for campo in CAMPOS_AVALIADOS:

            valor_esperado = (
                obter_valor_esperado(
                    esperado,
                    campo
                )
            )

            valor_obtido = (
                obter_valor_obtido(
                    obtido,
                    campo
                )
            )

            correto = comparar_campo(
                campo,
                valor_esperado,
                valor_obtido
            )

            total_por_campo[campo] += 1

            total_avaliacoes += 1

            if correto:

                acertos_por_campo[
                    campo
                ] += 1

                total_acertos += 1


            detalhes.append({
                "arquivo":
                    nome_arquivo,

                "campo":
                    campo,

                "correto":
                    correto,

                "esperado":
                    json.dumps(
                        valor_esperado,
                        ensure_ascii=False
                    ),

                "obtido":
                    json.dumps(
                        valor_obtido,
                        ensure_ascii=False
                    )
            })


        # =================================================
        # ALUCINAÇÕES
        # =================================================

        (
            alucinacoes,
            oportunidades
        ) = contar_alucinacoes(
            esperado,
            obtido
        )

        total_alucinacoes += (
            alucinacoes
        )

        total_oportunidades_alucinacao += (
            oportunidades
        )


        # =================================================
        # CAMPOS AUSENTES
        # =================================================

        ausentes_esperados = set(
            esperado.get(
                "campos_ausentes_esperados",
                []
            )
        )

        ausentes_obtidos = set(
            obtido.get(
                "campos_ausentes",
                []
            )
        )

        if ausentes_esperados:

            total_ausencias += 1

            if (
                ausentes_esperados
                == ausentes_obtidos
            ):
                ausencias_corretas += 1


        # =================================================
        # DIVERGÊNCIAS
        # =================================================

        divergencias_esperadas = set(
            esperado.get(
                "divergencias_esperadas",
                []
            )
        )

        divergencias_obtidas = {
            item.get("campo")
            for item
            in obtido.get(
                "divergencias",
                []
            )
        }

        if divergencias_esperadas:

            total_divergencias += 1

            if (
                divergencias_esperadas
                <= divergencias_obtidas
            ):
                divergencias_corretas += 1


    # =====================================================
    # MÉTRICAS
    # =====================================================

    acuracia_geral = (
        total_acertos
        / total_avaliacoes
        * 100
        if total_avaliacoes
        else 0
    )


    acuracia_por_campo = {}

    for campo in CAMPOS_AVALIADOS:

        total = total_por_campo[
            campo
        ]

        acertos = acertos_por_campo[
            campo
        ]

        acuracia_por_campo[
            campo
        ] = round(
            (
                acertos
                / total
                * 100
            )
            if total
            else 0,
            2
        )


    taxa_alucinacao = (
        total_alucinacoes
        / total_oportunidades_alucinacao
        * 100
        if total_oportunidades_alucinacao
        else 0
    )


    taxa_ausencias = (
        ausencias_corretas
        / total_ausencias
        * 100
        if total_ausencias
        else 0
    )


    taxa_divergencias = (
        divergencias_corretas
        / total_divergencias
        * 100
        if total_divergencias
        else 0
    )


    metricas = {
        "laudos_no_gabarito":
            len(gabarito),

        "laudos_processados":
            len(extracoes),

        "macrocampos_por_laudo":
            len(CAMPOS_AVALIADOS),

        "total_avaliacoes":
            total_avaliacoes,

        "total_acertos":
            total_acertos,

        "acuracia_geral_pct":
            round(
                acuracia_geral,
                2
            ),

        "acuracia_por_campo_pct":
            acuracia_por_campo,

        "alucinacoes":
            total_alucinacoes,

        "oportunidades_de_alucinacao":
            total_oportunidades_alucinacao,

        "taxa_alucinacao_pct":
            round(
                taxa_alucinacao,
                2
            ),

        "casos_com_campos_ausentes":
            total_ausencias,

        "ausencias_identificadas_corretamente":
            ausencias_corretas,

        "taxa_acerto_ausencias_pct":
            round(
                taxa_ausencias,
                2
            ),

        "casos_com_divergencia":
            total_divergencias,

        "divergencias_identificadas_corretamente":
            divergencias_corretas,

        "taxa_acerto_divergencias_pct":
            round(
                taxa_divergencias,
                2
            )
    }


    # =====================================================
    # EXPORTAÇÃO
    # =====================================================

    df_detalhes = pd.DataFrame(
        detalhes
    )

    df_detalhes.to_csv(
        CAMINHO_DETALHES,
        index=False,
        encoding="utf-8-sig"
    )


    with open(
        CAMINHO_METRICAS,
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            metricas,
            arquivo,
            ensure_ascii=False,
            indent=2
        )


    # =====================================================
    # TERMINAL
    # =====================================================

    print()
    print(
        "===== AVALIAÇÃO DA EXTRAÇÃO ====="
    )

    print(
        f"Laudos avaliados: "
        f"{len(gabarito)}"
    )

    print(
        f"Macrocampos avaliados: "
        f"{total_avaliacoes}"
    )

    print(
        f"Acertos: "
        f"{total_acertos}"
    )

    print(
        f"Acurácia geral: "
        f"{acuracia_geral:.2f}%"
    )

    print()

    print(
        "Acurácia por campo:"
    )

    for campo, percentual in (
        acuracia_por_campo.items()
    ):

        print(
            f"- {campo}: "
            f"{percentual:.2f}%"
        )

    print()

    print(
        "Taxa de alucinação: "
        f"{taxa_alucinacao:.2f}% "
        f"({total_alucinacoes}/"
        f"{total_oportunidades_alucinacao})"
    )

    print(
        "Acerto em campos ausentes: "
        f"{taxa_ausencias:.2f}% "
        f"({ausencias_corretas}/"
        f"{total_ausencias})"
    )

    print(
        "Acerto em divergências: "
        f"{taxa_divergencias:.2f}% "
        f"({divergencias_corretas}/"
        f"{total_divergencias})"
    )

    print()

    print(
        "Arquivos gerados:"
    )

    print(
        "reports/parte3/avaliacao_extracao_laudos.csv"
    )

    print(
        "reports/parte3/metricas_extracao_laudos.json"
    )


# =========================================================
# EXECUÇÃO
# =========================================================

if __name__ == "__main__":
    avaliar()