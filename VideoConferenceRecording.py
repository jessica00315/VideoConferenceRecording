# app.py
import streamlit as st
import tempfile
import os
import subprocess
import base64
import requests
import json
import whisper
import time
import gc
from datetime import datetime, timedelta

# ====== 頁面設定 ======
st.set_page_config(page_title="影片語音轉文字 + 摘要系統", layout="wide")
st.title("🎧 AI 語音轉文字＋角色摘要工具（繁體中文）")

log_path = "log.txt"
if not os.path.exists(log_path):
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("==== 使用紀錄 ====")

def write_log(message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n[{now}] {message}")

# ====== 側欄設定 ======
st.sidebar.header("📥 影片來源與 API 設定")
input_mode = st.sidebar.radio("選擇影片來源：", ["上傳影片檔", "YouTube 連結", "Google Drive 連結"])
gemini_api_key = st.sidebar.text_input("請輸入 Google Gemini API Key", type="password")
cleanup_files = st.sidebar.checkbox("✅ 任務完成後自動刪除影片與音訊檔案", value=True)

# ====== ffmpeg 測試 ======
try:
    subprocess.run(["ffmpeg", "-version"], check=True)
    st.sidebar.success("✅ ffmpeg 成功安裝")
except Exception as e:
    st.sidebar.error(f"❌ ffmpeg 無法執行: {e}")
    write_log(f"ffmpeg 錯誤：{e}")

# ====== 影片處理函式 ======
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

def extract_audio(video_path):
    audio_path = tempfile.mktemp(suffix=".wav")
    subprocess.run(["ffmpeg", "-i", video_path, "-ar", "16000", "-ac", "1", "-y", audio_path], capture_output=True)
    write_log(f"從影片擷取音訊：{video_path} -> {audio_path}")
    return audio_path

def transcribe_audio(audio_path):
    import whisper
    from datetime import timedelta

    st.info("🔍 擷取語音文字中…（Whisper 模型）")
    start_time = time.time()

    model = whisper.load_model("base")  # 你也可以改成 "small" 會比較快

    # 執行辨識，取得 segment 結果
    result = model.transcribe(audio_path, language="zh", verbose=False)
    segments = result["segments"]
    transcript_lines = []

    # 加入進度條顯示
    progress_bar = st.progress(0)
    total_segments = len(segments)

    for i, seg in enumerate(segments):
        start = str(timedelta(seconds=int(seg["start"])))
        text = seg["text"].strip()
        transcript_lines.append(f"[{start}] {text}")

        percent = int((i + 1) / total_segments * 100)
        progress_bar.progress(percent)

    progress_bar.empty()
    end_time = time.time()

    st.success(f"📝 語音文字擷取完成！耗時：{end_time - start_time:.2f} 秒")
    write_log(f"語音辨識完成：{audio_path}，共 {total_segments} 段，耗時 {end_time - start_time:.2f} 秒")

    return "\n".join(transcript_lines)

def summarize_with_gemini(transcript_text, api_key):
    prompt = "你是一位企業助理，請針對以下逐字稿依照發言者整理條列式摘要：\n\n" + transcript_text
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    headers = {"Content-Type": "application/json", "X-goog-api-key": api_key}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        write_log("呼叫 Gemini 取得摘要成功")
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    else:
        write_log(f"Gemini 摘要失敗：{response.text}")
        return f"❌ 摘要失敗：{response.text}"

def generate_html(transcript_text, summary):
    html = f"""
    <html><head><meta charset='utf-8'>
    <style>
    body {{ font-family: Arial; line-height: 1.6; padding: 20px; }}
    pre {{ background: #f8f8f8; padding: 10px; border-radius: 5px; }}
    h2 {{ color: #2c3e50; }}
    </style></head><body>
    <h2>🎧 語音逐字稿</h2>
    <pre>
{transcript_text}
    </pre>
    <h2>🧠 AI 條列摘要</h2>
    <pre>
{summary}
    </pre></body></html>"""
    return html

# ====== 處理影片來源 ======
video_path = None
if input_mode == "上傳影片檔":
    uploaded = st.file_uploader("請上傳影片檔（MP4, MP3, WAV）", type=["mp4", "mp3", "wav","webm"])
    if uploaded:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded.name)[1]) as tmp:
            tmp.write(uploaded.read())
            video_path = tmp.name
        write_log(f"使用者上傳影片：{uploaded.name}")
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

# ====== 主流程執行區 ======
if video_path and gemini_api_key:
    if st.button("▶️ 開始語音辨識與摘要"):
        audio_path = None
        try:
            start_audio = time.time()
            st.info("🎧 擷取音訊中…")
            audio_path = extract_audio(video_path)
            end_audio = time.time()
            st.success(f"🎧 音訊擷取完成！耗時：{end_audio - start_audio:.2f} 秒")

            st.info("🔍 擷取語音文字中…（Whisper 模型）")
            start_transcribe = time.time()
            transcript_text = transcribe_audio(audio_path)
            end_transcribe = time.time()
            st.success(f"📝 語音文字擷取完成！耗時：{end_transcribe - start_transcribe:.2f} 秒")
            st.code(transcript_text, language="text")

            st.info("🧠 呼叫 Gemini 進行摘要中…")
            start_summary = time.time()
            summary = summarize_with_gemini(transcript_text, gemini_api_key)
            end_summary = time.time()
            st.success(f"🧠 Gemini 摘要完成！耗時：{end_summary - start_summary:.2f} 秒")
            st.text_area("🔎 AI 條列摘要結果：", summary, height=300)

            st.info("💾 產出 HTML 檔案…")
            html_str = generate_html(transcript_text, summary)
            b64 = base64.b64encode(html_str.encode()).decode()
            href = f'<a href="data:text/html;base64,{b64}" download="transcript_summary.html">📥 下載完整 HTML 報告</a>'
            st.markdown(href, unsafe_allow_html=True)
            write_log("📥 使用者下載 HTML 成果報告")

        except Exception as e:
            st.error(f"❌ 發生錯誤：{e}")
            write_log(f"❌ 發生錯誤：{e}")

        finally:
            if cleanup_files:
                if video_path and os.path.exists(video_path):
                    os.remove(video_path)
                    st.sidebar.info("🧹 已自動刪除影片檔")
                    write_log(f"✅ 已刪除影片：{video_path}")
                if audio_path and os.path.exists(audio_path):
                    os.remove(audio_path)
                    st.sidebar.info("🧹 已自動刪除音訊檔")
                    write_log(f"✅ 已刪除音訊：{audio_path}")
            gc.collect()

# ====== 提供 LOG 下載 ======
with open(log_path, "r", encoding="utf-8") as f:
    st.sidebar.download_button("📄 下載操作紀錄 Log", f, file_name="轉錄紀錄_log.txt")
