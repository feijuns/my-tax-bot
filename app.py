import os
import base64
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, ImageMessage, TextSendMessage

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    try:
        # 1. 從 LINE 取得照片
        message_content = line_bot_api.get_message_content(event.message.id)
        image_bytes = b''
        for chunk in message_content.iter_content():
            image_bytes += chunk
            
        # 2. 將圖片轉成 Base64 代碼
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        # 3. 直接發送請求給 Google 的最新 1.5 Flash 伺服器 (繞過套件)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{
                "parts": [
                    {"text": "請幫我辨識這張發票照片，並直接輸出成國稅局標準的 81 Bytes 媒體申報檔 (TXT格式)。買方統編請預設為：66932243。不要輸出任何其他說明文字，只要那行 81 字元的字串就好。"},
                    {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}
                ]
            }]
        }
        
        # 4. 取得回應
        response = requests.post(url, headers=headers, json=payload)
        response_data = response.json()
        
        # 5. 抓取文字結果
        if 'candidates' in response_data:
            result_text = response_data['candidates'][0]['content']['parts'][0]['text'].strip()
        else:
            result_text = f"API錯誤回傳：{response_data}"
            
    except Exception as e:
        result_text = f"系統發生錯誤，請截圖：\n{str(e)}"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result_text))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
