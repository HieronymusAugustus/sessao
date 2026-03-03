import streamlit as st
import google.genai as genai
from google.genai.types import GenerateContentConfig
import pandas as pd
import tempfile
import time
import os

st.set_page_config(page_title="Sessão Virtuosa – TJPR", layout="wide")
st.title("⚖️ Sessão Virtuosa – TJPR")

st.write("""
Envie os dois PDFs:
- Processo judicial
- Voto/Acórdão

⚠️ Antes de qualquer análise, gere os resumos analíticos.
""")

# ------------------------------------------
# Modelo interno (Excel)
# ------------------------------------------
def carregar_modelo_ementa():
    df = pd.read_excel("modelo_sessao_virtuosa.xlsx")
    return "\n".join(df.astype(str).apply(" – ".join, axis=1))

modelo_ementa = carregar_modelo_ementa()

# ------------------------------------------
# API
# ------------------------------------------
API_KEY = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    st.error("API KEY não encontrada.")
    st.stop()

client = genai.Client(api_key=API_KEY)
MODEL = "gemini-1.5-pro"

# ------------------------------------------
# Uploaders
# ------------------------------------------
processo_file = st.file_uploader("📄 Processo Judicial (PDF)", type=["pdf"])
acordao_file = st.file_uploader("📘 Voto / Acórdão (PDF)", type=["pdf"])

# ------------------------------------------
# Auxiliares
# ------------------------------------------
def upload_to_gemini(f):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(f.read())
        return client.files.upload(file=tmp.name)

def aguardar(arquivo):
    while arquivo.state in ("PROCESSING", "PENDING"):
        time.sleep(1)
        arquivo = client.files.get(name=arquivo.name)
    return arquivo

# ------------------------------------------
# Session state
# ------------------------------------------
if "proc" not in st.session_state: st.session_state.proc = None
if "acor" not in st.session_state: st.session_state.acor = None
if "res_proc" not in st.session_state: st.session_state.res_proc = None
if "res_acor" not in st.session_state: st.session_state.res_acor = None

# ==========================================
# 0️⃣ GERAR RESUMOS ANALÍTICOS
# ==========================================
if st.button("0️⃣ Gerar Resumos Analíticos (obrigatório)"):
    if not processo_file or not acordao_file:
        st.warning("Envie ambos os PDFs.")
        st.stop()

    with st.spinner("Enviando arquivos..."):
        proc = aguardar(upload_to_gemini(processo_file))
        acor = aguardar(upload_to_gemini(acordao_file))

    st.session_state.proc = proc
    st.session_state.acor = acor

    # Resumo analítico do processo
    prompt_proc = """
Faça um RESUMO ANALÍTICO JURÍDICO COMPLETO do PROCESSO:
Inclua obrigatoriamente:
- pedidos da petição inicial
- fundamentos da inicial
- fundamentos da contestação
- pontos controvertidos
- análise da sentença (fundamentos + dispositivo)
- quem apelou (autor, réu ou ambos)
- fundamentos da apelação (itemizados)
- pontos efetivamente devolvidos à instância revisora

Máximo: 10.000 caracteres.
Proibido superficialidade.
"""

    with st.spinner("Gerando resumo analítico do processo..."):
        rproc = client.models.generate_content(
            model=MODEL, contents=[proc, prompt_proc],
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=3500),
        )
    st.session_state.res_proc = rproc.text

    # Resumo analítico do acórdão
    prompt_acor = """
Faça um RESUMO ANALÍTICO JURÍDICO COMPLETO do ACÓRDÃO:
Inclua:
- fundamentos do voto
- pontos realmente enfrentados
- capítulos omitidos
- coerência interna
- fundamentos relevantes para reforma/manutenção
- raciocínio decisório do relator

Máximo: 10.000 caracteres.
Proibido superficialidade.
"""

    with st.spinner("Gerando resumo analítico do acórdão..."):
        racor = client.models.generate_content(
            model=MODEL, contents=[acor, prompt_acor],
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=3500),
        )
    st.session_state.res_acor = racor.text

    st.success("Resumos gerados. Agora prossiga para as análises.")

# ==========================================
# 1️⃣ VERIFICAR EXISTÊNCIA DE INOVAÇÃO RECURSAL
# ==========================================
if st.session_state.res_proc and st.button("1️⃣ Verificar existência de inovação recursal"):
    prompt = f"""
Você é assessor do TJPR.
Com base EXCLUSIVAMENTE nos resumos analíticos:

PROCESSO:
{st.session_state.res_proc}

ACÓRDÃO:
{st.session_state.res_acor}

TAREFA:
1. Identifique quem apelou (autor, réu ou ambos).
2. Compare:
   - se apelante for autor → compare INICIAL × APELAÇÃO
   - se apelante for réu → compare CONTESTAÇÃO × APELAÇÃO
   - se ambos apelaram → analisar RECURSO POR RECURSO separadamente.
3. Aponte qualquer matéria NÃO constante das peças originárias.
4. Dê resposta FINAL curta:
   - “Há inovação recursal, porque…”
   - OU “Não há inovação recursal, porque…”

NÃO FAZER: cabeçalho, enfeite, explicação longa.
"""

    with st.spinner("Analisando inovação recursal..."):
        r1 = client.models.generate_content(
            model=MODEL, contents=prompt,
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=2500),
        )

    st.subheader("🔎 Inovação Recursal")
    st.write(r1.text)

# ==========================================
# 2️⃣ ANALISAR CABIMENTO DE ED
# ==========================================
if st.session_state.res_proc and st.button("2️⃣ Analisar cabimento de ED"):
    prompt = f"""
Você é assessor do TJPR.
Com base nos resumos analíticos:

PROCESSO:
{st.session_state.res_proc}

ACÓRDÃO:
{st.session_state.res_acor}

TAREFA:
Aponte, em ordem fixa:
1. OMISSÃO – apenas se o acórdão deixou de decidir ponto relevante.
2. CONTRADIÇÃO – ignorando meras citações; apenas contradições reais entre fundamentos e conclusão.
3. OBSCURIDADE – trechos ambíguos.
4. ERRO MATERIAL – erros numéricos, datas, nomes, valores.

RESPONDA NO FINAL, CURTO:
- “São cabíveis, porque…”
- OU “Não são cabíveis, porque…”
"""

    with st.spinner("Analisando cabimento de ED..."):
        r2 = client.models.generate_content(
            model=MODEL, contents=prompt,
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=2500),
        )

    st.subheader("✉️ Embargos de Declaração")
    st.write(r2.text)

# ==========================================
# 3️⃣ SINOPSE + COMENTÁRIO
# ==========================================
if st.session_state.res_proc and st.button("3️⃣ Gerar Sinopse + Comentário"):
    prompt = f"""
Você é assessor do TJPR.

Use EXCLUSIVAMENTE os resumos analíticos e o MODELO INTERNO abaixo.
Gere:

1) SINOPSE no MESMO ESTILO do modelo interno (estrutura, forma, concisão).
2) COMENTÁRIO conciso avaliando a adequação técnica do voto/acórdão.

MODELO INTERNO:
{modelo_ementa}

PROCESSO:
{st.session_state.res_proc}

ACÓRDÃO:
{st.session_state.res_acor}

NÃO inventar fatos.
NÃO produzir texto genérico.
"""

    with st.spinner("Gerando sinopse e comentário..."):
        r3 = client.models.generate_content(
            model=MODEL, contents=prompt,
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=3000),
        )

    st.subheader("📝 Sinopse + Comentário")
    st.write(r3.text)
