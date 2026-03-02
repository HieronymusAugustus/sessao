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
Envie os dois arquivos PDF:
- Processo judicial
- Voto / Acórdão

O modelo de ementa é interno.
""")

# -------------------------
# Carregar modelo interno
# -------------------------
def carregar_modelo_ementa():
    df = pd.read_excel("modelo_sessao_virtuosa.xlsx")
    return "\n".join(df.astype(str).apply(" – ".join, axis=1))

modelo_ementa = carregar_modelo_ementa()

# -------------------------
# API
# -------------------------
API_KEY = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    st.error("API KEY não encontrada.")
    st.stop()

client = genai.Client(api_key=API_KEY)
MODEL = "gemini-2.5-flash"

# -------------------------
# Uploaders
# -------------------------
processo_file = st.file_uploader("📄 Processo Judicial (PDF)", type=["pdf"])
acordao_file = st.file_uploader("📘 Voto/Acórdão (PDF)", type=["pdf"])

# -------------------------
# Funções auxiliares
# -------------------------
def upload_to_gemini(uploaded_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name
    return client.files.upload(file=tmp_path)

def aguardar(arquivo):
    while arquivo.state in ("PROCESSING", "PENDING"):
        time.sleep(1)
        arquivo = client.files.get(name=arquivo.name)
    return arquivo

# Sessão
if "proc" not in st.session_state:
    st.session_state.proc = None
if "acor" not in st.session_state:
    st.session_state.acor = None
if "resumo_proc" not in st.session_state:
    st.session_state.resumo_proc = None
if "resumo_acor" not in st.session_state:
    st.session_state.resumo_acor = None


# -------------------------
# ETAPA 0 – RESUMOS AUTOMÁTICOS
# -------------------------
if st.button("0️⃣ Gerar Resumos (obrigatório antes das análises)"):
    if not processo_file or not acordao_file:
        st.warning("Envie o processo e o acórdão.")
        st.stop()

    with st.spinner("Enviando arquivos para processamento..."):
        proc = upload_to_gemini(processo_file)
        acor = upload_to_gemini(acordao_file)
        proc = aguardar(proc)
        acor = aguardar(acor)

    st.session_state.proc = proc
    st.session_state.acor = acor

    # Resumo do processo
    prompt_resumo_proc = """
Resuma o PROCESSO JUDICIAL de forma extremamente objetiva e técnica.
No máximo 3000 caracteres.
"""

    with st.spinner("Resumindo o processo..."):
        r_proc = client.models.generate_content(
            model=MODEL,
            contents=[proc, prompt_resumo_proc],
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=1200),
        )

    st.session_state.resumo_proc = r_proc.text

    # Resumo do acórdão
    prompt_resumo_acor = """
Resuma o VOTO/ACÓRDÃO de forma extremamente objetiva e técnica.
No máximo 3000 caracteres.
"""

    with st.spinner("Resumindo o acórdão..."):
        r_acor = client.models.generate_content(
            model=MODEL,
            contents=[acor, prompt_resumo_acor],
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=1200),
        )

    st.session_state.resumo_acor = r_acor.text

    st.success("Resumos gerados com sucesso! Agora prossiga para as análises.")


# -------------------------
# ETAPA 1 – Inovação Recursal
# -------------------------
if st.session_state.resumo_proc and st.button("1️⃣ Analisar Inovação Recursal"):
    prompt = f"""
Você é assessor do TJPR.

Com base APENAS nestes resumos:

PROCESSO:
{st.session_state.resumo_proc}

ACÓRDÃO:
{st.session_state.resumo_acor}

Analise se há INOVAÇÃO RECURSAL.
Seja técnico, objetivo e direto.
"""

    with st.spinner("Analisando inovação recursal..."):
        r1 = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=2000),
        )

    st.subheader("🔎 Inovação Recursal")
    st.write(r1.text)


# -------------------------
# ETAPA 2 – Embargos
# -------------------------
if st.session_state.resumo_proc and st.button("2️⃣ Verificar Embargos de Declaração"):
    prompt = f"""
Você é assessor do TJPR.

Com base APENAS nestes resumos:

PROCESSO:
{st.session_state.resumo_proc}

ACÓRDÃO:
{st.session_state.resumo_acor}

Verifique o cabimento de EMBARGOS (omissão, obscuridade, contradição, erro material).
Seja técnico e objetivo.
"""

    with st.spinner("Analisando embargos..."):
        r2 = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=2000),
        )

    st.subheader("✉️ Embargos de Declaração")
    st.write(r2.text)


# -------------------------
# ETAPA 3 – Sinopse + Comentário
# -------------------------
if st.session_state.resumo_proc and st.button("3️⃣ Gerar Sinopse + Comentário"):
    prompt = f"""
Você é assessor do TJPR.

Com base NO MODELO INTERNO abaixo e nos resumos do processo e do acórdão:

MODELO:
{modelo_ementa}

PROCESSO:
{st.session_state.resumo_proc}

ACÓRDÃO:
{st.session_state.resumo_acor}

Gere:
1) SINOPSE no mesmo estilo do modelo interno.
2) COMENTÁRIO conciso, técnico e direto.

Não invente fatos. Mantenha o estilo do modelo.
"""

    with st.spinner("Gerando sinopse e comentário..."):
        r3 = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=3000),
        )

    st.subheader("📝 Sinopse + Comentário")
    st.write(r3.text)
