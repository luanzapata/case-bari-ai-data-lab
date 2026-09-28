import json
import logging
import os
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import BaseModel


# =========================================================
# CAMINHOS E CONFIGURAÇÃO
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

PASTA_LAUDOS = (
    BASE_DIR
    / "data"
    / "laudos_avaliacao"
)

PASTA_RELATORIOS = (
    BASE_DIR
    / "reports"
    / "parte3"
)

PASTA_LOGS = (
    BASE_DIR
    / "logs"
    / "parte3"
)

PASTA_RELATORIOS.mkdir(
    parents=True,
    exist_ok=True
)

PASTA_LOGS.mkdir(
    parents=True,
    exist_ok=True
)

load_dotenv(BASE_DIR / ".env")

CHAVE_API = os.getenv("GEMINI_API_KEY")

MODELO = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite"
)

INTERVALO_ENTRE_LAUDOS = 5

if not CHAVE_API:
    raise ValueError(
        "GEMINI_API_KEY não encontrada no arquivo .env."
    )


# =========================================================
# LOG
# =========================================================

momento_execucao = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

arquivo_log = (
    PASTA_LOGS
    / f"extracao_laudos_{momento_execucao}.log"
)

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s | %(message)s"
    ),
    handlers=[
        logging.FileHandler(
            arquivo_log,
            encoding="utf-8"
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# =========================================================
# CLIENTE GEMINI
# =========================================================

client = genai.Client(
    api_key=CHAVE_API
)


# =========================================================
# SCHEMA DA EXTRAÇÃO BRUTA DA IA
#
# A IA somente interpreta e extrai informações.
# Tratamento e decisões finais ficam no Python.
# =========================================================

class TextoEncontrado(BaseModel):
    valor_texto: str
    evidencia: str


class AreaEncontrada(BaseModel):
    rotulo: str
    valor_texto: str
    unidade: str | None
    evidencia: str


class AnoEncontrado(BaseModel):
    tipo: str
    valor_texto: str
    contexto: str | None
    evidencia: str


class OnusEncontrado(BaseModel):
    classificacao: str
    texto: str
    evidencia: str


class ResponsavelEncontrado(BaseModel):
    nome: str
    registro: str | None
    evidencia: str


class ExtracaoBrutaIA(BaseModel):
    tipos_imovel: list[TextoEncontrado]
    enderecos: list[TextoEncontrado]
    areas: list[AreaEncontrada]
    anos: list[AnoEncontrado]
    valores_avaliacao: list[TextoEncontrado]
    matriculas: list[TextoEncontrado]
    onus: list[OnusEncontrado]
    datas_vistoria: list[TextoEncontrado]
    responsaveis_tecnicos: list[ResponsavelEncontrado]


# =========================================================
# PROMPT
# =========================================================

INSTRUCOES = """
Você é responsável SOMENTE por identificar informações
explicitamente presentes em um laudo de avaliação imobiliária.

Não produza o resultado final da análise.

Não escolha entre informações conflitantes.

Não normalize números, valores monetários, datas ou unidades.

Não calcule informações que não estejam escritas.

REGRAS:

1. Nunca invente informações.

2. Quando uma informação não aparecer, retorne uma lista vazia
para aquele campo.

3. Capture TODAS as ocorrências relevantes.

Se dois valores diferentes aparecerem para o mesmo campo,
extraia os dois. Não escolha qual está correto.

4. Preserve números e valores monetários como aparecem
no documento.

Exemplo:

R$ 642.000,00

deve permanecer:

R$ 642.000,00

5. Para cada área encontrada, informe:

- rotulo;
- valor_texto;
- unidade;
- evidencia.

Exemplos de rótulos:

área do terreno
área construída
área coberta
área privativa
área total
área útil
área comum

Quando um segundo valor estiver comparando ou contradizendo
um valor anterior e o nome do campo não for repetido,
identifique pelo contexto qual campo está sendo referido.

Exemplo:

"No cabeçalho consta área total 95 m²,
porém a tabela interna registra 92 m²."

Extraia as duas ocorrências como "área total".

Não resolva a contradição.

6. Para informações relacionadas a ano, utilize:

ANO:
quando existe um ano explícito.

IDADE:
quando existe apenas idade ou idade aparente.

NAO_APLICAVEL:
quando o próprio documento afirma que ano não se aplica
ou que não existe edificação.

Não transforme idade em ano.

7. Para matrícula, extraia somente seu identificador.

Exemplo:

"Matrícula 184.772 do 14º CRI de São Paulo"

deve gerar:

184.772

8. Para informações de ônus, classifique semanticamente como:

SEM_ONUS:
o documento confirma que não existem ônus ou gravames.

COM_ONUS:
o documento informa algum ônus ou gravame existente.

NAO_INFORMADO:
o documento afirma que não existe informação suficiente.

NAO_VERIFICADO:
existe uma declaração, mas o documento informa que não foi
possível confirmar por falta de certidão ou documentação.

9. Para responsável técnico:

- nome deve conter somente o nome da pessoa;
- Eng., Arq., Perito e títulos semelhantes não fazem parte do nome;
- registro profissional deve ficar separado.

10. "evidencia" deve conter um trecho curto do documento que
sustente a informação extraída.

11. Não utilize conhecimento externo.

12. Não resolva inconsistências ou divergências.

O Python será responsável posteriormente por:

- normalização;
- conversão de unidades;
- tratamento de valores ausentes;
- identificação de divergências;
- definição do status final.
"""


# =========================================================
# LEITURA DOS ARQUIVOS
# =========================================================

def ler_laudo(caminho: Path) -> str:

    try:
        return caminho.read_text(
            encoding="utf-8-sig"
        )

    except UnicodeDecodeError:

        logger.warning(
            f"{caminho.name}: UTF-8 falhou. "
            "Tentando latin-1."
        )

        return caminho.read_text(
            encoding="latin-1"
        )


# =========================================================
# EXTRAÇÃO COM IA + RETRY
# =========================================================

def extrair_com_ia(
    texto: str,
    nome_arquivo: str,
    tentativas_maximas: int = 3
) -> ExtracaoBrutaIA:

    prompt = f"""
{INSTRUCOES}

ARQUIVO:
{nome_arquivo}

DOCUMENTO:

{texto}
"""

    for tentativa in range(
        1,
        tentativas_maximas + 1
    ):

        try:

            logger.info(
                f"{nome_arquivo}: "
                f"tentativa {tentativa}/"
                f"{tentativas_maximas}."
            )

            response = client.models.generate_content(
                model=MODELO,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type=(
                        "application/json"
                    ),
                    response_schema=ExtracaoBrutaIA,
                ),
            )

            return (
                ExtracaoBrutaIA
                .model_validate_json(
                    response.text
                )
            )

        except errors.ServerError as erro:

            if tentativa == tentativas_maximas:
                raise

            espera = 5 * tentativa

            logger.warning(
                f"{nome_arquivo}: "
                "Gemini temporariamente indisponível. "
                f"Nova tentativa em {espera}s. "
                f"Erro: {erro}"
            )

            time.sleep(espera)


        except errors.ClientError as erro:

            mensagem_erro = str(erro)

            if (
                "429" not in mensagem_erro
                and "RESOURCE_EXHAUSTED"
                not in mensagem_erro
            ):
                raise

            if tentativa == tentativas_maximas:
                raise

            espera = 30

            logger.warning(
                f"{nome_arquivo}: limite de requisições "
                f"da API atingido. "
                f"Nova tentativa em {espera}s."
            )

            time.sleep(
                espera
            )    

    raise RuntimeError(
        f"Não foi possível extrair {nome_arquivo}."
    )


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def limpar_texto(
    valor: str
) -> str:

    return " ".join(
        valor.strip().split()
    )


def remover_acentos(
    valor: str
) -> str:

    normalizado = unicodedata.normalize(
        "NFKD",
        valor
    )

    return "".join(
        caractere
        for caractere in normalizado
        if not unicodedata.combining(
            caractere
        )
    )


# =========================================================
# NORMALIZAÇÃO NUMÉRICA
# =========================================================

def normalizar_numero(
    valor_texto: str
) -> float | None:

    encontrados = re.findall(
        r"-?\d[\d.,]*",
        valor_texto
    )

    if not encontrados:
        return None

    valor = encontrados[0]

    # Exemplo:
    # 1.275.000,00
    if "," in valor:

        valor = (
            valor
            .replace(".", "")
            .replace(",", ".")
        )

    elif "." in valor:

        partes = valor.split(".")

        # Detecta pontos usados como separador
        # de milhares.
        #
        # 1.020
        # 3.900.000

        if (
            len(partes) > 1
            and all(
                len(parte) == 3
                for parte in partes[1:]
            )
        ):

            valor = "".join(partes)

    try:

        return float(valor)

    except ValueError:

        return None


# =========================================================
# NORMALIZAÇÃO DE ÁREAS
# =========================================================

def normalizar_area(
    valor_texto: str,
    unidade: str | None
) -> float | None:

    valor = normalizar_numero(
        valor_texto
    )

    if valor is None:
        return None

    texto_unidade = (
        unidade
        if unidade
        else valor_texto
    )

    unidade_normalizada = remover_acentos(
        texto_unidade.lower()
    )

    unidade_normalizada = (
        unidade_normalizada
        .replace("²", "2")
        .strip()
    )

    # hectare → m²
    if (
        "hectare" in unidade_normalizada
        or re.search(
            r"\bha\b",
            unidade_normalizada
        )
    ):

        return valor * 10000

    return valor


# =========================================================
# CLASSIFICAÇÃO DE ÁREAS
# =========================================================

def classificar_tipo_area(
    rotulo: str
) -> str | None:

    if not rotulo:
        return None

    texto = remover_acentos(
        rotulo.lower().strip()
    )

    if (
        "terreno" in texto
        or "lote" in texto
        or "superficie" in texto
    ):
        return "terreno_m2"

    if (
        "construida" in texto
        or "edificada" in texto
        or "benfeitoria" in texto
    ):
        return "construida_m2"

    if "coberta" in texto:
        return "coberta_m2"

    if "privativa" in texto:
        return "privativa_m2"

    if "total" in texto:
        return "total_m2"

    if "util" in texto:
        return "util_m2"

    if "comum" in texto:
        return "comum_m2"

    return None


# =========================================================
# TRATAMENTO DAS ÁREAS
# =========================================================

def tratar_areas(
    mencoes: list[AreaEncontrada],
    divergencias: list[dict]
) -> dict:

    resultado = {
        "terreno_m2": None,
        "construida_m2": None,
        "coberta_m2": None,
        "privativa_m2": None,
        "total_m2": None,
        "util_m2": None,
        "comum_m2": None
    }

    agrupadas = {}

    for mencao in mencoes:

        campo = classificar_tipo_area(
            mencao.rotulo
        )

        if campo is None:

            logger.warning(
                "Área não classificada: "
                f"'{mencao.rotulo}'"
            )

            continue

        agrupadas.setdefault(
            campo,
            []
        ).append(mencao)

    for campo_final, lista_mencoes in (
        agrupadas.items()
    ):

        valores_normalizados = []
        evidencias = []

        for mencao in lista_mencoes:

            valor = normalizar_area(
                valor_texto=(
                    mencao.valor_texto
                ),
                unidade=mencao.unidade
            )

            if valor is not None:

                valores_normalizados.append(
                    valor
                )

                evidencias.append(
                    mencao.evidencia
                )

        valores_unicos = list(
            dict.fromkeys(
                valores_normalizados
            )
        )

        if len(valores_unicos) == 1:

            resultado[campo_final] = (
                valores_unicos[0]
            )

        elif len(valores_unicos) > 1:

            resultado[campo_final] = None

            divergencias.append({
                "campo":
                    f"areas.{campo_final}",

                "valores_encontrados":
                    valores_unicos,

                "descricao":
                    "Foram encontrados valores "
                    "diferentes para o mesmo "
                    "tipo de área.",

                "evidencias":
                    evidencias
            })

    return resultado


# =========================================================
# TEXTOS SIMPLES
# =========================================================

def resolver_textos(
    mencoes: list[TextoEncontrado],
    campo: str,
    divergencias: list[dict]
) -> str | None:

    if not mencoes:
        return None

    valores = [
        limpar_texto(
            mencao.valor_texto
        )
        for mencao in mencoes
    ]

    valores_unicos = list(
        dict.fromkeys(
            valores
        )
    )

    if len(valores_unicos) == 1:

        return valores_unicos[0]

    divergencias.append({
        "campo":
            campo,

        "valores_encontrados":
            valores_unicos,

        "descricao":
            f"Foram encontrados valores "
            f"diferentes para {campo}.",

        "evidencias": [
            mencao.evidencia
            for mencao in mencoes
        ]
    })

    return None


# =========================================================
# VALORES MONETÁRIOS
# =========================================================

def resolver_numeros(
    mencoes: list[TextoEncontrado],
    campo: str,
    divergencias: list[dict]
) -> float | None:

    if not mencoes:
        return None

    valores = []

    for mencao in mencoes:

        numero = normalizar_numero(
            mencao.valor_texto
        )

        if numero is not None:
            valores.append(numero)

    valores_unicos = list(
        dict.fromkeys(
            valores
        )
    )

    if len(valores_unicos) == 1:

        return valores_unicos[0]

    if len(valores_unicos) > 1:

        divergencias.append({
            "campo":
                campo,

            "valores_encontrados":
                valores_unicos,

            "descricao":
                f"Foram encontrados valores "
                f"diferentes para {campo}.",

            "evidencias": [
                mencao.evidencia
                for mencao in mencoes
            ]
        })

    return None


# =========================================================
# ANO
# =========================================================

def tratar_ano(
    mencoes: list[AnoEncontrado],
    divergencias: list[dict]
) -> tuple[
    int | None,
    str | None,
    bool
]:

    if not mencoes:
        return None, None, True

    anos = [
        mencao
        for mencao in mencoes
        if mencao.tipo.upper() == "ANO"
    ]

    idades = [
        mencao
        for mencao in mencoes
        if mencao.tipo.upper() == "IDADE"
    ]

    nao_aplicavel = [
        mencao
        for mencao in mencoes
        if mencao.tipo.upper()
        == "NAO_APLICAVEL"
    ]

    if anos:

        valores = []

        for mencao in anos:

            encontrado = re.search(
                r"\b(18|19|20)\d{2}\b",
                mencao.valor_texto
            )

            if encontrado:

                valores.append(
                    int(
                        encontrado.group()
                    )
                )

        valores_unicos = list(
            dict.fromkeys(
                valores
            )
        )

        if len(valores_unicos) == 1:

            return (
                valores_unicos[0],
                anos[0].contexto,
                False
            )

        if len(valores_unicos) > 1:

            divergencias.append({
                "campo":
                    "ano",

                "valores_encontrados":
                    valores_unicos,

                "descricao":
                    "Foram encontrados anos "
                    "diferentes no documento.",

                "evidencias": [
                    mencao.evidencia
                    for mencao in anos
                ]
            })

            return None, None, False

    if nao_aplicavel:

        contexto = (
            nao_aplicavel[0].contexto
            or nao_aplicavel[0].valor_texto
        )

        return (
            None,
            contexto,
            False
        )

    if idades:

        contexto = (
            "Idade informada no documento: "
            + ", ".join(
                mencao.valor_texto
                for mencao in idades
            )
        )

        # Não calcula ano a partir da idade.
        return (
            None,
            contexto,
            True
        )

    return None, None, True


# =========================================================
# DATAS
# =========================================================

MESES_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12
}


