import streamlit as st
import google.genai as genai
from google.genai.types import GenerateContentConfig
from google.genai.errors import ClientError
import pypdf
import pandas as pd
import os
import requests  # se já estiver usando OpenRouter

st.set_page_config(page_title="Sessão Virtuosa – TJPR", layout="wide")
st.title("⚖️ Sessão Virtuosa – TJPR")

# ============================================================
# CONFIGURAÇÃO DAS API KEYS (3 Google + 1 OpenRouter)
# ============================================================

GOOGLE_KEYS = [
    st.secrets.get("GOOGLE_API_KEY_1") or os.getenv("GOOGLE_API_KEY_1"),
    st.secrets.get("GOOGLE_API_KEY_2") or os.getenv("GOOGLE_API_KEY_2"),
    st.secrets.get("GOOGLE_API_KEY_3") or os.getenv("GOOGLE_API_KEY_3"),
]

OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")

GOOGLE_KEYS = [k for k in GOOGLE_KEYS if k]

if not GOOGLE_KEYS:
    st.error("Nenhuma GOOGLE_API_KEY encontrada nos secrets/variáveis de ambiente.")
    st.stop()

if not OPENROUTER_API_KEY:
    st.warning("OPENROUTER_API_KEY não encontrada (apenas recursos Google funcionarão).")

# ============================================================
# SELEÇÃO DA CHAVE GOOGLE
# ============================================================

st.subheader("Seleção de chave da Google")

opcoes_keys = [f"Chave Google #{i+1}" for i in range(len(GOOGLE_KEYS))]
idx_key_escolhida = st.selectbox(
    "Escolha qual chave da Google usar:",
    list(range(len(GOOGLE_KEYS))),
    format_func=lambda i: opcoes_keys[i],
    index=0
)

API_KEY_GOOGLE_ATIVA = GOOGLE_KEYS[idx_key_escolhida]

client = genai.Client(api_key=API_KEY_GOOGLE_ATIVA)

# ============================================================
# (Opcional) OpenRouter – se já estiver usando
# ============================================================

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

def chamar_openrouter(prompt: str, model: str = "openrouter/auto") -> str:
    if not OPENROUTER_API_KEY:
        return "[OPENROUTER] API key não configurada."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    try:
        resp = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=60)
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[ERRO OPENROUTER: {e}]"

# =======================
# MODELOS DISPONÍVEIS
# =======================

# Modelos mais simples e ainda em uso (evitando os com desativação iminente)
# gemini-2.0-* → recomendação oficial: migrar para 2.5-flash / 2.5-flash-lite.[page:1]
MODELOS_VALIDOS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3-flash-preview",         # se quiser já testar 3.x preview
    "gemini-3.1-flash-lite-preview",  # simples e em prévia
]

st.subheader("Seleção de modelo Google Gemini")

modelo_escolhido = st.selectbox(
    "Escolha o modelo para uso (Google):",
    MODELOS_VALIDOS,
    index=0
)

MODEL = modelo_escolhido
st.write(f"📌 Modelo Google selecionado: **{MODEL}** com {opcoes_keys[idx_key_escolhida]}")

# ============================================================
# TESTADOR AUTOMÁTICO DA API KEY GOOGLE
# ============================================================

st.subheader("Teste automático da API KEY Google")

def testar_api_key_google(model):
    try:
        resposta = client.models.generate_content(
            model=model,
            contents="teste",
            config=GenerateContentConfig(
                max_output_tokens=5,
                temperature=0
            )
        )
        return ("OK", "API KEY Google válida e com quota disponível.")
    except Exception as e:
        erro = str(e)
        if "401" in erro or "PERMISSION_DENIED" in erro:
            return ("ERRO", "API KEY inválida ou não autorizada.")
        if "404" in erro:
            return ("ERRO", f"Modelo '{model}' não existe para esta conta.")
        if "429" in erro or "RESOURCE_EXHAUSTED" in erro:
            return ("ERRO", "Sem quota. API KEY está com LIMIT=0 ou modelo saturado.")
        return ("ERRO", f"Erro inesperado: {erro}")

status, mensagem = testar_api_key_google(MODEL)

if status == "OK":
    st.success(mensagem)
else:
    st.error(mensagem)
    st.stop()

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

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

Resuma juridicamente o trecho abaixo:

{chunk}

