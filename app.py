import streamlit as st
import google.genai as genai
from google.genai.types import GenerateContentConfig
import pandas as pd
import tempfile
import time
import os

st.set_page_config(page_title="Analisador Judicial – TJPR", layout="wide")
st.title("⚖️ Sessão Virtuosa")

st.write("""
Envie os arquivos abaixo para que o sistema analise:
1. Processo judicial inteiro (PDF)
2. Voto ou Acórdão (PDF)
3. Arquivo de modelos de ementa (Excel ou TXT)
""")

# ---------------------------
# CONFIGURAÇÃO DA API
# ---------------------------
API_KEY = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not API_KEY:
    st.error("API KEY não encontrada! Configure GOOGLE_API_KEY nos Secrets do Streamlit.")
    st.stop()

client = genai.Client(api_key=API_KEY)
MODEL = "gemini-2.5-flash"

# ---------------------------
# UPLOAD DE ARQUIVOS
# ---------------------------
processo_file = st.file_uploader("📄 Processo Judicial Completo (PDF)", type=["pdf"])
acordao_file = st.file_uploader("📘 Voto / Acórdão (PDF)", type=["pdf"])
import pandas as pd

def carregar_modelo_ementa():
    df = pd.read_excel("modelo_sessao_virtuosa.xlsx")
    # Transforma em texto contínuo
    return "\n".join(df.astype(str).apply(" – ".join, axis=1))

modelo_ementa = carregar_modelo_ementa()

def upload_to_gemini(uploaded_file):
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name
    return client.files.upload(file=tmp_path, display_name=uploaded_file.name)


def aguardar_processamento(arquivo):
    while arquivo.state in ("PROCESSING", "PENDING"):
        time.sleep(1)
        arquivo = client.files.get(name=arquivo.name)
    return arquivo

# ---------------------------
# BOTÃO – PROCESSAR
# ---------------------------
if st.button("▶️ Executar Análise Completa"):
   if not processo_file or not acordao_file:
       st.warning("Envie o processo e o acórdão antes de prosseguir.")
       st.stop()


    with st.spinner("Carregando arquivos no Google AI..."):
        proc_up = upload_to_gemini(processo_file)
        acor_up = upload_to_gemini(acordao_file)

        proc_up = aguardar_processamento(proc_up)
        acor_up = aguardar_processamento(acor_up)

      
    st.success("Arquivos prontos! Enviando para análise jurídica...")

    prompt = f"""
Você é assessor de desembargador do TJPR.

Sua tarefa é analisar, de forma técnica e objetiva:

1) Verificar **se há inovação recursal** no voto/acórdão enviado.
   - Cite os trechos relevantes do processo.
   - Explique por que há ou não há inovação.

2) Analisar **se cabem embargos de declaração** contra o acórdão.
   Verifique:
   - obscuridade
   - contradição
   - omissão
   - erro material

3) Com base no arquivo de modelo de ementa sinóptica abaixo, gere:
   a) **Ementa sinóptica** no mesmo estilo
   b) **Comentário conciso** sobre a adequação técnica do voto/acórdão.

MODELO DE EMENTA:
-----------------
{modelo_ementa}

IMPORTANTE:
- Responda de modo conciso, objetivo, técnico e no estilo TJPR.
- Use tópicos curtos.
- NÃO invente fatos não presentes no processo.
"""

    with st.spinner("Analisando o acórdão..."):
        resposta = client.models.generate_content(
            model=MODEL,
            contents=[proc_up, acor_up, prompt],
            config=GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=4000
            )
        )

    st.subheader("📌 Resultado da Análise")
    st.write(resposta.text)

    st.success("Concluído!")