def normalizar_data(
    valor_texto: str
) -> str | None:

    valor = limpar_texto(
        valor_texto
    )

    formatos = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d"
    ]

    for formato in formatos:

        try:

            data = datetime.strptime(
                valor,
                formato
            )

            return (
                data
                .date()
                .isoformat()
            )

        except ValueError:

            pass

    valor_sem_acento = remover_acentos(
        valor.lower()
    )

    padrao = re.search(
        r"(\d{1,2})\s+de\s+"
        r"([a-z]+)\s+de\s+"
        r"(\d{4})",
        valor_sem_acento
    )

    if padrao:

        dia = int(
            padrao.group(1)
        )

        mes_texto = (
            padrao.group(2)
        )

        ano = int(
            padrao.group(3)
        )

        mes = MESES_PT.get(
            mes_texto
        )

        if mes:

            try:

                return datetime(
                    ano,
                    mes,
                    dia
                ).date().isoformat()

            except ValueError:

                return None

    return None


def tratar_datas(
    mencoes: list[TextoEncontrado],
    divergencias: list[dict]
) -> str | None:

    if not mencoes:
        return None

    valores = []

    for mencao in mencoes:

        data = normalizar_data(
            mencao.valor_texto
        )

        if data:
            valores.append(data)

    valores_unicos = list(
        dict.fromkeys(
            valores
        )
    )

    if len(valores_unicos) == 1:

        return valores_unicos[0]

    if len(valores_unicos) > 1:

        divergencias.append({
            "campo":
                "data_vistoria",

            "valores_encontrados":
                valores_unicos,

            "descricao":
                "Foram encontradas datas "
                "de vistoria diferentes.",

            "evidencias": [
                mencao.evidencia
                for mencao in mencoes
            ]
        })

    return None


