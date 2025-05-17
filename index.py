#pip install Flask Flask-Login Flask-WTF psycopg2-binary hugchat requests pandas convertapi langdetect scikit-learn
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, MultipleFileField, DateTimeField
from wtforms.validators import DataRequired
import psycopg2
import json
from decimal import Decimal
from hugchat import hugchat
from hugchat.login import Login
import re
import requests
from datetime import datetime, timedelta
import pandas as pd  
import os
import convertapi
import random
import string
from langdetect import detect
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sfgfsjtdjtdjdjdt'

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
ALLOWED_EXTENSIONS = {'dwg', 'dxf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
api_key = '39e988e2fb55418c89445738230912'
convertapi.api_secret = '9Vyjri0fda9GMjuc'

db_config = {
    'host': '161.97.70.226',
    'user': 'iconstruct',
    'password': 'u9fk9jp0Ux4dlj71OCKb',
    'database': 'iconstruct',
}

connection = psycopg2.connect(**db_config)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_id, username, password):
        self.id = user_id
        self.username = username
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    with connection.cursor() as cursor:
        #cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
        user_data = cursor.fetchone()
        if user_data:
            return User(*user_data)
        else:
            return None
        
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/')
def home():
    return '<a href="/dashboard">dashboard</a>'

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        with connection.cursor() as cursor:
            cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password))
            user_data = cursor.fetchone()
        if user_data:
            user = User(*user_data)
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout successful!', 'success')
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT * FROM {current_user.username}')
        projects = cursor.fetchall()
    return render_template('dashboard.html', username=current_user.username, projects=projects)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        with connection.cursor() as cursor:
            cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
            existing_user = cursor.fetchone()
            if existing_user:
                flash('Username is already taken. Please choose a different one.', 'error')
            else:
                cursor.execute('INSERT INTO users (username, password) VALUES (%s, %s) RETURNING id', (username, password))
                new_user_id = cursor.fetchone()[0]
                cursor.execute(f'CREATE TABLE {username} (id serial PRIMARY KEY, projectname VARCHAR);')
                cursor.execute(f'CREATE TABLE {username}_data (key VARCHAR(255), value VARCHAR(255));')
                cursor.execute(f"INSERT INTO {username}_data (key, value) VALUES ('name', ''), ('username', '{username}'), ('email', ''), ('phone', ''), ('organization', ''), ('city', '');")
                connection.commit()
                user = User(new_user_id, username, password)
                login_user(user)
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('user_profile'))
    return render_template('register.html', form=form)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def user_profile():
    if request.method == 'GET':
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {current_user.username}_data")
            user_data = cursor.fetchall()
        user_dict = {key: value for key, value in user_data}
        return render_template('profile.html', user=user_dict)
    if request.method == 'POST':
        updated_data = {key: request.form[key] for key in request.form}
        with connection.cursor() as cursor:
            for key, value in updated_data.items():
                if key != 'username':
                    cursor.execute(
                        f"UPDATE {current_user.username}_data "
                        f"SET value = '{value}' "
                        f"WHERE key = '{key}';"
                    )
            connection.commit()
        return redirect(url_for('user_profile'))
    return render_template('profile.html')

