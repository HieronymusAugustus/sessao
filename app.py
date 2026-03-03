import streamlit as st

# ---------------------------------------
# IMPORTS
# ---------------------------------------
try:
    import pypdf
except ModuleNotFoundError:
    pypdf = None

try:
    import google.genai as genai
    from google.genai.types import GenerateContentConfig
    from google.genai.errors import ClientError
except Exception:
    genai = None
    GenerateContentConfig = None
    ClientError = Exception
    # If google.genai isn't available you can still import it when installed at runtime

# ---------------------------------------
# CONFIGURAÇÃO INICIAL
# ---------------------------------------
st.set_page_config(page_title="Sessão Virtuosa – TJPR", layout="wide")
st.title("⚖️ Sessão Virtuosa – TJPR")
st.write("""
Envie os dois PDFs:\n
- Processo judicial (PDF)\n- Voto / Acórdão (PDF)\n
Antes de qualquer análise, gere os resumos analíticos automáticos em blocos de 10.000 caracteres.
""")

# ---------------------------------------
# API CLIENTE
# ---------------------------------------
API_KEY = st.secrets.get("GOOGLE_API_KEY") if "GOOGLE_API_KEY" in st.secrets else None
if API_KEY is None:
    import os
    API_KEY = os.getenv("GOOGLE_API_KEY")

if genai is None:
    st.error("A biblioteca google.genai não está disponível. Verifique o requirements.")
else:
    client = genai.Client(api_key=API_KEY)

# ---------------------------------------
# LISTA MODELOS
# ---------------------------------------
available_models = []
raw_models = []
if genai is not None and API_KEY:
    try:
        raw_models = client.list_models()
        available_models = [m.name for m in raw_models]
    except Exception as e:
        st.warning(f"Erro ao listar modelos: {e}")

st.subheader("Modelos disponíveis nesta API KEY:")
st.write(available_models)

# ---------------------------------------
# SELEÇÃO AUTOMÁTICA DE MODELO
# ---------------------------------------
# Ordem de preferência: gemini-2.0-pro, gemini-2.5-flash-exp, gemini-2.5-flash
preferred_order = ["gemini-2.0-pro", "gemini-2.5-flash-exp", "gemini-2.5-flash"]
MODEL = None
for m in preferred_order:
    if m in available_models:
        MODEL = m
        break
# Se não encontrado, escolher primeiro modelo com método generateContent
if MODEL is None and raw_models:
    for m in raw_models:
        try:
            if hasattr(m, "supported_methods") and "generateContent" in m.supported_methods:
                MODEL = m.name
                break
        except Exception:
            # alguns objetos modelo podem não ter a propriedade supported_methods
            continue
# Fallback final: primeiro modelo da lista
if MODEL is None and available_models:
    MODEL = available_models[0]

if MODEL is None:
    st.error("Nenhum modelo disponível. Verifique sua API_KEY e conectividade.")
else:
    st.write(f"Modelo selecionado: {MODEL}")

# ---------------------------------------
# FUNÇÕES AUXILIARES
# ---------------------------------------
# Extração do texto do PDF
def extrair_texto_pdf(arq):
    if pypdf is None:
        return ""  # pypdf não disponível
    reader = pypdf.PdfReader(arq)
    texto = []
    for pagina in reader.pages:
        try:
            texto.append(pagina.extract_text() or "")
        except Exception:
            texto.append("")
    return "\n".join(texto)

# Dividir texto em blocos de 10.000 caracteres
def chunk_text(texto, tamanho=10000):
    return [texto[i:i+tamanho] for i in range(0, len(texto), tamanho)]

# Função de chamada à API para resumir um bloco
def resumir_chunk(chunk):
    if genai is None or API_KEY is None or MODEL is None:
        return ""  # modelo ou API não configurados
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
    try:
        resposta = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=1000)
        )
        return resposta.text
    except Exception as e:
        # Se for ClientError ou outro, aparece no app
        st.error(f"Erro de API ao resumir chunk: {e}")
        return ""

# Helper para mostrar texto em fonte menor
def fonte_pequena(texto):
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
    else:
        with st.spinner("Extraindo texto..."):
            texto_proc = extrair_texto_pdf(proc_pdf)
            texto_acor = extrair_texto_pdf(acor_pdf)
        chunks_proc = chunk_text(texto_proc, 10000)
        chunks_acor = chunk_text(texto_acor, 10000)
        mini_resumos_proc = []
        mini_resumos_acor = []
        st.subheader("Mini-resumos do PROCESSO (debug)")
        for i, ch in enumerate(chunks_proc):
            with st.spinner(f"Resumindo bloco {i+1}/{len(chunks_proc)} do processo..."):
                r = resumir_chunk(ch)
                mini_resumos_proc.append(r)
                st.markdown(fonte_pequena(f"<b>Bloco {i+1}</b><br>{r}"), unsafe_allow_html=True)
        st.subheader("Mini-resumos do ACÓRDÃO (debug)")
        for i, ch in enumerate(chunks_acor):
            with st.spinner(f"Resumindo bloco {i+1}/{len(chunks_acor)} do acórdão..."):
                r = resumir_chunk(ch)
                mini_resumos_acor.append(r)
                st.markdown(fonte_pequena(f"<b>Bloco {i+1}</b><br>{r}"), unsafe_allow_html=True)
        # Guardar no estado
        st.session_state.mini_proc = mini_resumos_proc
        st.session_state.mini_acor = mini_resumos_acor
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
    try:
        r1 = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=1500)
        )
        st.subheader("🔎 Inovação Recursal – Resultado")
        st.write(r1.text)
    except Exception as e:
        st.error(f"Erro de API na inovação recursal: {e}")

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
    try:
        r2 = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=1500)
        )
        st.subheader("✉️ Embargos de Declaração – Resultado")
        st.write(r2.text)
    except Exception as e:
        st.error(f"Erro de API nos Embargos de Declaração: {e}")

# =======================================
# 3️⃣ SINOPSE + COMENTÁRIO
# =======================================
# Carregar modelo interno de Ementa (arquivo Excel) de forma preguiçosa
@st.cache_data
def carregar_modelo_ementa():
    import pandas as pd
    df = pd.read_excel("modelo_sessao_virtuosa.xlsx", engine="openpyxl")
    return "\n".join(df.astype(str).apply(" – ".join, axis=1))

modelo_ementa = carregar_modelo_ementa()

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
    try:
        r3 = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(temperature=0.1, max_output_tokens=2500)
        )
        st.subheader("📝 Sinopse + Comentário")
        st.write(r3.text)
    except Exception as e:
        st.error(f"Erro de API na Sinopse + Comentário: {e}")
