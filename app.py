import streamlit as st
import google.genai as genai
from google.genai.types import GenerateContentConfig
from google.genai.errors import ClientError
import pypdf
import pandas as pd
import time
import os

st.set_page_config(page_title="Sessão Virtuosa – TJPR", layout="wide")
st.title("⚖️ Sessão Virtuosa – TJPR")

# -------------------------------------------------------
# CONFIGURAÇÃO
# -------------------------------------------------------
API_KEY = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    st.error("API KEY não encontrada.")
    st.stop()

client = genai.Client(api_key=API_KEY)

st.write("""
Envie o processo judicial e o acórdão.

Depois gere o resumo analítico em blocos de 10.000 caracteres.
""")

# -------------------------------------------------------
# MODELOS DISPONÍVEIS (sem list_models, manual)
# -------------------------------------------------------
MODELOS_VALIDOS = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-2.5-flash-exp",
    "gemini-2.0-pro",
]

modelo_escolhido = st.selectbox(
    "Escolha o modelo:",
    MODELOS_VALIDOS,
    index=0  # gemini-2.0-flash é o padrão confiável
)

MODEL = modelo_escolhido
st.write(f"📌 Modelo selecionado: **{MODEL}**")

# -------------------------------------------------------
# FUNÇÕES
# -------------------------------------------------------

def extrair_texto_pdf(file):
    reader = pypdf.PdfReader(file)
    texto = []
    for page in reader.pages:
        try:
            texto.append(page.extract_text() or "")
        except:
            texto.append("")
    return "\n".join(texto)

def chunk_text(texto, tamanho=10000):
    return [texto[i:i+tamanho] for i in range(0, len(texto), tamanho)]

def resumir_chunk(chunk):
    prompt = f"""
Você é assessor do TJPR.

Resuma juridicamente o trecho abaixo, mantendo:

- pedidos da inicial
- fundamentos da inicial
- fundamentos da contestação
- pontos controvertidos
- fundamentos da sentença
- fundamentos da apelação

Trecho:
{chunk}
"""
    try:
        r = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=1000
            )
        )
        return r.text
    except Exception as e:
        return f"[ERRO NO MODELO: {e}]"

def fonte_pequena(texto):
    return f"<div style='font-size:0.7rem; color:#555;'>{texto}</div>"

def carregar_modelo_ementa():
    df = pd.read_excel("modelo_sessao_virtuosa.xlsx")
    return "\n".join(df.astype(str).apply(" – ".join, axis=1))


# -------------------------------------------------------
# STATE
# -------------------------------------------------------
for key in ["res_proc", "res_acor", "mini_proc", "mini_acor"]:
    if key not in st.session_state:
        st.session_state[key] = None if "res" in key else []

# -------------------------------------------------------
# UPLOAD
# -------------------------------------------------------
proc_pdf = st.file_uploader("📄 Processo judicial (PDF)", type=["pdf"])
acor_pdf = st.file_uploader("📘 Voto / Acórdão (PDF)", type=["pdf"])


# -------------------------------------------------------
# 0️⃣ GERAR RESUMOS
# -------------------------------------------------------
if st.button("0️⃣ Gerar Resumos Analíticos (obrigatório)"):
    if not proc_pdf or not acor_pdf:
        st.warning("Envie os dois PDFs.")
        st.stop()

    with st.spinner("Extraindo texto..."):
        texto_proc = extrair_texto_pdf(proc_pdf)
        texto_acor = extrair_texto_pdf(acor_pdf)

    chunks_proc = chunk_text(texto_proc)
    chunks_acor = chunk_text(texto_acor)

    mini_proc = []
    mini_acor = []

    st.subheader("Mini-resumos do PROCESSO")
    for i, ch in enumerate(chunks_proc):
        with st.spinner(f"Bloco {i+1}/{len(chunks_proc)}..."):
            r = resumir_chunk(ch)
            mini_proc.append(r)
            st.markdown(fonte_pequena(r), unsafe_allow_html=True)

    st.subheader("Mini-resumos do ACÓRDÃO")
    for i, ch in enumerate(chunks_acor):
        with st.spinner(f"Bloco {i+1}/{len(chunks_acor)}..."):
            r = resumir_chunk(ch)
            mini_acor.append(r)
            st.markdown(fonte_pequena(r), unsafe_allow_html=True)

    st.session_state.mini_proc = mini_proc
    st.session_state.mini_acor = mini_acor
    st.session_state.res_proc = "\n".join(mini_proc)
    st.session_state.res_acor = "\n".join(mini_acor)

    st.success("✔ Resumos analíticos completos.")


# -------------------------------------------------------
# 1️⃣ INOVAÇÃO RECURSAL
# -------------------------------------------------------
if st.session_state.res_proc and st.button("1️⃣ Verificar existência de inovação recursal"):
    prompt = f"""
PROCESSO:
{st.session_state.res_proc}

ACÓRDÃO:
{st.session_state.res_acor}

TAREFA:
1. Identificar quem apelou.
2. Comparar (autor): INICIAL × APELAÇÃO
3. Comparar (réu): CONTESTAÇÃO × APELAÇÃO
4. Resposta final, curta:
   - "Há inovação recursal, porque..."
   - ou "Não há inovação recursal, porque..."
"""

    try:
        r = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(max_output_tokens=1500)
        )
        st.write(r.text)
    except Exception as e:
        st.error(f"Erro ao analisar inovação recursal: {e}")


# -------------------------------------------------------
# 2️⃣ EMBARGOS DE DECLARAÇÃO
# -------------------------------------------------------
if st.session_state.res_proc and st.button("2️⃣ Analisar cabimento de ED"):
    prompt = f"""
PROCESSO:
{st.session_state.res_proc}

ACÓRDÃO:
{st.session_state.res_acor}

TAREFA:
Avaliar:
- Omissão
- Contradição
- Obscuridade
- Erro material

Resposta final:
"São cabíveis, porque..."
ou
"Não são cabíveis, porque..."
"""

    try:
        r = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(max_output_tokens=1500)
        )
        st.write(r.text)
    except Exception as e:
        st.error(f"Erro ao analisar ED: {e}")


# -------------------------------------------------------
# 3️⃣ SINOPSE + COMENTÁRIO
# -------------------------------------------------------
if st.session_state.res_proc and st.button("3️⃣ Gerar Sinopse + Comentário"):
    modelo_ementa = carregar_modelo_ementa()

    prompt = f"""
PROCESSO:
{st.session_state.res_proc}

ACÓRDÃO:
{st.session_state.res_acor}

MODELO INTERNO:
{modelo_ementa}

TAREFA:
Gerar:
1) Sinopse no estilo do modelo interno
2) Comentário técnico e conciso
"""

    try:
        r = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(max_output_tokens=2500)
        )
        st.write(r.text)
    except Exception as e:
        st.error(f"Erro na sinopse/comentário: {e}")