# =========================================================
# ÔNUS
# =========================================================

STATUS_ONUS_VALIDOS = {
    "SEM_ONUS",
    "COM_ONUS",
    "NAO_INFORMADO",
    "NAO_VERIFICADO"
}


def tratar_onus(
    mencoes: list[OnusEncontrado],
    divergencias: list[dict]
) -> dict:

    if not mencoes:

        return {
            "status":
                "NAO_INFORMADO",

            "descricao":
                None
        }

    status = []

    descricoes = []

    for mencao in mencoes:

        classificacao = (
            mencao
            .classificacao
            .upper()
            .strip()
        )

        if (
            classificacao
            in STATUS_ONUS_VALIDOS
        ):

            status.append(
                classificacao
            )

        descricoes.append(
            limpar_texto(
                mencao.texto
            )
        )

    status_unicos = list(
        dict.fromkeys(
            status
        )
    )

    descricoes_unicas = list(
        dict.fromkeys(
            descricoes
        )
    )

    if len(status_unicos) == 1:

        return {
            "status":
                status_unicos[0],

            "descricao":
                " | ".join(
                    descricoes_unicas
                )
        }

    divergencias.append({
        "campo":
            "onus",

        "valores_encontrados":
            status_unicos,

        "descricao":
            "O documento apresenta "
            "informações conflitantes "
            "sobre ônus.",

        "evidencias": [
            mencao.evidencia
            for mencao in mencoes
        ]
    })

    return {
        "status":
            None,

        "descricao":
            " | ".join(
                descricoes_unicas
            )
    }


