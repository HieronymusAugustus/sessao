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
Envie os arquivos:
- Processo judicial (PDF)
- Voto/Acórdão (PDF)

O modelo de ementa é interno.
""")

# Modelo interno ----------------------------------------------------
def carregar_modelo_ementa():
    df = pd.read_excel("modelo_sessao_virtuosa.xlsx")
    return "\n".join(df.astype(str).apply(" – ".join, axis=1))

modelo_ementa = carregar_modelo_ementa()

# API ---------------------------------------------------------------
API_KEY = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    st.error("API KEY não encontrada.")
    st.stop()

client = genai.Client(api_key=API_KEY)
MODEL = "gemini-2.5-flash"

# Uploads -----------------------------------------------------------
processo_file = st.file_uploader("📄 Processo Judicial (PDF)", type=["pdf"])
acordao_file = st.file_uploader("📘 Voto/Acórdão (PDF)", type=["pdf"])

# Funções auxiliares ------------------------------------------------
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

# Sessão ------------------------------------------------------------
if "proc" not in st.session_state:
    st.session_state.proc = None
if "acor" not in st.session_state:
    st.session_state.acor = None

# ETAPA 1 – Inovação Recursal --------------------------------------
if st.button("1️⃣ Analisar Inovação Recursal"):
    if not processo_file or not acordao_file:
        st.warning("Envie os dois PDFs.")
        st.stop()

    with st.spinner("Enviando arquivos..."):
        proc = upload_to_gemini(processo_file)
        acor = upload_to_gemini(acordao_file)
        proc = aguardar(proc)
        acor = aguardar(acor)

    st.session_state.proc = proc
    st.session_state.acor = acor

    prompt = """
Você é assessor de desembargador do TJPR.
Analise se há INOVAÇÃO RECURSAL no voto/acórdão.
Seja objetivo e técnico.
"""

    with st.spinner("Analisando..."):
        r = client.models.generate_content(
            model=MODEL,
            contents=[proc, acor, prompt],
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=1500)
        )

    st.subheader("🔎 Inovação Recursal")
    st.write(r.text)

# ETAPA 2 – Embargos de Declaração ---------------------------------
if st.session_state.proc and st.button("2️⃣ Verificar Embargos de Declaração"):
    proc = st.session_state.proc
    acor = st.session_state.acor

    prompt = """
Você é assessor do TJPR.
Verifique o cabimento de EMBARGOS DE DECLARAÇÃO (omissão, obscuridade, contradição, erro material).
Seja direto e técnico.
"""

    with st.spinner("Analisando..."):
        r2 = client.models.generate_content(
            model=MODEL,
            contents=[proc, acor, prompt],
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=1500)
        )

    st.subheader("✉️ Embargos de Declaração")
    st.write(r2.text)

# ETAPA 3 – Sinopse + Comentário -----------------------------------
if st.session_state.proc and st.button("3️⃣ Gerar Sinopse e Comentário"):
    proc = st.session_state.proc
    acor = st.session_state.acor

    prompt = f"""
Você é assessor de desembargador do TJPR.

Com base NO MODELO abaixo, gere:
1) SINOPSE (como ementa)
2) COMENTÁRIO conciso sobre o voto/acórdão

MODELO:
-------
{modelo_ementa}
-------

Estilo: direto, objetivo e técnico.
"""

    with st.spinner("Gerando..."):
        r3 = client.models.generate_content(
            model=MODEL,
            contents=[proc, acor, prompt],
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=2000)
        )

    st.subheader("📝 Sinopse e Comentário")
    st.write(r3.text)
