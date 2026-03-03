import streamlit as st
import google.genai as genai
from google.genai.types import GenerateContentConfig
import pandas as pd
import pypdf
import time
import os
import textwrap

# ---------------------------------------
# CONFIGURAÇÃO INICIAL
# ---------------------------------------
st.set_page_config(page_title="Sessão Virtuosa – TJPR", layout="wide")
st.title("⚖️ Sessão Virtuosa – TJPR")

st.write("""
Envie os dois PDFs:

- Processo judicial (PDF)
- Voto / Acórdão (PDF)

Antes de qualquer análise, gere os resumos analíticos automáticos em blocos de 10.000 caracteres.
""")

# ---------------------------------------
# MODELO DE EMENTA (EXCEL INTERNO)
# ---------------------------------------
def carregar_modelo_ementa():
    df = pd.read_excel("modelo_sessao_virtuosa.xlsx")
    return "\n".join(df.astype(str).apply(" – ".join, axis=1))

modelo_ementa = carregar_modelo_ementa()

# ---------------------------------------
# API GOOGLE
# ---------------------------------------
API_KEY = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    st.error("API KEY não encontrada.")
    st.stop()

client = genai.Client(api_key=API_KEY)
MODEL = "gemini-1.5-pro"

# ---------------------------------------
# FUNÇÕES AUXILIARES
# ---------------------------------------

def extrair_texto_pdf(file):
    """Extrai todo o texto do PDF usando pypdf."""
    reader = pypdf.PdfReader(file)
    texto = []
    for page in reader.pages:
        try:
            texto.append(page.extract_text() or "")
        except:
            texto.append("")
    return "\n".join(texto)

def chunk_text(texto, tamanho=10000):
    """Divide o texto em blocos de tamanho ~10k caracteres."""
    return [texto[i:i+tamanho] for i in range(0, len(texto), tamanho)]

def resumir_chunk(chunk):
    """Pede ao modelo um mini‑resumo jurídico do bloco."""
    prompt = f"""
Você é assessor do TJPR.

Resuma juridicamente o seguinte trecho, mantendo:

- pedidos da inicial
- fundamentos da inicial
- fundamentos da contestação
- pontos controvertidos
- fundamentos da sentença
- fundamentos da apelação
- qualquer elemento útil para inovação recursal e embargos

Trecho:
{chunk}

O resumo deve ser objetivo, completo e técnico.
"""
    resposta = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=GenerateContentConfig(temperature=0.1, max_output_tokens=1000)
    )
    return resposta.text


def fonte_pequena(texto):
    """Renderiza texto em fonte menor."""
    return f"<div style='font-size:0.65rem; color:#555;'>{texto}</div>"


# ---------------------------------------
# STATE
# ---------------------------------------
if "res_proc" not in st.session_state:
    st.session_state.res_proc = None
if "res_acor" not in st.session_state:
    st.session_state.res_acor = None
if "mini_proc" not in st.session_state:
    st.session_state.mini_proc = []
if "mini_acor" not in st.session_state:
    st.session_state.mini_acor = []

# ---------------------------------------
# UPLOAD
# ---------------------------------------
proc_pdf = st.file_uploader("📄 Processo judicial (PDF)", type=["pdf"])
acor_pdf = st.file_uploader("📘 Voto / Acórdão (PDF)", type=["pdf"])

