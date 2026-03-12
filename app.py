import os
import base64
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, ImageMessage, TextSendMessage
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# 載入金鑰
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# 設定 Google Sheets 驗證 (讓機器人拿工作證登入)
scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file('google_key.json', scopes=scope)
client = gspread.authorize(creds)

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
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        # 2. 呼叫 Gemini 辨識 (要求輸出 CSV 格式)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        prompt = """
        請幫我辨識這張發票照片，並直接輸出成純文字（以逗號分隔），不要任何標題行、不要多餘說明、不要用 Markdown 標記。
        買方統編請預設為：66932243。
        請嚴格按照以下順序輸出這 8 個欄位：
        發票日期(YYYY/MM/DD),發票字軌號碼,賣方統一編號,買方統一編號,銷售額,營業稅額,總計金額,格式代號
        """
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}
                ]
            }]
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response_data = response.json()
        
        # 3. 抓取文字結果並寫入 Excel
        if 'candidates' in response_data:
            result_text = response_data['candidates'][0]['content']['parts'][0]['text'].strip()
            
            # 將逗號分隔的文字轉換成陣列
            row_data = [item.strip() for item in result_text.split(',')]
            
            # 開啟你的 Google 試算表 (檔名必須是「發票記帳」)
            sheet = client.open('發票記帳').sheet1
            sheet.append_row(row_data)
            
            reply_msg = f"✅ 記帳成功！已幫你自動填入雲端 Excel：\n{result_text}"
        else:
            reply_msg = f"API錯誤回傳：{response_data}"
            
    except Exception as e:
        reply_msg = f"系統發生錯誤，請截圖：\n{str(e)}"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
