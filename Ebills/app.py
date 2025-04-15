from flask import Flask, render_template, request, redirect, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database initialization
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meter_boards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            biller_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            meter_number TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meter_id INTEGER NOT NULL,
        previous_reading INTEGER NOT NULL,
        present_reading INTEGER NOT NULL,
        units INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        created_at NUM NOT NULL,      -- Timestamp when the bill is generated
        last_date NUM NOT NULL,       -- Due date for the bill (3 days after generation)
        penalty INTEGER DEFAULT 0,         -- Penalty applied if the last bill is unpaid or delayed
        paid_on NUM NULL,             -- Timestamp when the bill is paid
        FOREIGN KEY (meter_id) REFERENCES meter_boards (id)
    )
''')



    conn.commit()
    conn.close()

init_db()

# SMTP Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_EMAIL = "skylineshopify@gmail.com"
SMTP_PASSWORD = "uyoy itaj vcmq jbdk"

# Utility function to send email
def send_email(recipient, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = recipient
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if not name or not email or not phone or not password or not confirm_password:
            flash('All fields are required!', 'danger')
            return redirect('/register')

        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect('/register')

        hashed_password = generate_password_hash(password)

        try:
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO admins (name, email, phone, password)
                VALUES (?, ?, ?, ?)
            ''', (name, email, phone, hashed_password))
            conn.commit()
            conn.close()

            flash('Admin registered successfully!', 'success')
            return redirect('/login')
        except sqlite3.IntegrityError:
            flash('Error: Email or phone number already exists.', 'danger')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_or_phone = request.form['email_or_phone']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM admins WHERE (email = ? OR phone = ?)
        ''', (email_or_phone, email_or_phone))
        admin = cursor.fetchone()
        conn.close()

        if admin and check_password_hash(admin[4], password):
            session['admin_id'] = admin[0]
            session['admin_name'] = admin[1]
            flash('Login successful!', 'success')
            return redirect('/dashboard')
        else:
            flash('Invalid email/phone or password.', 'danger')

    return render_template('login.html')
import json
@app.route('/dashboard')
def dashboard():
    if 'admin_id' not in session:
        return redirect('/login')

    # Connect to the database
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Query to get total units per created_date and total amount
    c.execute('''
        SELECT strftime('%Y-%m-%d', b.created_at) AS created_date, 
               SUM(b.units) AS total_units, 
               SUM(b.amount) AS total_amount,
               SUM(CASE WHEN b.paid_on IS NOT NULL AND b.paid_on != 0 THEN b.amount ELSE 0 END) AS paid_amount,
               SUM(CASE WHEN b.paid_on IS NULL OR b.paid_on == 0 THEN b.amount ELSE 0 END) AS pending_amount
        FROM bills b
        JOIN meter_boards mb ON b.meter_id = mb.id
        GROUP BY created_date
        ORDER BY created_date
    ''')
    data = c.fetchall()

    # Fetch total power consumption across all meter_id
    c.execute('SELECT SUM(units), SUM(amount) FROM bills')
    total_consumption_data = c.fetchone()

    # Fetch admin name from the session
    admin_name = session.get('admin_name')

    conn.close()

    # Format data for chart
    chart_data = {
        "dates": [row[0] for row in data],
        "units": [row[1] for row in data],
        "amounts": [row[2] for row in data]
    }

    return render_template('dashboard.html', 
                           admin_name=admin_name,
                           total_consumption_data=total_consumption_data,
                           chart_data=json.dumps(chart_data),
                           data=data)

@app.route('/add_meter', methods=['GET', 'POST'])
def add_meter():
    if 'admin_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        name = request.form['name']
        biller_name = request.form['biller_name']
        phone = request.form['phone']
        email = request.form['email']

        if not name or not biller_name or not phone or not email:
            flash('All fields are required!', 'danger')
            return redirect('/add_meter')

        meter_number = "M" + ''.join(random.choices(string.digits, k=6))
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        hashed_password = generate_password_hash(password)

        try:
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO meter_boards (name, biller_name, phone, email, meter_number, password)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, biller_name, phone, email, meter_number, hashed_password))
            conn.commit()
            conn.close()

            # Send email
            subject = "Meter Board Registration Successful"
            body = f"Hello {biller_name},\n\nYour meter board has been successfully registered.\n\nMeter Number: {meter_number}\nPassword: {password}\n\nThank you."
            if send_email(email, subject, body):
                flash('Meter board added and email sent successfully!', 'success')
            else:
                flash('Meter board added, but email could not be sent.', 'warning')

            return redirect('/add_meter')
        except sqlite3.IntegrityError:
            flash('Error: Meter number or email already exists.', 'danger')

    return render_template('add_meter.html')

@app.route('/biller_login', methods=['GET', 'POST'])
def biller_login():
    if request.method == 'POST':
        login_input = request.form['login_input']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM meter_boards 
            WHERE email = ? OR phone = ? OR meter_number = ?
        ''', (login_input, login_input, login_input))
        biller = cursor.fetchone()
        conn.close()

        if biller and check_password_hash(biller[6], password):
            session['biller_id'] = biller[0]
            session['biller_name'] = biller[1]
            session['biller_email'] = biller[4]
            session['biller_phone'] = biller[3]
            session['biller_meter_number'] = biller[5]
            flash('Login successful!', 'success')
            return redirect('/biller_dashboard')
        else:
            flash('Invalid login credentials.', 'danger')

    return render_template('biller_login.html')


