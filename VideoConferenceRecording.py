import streamlit as st
import tempfile
import os
import whisper
from openai import OpenAI

# === 頁面設定 ===
st.set_page_config(page_title="部門紀錄轉文字＋摘要", layout="centered")
st.title("📁 部門紀錄自動轉文字＋摘要")

# === Whisper 模型準備 ===
model = whisper.load_model("base")

# === 建立 Tabs ===
tab1, tab2 = st.tabs(["🎧 語音轉文字", "🧠 AI 摘要整理"])

# === Tab 1：語音轉文字 ===
with tab1:
    uploaded_file = st.file_uploader("請上傳 MP3 / MP4 / WAV", type=["mp3", "mp4", "wav"])

    if uploaded_file:
        with st.spinner("轉換中..."):
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1])
            temp_file.write(uploaded_file.read())
            temp_file_path = temp_file.name
            temp_file.close()

            result = model.transcribe(temp_file_path, language="zh")

            st.success("✅ 語音轉文字完成！")
            st.text_area("逐字稿內容", result["text"], height=300)

            txt_path = temp_file_path + ".txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(result["text"])
            with open(txt_path, "rb") as f:
                st.download_button("📥 下載轉錄文字檔 (.txt)", f, file_name="transcript.txt")

            os.remove(temp_file_path)
            os.remove(txt_path)

# === Tab 2：AI 摘要整理 ===
with tab2:
    st.subheader("貼上內容讓 AI 幫你做摘要整理")
    input_text = st.text_area("請貼上部門逐字稿或報告內容")

    if st.button("開始摘要"):
        if input_text.strip() == "":
            st.warning("請先輸入內容！")
        else:
            with st.spinner("AI 正在摘要中..."):
                api_key = st.secrets["OPENAI_API_KEY"]  # 應在 .streamlit/secrets.toml 設定
                client = OpenAI(api_key=api_key)

                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "你是一位幫助企業整理會議重點的助理，請用條列式摘要"},
                        {"role": "user", "content": input_text}
                    ]
                )
                summary = response.choices[0].message.content
                st.success("✅ 摘要完成")
                st.text_area("AI 摘要結果", summary, height=300)