@app.route('/createproject', methods=['GET', 'POST'])
@login_required
def project_form():
    if request.method == 'POST':
        project_data = {
            'project_name': request.form['projectName'],
            'client': request.form['client'],
            'type': request.form['type'],
            'start_date': request.form['startDate'],
            'end_date': request.form['endDate'],
            'location': request.form['projectLocation']
        }
        project_name = project_data['project_name']
        values = project_data.values()
        data = list(values)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {current_user.username}_{project_name}_inventory (id SERIAL PRIMARY KEY, item VARCHAR(255), quantity INTEGER, rate numeric(10,2) DEFAULT 0.00, price numeric(10,2) DEFAULT 0.00, entries jsonb);")
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {current_user.username}_{project_name}_manpower (id SERIAL PRIMARY KEY, department VARCHAR(255), num_workers INTEGER);")
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {current_user.username}_{project_name}_equipment (id SERIAL PRIMARY KEY, equipment VARCHAR(255), available INTEGER, standby INTEGER);")
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {current_user.username}_{project_name}_cad (id SERIAL PRIMARY KEY, title VARCHAR(255), filename VARCHAR(255));")
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {current_user.username}_{project_name}_workerdata (id SERIAL PRIMARY KEY, unid VARCHAR(10), name VARCHAR(255) NOT NULL, phone VARCHAR(20) NOT NULL, department VARCHAR(255) NOT NULL, aadharid VARCHAR(20) NOT NULL, nativecity VARCHAR(255) NOT NULL, emergencycontact VARCHAR(20) NOT NULL);")
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {current_user.username}_{project_name}_projectdata (key VARCHAR(255), value VARCHAR(255));")
            cursor.execute(f"INSERT INTO {current_user.username}_{project_name}_projectdata (key, value) VALUES ('project_name', '{data[0]}'), ('project_manager', '{current_user.username}'), ('client', '{data[1]}'), ('type', '{data[2]}'), ('start_date', '{data[3]}'), ('end_date', '{data[4]}'), ('location', '{data[5]}');")
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {current_user.username}_{project_name}_attendance (unid VARCHAR(10), name VARCHAR(255));")
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {current_user.username}_{project_name}_worklog (sno SERIAL PRIMARY KEY, date DATE NOT NULL, title VARCHAR(100) NOT NULL, description TEXT NOT NULL,photos JSONB)")
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {current_user.username}_{project_name}_machinery(id SERIAL PRIMARY KEY, machine_name VARCHAR(255), machine_description VARCHAR(255), purchase_date DATE, next_service_date DATE, daily_operating_cost DECIMAL, insurance_expiry DATE, driver_name VARCHAR(255), driving_license_expiry DATE, vehicle_registration_number VARCHAR(255), lat VARCHAR(255), lon VARCHAR(255));")

        manpower_fields = request.form.getlist('department[]')
        num_workers_fields = request.form.getlist('numWorkers[]')
        for i in range(len(manpower_fields)):
            manpower_data = {
                'department': manpower_fields[i],
                'num_workers': num_workers_fields[i]
            }
            with connection.cursor() as cursor:
                keys = manpower_data.keys()
                columns = ', '.join(keys)
                values = ', '.join('%({})s'.format(key) for key in keys)
                query = f"INSERT INTO {current_user.username}_{project_data['project_name']}_manpower ({columns}) VALUES ({values}) RETURNING id;"
                cursor.execute(query, manpower_data)
        inventory_fields = request.form.getlist('item[]')
        quantity_fields = request.form.getlist('quantity[]')
        rate_fields = request.form.getlist('rate[]')
        for i in range(len(inventory_fields)):
            inventory_data = {
                'item': inventory_fields[i],
                'quantity': quantity_fields[i],
                'rate': rate_fields[i],
                'price': (int(quantity_fields[i])*int(rate_fields[i])),
            }
            with connection.cursor() as cursor:
                keys = inventory_data.keys()
                columns = ', '.join(keys)
                values = ', '.join('%({})s'.format(key) for key in keys)
                query = f"INSERT INTO {current_user.username}_{project_data['project_name']}_inventory ({columns}) VALUES ({values}) RETURNING id;"
                cursor.execute(query, inventory_data)
        equipment_fields = request.form.getlist('equipment[]')
        available_fields = request.form.getlist('available[]')
        standby_fields = request.form.getlist('standby[]')
        for i in range(len(equipment_fields)):
            equipment_data = {
                'equipment': equipment_fields[i],
                'available': available_fields[i],
                'standby': standby_fields[i]
            }
            with connection.cursor() as cursor:
                keys = equipment_data.keys()
                columns = ', '.join(keys)
                values = ', '.join('%({})s'.format(key) for key in keys)
                query = f"INSERT INTO {current_user.username}_{project_data['project_name']}_equipment ({columns}) VALUES ({values}) RETURNING id;"
                cursor.execute(query, equipment_data)
        with connection.cursor() as cursor:
            query = f"INSERT INTO {current_user.username} (projectname) VALUES ('{request.form['projectName']}')"
            cursor.execute(query, project_data)
        connection.commit()
        return redirect('/dashboard')
    return render_template('createproject/onboard.html')

# Project
@app.route('/project/<string:projectname>', methods=['GET', 'POST'])
@login_required
def project_dashboard(projectname):
    return render_template('project/dashboard.html', projectname=projectname)

@app.route('/project/delete/<string:projectname>', methods=['GET', 'POST'])
@login_required
def project_delete(projectname):
    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {current_user.username} WHERE projectname = '{projectname}'")
        cursor.execute(f"DROP TABLE {current_user.username}_{projectname}_inventory")
        cursor.execute(f"DROP TABLE {current_user.username}_{projectname}_manpower")
        cursor.execute(f"DROP TABLE {current_user.username}_{projectname}_equipment")
        cursor.execute(f"DROP TABLE {current_user.username}_{projectname}_projectdata")
        cursor.execute(f"DROP TABLE {current_user.username}_{projectname}_cad")
        cursor.execute(f"DROP TABLE {current_user.username}_{projectname}_workerdata")
        cursor.execute(f"DROP TABLE {current_user.username}_{projectname}_attendance")
        cursor.execute(f"DROP TABLE {current_user.username}_{projectname}_worklog")
        cursor.execute(f"DROP TABLE {current_user.username}_{projectname}_machinery")
    connection.commit()
    return redirect(url_for('dashboard'))

@app.route('/project/<string:projectname>/profile', methods=['GET', 'POST'])
@login_required
def project_profile(projectname):
    if request.method == 'GET':
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {current_user.username}_{projectname}_projectdata")
            user_data = cursor.fetchall()
        user_dict = {key: value for key, value in user_data}
        return render_template('project/profile.html', user=user_dict, projectname=projectname)
    if request.method == 'POST':
        updated_data = {key: request.form[key] for key in request.form}
        with connection.cursor() as cursor:
            for key, value in updated_data.items():
                if key != 'username':
                    cursor.execute(
                        f"UPDATE {current_user.username}_{projectname}_projectdata "
                        f"SET value = '{value}' "
                        f"WHERE key = '{key}';"
                    )
            connection.commit()
        return redirect(url_for('project_profile', projectname=projectname))
    return render_template('project/profile.html')

# Inventory
@app.route('/project/<string:projectname>/inventory', methods=['GET', 'POST'])
@login_required
def inventory(projectname):
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT * FROM {current_user.username}_{projectname}_inventory')
        inventory_data = cursor.fetchall()
        cursor.execute(f'SELECT price FROM {current_user.username}_{projectname}_inventory')
        prices = cursor.fetchall()
    total_price = sum(Decimal(price) for (price,) in prices)
    return render_template('inventory/index.html', inventory=inventory_data, total_price=total_price,projectname=projectname)

@app.route('/project/<string:projectname>/inventory/add',  methods=['GET', 'POST'])
@login_required
def inventory_add(projectname):
    if request.method == 'POST':
        item = request.form['item']
        quantity = request.form['quantity']
        rate = request.form['rate']
        price = int(quantity) * int(rate)
        with connection.cursor() as cursor:
            cursor.execute(f"INSERT INTO {current_user.username}_{projectname}_inventory (item, quantity, rate, price) VALUES ('{item}', '{quantity}', '{rate}', '{price}')")
        connection.commit()
    return redirect(url_for('inventory', projectname=projectname))