# =========================================================
# RESPONSÁVEL TÉCNICO
# =========================================================

def tratar_responsavel(
    mencoes: list[ResponsavelEncontrado],
    divergencias: list[dict]
) -> dict:

    if not mencoes:

        return {
            "nome": None,
            "registro": None
        }

    valores = []

    for mencao in mencoes:

        nome = limpar_texto(
            mencao.nome
        )

        registro = (
            limpar_texto(
                mencao.registro
            )
            if mencao.registro
            else None
        )

        valores.append(
            (
                nome,
                registro
            )
        )

    valores_unicos = list(
        dict.fromkeys(
            valores
        )
    )

    if len(valores_unicos) == 1:

        nome, registro = (
            valores_unicos[0]
        )

        return {
            "nome":
                nome,

            "registro":
                registro
        }

    divergencias.append({
        "campo":
            "responsavel_tecnico",

        "valores_encontrados": [
            {
                "nome": nome,
                "registro": registro
            }
            for nome, registro
            in valores_unicos
        ],

        "descricao":
            "Foram encontrados responsáveis "
            "técnicos diferentes.",

        "evidencias": [
            mencao.evidencia
            for mencao in mencoes
        ]
    })

    return {
        "nome": None,
        "registro": None
    }


# =========================================================
# TRATAMENTO FINAL
# =========================================================