# =======================================
# 0️⃣ GERAR RESUMOS ANALÍTICOS AUTOMÁTICOS
# =======================================
if st.button("0️⃣ Gerar Resumos Analíticos (obrigatório)"):
    if not proc_pdf or not acor_pdf:
        st.warning("Envie ambos os PDFs.")
        st.stop()

    with st.spinner("Extraindo texto..."):
        texto_proc = extrair_texto_pdf(proc_pdf)
        texto_acor = extrair_texto_pdf(acor_pdf)

    chunks_proc = chunk_text(texto_proc, 10000)
    chunks_acor = chunk_text(texto_acor, 10000)

    mini_resumos_proc = []
    mini_resumos_acor = []

    # -----------------------
    # PROCESSO
    # -----------------------
    st.subheader("Mini‑resumos do PROCESSO (debug)")
    for i, ch in enumerate(chunks_proc):
        with st.spinner(f"Resumindo bloco {i+1}/{len(chunks_proc)} do processo..."):
            r = resumir_chunk(ch)
            mini_resumos_proc.append(r)
            st.markdown(fonte_pequena(f"<b>Bloco {i+1}</b><br>{r}"), unsafe_allow_html=True)

    # -----------------------
    # ACÓRDÃO
    # -----------------------
    st.subheader("Mini‑resumos do ACÓRDÃO (debug)")
    for i, ch in enumerate(chunks_acor):
        with st.spinner(f"Resumindo bloco {i+1}/{len(chunks_acor)} do acórdão..."):
            r = resumir_chunk(ch)
            mini_resumos_acor.append(r)
            st.markdown(fonte_pequena(f"<b>Bloco {i+1}</b><br>{r}"), unsafe_allow_html=True)

    # Guarda no estado
    st.session_state.mini_proc = mini_resumos_proc
    st.session_state.mini_acor = mini_resumos_acor

    # Consolidação
    st.session_state.res_proc = "\n".join(mini_resumos_proc)
    st.session_state.res_acor = "\n".join(mini_resumos_acor)

    st.success("Resumos analíticos gerados com sucesso! Agora prossiga para as análises.")

# =======================================
# 1️⃣ VERIFICAR EXISTÊNCIA DE INOVAÇÃO RECURSAL
# =======================================
if st.session_state.res_proc and st.button("1️⃣ Verificar existência de inovação recursal"):
    prompt = f"""
Você é assessor do TJPR.

PROCESSO (resumo consolidado):
{st.session_state.res_proc}

ACÓRDÃO (resumo consolidado):
{st.session_state.res_acor}

TAREFA:
1. Identifique quem apelou (autor, réu ou ambos).
2. Compare:
   - inicial × apelação (se autor apelou)
   - contestação × apelação (se réu apelou)
   - recursos separados (se ambos apelaram)
3. Verificar se há inovação recursal objetiva.
4. Resposta final (curta e direta):
   - "Há inovação recursal, porque..."
   - ou "Não há inovação recursal, porque..."
"""

    with st.spinner("Analisando inovação recursal..."):
        r1 = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=1500)
        )

    st.subheader("🔎 Inovação Recursal – Resultado")
    st.write(r1.text)

# =======================================
# 2️⃣ ANALISAR CABIMENTO DE ED
# =======================================
if st.session_state.res_proc and st.button("2️⃣ Analisar cabimento de ED"):
    prompt = f"""
Você é assessor do TJPR.

Com base nos resumos:

PROCESSO:
{st.session_state.res_proc}

ACÓRDÃO:
{st.session_state.res_acor}

TAREFA:
- Verificar OMISSÃO (item a item)
- Verificar CONTRADIÇÃO (ignorar citações)
- Verificar OBSCURIDADE
- Verificar ERRO MATERIAL

Resposta final (curta):
- "São cabíveis, porque..."
- ou "Não são cabíveis, porque..."
"""

    with st.spinner("Analisando ED..."):
        r2 = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=1500)
        )

    st.subheader("✉️ Embargos de Declaração – Resultado")
    st.write(r2.text)

# =======================================
# 3️⃣ SINOPSE + COMENTÁRIO
# =======================================
if st.session_state.res_proc and st.button("3️⃣ Gerar Sinopse + Comentário"):
    prompt = f"""
Você é assessor do TJPR.

Use EXCLUSIVAMENTE:

PROCESSO (resumo consolidado):
{st.session_state.res_proc}

ACÓRDÃO (resumo consolidado):
{st.session_state.res_acor}

MODELO INTERNO:
{modelo_ementa}

TAREFA:
1. Gerar SINOPSE no estilo do modelo interno.
2. Gerar COMENTÁRIO conciso avaliando tecnicamente o acórdão.

NÃO inventar fatos.
"""

    with st.spinner("Gerando sinopse e comentário..."):
        r3 = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=2500)
        )

    st.subheader("📝 Sinopse + Comentário")
    st.write(r3.text)