@app.route('/project/<string:projectname>/inventory/addai', methods=['POST'])
@login_required
def inventory_addai(projectname):
    if request.method == 'POST':
        ai = request.form['ai']
        cookie_path_dir = "./cookies_snapshot"
        sign = Login("nitishkumar.blog@gmail.com", None)
        cookies = sign.loadCookiesFromDir(cookie_path_dir) 
        chatbot = hugchat.ChatBot(cookies=cookies.get_dict())
        table = f'{current_user.username}_{projectname}_inventory'
        prompt = f" make it as sql (item,quantity, rate) insert this to a table named {table}. also multiply quantity and rate and insert into column price. insert(item,quantity, rate,price) give me only the sql command."
        query = ai + prompt
        query_result = chatbot.query(query)
        pattern = r'```sql(.*?)```'
        match = re.search(pattern, str(query_result), re.DOTALL)
        sql = match.group(1).strip() if match else None
        with connection.cursor() as cursor:
            cursor.execute(sql)
        connection.commit()
    return redirect(url_for('inventory', projectname=projectname))

@app.route('/project/<string:projectname>/inventory/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def inventory_edit(id, projectname):
    if request.method == 'POST':
        new_item = request.form['item']
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE {current_user.username}_{projectname}_inventory SET item = '{new_item}' WHERE id = {id}")
        connection.commit()
        return redirect(url_for('inventory', projectname=projectname))

    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {current_user.username}_{projectname}_inventory WHERE id = {id}")
        item_data = cursor.fetchone()
    return render_template('inventory/edit.html', item=item_data,projectname=projectname)

@app.route('/project/<string:projectname>/inventory/delete/<int:id>')
@login_required
def inventory_delete(id, projectname):
    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {current_user.username}_{projectname}_inventory WHERE id = {id}")
    connection.commit()
    return redirect(url_for('inventory', projectname=projectname))

@app.route('/project/<string:projectname>/inventory/entry/<int:id>', methods=['GET'])
@login_required
def inventory_view_entry(id, projectname):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT entries FROM {current_user.username}_{projectname}_inventory WHERE id = {id}")
        entry_data = cursor.fetchone()
        cursor.execute(f"SELECT * FROM {current_user.username}_{projectname}_inventory WHERE id = {id}")
        inventory_data = cursor.fetchone()
    if entry_data:
        return render_template('inventory/entry.html', id=id, entries=entry_data[0],inventory_data=inventory_data, projectname=projectname)
    else:
        return "Entry not found."
    
@app.route('/project/<string:projectname>/inventory/entry/add/<int:id>', methods=['POST'])
@login_required
def inventory_add_entry(id, projectname):
    if request.method == 'POST':
        quantity = float(request.form['quantity'])
        entry_type = request.form['type']
        rate = float(request.form['rate']) if request.form['rate'] else None
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT quantity, rate, price, entries FROM {current_user.username}_{projectname}_inventory WHERE id = {id}")
            table = f'{current_user.username}_{projectname}_inventory'
            result = cursor.fetchone()
            existing_quantity, existing_rate, existing_price, existing_entries = (
                float(result[0]), float(result[1]),
                float(result[2]) if result[2] is not None else Decimal(0.00),
                result[3]
            )
            new_entry = {"quantity": quantity, "type": entry_type, "rate": rate}
            if existing_entries is None:
                existing_entries = []
            if entry_type == 'in':
                new_average_rate = ((existing_rate * existing_quantity) + (rate * quantity)) / (existing_quantity + quantity)
                new_quantity = existing_quantity + quantity
                new_price = Decimal(existing_price) + (Decimal(rate) * Decimal(quantity))
                existing_entries.append(new_entry)
                entries_json = json.dumps(existing_entries)
                query = f"UPDATE {table} SET quantity = %s, rate = %s, price = %s, entries = %s WHERE id = %s"
                cursor.execute(query, (new_quantity, new_average_rate, new_price, entries_json, id))
            elif entry_type == 'used':
                new_quantity = existing_quantity - quantity
                if new_quantity < 0:
                    return jsonify({"error": "Not enough quantity available for 'used' entry."}), 400
                existing_entries.append(new_entry)
                entries_json = json.dumps(existing_entries)
                query = f"UPDATE {table} SET quantity = %s, entries = %s WHERE id = %s"
                cursor.execute(query, (new_quantity, entries_json, id))
            else:
                return jsonify({"error": "Invalid entry type. Use 'in' or 'used'."}), 400
        connection.commit()
    return redirect(url_for('inventory_view_entry', id=id, projectname=projectname))

@app.route('/project/<string:projectname>/inventory/entry/delete/<int:id>/<int:index>')
@login_required
def inventory_delete_entry(id, projectname, index):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT quantity, rate, price, entries FROM {current_user.username}_{projectname}_inventory WHERE id = {id}")
        result = cursor.fetchone()
        existing_quantity, existing_rate, existing_price, existing_entries = (
            float(result[0]), float(result[1]),
            Decimal(result[2]) if result[2] is not None else Decimal(0.00),
            result[3]
        )
        if existing_entries and 0 <= index < len(existing_entries):
            deleted_entry = existing_entries.pop(index)
            if 'type' in deleted_entry and deleted_entry['type'] == 'used':
                existing_quantity += deleted_entry.get('quantity', 0)
            elif 'type' in deleted_entry and deleted_entry['type'] == 'in':
                existing_quantity -= deleted_entry.get('quantity', 0)
                existing_price -= Decimal(deleted_entry.get('rate', 0)) * Decimal(deleted_entry.get('quantity', 0))
                if existing_quantity > 0:
                    existing_rate = float(existing_price) / float(existing_quantity)
                else:
                    existing_rate = 0
            else:
                return jsonify({"error": "Invalid entry type. Use 'in' or 'used'."}), 400
            entries_json = json.dumps(existing_entries)
            table = f'{current_user.username}_{projectname}_inventory'
            query = f"UPDATE {table} SET quantity = %s, rate = %s, price = %s, entries = %s WHERE id = %s"
            cursor.execute(query, (existing_quantity, existing_rate, existing_price, entries_json, id))
            connection.commit()
    return redirect(url_for('inventory_view_entry', id=id, projectname=projectname))

# Manpower
@app.route('/project/<string:projectname>/manpower')
@login_required
def manpower_index(projectname):
    with connection.cursor() as cursor:
            cursor.execute(f"SELECT id, unid, name, phone, department, aadharid, nativecity, emergencycontact FROM {current_user.username}_{projectname}_workerdata")
            worker_data = cursor.fetchall()
    return render_template('manpower/index.html', projectname=projectname, worker_data=worker_data)

@app.route('/project/<string:projectname>/manpower/departments')
@login_required
def manpower_departments(projectname):
    with connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {current_user.username}_{projectname}_manpower")
            manpower_departments = cursor.fetchall()
    return render_template('manpower/departments.html', projectname=projectname, manpower_departments=manpower_departments)

@app.route('/project/<string:projectname>/manpower/departments/add', methods=['GET'])
@login_required
def manpower_add_department(projectname):
    return render_template('manpower/adddepartment.html', projectname=projectname)

@app.route('/project/<string:projectname>/manpower/departments/adddepartment', methods=['POST'])
@login_required
def manpower_add_departmentdata(projectname):
    if request.method == 'POST':
        name = request.form.get('DepartmentName')
        count = request.form.get('DepartmentCount')
        with connection.cursor() as cursor:
            cursor.execute(f"INSERT INTO {current_user.username}_{projectname}_manpower (department, num_workers) VALUES (%s, %s)", (name, count))
        connection.commit()
    return redirect(url_for('manpower_departments', projectname=projectname))

@app.route('/project/<string:projectname>/manpower/departments/edit/<int:department_id>', methods=['GET', 'POST'])
@login_required
def manpower_edit_department(projectname, department_id):
    if request.method == 'GET':
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT id, department, num_workers "
                f"FROM {current_user.username}_{projectname}_manpower "
                f"WHERE id = %s", (department_id,)
            )
            department_data = cursor.fetchone()
        return render_template('manpower/editdepartment.html', projectname=projectname, department_data=department_data)
    elif request.method == 'POST':
        name = request.form.get('DepartmentName')
        count = request.form.get('DepartmentCount')

        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {current_user.username}_{projectname}_manpower "
                "SET department = %s, num_workers = %s "
                "WHERE id = %s",
                (name, count, department_id)
            )
        connection.commit()
        return redirect(url_for('manpower_departments', projectname=projectname))