@app.route('/biller_dashboard')
def biller_dashboard():
    if 'biller_id' not in session:
        return redirect('/biller_login')

    biller_id = session['biller_id']
    
    # Connect to the database
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Get meter_id from the biller's meter_number in meter_boards table
    c.execute('SELECT id FROM meter_boards WHERE meter_number = ?', (session['biller_meter_number'],))
    meter_id = c.fetchone()[0]

    # Get all bills for this meter_id from the bills table
    c.execute('''
        SELECT id, units, amount, created_at, paid_on
        FROM bills
        WHERE meter_id = ?
    ''', (meter_id,))
    bills = c.fetchall()

    # Separate bills into paid and pending
    paid_bills = [bill for bill in bills if bill[4] is not None]
    pending_bills = [bill for bill in bills if bill[4] is None]

    conn.close()

    return render_template(
        'biller_dashboard.html',
        name=session['biller_name'],
        email=session['biller_email'],
        phone=session['biller_phone'],
        meter_number=session['biller_meter_number'],
        paid_bills=paid_bills,
        pending_bills=pending_bills
    )
@app.route('/get_meter_details')
def get_meter_details():
    meter_number = request.args.get('meter_number')
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Fetch user details for the selected meter number
    cursor.execute('SELECT id, name, phone, email FROM meter_boards WHERE meter_number = ?', (meter_number,))
    meter_details = cursor.fetchone()

    # Fetch the latest bill's present reading for this meter
    cursor.execute('SELECT present_reading FROM bills WHERE meter_id = ? ORDER BY id DESC LIMIT 1', (meter_details[0],))
    last_bill = cursor.fetchone()
    previous_reading = last_bill[0] if last_bill else 0  # Default to 0 if no previous bill

    conn.close()
    return {
        "name": meter_details[1],
        "phone": meter_details[2],
        "email": meter_details[3],
        "previous_reading": previous_reading
    }

@app.route('/biller_logout')
def biller_logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect('/')

from datetime import datetime, timedelta
import pytz

