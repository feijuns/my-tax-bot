import os
import io
import PIL.Image
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, ImageMessage, TextSendMessage
import google.generativeai as genai

app = Flask(__name__)

# 從雲端環境變數抓取金鑰 (保護密碼不外洩)
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro-vision')

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
        img = PIL.Image.open(io.BytesIO(image_bytes))
        
        # 2. 呼叫 Gemini 進行辨識
        prompt = "請幫我辨識這張發票照片，並直接輸出成國稅局標準的 81 Bytes 媒體申報檔 (TXT格式)。買方統編請預設為：66932243。不要輸出任何其他說明文字，只要那行 81 字元的字串就好。"
        response = model.generate_content([prompt, img])
        result_text = response.text.strip()
        
    except Exception as e:
        result_text = f"系統發生錯誤，請把這段文字截圖給小幫手看：\n{str(e)}"

    # 3. 將結果傳回 LINE
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=result_text)
    )

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
