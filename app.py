
from flask import Flask, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BMTaskHub</title>
<style>
body {
  background: #101014;
  color: white;
  font-family: Arial, sans-serif;
  text-align: center;
  padding: 35px 15px;
}
.card {
  max-width: 480px;
  margin: 30px auto;
  padding: 28px;
  background: #19171d;
  border: 1px solid #39313b;
  border-radius: 22px;
}
p { color: #bbb; line-height: 1.7; }
a {
  display: inline-block;
  padding: 14px 22px;
  background: #ff793d;
  color: white;
  text-decoration: none;
  border-radius: 12px;
}
</style>
</head>
<body>
<div class="card">
  <h1>🦊 BMTaskHub</h1>
  <p>Find tasks. Complete tasks. Earn rewards.</p>
  <p>💼 Client — Post tasks</p>
  <p>👷 Worker — Complete tasks</p>
  <a href="https://t.me/YOUR_BOT_USERNAME">
    Open Telegram Bot
  </a>
</div>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