def tratar_extracao(
    bruto: ExtracaoBrutaIA
) -> dict:

    divergencias = []

    tipo_imovel = resolver_textos(
        bruto.tipos_imovel,
        "tipo_imovel",
        divergencias
    )

    endereco = resolver_textos(
        bruto.enderecos,
        "endereco",
        divergencias
    )

    areas = tratar_areas(
        bruto.areas,
        divergencias
    )

    (
        ano,
        ano_contexto,
        ano_ausente
    ) = tratar_ano(
        bruto.anos,
        divergencias
    )

    valor_avaliacao = (
        resolver_numeros(
            bruto.valores_avaliacao,
            "valor_avaliacao_brl",
            divergencias
        )
    )

    matricula = resolver_textos(
        bruto.matriculas,
        "matricula",
        divergencias
    )

    onus = tratar_onus(
        bruto.onus,
        divergencias
    )

    data_vistoria = tratar_datas(
        bruto.datas_vistoria,
        divergencias
    )

    responsavel = tratar_responsavel(
        bruto.responsaveis_tecnicos,
        divergencias
    )


    # =====================================================
    # CAMPOS AUSENTES
    # =====================================================

    campos_ausentes = []

    if not bruto.tipos_imovel:
        campos_ausentes.append(
            "tipo_imovel"
        )

    if not bruto.enderecos:
        campos_ausentes.append(
            "endereco"
        )

    if not bruto.areas:
        campos_ausentes.append(
            "areas"
        )

    if ano_ausente:
        campos_ausentes.append(
            "ano"
        )

    if not bruto.valores_avaliacao:
        campos_ausentes.append(
            "valor_avaliacao_brl"
        )

    if not bruto.matriculas:
        campos_ausentes.append(
            "matricula"
        )

    if not bruto.onus:
        campos_ausentes.append(
            "onus"
        )

    if not bruto.datas_vistoria:
        campos_ausentes.append(
            "data_vistoria"
        )

    if not bruto.responsaveis_tecnicos:
        campos_ausentes.append(
            "responsavel_tecnico"
        )


    # =====================================================
    # STATUS FINAL - DEFINIDO PELO PYTHON
    # =====================================================

    if divergencias:

        status = "CONTRADITORIO"

    elif campos_ausentes:

        status = "PARCIAL"

    else:

        status = "OK"


    return {
        "tipo_imovel":
            tipo_imovel,

        "endereco":
            endereco,

        "areas":
            areas,

        "ano":
            ano,

        "ano_contexto":
            ano_contexto,

        "valor_avaliacao_brl":
            valor_avaliacao,

        "matricula":
            matricula,

        "onus":
            onus,

        "data_vistoria":
            data_vistoria,

        "responsavel_tecnico":
            responsavel,

        "status_extracao":
            status,

        "campos_ausentes":
            campos_ausentes,

        "divergencias":
            divergencias
    }