@app.route('/project/<string:projectname>/manpower/departments/delete/<int:department_id>', methods=['GET'])
@login_required
def manpower_delete_department(projectname, department_id):
    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {current_user.username}_{projectname}_manpower WHERE id = %s", (department_id,))
    connection.commit()
    return redirect(url_for('manpower_departments', projectname=projectname))

@app.route('/project/<string:projectname>/addworker')
@login_required
def add_worker(projectname):
    return render_template('manpower/addworker.html', projectname=projectname)

@app.route('/project/<string:projectname>/editworker/<int:worker_id>', methods=['GET', 'POST'])
@login_required
def edit_worker(projectname, worker_id):
    if request.method == 'GET':
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT id, unid, name, phone, department, aadharid, nativecity, emergencycontact "
                f"FROM {current_user.username}_{projectname}_workerdata "
                f"WHERE id = %s", (worker_id,)
            )
            worker_data = cursor.fetchone()
        return render_template('manpower/editworker.html', projectname=projectname, worker_data=worker_data)

    elif request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        department = request.form.get('department')
        aadharid = request.form.get('aadharid')
        nativecity = request.form.get('nativecity')
        emergencycontact = request.form.get('emergencycontact')

        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {current_user.username}_{projectname}_workerdata "
                "SET name = %s, phone = %s, department = %s, aadharid = %s, "
                "nativecity = %s, emergencycontact = %s "
                "WHERE id = %s",
                (name, phone, department, aadharid, nativecity, emergencycontact, worker_id)
            )
            unid="W"+str(worker_id)
            cursor.execute(f"UPDATE {current_user.username}_{projectname}_attendance SET name = %s WHERE unid = %s", (name, unid))
        connection.commit()
        return redirect(url_for('manpower_index', projectname=projectname))

@app.route('/project/<string:projectname>/deleteworker/<int:worker_id>', methods=['GET'])
@login_required
def delete_worker(projectname, worker_id):
    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {current_user.username}_{projectname}_workerdata WHERE id = %s", (worker_id,))
        worker_id="W"+str(worker_id)
        cursor.execute(f"DELETE FROM {current_user.username}_{projectname}_attendance WHERE unid = %s", (worker_id,))
    connection.commit()
    return redirect(url_for('manpower_index', projectname=projectname))