@app.route('/add_bill', methods=['GET', 'POST'])
def add_bill():
    if 'admin_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Fetch all meter numbers
    cursor.execute('SELECT meter_number FROM meter_boards')
    meter_numbers = [row[0] for row in cursor.fetchall()]

    if request.method == 'POST':
        meter_number = request.form['meter_number']
        present_reading = int(request.form['present_reading'])

        # Fetch the user details for the selected meter number
        cursor.execute('SELECT id, name, phone, email FROM meter_boards WHERE meter_number = ?', (meter_number,))
        meter_details = cursor.fetchone()
        meter_id, name, phone, email = meter_details
        from datetime import datetime, timedelta
        import pytz

        # Fetch the latest bill for this meter number
        cursor.execute('SELECT id, present_reading, paid_on FROM bills WHERE meter_id = ? ORDER BY id DESC LIMIT 1', (meter_id,))
        last_bill = cursor.fetchone()

        # Calculate previous reading and delay penalty
        if last_bill:
            last_bill_id, previous_reading, paid_on = last_bill
            if paid_on:
                # Convert paid_on (which is now stored as DATETIME) to a datetime object with timezone info
                paid_on_date = datetime.strptime(paid_on, '%Y-%m-%d %H:%M:%S')
                paid_on_date = pytz.timezone('Asia/Kolkata').localize(paid_on_date)  # Make it aware
            else:
                paid_on_date = None
        else:
            previous_reading = 0
            paid_on_date = None

        # Check for delay and calculate penalty
        penalty = 0
        if last_bill and paid_on_date:
            # Ensure the current time is also aware
            current_time = datetime.now(pytz.timezone('Asia/Kolkata'))  # Make current time aware
            last_due_date = paid_on_date + timedelta(days=3)
            
            if current_time > last_due_date:
                penalty = 100



        # Calculate units and amount
        units = present_reading - previous_reading
        amount = (units * 100) + penalty  # 1 unit = 100 Rs, add penalty if applicable

        # Get current IST date and time
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        last_date = now + timedelta(days=3)

        # Store the bill in the database
        cursor.execute('''
            INSERT INTO bills (meter_id, previous_reading, present_reading, units, amount, created_at, last_date, penalty)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (meter_id, previous_reading, present_reading, units, amount, now.strftime('%Y-%m-%d %H:%M:%S'), 
              last_date.strftime('%Y-%m-%d %H:%M:%S'), penalty))
        conn.commit()

        # Send email with bill details
        subject = "Electricity Bill Generated"
        body = f"""Hello {name},

Your electricity bill has been generated.

Meter Number: {meter_number}
Previous Reading: {previous_reading}
Present Reading: {present_reading}
Units Consumed: {units}
Total Amount: Rs. {amount}
Due Date: {last_date.strftime('%d-%m-%Y')}

Thank you."""
        if send_email(email, subject, body):
            flash('Bill generated and email sent successfully!', 'success')
        else:
            flash('Bill generated, but email could not be sent.', 'warning')

        return redirect('/dashboard')

    conn.close()
    return render_template('add_bill.html', meter_numbers=meter_numbers)
from flask import Flask, render_template, request
import sqlite3
from datetime import datetime
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row  # This allows you to access columns by name
    return conn

# Route for the bill prediction page
@app.route('/predict_bill', methods=['GET', 'POST'])
def predict_bill():
    conn = get_db_connection()

    if request.method == 'POST':
        meter_number = request.form['meter_id']  # This is the entered meter number

        # Step 1: Fetch the meter_id from the meter_boards table
        meter_query = 'SELECT id FROM meter_boards WHERE meter_number = ?'
        meter = conn.execute(meter_query, (meter_number,)).fetchone()
        print(f"Meter Query Result: {meter}")

        if meter:  # If a matching meter is found
            meter_id = meter['id']

            # Step 2: Fetch all paid amounts for the selected meter_id from the bills table
            bills_query = '''
                SELECT amount FROM bills WHERE meter_id = ? AND paid_on IS NOT NULL
            '''
            paid_amounts = conn.execute(bills_query, (meter_id,)).fetchall()
            print(f"Paid Amounts: {paid_amounts}")

            # Step 3: Calculate the average of paid amounts
            if paid_amounts:
                total_amount = sum([amt['amount'] for amt in paid_amounts])
                avg_amount = total_amount / len(paid_amounts)
                print(f"Total Amount: {total_amount}, Average Amount: {avg_amount}")
            else:
                avg_amount = 0
                print("No paid amounts found.")

            predicted_amount = avg_amount
        else:
            # If no matching meter is found, show no prediction
            print("No matching meter found.")
            predicted_amount = None

        conn.close()

        return render_template(
            'predict_bill.html',
            predicted_amount=predicted_amount,
            meter_id=meter_number
        )

    else:
        # For GET request, load the form with no prediction
        conn.close()
        return render_template('predict_bill.html', predicted_amount=None)

@app.route('/view_all_bills')
def view_all_bills():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Fetch pending bills (where paid_on is NULL)
    c.execute('''
        SELECT b.id, mb.biller_name, b.units, b.amount, b.created_at, b.last_date, b.penalty
        FROM bills b
        JOIN meter_boards mb ON b.meter_id = mb.id
        WHERE b.paid_on IS NULL
    ''')
    pending_bills = [
        {
            'id': row[0],
            'biller_name': row[1],
            'units': row[2],
            'amount': row[3],
            'created_at': row[4],
            'last_date': row[5],
            'overdue': "Yes" if row[6] not in (0, None) else "No"  # Overdue based on penalty
        }
        for row in c.fetchall()
    ]

    # Fetch paid bills (where paid_on is NOT NULL)
    c.execute('''
        SELECT b.id, mb.biller_name, b.units, b.amount, b.created_at, b.last_date, b.paid_on, b.penalty
        FROM bills b
        JOIN meter_boards mb ON b.meter_id = mb.id
        WHERE b.paid_on IS NOT NULL
    ''')
    paid_bills = [
        {
            'id': row[0],
            'biller_name': row[1],
            'units': row[2],
            'amount': row[3],
            'created_at': row[4],
            'last_date': row[5],
            'paid_on': row[6],
            'overdue': "Yes" if row[7] not in (0, None) else "No"  # Overdue based on penalty
        }
        for row in c.fetchall()
    ]

    conn.close()

    return render_template('view_all_bills.html', pending_bills=pending_bills, paid_bills=paid_bills)
@app.route('/view_meter_boards')
def view_meter_boards():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id, name, biller_name, phone, email, meter_number FROM meter_boards")
    meter_boards = c.fetchall()
    conn.close()
    return render_template('view_meter_boards.html', meter_boards=meter_boards)
from flask import Flask, render_template, request, redirect, url_for, flash
@app.route('/edit_meter_board/<int:meter_id>', methods=['GET', 'POST'])
def edit_meter_board(meter_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    if request.method == 'POST':
        name = request.form['name']
        biller_name = request.form['biller_name']
        phone = request.form['phone']
        email = request.form['email']
        meter_number = request.form['meter_number']
        password = request.form['password']

        c.execute('''
            UPDATE meter_boards 
            SET name = ?, biller_name = ?, phone = ?, email = ?, meter_number = ?, password = ? 
            WHERE id = ?
        ''', (name, biller_name, phone, email, meter_number, password, meter_id))
        conn.commit()
        conn.close()
        flash("Meter board updated successfully!", "success")
        return redirect(url_for('view_meter_boards'))

    c.execute("SELECT * FROM meter_boards WHERE id = ?", (meter_id,))
    meter_board = c.fetchone()
    conn.close()
    return render_template('edit_meter_board.html', meter_board=meter_board)

@app.route('/delete_meter_board/<int:meter_id>', methods=['POST'])
def delete_meter_board(meter_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM meter_boards WHERE id = ?", (meter_id,))
    conn.commit()
    conn.close()
    flash("Meter board deleted successfully!", "success")
    return redirect(url_for('view_meter_boards'))
    
@app.route('/total_power_consumption')
def total_power_consumption():
    # Connect to the database
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Query to get total units, total amount, and meter_number for each meter_id
    c.execute('''
        SELECT b.meter_id, mb.meter_number, SUM(b.units), SUM(b.amount)
        FROM bills b
        JOIN meter_boards mb ON b.meter_id = mb.id
        GROUP BY b.meter_id
    ''')
    data = c.fetchall()  # Fetch all results

    # Get current date and time
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn.close()

    # Pass the data to the template
    return render_template('total_power_consumption.html', data=data, current_datetime=current_datetime)
import time
@app.route('/pay_bill/<int:bill_id>', methods=['POST'])
def pay_bill(bill_id):
    if 'biller_id' not in session:
        return redirect('/biller_login')

    # Connect to the database
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Get the current date and time in the format 'YYYY-MM-DD HH:MM:SS'
    current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Update the paid_on field with the formatted datetime string
    c.execute('''
        UPDATE bills 
        SET paid_on = ? 
        WHERE id = ?
    ''', (current_datetime, bill_id))
    conn.commit()

    conn.close()

    # Redirect to the biller's dashboard after payment
    return redirect(url_for('biller_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)