Resumo jurídico, técnico e completo, incluindo pedidos, fundamentos e controvérsias.
"""
    try:
        r = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=800
            )
        )
        return r.text
    except Exception as e:
        return f"[ERRO NO MODELO GOOGLE: {e}]"

def fonte_pequena(texto):
    return f"<div style='font-size:0.75rem; color:#555;'>{texto}</div>"

def carregar_modelo_ementa():
    df = pd.read_excel("modelo_sessao_virtuosa.xlsx")
    return "\n".join(df.astype(str).apply(" – ".join, axis=1))

# ============================================================
# STATE
# ============================================================

for var in ["mini_proc", "mini_acor", "res_proc", "res_acor"]:
    if var not in st.session_state:
        st.session_state[var] = None if "res" in var else []

# ============================================================
# UPLOADS
# ============================================================

proc_pdf = st.file_uploader("📄 Processo judicial (PDF)", type=["pdf"])
acor_pdf = st.file_uploader("📘 Voto / Acórdão (PDF)", type=["pdf"])

# ============================================================
# 0️⃣ GERAR RESUMOS
# ============================================================

if st.button("0️⃣ Gerar Resumos Analíticos (obrigatório)"):
    if not proc_pdf or not acor_pdf:
        st.warning("Envie ambos os PDFs.")
        st.stop()

    with st.spinner("Extraindo texto..."):
        texto_proc = extrair_texto_pdf(proc_pdf)
        texto_acor = extrair_texto_pdf(acor_pdf)

    chunks_proc = chunk_text(texto_proc)
    chunks_acor = chunk_text(texto_acor)

    mini_p = []
    mini_a = []

    st.subheader("Mini‑resumos do PROCESSO")
    for i, ch in enumerate(chunks_proc):
        with st.spinner(f"Processo – Bloco {i+1}/{len(chunks_proc)}"):
            resumo = resumir_chunk(ch)
            mini_p.append(resumo)
            st.markdown(fonte_pequena(resumo), unsafe_allow_html=True)

    st.subheader("Mini‑resumos do ACÓRDÃO")
    for i, ch in enumerate(chunks_acor):
        with st.spinner(f"Acórdão – Bloco {i+1}/{len(chunks_acor)}"):
            resumo = resumir_chunk(ch)
            mini_a.append(resumo)
            st.markdown(fonte_pequena(resumo), unsafe_allow_html=True)

    st.session_state.mini_proc = mini_p
    st.session_state.mini_acor = mini_a
    st.session_state.res_proc = "\n".join(mini_p)
    st.session_state.res_acor = "\n".join(mini_a)

    st.success("✔ Resumos gerados.")

# ============================================================
# 1️⃣ INOVAÇÃO RECURSAL
# ============================================================

if st.session_state.res_proc and st.button("1️⃣ Verificar existência de inovação recursal"):
    prompt = f"""
PROCESSO:
{st.session_state.res_proc}

ACÓRDÃO:
{st.session_state.res_acor}

TAREFA:
1. Identificar quem apelou.
2. Comparar :
   • INICIAL × APELAÇÃO (autor)
   • CONTESTAÇÃO × APELAÇÃO (réu)
3. Concluir de forma objetiva:
   • “Há inovação recursal, porque…”
   • ou “Não há inovação recursal, porque…”
"""
    try:
        r = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(max_output_tokens=1500)
        )
        st.subheader("🔎 Resultado – Inovação Recursal (Google)")
        st.write(r.text)
    except Exception as e:
        st.error(f"Erro na inovação recursal (Google): {e}")

# ============================================================
# 2️⃣ EMBARGOS DE DECLARAÇÃO
# ============================================================

if st.session_state.res_proc and st.button("2️⃣ Analisar cabimento de ED"):
    prompt = f"""
PROCESSO:
{st.session_state.res_proc}

ACÓRDÃO:
{st.session_state.res_acor}

Avalie rigorosamente:

• Omissão  
• Contradição  
• Obscuridade  
• Erro material  

Conclusão curta:
“São cabíveis, porque…” 
ou 
“Não são cabíveis, porque…”
"""
    try:
        r = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(max_output_tokens=1500)
        )
        st.subheader("✉️ Resultado – Embargos de Declaração (Google)")
        st.write(r.text)
    except Exception as e:
        st.error(f"Erro nos embargos (Google): {e}")

# ============================================================
# 3️⃣ SINOPSE + COMENTÁRIO
# ============================================================

if st.session_state.res_proc and st.button("3️⃣ Gerar Sinopse + Comentário"):
    modelo_ementa = carregar_modelo_ementa()

    prompt = f"""
PROCESSO:
{st.session_state.res_proc}

ACÓRDÃO:
{st.session_state.res_acor}

MODELO INTERNO:
{modelo_ementa}

Elabore:
1) SINOPSE no estilo do modelo interno
2) COMENTÁRIO técnico conciso

Sem inventar fatos.
"""
    try:
        r = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=GenerateContentConfig(max_output_tokens=2500)
        )
        st.subheader("📝 Sinopse + Comentário (Google)")
        st.write(r.text)
    except Exception as e:
        st.error(f"Erro na Sinopse/Comentário (Google): {e}")