@app.route('/project/<string:projectname>/addworkerdata', methods=['POST'])
@login_required
def add_worker_data(projectname):
    if request.method == 'POST':
        names = request.form.getlist('name[]')
        phones = request.form.getlist('phone[]')
        departments = request.form.getlist('department[]')
        aadharids = request.form.getlist('aadharid[]')
        nativecities = request.form.getlist('nativecity[]')
        emergencycontacts = request.form.getlist('emergencycontact[]')
        with connection.cursor() as cursor:
            for i in range(len(names)):
                cursor.execute(
                    f"INSERT INTO {current_user.username}_{projectname}_workerdata "
                    "(name, phone, department, aadharid, nativecity, emergencycontact) "
                    "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                    (names[i], phones[i], departments[i], aadharids[i], nativecities[i], emergencycontacts[i])
                )
                worker_id = cursor.fetchone()[0]
                cursor.execute(f"UPDATE {current_user.username}_{projectname}_workerdata SET unid = 'W'||{worker_id} WHERE id = {worker_id}")
                workerid="W"+str(worker_id)
                cursor.execute(f"INSERT INTO {current_user.username}_{projectname}_attendance (unid, name) VALUES (%s, %s)", (workerid, names[i]))
        connection.commit()
    return redirect(url_for('manpower_index', projectname=projectname))

@app.route('/project/<string:projectname>/get_departments', methods=['GET'])
@login_required
def get_departments(projectname):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT department FROM {current_user.username}_{projectname}_manpower")
        departments = cursor.fetchall()
    return jsonify(departments)

# Weather
@app.route('/project/<string:projectname>/weather')
@login_required
def weather(projectname):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT value FROM {current_user.username}_{projectname}_projectdata WHERE key='location'")
        result = cursor.fetchone()
    api_endpoint = f'https://api.weatherapi.com/v1/forecast.json?key={api_key}&q={result[0]}&days=1&aqi=yes&alerts=yes'
    response = requests.get(api_endpoint)
    data = response.json()
    hourly_forecast = []
    hourlyForecast=[]
    for forecast in data['forecast']['forecastday'][0]['hour']:
        time_utc = datetime.strptime(forecast['time'], '%Y-%m-%d %H:%M')
        utc_offset = data.get('location', {}).get('utc_offset', 0)
        time_local = time_utc + timedelta(hours=utc_offset)
        formatted_time = time_local.strftime('%I:%M %p - ') + (time_local + timedelta(hours=1)).strftime('%I:%M %p')
        weather_info = {
            'time': formatted_time,
            'temperature': forecast['temp_c'],
            'chance_of_rain': forecast.get('chance_of_rain', 0),
            'wind_speed': forecast['wind_kph'],
            'aqi': forecast.get('air_quality', {}).get('pm10', 0),
            'uv_index': forecast.get('uv', 0),
        }
        hourly_forecast.append(weather_info)
        weatherInfo = {
            'time': forecast['time'],
            'temperature': forecast['temp_c'],
            'chance_of_rain': forecast.get('chance_of_rain', 0),
            'wind_speed': forecast['wind_kph'],
            'aqi': forecast.get('air_quality', {}).get('pm10', 0),
            'uv_index': forecast.get('uv', 0),
        }
        hourlyForecast.append(weatherInfo)
    df = pd.DataFrame(hourlyForecast)
    df['time'] = pd.to_datetime(df['time'])
    aqiWeightScores = {0: 100, 1: 90, 2: 80, 3: 70, 4: 60, 5: 50}
    temperatureWeightScores = {0: 40, 1: 50, 2: 60, 3: 70, 4: 80, 5: 100, 6: 80, 7: 50, 8: 40}
    uvIndexWeightScores = {0: 100, 1: 90, 2: 80, 3: 70, 4: 60}
    rainWeight = 0.65
    temperatureWeight = 0.15
    windSpeedWeight = 0.05
    aqiWeight = 0.05
    uvIndexWeight = 0.1
    df['score'] = (
        (100 - df['chance_of_rain']) * rainWeight +
        df['temperature'].apply(lambda x: temperatureWeightScores[next(i for i, v in enumerate([3, 7, 12, 17, 22, 27, 32, 35, 37]) if x < v)]) * temperatureWeight +
        (10 - df['wind_speed']) * windSpeedWeight +
        (100 - df['aqi'].apply(lambda x: aqiWeightScores[next(i for i, v in enumerate([50, 100, 250, 350, 430]) if x <= v)]) * aqiWeight) +
        df['uv_index'].apply(lambda x: uvIndexWeightScores[next(i for i, v in enumerate([2, 5, 7, 10]) if x <= v)]) * uvIndexWeight
    )
    minScore = df['score'].min()
    maxScore = df['score'].max()
    df['normalized_score'] = ((df['score'] - minScore) / (maxScore - minScore)) * 100
    startHour = 7
    endHour = 17
    topHours = 8
    percentageRadius = 10
    currentDate = datetime.now().strftime('%Y-%m-%d')
    startTimeStr = f'{currentDate} {startHour:02d}:00'
    endTimeStr = f'{currentDate} {endHour:02d}:00'
    bestTimeDf = df[(df['time'].between(startTimeStr, endTimeStr))]
    bestTimeDf = bestTimeDf.sort_values(by='normalized_score', ascending=False)
    selectedHours = bestTimeDf.head(topHours)
    eighthHourScore = selectedHours['normalized_score'].iloc[-1]
    thresholdScore = eighthHourScore - (eighthHourScore * (percentageRadius / 100))
    additionalHours = bestTimeDf[
        (bestTimeDf['normalized_score'] >= thresholdScore) & ~bestTimeDf['time'].isin(selectedHours['time'])
    ].head(topHours - 1)
    selectedIntervals = pd.concat([selectedHours, additionalHours]).sort_values(by='normalized_score', ascending=False).reset_index(drop=True)
    selectedIntervals['time'] = pd.to_datetime(selectedIntervals['time'])
    selectedIntervals = selectedIntervals.sort_values(by='time', ascending=True)
    selectedIntervals['intTime'] = selectedIntervals['time'].dt.hour
    intTimeArray = selectedIntervals['intTime'].to_numpy()
    sortedArray = sorted(set(intTimeArray))
    consecutiveSets = []
    currentSet = []
    for num in sortedArray:
        if not currentSet or num == currentSet[-1] + 1:
            currentSet.append(num)
        else:
            consecutiveSets.append(currentSet)
            currentSet = [num]
    consecutiveSets.append(currentSet)
    sortedConsecutiveSets = sorted(consecutiveSets, key=len, reverse=True)
    newArray = [item for sublist in sortedConsecutiveSets for item in sublist]
    intTimeArray = sorted(newArray[:8])
    timeIntervals = []
    i = 0
    while i < len(intTimeArray):
        start = intTimeArray[i]
        end = start
        while i + 1 < len(intTimeArray) and intTimeArray[i + 1] == intTimeArray[i] + 1:
            i += 1
            end = intTimeArray[i]
        startHour = start
        endHour = end + 1
        startPeriod = "AM" if startHour < 12 else "PM"
        endPeriod = "AM" if endHour < 12 else "PM"
        if startHour > 12:
            startHour -= 12
        if endHour > 12:
            endHour -= 12
        timeInterval = f"{startHour}:00 {startPeriod} - {endHour}:00 {endPeriod}"
        timeIntervals.append(timeInterval)
        i += 1
    return render_template('weather/index.html', hourly_forecast=hourly_forecast, timeIntervals=timeIntervals, city=result[0])

