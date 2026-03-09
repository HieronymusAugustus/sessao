import streamlit as st
import google.genai as genai
from google.genai.types import GenerateContentConfig
from google.genai.errors import ClientError
import pypdf
import pandas as pd
import os
import requests
import time
import json

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

# =======================
# MODELOS DISPONÍVEIS
# =======================

MODELOS_VALIDOS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
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
            return ("ERRO", "Sem quota no momento. Aguarde 1 minuto e tente novamente.")
        return ("ERRO", f"Erro inesperado: {erro}")

status, mensagem = testar_api_key_google(MODEL)

if status == "OK":
    st.success(mensagem)
else:
    st.error(mensagem)
    st.stop()

# ============================================================
# FUNÇÃO GENÉRICA COM RETRY (EVITA ESTOURAR QUOTA)
# ============================================================

def gerar_conteudo_com_retry(prompt: str, max_tokens: int = 600, temperatura: float = 0.1):
    """Wrapper para GenerateContent com retry em caso de 429/RESOURCE_EXHAUSTED."""
    tentativas = 3
    for tentativa in range(tentativas):
        try:
            r = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=temperatura,
                    max_output_tokens=max_tokens
                )
            )
            return r.text
        except Exception as e:
            msg = str(e)
            # Se for quota/rate limit, tenta respeitar o retryDelay
            if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                # tenta extrair retryDelay do JSON, se vier
                retry_seconds = 60
                try:
                    d = json.loads(msg[msg.find("{"):])
                    details = d.get("error", {}).get("details", [])
                    for det in details:
                        if det.get("@type", "").endswith("RetryInfo"):
                            delay = det.get("retryDelay", "60s")
                            retry_seconds = int(delay.replace("s", "")) or 60
                            break
                except Exception:
                    pass
                if tentativa < tentativas - 1:
                    st.warning(f"Quota temporariamente esgotada. Aguardando {retry_seconds}s e tentando novamente...")
                    time.sleep(retry_seconds)
                    continue
            # Se não for erro de quota, ou acabou as tentativas, devolve erro
            return f"[ERRO NO MODELO GOOGLE: {e}]"
    return "[ERRO NO MODELO GOOGLE: muitas tentativas com RESOURCE_EXHAUSTED]"

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

def chunk_text(texto, tamanho=8000):
    return [texto[i:i+tamanho] for i in range(0, len(texto), tamanho)]

def resumir_chunk(chunk):
    prompt = f"""
Você é assessor do TJPR.

Resuma juridicamente o trecho abaixo:

{chunk}

Resumo jurídico, técnico e completo, incluindo pedidos, fundamentos e controvérsias.
"""
    return gerar_conteudo_com_retry(prompt, max_tokens=500, temperatura=0.1)

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
# 0️⃣ GERAR RESUMOS (AJUSTADO PARA FREE TIER)
# ============================================================

modo_economico = st.checkbox("Modo econômico (menos blocos, menos chamadas)", value=True)

if st.button("0️⃣ Gerar Resumos Analíticos (obrigatório)"):
    if not proc_pdf or not acor_pdf:
        st.warning("Envie ambos os PDFs.")
        st.stop()

    with st.spinner("Extraindo texto..."):
        texto_proc = extrair_texto_pdf(proc_pdf)
        texto_acor = extrair_texto_pdf(acor_pdf)

    chunks_proc = chunk_text(texto_proc)
    chunks_acor = chunk_text(texto_acor)

    # Limita quantidade de chunks no free tier
    if modo_economico:
        max_chunks = 5
        chunks_proc = chunks_proc[:max_chunks]
        chunks_acor = chunks_acor[:max_chunks]

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
    r_text = gerar_conteudo_com_retry(prompt, max_tokens=900, temperatura=0.2)
    st.subheader("🔎 Resultado – Inovação Recursal (Google)")
    st.write(r_text)

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
    r_text = gerar_conteudo_com_retry(prompt, max_tokens=900, temperatura=0.2)
    st.subheader("✉️ Resultado – Embargos de Declaração (Google)")
    st.write(r_text)

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
    r_text = gerar_conteudo_com_retry(prompt, max_tokens=1600, temperatura=0.2)
    st.subheader("📝 Sinopse + Comentário (Google)")
    st.write(r_text)
