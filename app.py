from flask import Flask, render_template, request, redirect, session
import sqlite3
import razorpay

app = Flask(__name__)
app.secret_key = "secret123"

# 🔐 RAZORPAY KEYS (REPLACE WITH YOURS)
RAZORPAY_KEY_ID = "rzp_test_SkDRUaJTUjukVV"
RAZORPAY_KEY_SECRET = "B8Io4cCVeqL3SvGZ8Ho7rLe0"

client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# 🚌 Dummy bus data
buses = [
    {"id": 1, "from": "Bangalore", "to": "Chennai", "time": "10:00 AM", "price": 500},
    {"id": 2, "from": "Bangalore", "to": "Hyderabad", "time": "08:00 PM", "price": 700}
]

# 📦 DATABASE INIT
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bus_id INTEGER,
            seat TEXT,
            date TEXT
        )
    ''')

    conn.commit()
    conn.close()

init_db()


# 🏠 HOME
@app.route('/')
def home():
    return render_template('index.html')


# 🔐 REGISTER
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()

        return redirect('/login')

    return render_template('register.html')


# 🔐 LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user'] = username
            return redirect('/')
        else:
            return "Invalid login!"

    return render_template('login.html')


# 🚪 LOGOUT
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')


# 🔍 SEARCH
@app.route('/search', methods=['POST'])
def search():
    from_city = request.form.get('from')
    to_city = request.form.get('to')
    date = request.form.get('date')

    results = [
        b for b in buses
        if b["from"].lower() == from_city.lower() and b["to"].lower() == to_city.lower()
    ]

    return render_template('search.html', buses=results, date=date)


# 🪑 SELECT BUS
@app.route('/select/<int:bus_id>')
def select_bus(bus_id):
    if 'user' not in session:
        return redirect('/login')

    date = request.args.get('date')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT seat FROM bookings WHERE bus_id=? AND date=?", (bus_id, date))
    booked_seats = [row[0] for row in cursor.fetchall()]
    conn.close()

    bus = next((b for b in buses if b["id"] == bus_id), None)

    return render_template('seats.html', bus=bus, date=date, booked_seats=booked_seats)


# 💳 PAYMENT (CREATE ORDER)
@app.route('/book', methods=['POST'])
def book():

    if 'user' not in session:
        return redirect('/login')

    bus_id = request.form.get('bus_id')
    seat = request.form.get('seat')
    date = request.form.get('date')

    if not bus_id or not seat or not date:
        return "❌ Missing data"

    # 🔍 check already booked
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM bookings WHERE bus_id=? AND seat=? AND date=?",
        (bus_id, seat, date)
    )

    if cursor.fetchone():
        conn.close()
        return "❌ Seat already booked!"

    conn.close()

    # 💰 amount (you can change later)
    amount = 500 * 100

    # 🧾 create order
    order = client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })

    return render_template(
        "payment.html",
        order_id=order["id"],
        amount=amount,
        bus_id=bus_id,
        seat=seat,
        date=date
    )

@app.route('/success')
def success():
    return '''
    <html>
    <head>
    <style>
    body {
        font-family: Arial;
        background: #f5f5f5;
        text-align: center;
        padding-top: 100px;
    }
    .box {
        background: white;
        padding: 30px;
        margin: auto;
        width: 350px;
        border-radius: 10px;
        box-shadow: 0 0 10px gray;
    }
    .success {
        color: green;
        font-size: 22px;
    }
    </style>
    </head>
    <body>

    <div class="box">
        <div class="success">Payment Successful!</div>
        <p>Your seat is booked.</p>
        <a href="/">Go Home</a>
    </div>

    </body>
    </html>
    '''

@app.route('/verify_payment', methods=['POST'])
def verify_payment():

    data = request.get_json()

    razorpay_order_id = data.get('razorpay_order_id')
    razorpay_payment_id = data.get('razorpay_payment_id')
    razorpay_signature = data.get('razorpay_signature')

    bus_id = data.get('bus_id')
    seat = data.get('seat')
    date = data.get('date')

    try:
        # 🔐 Verify signature
        client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        })

        # ✅ Only save after verification
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO bookings (bus_id, seat, date) VALUES (?, ?, ?)",
            (bus_id, seat, date)
        )

        conn.commit()
        conn.close()

        return "success"

    except:
        return "failed"
    
if __name__ == '__main__':
    app.run(debug=True)