# CAD
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_random_string(length=10):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def get_uploaded_files(projectname):
    with psycopg2.connect(**db_config) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT id, title, filename FROM {current_user.username}_{projectname}_cad")
            files = cursor.fetchall()
    return files

def convert_dwg_to_png(input_path, output_folder):
    result = convertapi.convert('png', {'File': input_path}, from_format='dwg')
    output_path = os.path.join(output_folder, f"{os.path.splitext(os.path.basename(input_path))[0]}.png")
    result.save_files(output_folder)
    return output_path

@app.route('/project/<string:projectname>/cad')
@login_required
def cad_index(projectname):
    files = get_uploaded_files(projectname)
    return render_template('cad/index.html', files=files, projectname=projectname)

@app.route('/project/<string:projectname>/cad/convert', methods=['POST'])
@login_required
def cad_convert(projectname):
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename):
            random_filename = generate_random_string() + '.dwg'
            title = request.form.get('title', 'Untitled') 
            filename = os.path.join(app.config['UPLOAD_FOLDER'], random_filename)
            file.save(filename)
            try:
                output_filename = convert_dwg_to_png(filename, app.config['OUTPUT_FOLDER'])
                with psycopg2.connect(**db_config) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(f"INSERT INTO {current_user.username}_{projectname}_cad (title, filename) VALUES ('{title}', '{random_filename}')")
                files = get_uploaded_files(projectname)
                success_message = 'File uploaded successfully.'
                return render_template('cad/index.html', files=files, success_message=success_message, projectname=projectname)
            except Exception as e:
                return redirect(request.url)
    return redirect(request.url)

@app.route('/project/<string:projectname>/cad/download/<filename>')
@login_required
def cad_download(projectname, filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True, download_name=filename)

@app.route('/project/<string:projectname>/cad/view/<filename>')
@login_required
def cad_view(projectname, filename):
    with psycopg2.connect(**db_config) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT filename FROM {current_user.username}_{projectname}_cad WHERE filename = '{filename}'")
            result = cursor.fetchone()
    if result:
        filename = result[0].split('.')[0]
        filename=filename+".png"
        return render_template('cad/view.html', filename=filename, projectname=projectname)
    flash('File not found')
    return redirect(url_for('cad_index', projectname=projectname))

@app.route('/project/<string:projectname>/cad/edit/<filename>', methods=['GET', 'POST'])
@login_required
def cad_edit(projectname, filename):
    with psycopg2.connect(**db_config) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT title FROM {current_user.username}_{projectname}_cad WHERE filename = '{filename}'")
            current_title = cursor.fetchone()[0] if cursor.rowcount > 0 else 'Untitled'
    if request.method == 'POST':
        new_title = request.form.get('new_title', 'Untitled')
        with psycopg2.connect(**db_config) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"UPDATE {current_user.username}_{projectname}_cad SET title = '{new_title}' WHERE filename = '{filename}'")
        flash('File title updated successfully')
        return redirect(url_for('cad_index', projectname=projectname))
    else:
        return render_template('cad/edit.html', filename=filename, current_title=current_title, projectname=projectname)

@app.route('/project/<string:projectname>/cad/delete/<filename>')
@login_required
def cad_delete(projectname, filename):
    with psycopg2.connect(**db_config) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {current_user.username}_{projectname}_cad WHERE filename = '{filename}'")
    flash('File deleted successfully')
    return redirect(url_for('cad_index', projectname=projectname))

