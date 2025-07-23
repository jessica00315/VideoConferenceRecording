# VideoConferenceRecording.py
import streamlit as st
import tempfile
import os
import subprocess
import base64
import requests
import json
import whisper
import asyncio
import time
import gc
from datetime import datetime, timedelta

st.set_page_config(page_title="影片語音轉文字 + 摘要系統", layout="wide")
st.title("🎧 AI 語音轉文字＋角色摘要工具（繁體中文, Async 支援）")

log_path = "log.txt"
if not os.path.exists(log_path):
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("==== 使用紀錄 ====")

def write_log(message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n[{now}] {message}")

st.sidebar.header("📥 影片來源與 API 設定")
input_mode = st.sidebar.radio("選擇影片來源：", ["上傳影片檔", "YouTube 連結", "Google Drive 連結"])
gemini_api_key = st.sidebar.text_input("請輸入 Google Gemini API Key", type="password")
cleanup_files = st.sidebar.checkbox("任務完成後自動刪除影片與音訊檔案", value=True)

def extract_audio(video_path):
    audio_path = tempfile.mktemp(suffix=".mp3")
    subprocess.run(["ffmpeg", "-i", video_path, "-vn", "-ar", "16000", "-ac", "1", "-y", audio_path], capture_output=True)
    write_log(f"從影片擷取音訊：{video_path} -> {audio_path}")
    return audio_path

def generate_html(transcript_text, summary):
    lines = transcript_text.split('\n')
    toggled_segments = ''
    for i, line in enumerate(lines):
        toggled_segments += f"<details><summary>段落 {i+1}</summary><p>{line}</p></details>\n"

    return f"""
    <html><head><meta charset='utf-8'>
    <style>
    body {{ font-family: Arial; line-height: 1.6; padding: 20px; }}
    h2 {{ color: #2c3e50; }}
    pre, details {{ background: #f4f4f4; border: 1px solid #ccc; border-radius: 5px; padding: 10px; margin-bottom: 10px; }}
    summary {{ font-weight: bold; cursor: pointer; }}
    </style></head><body>
    <h2>🧠 AI 條列摘要</h2>
    <pre>{summary}</pre>
    <h2>🎧 語音逐字稿（可收合）</h2>
    {toggled_segments}
    </body></html>
    """

def download_from_youtube(url):
    output_path = tempfile.mktemp(suffix=".mp4")
    subprocess.call(["yt-dlp", "-f", "bestaudio", "-o", output_path, url])
    write_log(f"從 YouTube 下載影片：{url}")
    return output_path

def download_from_gdrive(url):
    file_id = url.split("/d/")[1].split("/")[0]
    dl_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    response = requests.get(dl_url)
    output_path = tempfile.mktemp(suffix=".mp4")
    with open(output_path, 'wb') as f:
        f.write(response.content)
    write_log(f"從 Google Drive 下載影片：{url}")
    return output_path

async def transcribe_audio_with_progress(audio_path):
    st.info("🔍 使用 Whisper 處理中…")
    model = whisper.load_model("large-v2")
    result = model.transcribe(audio_path, language="zh", verbose=False)
    transcript_lines = []
    progress = st.progress(0)
    segments = result["segments"]
    total = len(segments)
    for i, seg in enumerate(segments):
        start = str(timedelta(seconds=int(seg["start"])))
        text = seg["text"].strip()
        transcript_lines.append(f"[{start}] {text}")
        await asyncio.sleep(0.01)
        progress.progress((i + 1) / total)
    progress.empty()
    return "\n".join(transcript_lines)

async def summarize_with_gemini(transcript_text, api_key):
    prompt = (
        "你是一位會議記錄整理助理，請依據以下逐字稿，自動分析每段對話的說話者特徵與主題，"
        "將不同講者的內容進行條列式歸類，摘要要有邏輯清楚的結構與標題：\n\n" + transcript_text
    )
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    headers = {"Content-Type": "application/json", "X-goog-api-key": api_key}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        write_log("✅ Gemini 摘要成功")
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    else:
        raise RuntimeError(response.text)

# ====== 處理影片來源 ======
MAX_FILE_SIZE_MB = 500
video_path = None
if input_mode == "上傳影片檔":
    uploaded = st.file_uploader("請上傳影片檔（MP4, MP3, WAV, WEBM）", type=["mp4", "mp3", "wav", "webm"])
    if uploaded:
        uploaded.seek(0, os.SEEK_END)
        file_size_mb = uploaded.tell() / (1024 * 1024)
        uploaded.seek(0)
        if file_size_mb > MAX_FILE_SIZE_MB:
            st.error(f"🚨 檔案大小為 {file_size_mb:.2f} MB，超過限制（{MAX_FILE_SIZE_MB}MB）")
        else:
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

# ====== 非同步主流程執行 ======
if video_path and gemini_api_key:
    if st.button("▶️ 開始語音辨識與摘要（Async）"):
        async def main_flow():
            audio_path = extract_audio(video_path)
            if cleanup_files and os.path.exists(video_path):
                os.remove(video_path)
                st.sidebar.info("🧹 已刪除原始影片檔")
            transcript_text = await transcribe_audio_with_progress(audio_path)
            st.code(transcript_text, language="text")
            st.info("🧠 Gemini 進行摘要中…")
            summary = await summarize_with_gemini(transcript_text, gemini_api_key)
            st.text_area("🔎 條列摘要結果（自動分類講者）", summary, height=300)
            html_str = generate_html(transcript_text, summary)
            b64 = base64.b64encode(html_str.encode()).decode()
            href = f'<a href="data:text/html;base64,{b64}" download="transcript_summary.html">📥 下載 HTML 報告</a>'
            st.markdown(href, unsafe_allow_html=True)
            if cleanup_files and os.path.exists(audio_path):
                os.remove(audio_path)
                st.sidebar.info("🧹 已刪除音訊檔")
        asyncio.run(main_flow())

# ====== Log 下載 ======
if os.path.exists(log_path):
    with open(log_path, "r", encoding="utf-8") as f:
        st.sidebar.download_button("📄 下載操作紀錄 Log", f, file_name="轉錄紀錄_log.txt")