# =========================================================
# FORMATO CSV
# =========================================================

def achatar_resultado(
    resultado: dict
) -> dict:

    areas = resultado["areas"]

    onus = resultado["onus"]

    responsavel = (
        resultado[
            "responsavel_tecnico"
        ]
    )

    return {
        "arquivo":
            resultado["arquivo"],

        "tipo_imovel":
            resultado["tipo_imovel"],

        "endereco":
            resultado["endereco"],

        "area_terreno_m2":
            areas["terreno_m2"],

        "area_construida_m2":
            areas["construida_m2"],

        "area_coberta_m2":
            areas["coberta_m2"],

        "area_privativa_m2":
            areas["privativa_m2"],

        "area_total_m2":
            areas["total_m2"],

        "area_util_m2":
            areas["util_m2"],

        "area_comum_m2":
            areas["comum_m2"],

        "ano":
            resultado["ano"],

        "ano_contexto":
            resultado["ano_contexto"],

        "valor_avaliacao_brl":
            resultado[
                "valor_avaliacao_brl"
            ],

        "matricula":
            resultado["matricula"],

        "onus_status":
            onus["status"],

        "onus_descricao":
            onus["descricao"],

        "data_vistoria":
            resultado["data_vistoria"],

        "responsavel_nome":
            responsavel["nome"],

        "responsavel_registro":
            responsavel["registro"],

        "status_extracao":
            resultado[
                "status_extracao"
            ],

        "campos_ausentes":
            json.dumps(
                resultado[
                    "campos_ausentes"
                ],
                ensure_ascii=False
            ),

        "divergencias":
            json.dumps(
                resultado[
                    "divergencias"
                ],
                ensure_ascii=False
            )
    }


# =========================================================
# PROCESSAMENTO DE TODOS OS LAUDOS
# =========================================================