@app.route('/project/<string:projectname>/cad/uploads/<filename>')
@login_required
def cad_uploaded_file(projectname, filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/output/<filename>')
@login_required
def cad_converted_file(projectname, filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

# Chatbot
@app.route("/project/<string:projectname>/chatbot")
@login_required
def chat_home(projectname):
    return render_template("chat/index.html")

@app.route("/chatget")
@login_required
def get_bot_response():
    cookie_path_dir = "./cookies_snapshot"
    sign = Login("nitishkumar.blog@gmail.com", None)
    cookies = sign.loadCookiesFromDir(cookie_path_dir) 
    chatbot = hugchat.ChatBot(cookies=cookies.get_dict())  
    userText = request.args.get('msg')
    language=detect(userText)
    if language=="en" or language=="sw":
        query = "Note: Keep your response as short as possible. Don't give negative response like 'Im not able to provide instructions'. Just tell what you know. Question: "+userText
        query_result = chatbot.query(query)
        ans=str(query_result)
    else:
        payload = {"from": "auto", "to": "en", "text": userText}
        headers = {"content-type": "application/x-www-form-urlencoded", "X-RapidAPI-Key": "dcab9cf74dmshe292ac2decf874fp1f2036jsnfddf994f902b", "X-RapidAPI-Host": "google-translate113.p.rapidapi.com"}
        response = requests.post("https://google-translate113.p.rapidapi.com/api/v1/translator/text", data=payload, headers=headers)
        output=response.json()
        query = "Note: Keep your response as short as possible. Don't give negative response like 'Im not able to provide instructions'. Just tell what you know. Question: "+output["trans"]
        query_result = chatbot.query(query)
        ans=str(query_result)
        payload = {"from": "en", "to": language, "text": ans}
        response = requests.post("https://google-translate113.p.rapidapi.com/api/v1/translator/text", data=payload, headers=headers)
        output=response.json()
        ans=output["trans"]
    return ans

# Attendance
@app.route('/project/<string:projectname>/attendance')
@login_required
def view_attendance(projectname):
    query = f"SELECT * FROM {current_user.username}_{projectname}_attendance;"
    data = pd.read_sql(query, connection)
    return render_template('attendance/index.html', table_data=data.to_html(index=False), projectname=projectname)

# Predictive Maintenance
@app.route('/project/<string:projectname>/predictivemaintenance')
@login_required
def predictivemaintenance(projectname):
    query = "SELECT * FROM pm;"
    data = pd.read_sql(query, connection)
    features = data.drop('maintenance', axis=1)
    target = data['maintenance']
    label_encoder = LabelEncoder()
    features['equipment_type'] = label_encoder.fit_transform(features['equipment_type'])
    reverse_mapping = dict(zip(label_encoder.transform(label_encoder.classes_), label_encoder.classes_))
    X_train, X_test, y_train, y_test = train_test_split(features, target, test_size=0.2, random_state=42)
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)
    result_df = pd.DataFrame()
    thresholds = {'Noise': 0.65, 'Load_Capacity': 0.6, 'Engine_Temperature': 0.4, 'Oil_Level': 0.2,'Vibrations':0.6}
    alerts = pd.DataFrame(index=X_test.index)
    for param, threshold in thresholds.items():
        alerts[param + '_Alert'] = model.predict_proba(X_test)[:, 1] > threshold
    result_df['Maintenance_Alerts'] = alerts.sum(axis=1)
    result_df['Maintenance_Level'] = pd.cut(result_df['Maintenance_Alerts'], bins=[-1, 0, 1, 2,3 ,float('inf')], labels=['No Alert', 'Low', 'Medium', 'High','Very high'], right=True)
    result_df['Critical_Alerts'] = result_df['Maintenance_Alerts'] == 5
    result_df['Needs_Maintenance_Alerts'] = alerts.any(axis=1)
    X_test['equipment_type'] = X_test['equipment_type'].map(reverse_mapping)
    categorical_columns = X_test.select_dtypes(include='category').columns
    X_test[categorical_columns] = X_test[categorical_columns].astype(str)
    X_test.fillna('Not_Applicable', inplace=True)
    result_df = pd.concat([result_df, X_test.reset_index(), alerts], axis=1)
    result_df.to_csv('Testing_emptycells_4.csv', index=False)
    df = pd.read_csv("Testing_emptycells_4.csv")
    df = df.apply(lambda x: pd.Series(x.dropna().values)).fillna(' ')
    os.remove('Testing_emptycells_4.csv')
    json_data=df[df['Critical_Alerts']][['equipment_type']].to_json(orient='records')
    json_df = pd.read_json(json_data, orient='records')
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM alert;")
        for _, row in json_df.iterrows():
            cursor.execute("INSERT INTO alert (equipment_type) VALUES (%s);", (row['equipment_type'],))
    connection.commit()
    return render_template('predictivemaintenance/index.html', table_data=df.to_html(index=False), projectname=projectname)

@app.route('/project/<string:projectname>/predictivemaintenance/data')
@login_required
def predictivemaintenance_data(projectname):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = 'pm';")
        column_names = [row[0] for row in cursor.fetchall()]
        columns = column_names[::-1]
        cursor.execute(f"SELECT * FROM pm;")
        table_data = cursor.fetchall()
    return render_template('predictivemaintenance/data.html', table_data=table_data, columns=columns, projectname=projectname)

@app.route('/getalert', methods=['GET'])
def fetch_alert_data():
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM alert;")
        columns = [desc[0] for desc in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return jsonify(data)

# Work Log
ALLOWED_EXTENSIONSW = {'png', 'jpg', 'jpeg', 'pdf'}
UPLOADS_FOLDER = 'static'

class PostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    date = DateTimeField('Date', render_kw={'readonly': True}, default=datetime.today)
    description = TextAreaField('Description', validators=[DataRequired()])
    photos = MultipleFileField('Photos')

@app.route('/project/<string:projectname>/worklog')
@login_required
def worklog(projectname):
    cursor = connection.cursor()
    cursor.execute(f"SELECT * FROM {current_user.username}_{projectname}_worklog")
    posts = cursor.fetchall()
    return render_template('worklog/index.html', posts=posts, projectname=projectname)

@app.route('/project/<string:projectname>/worklog/add', methods=['GET', 'POST'])
@login_required
def worklog_add(projectname):
    form = PostForm()
    if request.method == 'POST' and form.validate_on_submit():
        title = form.title.data
        date = form.date.data.strftime('%Y-%m-%d')
        description = form.description.data
        folder_name = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        folder_path = os.path.join(UPLOADS_FOLDER, folder_name)
        os.makedirs(folder_path)
        photos_urls = []
        for i, photo in enumerate(form.photos.data):
            if photo and ('.' in photo.filename and photo.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONSW):
                photo_filename = f'photo_{i}.{photo.filename.rsplit(".", 1)[1].lower()}'
                photo_path = os.path.join(folder_path, photo_filename)
                photo.save(photo_path)
                photos_urls.append(url_for('uploaded_file', folder=folder_name, filename=photo_filename))
            else:
                flash(f'Invalid file type for {photo.filename}. Only PNG, JPG, and PDF are allowed.', 'danger')
                return redirect(url_for('worklog'))
        cursor = connection.cursor()
        cursor.execute(f'INSERT INTO {current_user.username}_{projectname}_worklog (date, title, description, photos) VALUES (%s, %s, %s, %s)',(date, title, description, json.dumps(photos_urls)))
        connection.commit()
        flash('Post submitted successfully', 'success')
        return redirect(url_for('worklog', projectname=projectname))
    return render_template('worklog/add.html', form=form, projectname=projectname)

@app.route('/static/<folder>/<filename>')
def uploaded_file(folder, filename):
    return send_from_directory(os.path.join(UPLOADS_FOLDER, folder), filename)
# Machinery
@app.route('/project/<string:projectname>/machinery')
@login_required
def machinery_list(projectname):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {current_user.username}_{projectname}_machinery")
        machinery_list = cursor.fetchall()
    return render_template('machinery/list.html', projectname=projectname, machinery_list=machinery_list)

@app.route('/project/<string:projectname>/machinery/add', methods=['GET'])
@login_required
def machinery_add_form(projectname):
    return render_template('machinery/add.html', projectname=projectname)

@app.route('/project/<string:projectname>/machinery/add', methods=['POST'])
@login_required
def machinery_add_data(projectname):
    if request.method == 'POST':
        machine_name = request.form.get('machine_name')
        machine_description = request.form.get('machine_description')
        purchase_date = datetime.strptime(request.form.get('purchase_date'), '%Y-%m-%d')
        next_service_date = datetime.strptime(request.form.get('next_service_date'), '%Y-%m-%d')
        daily_operating_cost = float(request.form.get('daily_operating_cost'))
        insurance_expiry = datetime.strptime(request.form.get('insurance_expiry'), '%Y-%m-%d')
        driver_name = request.form.get('driver_name')
        driving_license_expiry = datetime.strptime(request.form.get('driving_license_expiry'), '%Y-%m-%d')
        vehicle_registration_number = request.form.get('vehicle_registration_number')

        with connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {current_user.username}_{projectname}_machinery "
                "(machine_name, machine_description, purchase_date, next_service_date, daily_operating_cost, "
                "insurance_expiry, driver_name, driving_license_expiry, vehicle_registration_number) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (machine_name, machine_description, purchase_date, next_service_date, daily_operating_cost,
                 insurance_expiry, driver_name, driving_license_expiry, vehicle_registration_number)
            )
        connection.commit()
    return redirect(url_for('machinery_list', projectname=projectname))

