import socket
import io
import base64
from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO, emit
import qrcode

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# 取得電腦在局域網內的 IP 位址
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

PORT = 5000
LOCAL_IP = get_local_ip()
VOTE_URL = f"http://{LOCAL_IP}:{PORT}/vote"

# 投票資料
poll_data = {
    "options": ["台灣", "日本", "韓國"],
    "votes": {"台灣": 0, "日本": 0, "韓國": 0}
}

# HTML 範本 (電腦端)
INDEX_HTML = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>文字雲投票主控台 (Python)</title>
    <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/wordcloud@1.2.2/src/wordcloud2.min.js"></script>
    <style>
        body { font-family: sans-serif; max-width: 1000px; margin: 20px auto; padding: 20px; background: #f0f2f5; }
        .flex { display: flex; gap: 20px; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .qr-card { text-align: center; width: 250px; }
        .main-card { flex: 1; }
        .tag { display: inline-block; background: #e4e6eb; padding: 5px 10px; border-radius: 15px; margin: 3px; }
        #canvas-container { width: 100%; height: 400px; background: #fff; border: 1px solid #ccc; }
        img { max-width: 180px; }
    </style>
</head>
<body>
    <div class="flex">
        <div class="card qr-card">
            <h3>📱 手機掃碼投票</h3>
            <img id="qrcode" src="" alt="QR Code Loading...">
            <p id="vote-url" style="font-size: 12px; color: #666; word-break: break-all;"></p>
        </div>
        <div class="card main-card">
            <h3>⚙️ 選項管理</h3>
            <input type="text" id="new-opt" placeholder="輸入新選項">
            <button onclick="addOption()">新增</button>
            <button onclick="resetVotes()" style="color:red; margin-left: 20px;">重置票數</button>
            <div id="options-list" style="margin-top: 10px;"></div>
        </div>
    </div>
    <div class="card">
        <h3>☁️ 即時票選文字雲</h3>
        <div id="canvas-container">
            <canvas id="cloud-canvas" width="920" height="400"></canvas>
        </div>
    </div>

    <script>
        const socket = io();

        fetch('/api/info')
            .then(res => res.json())
            .then(data => {
                document.getElementById('qrcode').src = data.qrCode;
                document.getElementById('vote-url').innerText = data.url;
            });

        function addOption() {
            const input = document.getElementById('new-opt');
            if (input.value.trim()) {
                socket.emit('add_option', { option: input.value.trim() });
                input.value = '';
            }
        }

        function removeOption(opt) {
            socket.emit('remove_option', { option: opt });
        }

        function resetVotes() {
            if (confirm("確定要重置票數嗎？")) socket.emit('reset_votes');
        }

        socket.on('update_data', (data) => {
            const list = document.getElementById('options-list');
            list.innerHTML = data.options.map(opt => 
                `<span class="tag">${opt} (${data.votes[opt] || 0}票) 
                    <b style="cursor:pointer;color:red" onclick="removeOption('${opt}')">✕</b>
                </span>`
            ).join('');

            const cloudData = data.options.map(opt => [opt, (data.votes[opt] || 0) * 15 + 15]);
            WordCloud(document.getElementById('cloud-canvas'), {
                list: cloudData,
                gridSize: 8,
                weightFactor: 1,
                color: 'random-dark',
                rotateRatio: 0.2
            });
        });
    </script>
</body>
</html>
"""

# HTML 範本 (手機端)
VOTE_HTML = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>手機投票</title>
    <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    <style>
        body { font-family: sans-serif; padding: 20px; text-align: center; background: #f8f9fa; }
        .vote-btn {
            display: block; width: 100%; padding: 15px; margin: 10px 0;
            font-size: 18px; color: white; background: #007bff;
            border: none; border-radius: 8px; cursor: pointer;
        }
        .vote-btn:active { background: #0056b3; }
    </style>
</head>
<body>
    <h2>請選擇一項進行投票</h2>
    <div id="buttons-container"></div>

    <script>
        const socket = io();

        function vote(opt) {
            socket.emit('cast_vote', { option: opt });
            alert(`已成功投給「${opt}」！`);
        }

        socket.on('update_data', (data) => {
            const container = document.getElementById('buttons-container');
            container.innerHTML = data.options.map(opt => 
                `<button class="vote-btn" onclick="vote('${opt}')">${opt}</button>`
            ).join('');
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/vote')
def vote_page():
    return render_template_string(VOTE_HTML)

@app.route('/api/info')
def get_info():
    # 動態生成 QR Code Base64 圖片
    qr = qrcode.make(VOTE_URL)
    buffered = io.BytesIO()
    qr.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    return jsonify({
        "url": VOTE_URL,
        "qrCode": f"data:image/png;base64,{img_str}"
    })

# Socket.io 事件處理
@socketio.on('connect')
def handle_connect():
    emit('update_data', poll_data)

@socketio.on('add_option')
def handle_add_option(data):
    opt = data.get('option')
    if opt and opt not in poll_data['options']:
        poll_data['options'].append(opt)
        poll_data['votes'][opt] = 0
        emit('update_data', poll_data, broadcast=True)

@socketio.on('remove_option')
def handle_remove_option(data):
    opt = data.get('option')
    if opt in poll_data['options']:
        poll_data['options'].remove(opt)
        poll_data['votes'].pop(opt, None)
        emit('update_data', poll_data, broadcast=True)

@socketio.on('cast_vote')
def handle_cast_vote(data):
    opt = data.get('option')
    if opt in poll_data['votes']:
        poll_data['votes'][opt] += 1
        emit('update_data', poll_data, broadcast=True)

@socketio.on('reset_votes')
def handle_reset_votes():
    for opt in poll_data['options']:
        poll_data['votes'][opt] = 0
    emit('update_data', poll_data, broadcast=True)

if __name__ == '__main__':
    print(f"=========================================")
    print(f"伺服器已啟動！")
    print(f"電腦主控台: http://localhost:{PORT}")
    print(f"手機投票網址 (同Wi-Fi): {VOTE_URL}")
    print(f"=========================================")
    socketio.run(app, host='0.0.0.0', port=PORT, debug=True)