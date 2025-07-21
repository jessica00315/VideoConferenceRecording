# app.py
import streamlit as st
import tempfile
import os
import subprocess
import base64
import requests
import json
from datetime import timedelta
import whisper
import gdown




# ====== 前端設定 ======
st.set_page_config(page_title="影片語音轉文字 + 摘要系統", layout="wide")
st.title("🎧 AI 語音轉文字＋角色摘要工具（繁體中文）")

# ====== 使用者輸入 ======
st.sidebar.header("📥 影片來源與 API 設定")
input_mode = st.sidebar.radio("選擇影片來源：", ["上傳影片檔", "YouTube 連結", "Google Drive 連結"])
gemini_api_key = st.sidebar.text_input("請輸入 Google Gemini API Key", type="password")

# ====== 處理影片來源 ======
def download_from_youtube(url):
    output_path = tempfile.mktemp(suffix=".mp4")
    subprocess.call(["yt-dlp", "-f", "bestaudio", "-o", output_path, url])
    return output_path
    

def download_from_gdrive(url):
    file_id = url.split("/d/")[1].split("/")[0]
    dl_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    response = requests.get(dl_url)
    output_path = tempfile.mktemp(suffix=".mp4")
    with open(output_path, 'wb') as f:
        f.write(response.content)
    return output_path


def extract_audio(video_path):
    audio_path = tempfile.mktemp(suffix=".wav")
    subprocess.call(["ffmpeg", "-i", video_path, "-ar", "16000", "-ac", "1", "-y", audio_path])
    return audio_path

# ====== Whisper 語音辨識（繁體中文） ======
def transcribe_audio(audio_path):
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, language="zh")
    segments = result["segments"]
    transcript_lines = []
    for seg in segments:
        start_time = str(timedelta(seconds=int(seg["start"])))
        speaker_text = seg["text"].strip()
        transcript_lines.append(f"[{start_time}] {speaker_text}")
    return "\n".join(transcript_lines)

# ====== Gemini 摘要功能 ======
def summarize_with_gemini(transcript_text, api_key):
    prompt = "你是一位企業助理，請針對以下逐字稿依照發言者整理條列式摘要：\n\n" + transcript_text

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": api_key
    }

    payload = {
        "contents": [{ "parts": [{ "text": prompt }] }]
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    else:
        return f"❌ 摘要失敗：{response.text}"

# ====== 產出 HTML ======
def generate_html(transcript_text, summary):
    html = """
    <html><head><meta charset='utf-8'>
    <style>
    body { font-family: Arial; line-height: 1.6; padding: 20px; }
    pre { background: #f8f8f8; padding: 10px; border-radius: 5px; }
    h2 { color: #2c3e50; }
    </style></head><body>
    <h2>🎧 語音逐字稿</h2>
    <pre>
""" + transcript_text + """
    </pre>
    <h2>🧠 AI 條列摘要</h2>
    <pre>
""" + summary + """
    </pre></body></html>"""
    return html

# ====== 主流程執行區塊 ======
if input_mode == "上傳影片檔":
    uploaded = st.file_uploader("請上傳影片檔（MP4, MP3）", type=["mp4", "mp3", "wav"])
    if uploaded:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded.name)[1]) as tmp:
            tmp.write(uploaded.read())
            video_path = tmp.name
elif input_mode == "YouTube 連結":
    yt_url = st.sidebar.text_input("請輸入 YouTube 連結")
    if yt_url:
        st.sidebar.info("正在下載 YouTube 音訊…")
        video_path = download_from_youtube(yt_url)
elif input_mode == "Google Drive 連結":
    gdrive_url = st.sidebar.text_input("請輸入 Google Drive 分享連結")
    if gdrive_url:
        st.sidebar.info("正在下載 Google Drive 檔案…")
        video_path = download_from_gdrive(gdrive_url)

if 'video_path' in locals() and gemini_api_key:
    st.info("🎧 擷取音訊中…")
    audio_path = extract_audio(video_path)

    st.info("🔍 擷取語音文字中…（Whisper 模型）")
    transcript_text = transcribe_audio(audio_path)

    st.success("📝 語音文字擷取完成：")
    st.code(transcript_text, language="text")

    st.info("🧠 呼叫 Gemini 進行摘要中…")
    summary = summarize_with_gemini(transcript_text, gemini_api_key)
    st.text_area("🔎 AI 條列摘要結果：", summary, height=300)

    st.info("💾 產出 HTML 檔案…")
    html_str = generate_html(transcript_text, summary)
    b64 = base64.b64encode(html_str.encode()).decode()
    href = f'<a href="data:text/html;base64,{b64}" download="transcript_summary.html">📥 下載完整 HTML 報告</a>'
    st.markdown(href, unsafe_allow_html=True)