@app.route('/project/<string:projectname>/machinery/edit/<int:machine_id>', methods=['GET', 'POST'])
@login_required
def machinery_edit_form(projectname, machine_id):
    if request.method == 'GET':
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM {current_user.username}_{projectname}_machinery WHERE id = %s", (machine_id,)
            )
            machine_data = cursor.fetchone()
        return render_template('machinery/edit.html', projectname=projectname, machine_data=machine_data)
    elif request.method == 'POST':
        machine_name = request.form.get('machine_name')
        machine_description = request.form.get('machine_description')
        purchase_date = datetime.strptime(request.form.get('purchase_date'), '%Y-%m-%d')
        next_service_date = datetime.strptime(request.form.get('next_service_date'), '%Y-%m-%d')
        daily_operating_cost = float(request.form.get('daily_operating_cost'))
        insurance_expiry = datetime.strptime(request.form.get('insurance_expiry'), '%Y-%m-%d')
        driver_name = request.form.get('driver_name')
        driving_license_expiry = datetime.strptime(request.form.get('driving_license_expiry'), '%Y-%m-%d')
        vehicle_registration_number = request.form.get('vehicle_registration_number')

        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {current_user.username}_{projectname}_machinery "
                "SET machine_name = %s, machine_description = %s, purchase_date = %s, next_service_date = %s, "
                "daily_operating_cost = %s, insurance_expiry = %s, driver_name = %s, "
                "driving_license_expiry = %s, vehicle_registration_number = %s"
                "WHERE id = %s",
                (machine_name, machine_description, purchase_date, next_service_date, daily_operating_cost,
                 insurance_expiry, driver_name, driving_license_expiry, vehicle_registration_number, machine_id)
            )
        connection.commit()
        return redirect(url_for('machinery_list', projectname=projectname))

@app.route('/project/<string:projectname>/machinery/delete/<int:machine_id>', methods=['GET'])
@login_required
def machinery_delete(projectname, machine_id):
    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {current_user.username}_{projectname}_machinery WHERE id = %s", (machine_id,))
    connection.commit()
    return redirect(url_for('machinery_list', projectname=projectname))


if __name__ == '__main__':
    app.run(debug=True, port=9000)