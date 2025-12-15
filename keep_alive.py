from flask import Flask
from threading import Thread

# تهيئة تطبيق Flask
app = Flask('')

# دالة مسار الصفحة الرئيسية (تظهر عند زيارة الرابط العام)
@app.route('/')
def home():
    return "Bot is awake and running!"

# دالة لتشغيل الخادم في Thread منفصلة
def run():
    # تشغيل الخادم على المنفذ 8080 وبشكل عام
    app.run(host='0.0.0.0', port=8080)

# الدالة الرئيسية التي يتم استدعاؤها من main.py
def keep_alive():
    t = Thread(target=run)
    t.start()
