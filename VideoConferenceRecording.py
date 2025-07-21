# app.py
import streamlit as st
import tempfile
import os
import subprocess
import base64
import requests
import json
from datetime import timedelta

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

# ====== 語音辨識（使用 Google Speech-to-Text） ======
def fake_transcription(audio_path):
    # 模擬語音辨識輸出（請替換為真正 Google Speech-to-Text 調用）
    return [
        {"start": 12, "speaker": "總經理", "text": "我們今天要討論的是永續包材的推進。"},
        {"start": 95, "speaker": "行銷主管", "text": "我建議下季聚焦於核心產品推廣。"},
    ]

# ====== Gemini 摘要功能 ======
def summarize_with_gemini(text_blocks, api_key):
    prompt = """你是一位企業助理，請針對以下逐字稿依照發言者整理條列式摘要：

"""
    for blk in text_blocks:
        prompt += f"【{blk['speaker']}】：{blk['text']}\n"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
    }
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    response = requests.post(url, headers=headers, data=json.dumps(payload))

    if response.status_code == 200:
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    else:
        return f"❌ 摘要失敗：{response.text}"

# ====== 產出 HTML ======
def generate_html(transcript, summary):
    html = """
    <html><head><meta charset='utf-8'>
    <style>
    body { font-family: Arial; line-height: 1.6; padding: 20px; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 40px; }
    th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
    th { background-color: #f0f0f0; }
    h2 { color: #2c3e50; }
    </style></head><body>
    <h2>🎧 語音逐字稿</h2>
    <table><tr><th>時間</th><th>發言者</th><th>發言內容</th></tr>
    """
    for item in transcript:
        time_str = str(timedelta(seconds=int(item['start'])))
        html += f"<tr><td>{time_str}</td><td>{item['speaker']}</td><td>{item['text']}</td></tr>"
    html += "</table>"
    html += "<h2>🧠 AI 條列摘要</h2>"
    html += summary.replace("\n", "<br>")
    html += "</body></html>"
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

    st.info("🔍 語音辨識中…（示意版，請串接 Google Speech-to-Text）")
    transcript = fake_transcription(audio_path)  # TODO: 替換為正式辨識

    st.success("📝 語音轉文字完成！")
    for item in transcript:
        st.markdown(f"`[{str(timedelta(seconds=item['start']))}]` **{item['speaker']}**：{item['text']}")

    st.info("🧠 呼叫 Gemini 進行摘要中…")
    summary = summarize_with_gemini(transcript, gemini_api_key)
    st.text_area("🔎 AI 條列摘要結果：", summary, height=300)

    st.info("💾 產出 HTML 檔案…")
    html_str = generate_html(transcript, summary)
    b64 = base64.b64encode(html_str.encode()).decode()
    href = f'<a href="data:text/html;base64,{b64}" download="transcript_summary.html">📥 下載完整 HTML 報告</a>'
    st.markdown(href, unsafe_allow_html=True)