def processar_laudos():

    arquivos = sorted(
        PASTA_LAUDOS.glob(
            "*.txt"
        )
    )

    if not arquivos:

        raise FileNotFoundError(
            "Nenhum arquivo .txt foi encontrado em "
            f"{PASTA_LAUDOS}"
        )

    logger.info(
        f"{len(arquivos)} laudo(s) encontrado(s)."
    )

    resultados_finais = []
    extracoes_brutas = []
    erros_processamento = []


    for indice, arquivo in enumerate(
        arquivos,
        start=1
    ):

        logger.info(
            f"Processando "
            f"{indice}/{len(arquivos)}: "
            f"{arquivo.name}"
        )

        try:

            texto = ler_laudo(
                arquivo
            )

            bruto = extrair_com_ia(
                texto=texto,
                nome_arquivo=arquivo.name
            )

            resultado = tratar_extracao(
                bruto
            )

            resultado = {
                "arquivo":
                    arquivo.name,

                **resultado
            }

            resultados_finais.append(
                resultado
            )

            extracoes_brutas.append({
                "arquivo":
                    arquivo.name,

                "extracao_bruta":
                    bruto.model_dump(
                        mode="json"
                    )
            })

            logger.info(
                f"{arquivo.name}: "
                f"{resultado['status_extracao']}"
            )

            if indice < len(arquivos):
                logger.info(
                    f"Aguardando {INTERVALO_ENTRE_LAUDOS}s "
        "antes do próximo laudo."
                )

                time.sleep(
                    INTERVALO_ENTRE_LAUDOS
                )
       
        except Exception as erro:

            logger.exception(
                f"Erro ao processar "
                f"{arquivo.name}: {erro}"
            )

            erros_processamento.append({
                "arquivo":
                    arquivo.name,

                "erro":
                    str(erro)
            })

            # Um laudo com erro não impede
            # o processamento dos demais.
            continue


    return (
        resultados_finais,
        extracoes_brutas,
        erros_processamento
    )


# =========================================================
# EXPORTAÇÃO
# =========================================================

def salvar_resultados(
    resultados_finais: list[dict],
    extracoes_brutas: list[dict],
    erros_processamento: list[dict]
):

    caminho_json = (
        PASTA_RELATORIOS
        / "extracao_laudos.json"
    )

    caminho_bruto = (
        PASTA_RELATORIOS
        / "extracao_laudos_bruta.json"
    )

    caminho_csv = (
        PASTA_RELATORIOS
        / "extracao_laudos.csv"
    )

    caminho_erros = (
        PASTA_RELATORIOS
        / "erros_extracao_laudos.json"
    )


    # Resultado final
    with open(
        caminho_json,
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            resultados_finais,
            arquivo,
            ensure_ascii=False,
            indent=2
        )


    # Extração original da IA + evidências
    with open(
        caminho_bruto,
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            extracoes_brutas,
            arquivo,
            ensure_ascii=False,
            indent=2
        )


    # Erros
    with open(
        caminho_erros,
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            erros_processamento,
            arquivo,
            ensure_ascii=False,
            indent=2
        )


    # CSV consolidado
    linhas = [
        achatar_resultado(
            resultado
        )
        for resultado
        in resultados_finais
    ]

    df = pd.DataFrame(
        linhas
    )

    df.to_csv(
        caminho_csv,
        index=False,
        encoding="utf-8-sig"
    )


    logger.info(
        f"Resultado JSON: "
        f"{caminho_json}"
    )

    logger.info(
        f"Extração bruta: "
        f"{caminho_bruto}"
    )

    logger.info(
        f"Resultado CSV: "
        f"{caminho_csv}"
    )

    logger.info(
        f"Erros: "
        f"{caminho_erros}"
    )


# =========================================================
# EXECUÇÃO
# =========================================================

if __name__ == "__main__":

    logger.info(
        "=== INÍCIO DA EXTRAÇÃO DOS LAUDOS ==="
    )

    try:

        (
            resultados,
            extracoes_brutas,
            erros
        ) = processar_laudos()

        salvar_resultados(
            resultados_finais=resultados,
            extracoes_brutas=(
                extracoes_brutas
            ),
            erros_processamento=erros
        )

        logger.info(
            "=== EXTRAÇÃO FINALIZADA ==="
        )

        print()
        print(
            "Extração concluída."
        )

        print(
            f"Laudos processados com sucesso: "
            f"{len(resultados)}"
        )

        print(
            f"Laudos com erro técnico: "
            f"{len(erros)}"
        )

        print()

        print(
            "Arquivos gerados:"
        )

        print(
            "reports/extracao_laudos.json"
        )

        print(
            "reports/extracao_laudos_bruta.json"
        )

        print(
            "reports/extracao_laudos.csv"
        )

        print(
            "reports/erros_extracao_laudos.json"
        )

    except Exception as erro:

        logger.exception(
            f"Execução interrompida: {erro}"
        )

        raise