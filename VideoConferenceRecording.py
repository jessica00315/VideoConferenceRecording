import streamlit as st
import tempfile
import os
import whisper
import openai

# 初始化頁面
st.set_page_config(page_title="部門語音紀錄與摘要工具", layout="centered")
st.title("🗂️ 部門紀錄自動轉文字＋摘要")

# Tab 功能：語音轉文字 / 文字摘要
tab1, tab2 = st.tabs(["🎧 語音轉文字", "🧠 AI 摘要整理"])

with tab1:
    st.subheader("上傳影片/音訊 → 自動轉為繁體中文逐字稿")
    uploaded_file = st.file_uploader("請上傳 MP3 / MP4 / WAV", type=["mp3", "mp4", "wav"])

    if uploaded_file:
        with st.spinner("轉換中..."):
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1])
            temp_file.write(uploaded_file.read())
            temp_file_path = temp_file.name
            temp_file.close()

            model = whisper.load_model("base")
            result = model.transcribe(temp_file_path, language="zh")

            st.success("語音轉文字完成！")
            st.text_area("逐字稿內容", result["text"], height=300)

            # 提供下載
            txt_path = temp_file_path + ".txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(result["text"])
            with open(txt_path, "rb") as f:
                st.download_button("📥 下載 txt", f, file_name="transcript.txt")

            os.remove(temp_file_path)
            os.remove(txt_path)

with tab2:
    st.subheader("貼上內容讓 AI 幫你做摘要整理")
    input_text = st.text_area("請貼上部門逐字稿、報告內容...", height=300)

    if st.button("✍️ 開始摘要"):
        if not input_text.strip():
            st.warning("請先輸入文字")
        else:
            with st.spinner("AI 正在摘要中..."):
                # 🔁 請填入你自己的 OpenAI API Key（或使用 HuggingFace 模型也行）
                openai.api_key = st.secrets.get("OPENAI_API_KEY")  # 建議存 secrets

                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "你是一位善於彙整報告的助理，請以條列方式整理重點摘要"},
                        {"role": "user", "content": input_text}
                    ]
                )

                summary = response.choices[0].message.content
                st.success("以下是摘要：")
                st.text_area("AI 摘要結果", summary, height=300)
