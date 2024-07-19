from flask import Flask, render_template, request, redirect, url_for , session ,flash
import pymysql
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, TextAreaField, DateField, FileField, SubmitField, URLField, SelectField , PasswordField
from wtforms.validators import DataRequired, Length, NumberRange, Regexp, URL, Email
from flask_bootstrap import Bootstrap
from datetime import date
import os
from werkzeug.utils import secure_filename
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

Bootstrap(app)



def get_db_connection():
    """Establishes a new database connection using pymysql."""
    return pymysql.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB'],
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

class LoginForm(FlaskForm):
    username = StringField('اسم المستخدم', validators=[DataRequired()])
    password = PasswordField('كلمة المرور', validators=[DataRequired()])
    submit = SubmitField('دخول')

class ToolForm(FlaskForm):
    id = StringField('ID', validators=[
        DataRequired(),
        Length(min=1, max=20, message="ادخل حتى 20 رقم فقط"),
        Regexp('^[0-9]*$', message="ادخل ارقام فقط بدون حروف")
    ])
    name = StringField('Name', validators=[DataRequired()])
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=1, message="ادخل كمية رقمية")])
    description = TextAreaField('Description')
    expire_date = DateField('Expire Date', format='%Y-%m-%d', validators=[DataRequired()])
    photo = FileField('Photo')
    storage_id = SelectField('Storage Location', coerce=int, validators=[DataRequired()])
    min = IntegerField('min', validators=[DataRequired(), NumberRange(min=1, message="ادخل كمية رقمية")])



class AdminForm(FlaskForm):
    name = StringField('الاسم', validators=[DataRequired()])
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    phone_number = StringField('رقم الهاتف', validators=[DataRequired()])
    submit = SubmitField('حفظ')

class StorageForm(FlaskForm):
    name = StringField('الاسم', validators=[DataRequired()])
    location = StringField('الموقع', validators=[DataRequired()])
    location_url = URLField('رابط الموقع', validators=[DataRequired(), URL()])
    admin_id = SelectField('المسؤول', coerce=int, validators=[DataRequired()])
    submit = SubmitField('حفظ')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        if username == 'admin' and password == 'admin':
            session['username'] = username
            return redirect(url_for('index'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))

    db = get_db_connection()
    cur = db.cursor()

    cur.execute("SELECT COUNT(*) AS tool_count FROM tools")
    tool_count = cur.fetchone()['tool_count']

    cur.execute("SELECT COUNT(*) AS storages_count FROM storages")
    storages_count = cur.fetchone()['storages_count']

    cur.execute("SELECT COUNT(*) AS admins_count FROM admins")
    admins_count = cur.fetchone()['admins_count']

    cur.close()
    db.close()

    return render_template('layout.html', tool_count=tool_count, storages_count=storages_count, admins_count=admins_count)

@app.route('/registerTool', methods=['GET', 'POST'])
def register_tool():
    db = get_db_connection()
    cur = db.cursor()
    
    # Fetch storage locations
    cur.execute("SELECT storage_id, name FROM storages")
    storages = cur.fetchall()
    cur.close()
    db.close()

    # Create form and populate storage choices
    form = ToolForm()
    form.storage_id.choices = [(storage['storage_id'], storage['name']) for storage in storages]

    message = request.args.get('message')
    message_type = request.args.get('message_type')

    if form.validate_on_submit():
        id = form.id.data
        name = form.name.data
        quantity = form.quantity.data
        description = form.description.data
        expire_date = form.expire_date.data
        status = 'expired' if expire_date < date.today() else 'available'
        storage_id = form.storage_id.data
        min = form.min.data

        # Handle file upload
        if form.photo.data:
            filename = secure_filename(form.photo.data.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            form.photo.data.save(file_path)
        else:
            filename = None

        db = get_db_connection()
        cur = db.cursor()
        cur.execute("SELECT * FROM tools WHERE id = %s", (id,))
        existing_tool = cur.fetchone()

        if existing_tool:
            message = 'هذه الأداة موجودة بالفعل في قاعدة البيانات'
            message_type = 'danger'
            db.close()
            return redirect(url_for('register_tool', message=message, message_type=message_type))

        cur.execute(
            "INSERT INTO tools (id, name, quantity, description, expire_date, status, photo, storage_id, min) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (id, name, quantity, description, expire_date, status, filename, storage_id , min)
        )
        db.commit()
        cur.close()
        db.close()

        message = 'تم إضافة الأداة بنجاح'
        message_type = 'success'
        
        return redirect(url_for('register_tool', message=message, message_type=message_type))

    return render_template('reg.html', form=form, message=message, message_type=message_type)












@app.route('/tools', methods=['GET', 'POST'])
def tools():
    message = request.args.get('message')
    message_type = request.args.get('message_type')

    db = get_db_connection()
    cur = db.cursor(pymysql.cursors.DictCursor)  # Ensure the cursor returns dictionaries
    cur.execute("""
    SELECT tools.id, tools.name, tools.quantity, tools.description, tools.expire_date, 
           tools.status, tools.photo, `usage`, storages.name AS storage_name
    FROM tools
    LEFT JOIN storages ON tools.storage_id = storages.storage_id
    """)
    tools = cur.fetchall()

    cur.execute("SELECT storage_id, name FROM storages")
    storages = cur.fetchall()

    cur.close()
    db.close()

    today = date.today()
    updated_tools = []
    for tool in tools:
        expire_date = tool['expire_date']
        status = 'expired' if expire_date and expire_date < today else 'available'
        tool['status'] = status
        updated_tools.append(tool)

    return render_template('tools.html', tools=updated_tools, storages=storages, message=message, message_type=message_type)


@app.route('/updateTool', methods=['POST'])
def update_tool():
    id = request.form['id']
    name = request.form['name']
    quantity = request.form['quantity']
    description = request.form['description']
    expire_date = request.form['expire_date']
    storage_id = request.form['storage_id']
    usage = request.form['usage']
    status = 'expired' if expire_date < date.today().isoformat() else 'available'

    db = get_db_connection()
    cur = db.cursor()

    if 'photo' in request.files and request.files['photo'].filename != '':
        file = request.files['photo']
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        cur.execute("""
            UPDATE tools
            SET name=%s, quantity=%s, description=%s, expire_date=%s, status=%s, photo=%s, `usage`=%s, storage_id=%s
            WHERE id=%s
        """, (name, quantity, description, expire_date, status, filename, usage, storage_id, id))
    else:
        cur.execute("""
            UPDATE tools
            SET name=%s, quantity=%s, description=%s, expire_date=%s, status=%s, `usage`=%s, storage_id=%s
            WHERE id=%s
        """, (name, quantity, description, expire_date, status, usage, storage_id, id))

    db.commit()
    cur.close()
    db.close()

    message = 'تم تعديل الأداة بنجاح'
    message_type = 'success'

    return redirect(url_for('tools', message=message, message_type=message_type))


@app.route('/deleteTool/<tool_id>', methods=['GET'])
def delete_tool(tool_id):
    db = get_db_connection()
    cur = db.cursor()
    cur.execute("DELETE FROM tools WHERE id = %s", (tool_id,))
    db.commit()
    cur.close()
    db.close()

    message = 'تم حذف الأداة بنجاح'
    message_type = 'success'
    return redirect(url_for('tools', message=message, message_type=message_type))



@app.route('/addAdmin', methods=['GET', 'POST'])
def add_admin():
    form = AdminForm()
    message = None
    message_type = None

    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        phone_number = form.phone_number.data
        
        db = get_db_connection()
        cur = db.cursor()
        cur.execute("SELECT * FROM admins WHERE email = %s", (email,))
        existing_admin = cur.fetchone()

        if existing_admin:
            message = 'هذا المسؤول موجود بالفعل في قاعدة البيانات'
            message_type = 'danger'
            cur.close()
            db.close()
        else:
            cur.execute(
                "INSERT INTO admins (name, email, phone_number) VALUES (%s, %s, %s)",
                (name, email, phone_number)
            )
            db.commit()
            cur.close()
            db.close()

            message = 'تم إضافة المسؤول بنجاح'
            message_type = 'success'

    if form.errors:
        message = 'يوجد خطأ في البيانات المدخلة، يرجى التحقق من المدخلات.'
        message_type = 'danger'

    return render_template('add_admin.html', form=form, message=message, message_type=message_type)


@app.route('/admins', methods=['GET', 'POST'])
def admins():
    message = request.args.get('message')
    message_type = request.args.get('message_type')

    db = get_db_connection()
    cur = db.cursor()
    cur.execute("SELECT admin_id, name, email, phone_number FROM admins")
    admins = cur.fetchall()
    cur.close()
    db.close()

    updated_admins = []
    for admin in admins:
        admin_dict = {
            'admin_id': admin['admin_id'],
            'name': admin['name'],
            'email': admin['email'],
            'phone_number': admin['phone_number']
        }
        updated_admins.append(admin_dict)

    return render_template('admins.html', admins=updated_admins, message=message, message_type=message_type)



@app.route('/deleteAdmin/<admin_id>', methods=['GET'])
def delete_admin(admin_id):
    db = get_db_connection()
    cur = db.cursor()
    cur.execute("DELETE FROM admins WHERE admin_id = %s", [admin_id])
    db.commit()
    cur.close()
    db.close()

    message = 'تم حذف المسؤول بنجاح'
    message_type = 'success'
    return redirect(url_for('admins', message=message, message_type=message_type))


@app.route('/updateAdmin', methods=['POST'])
def update_admin():
    admin_id = request.form['admin_id']
    name = request.form['name']
    email = request.form['email']
    phone_number = request.form['phone_number']

    db = get_db_connection()
    cur = db.cursor()
    cur.execute("""
        UPDATE admins
        SET name=%s, email=%s, phone_number=%s
        WHERE admin_id=%s
    """, (name, email, phone_number, admin_id))
    db.commit()
    cur.close()
    db.close()

    message = 'تم تعديل المسؤول بنجاح'
    message_type = 'success'

    return redirect(url_for('admins', message=message, message_type=message_type))


@app.route('/addStorage', methods=['GET', 'POST'])
def add_storage():
    form = StorageForm()
    message = None
    message_type = None

    db = get_db_connection()
    cur = db.cursor()
    cur.execute("SELECT admin_id, name FROM admins")
    admins = cur.fetchall()
    form.admin_id.choices = [(admin['admin_id'], admin['name']) for admin in admins]

    if form.validate_on_submit():
        name = form.name.data
        location = form.location.data
        location_url = form.location_url.data
        admin_id = form.admin_id.data

        cur.execute("SELECT * FROM storages WHERE name = %s", (name,))
        existing_storage = cur.fetchone()

        if existing_storage:
            message = 'هذا المخزن موجود بالفعل في قاعدة البيانات'
            message_type = 'danger'
        else:
            cur.execute(
                "INSERT INTO storages (name, location, location_url, admin_id) VALUES (%s, %s, %s, %s)",
                (name, location, location_url, admin_id)
            )
            db.commit()
            message = 'تم إضافة المخزن بنجاح'
            message_type = 'success'

    if form.errors:
        message = 'يوجد خطأ في البيانات المدخلة، يرجى التحقق من المدخلات.'
        message_type = 'danger'

    cur.close()
    db.close()
    return render_template('add_storage.html', form=form, message=message, message_type=message_type)



@app.route('/storages', methods=['GET', 'POST'])
def storages():
    message = request.args.get('message')
    message_type = request.args.get('message_type')

    db = get_db_connection()
    cur = db.cursor()
    cur.execute("""
        SELECT s.storage_id, s.name, s.location, s.location_url, a.name as admin_name
        FROM storages s
        LEFT JOIN admins a ON s.admin_id = a.admin_id
    """)
    storages = cur.fetchall()
    cur.close()
    db.close()

    # Fetch all admins (assuming you have an Admin model or table)
    db = get_db_connection()
    cur = db.cursor()
    cur.execute("SELECT admin_id, name FROM admins")
    admins = cur.fetchall()
    cur.close()
    db.close()

    updated_storages = []
    for storage in storages:
        storage_dict = {
            'storage_id': storage['storage_id'],
            'name': storage['name'],
            'location': storage['location'],
            'location_url': storage['location_url'],
            'admin_name': storage['admin_name']
        }
        updated_storages.append(storage_dict)

    return render_template('storages.html', storages=updated_storages, message=message, message_type=message_type, admins=admins)


@app.route('/updateStorage', methods=['POST'])
def update_storage():
    storage_id = request.form['storage_id']
    name = request.form['name']
    location = request.form['location']
    location_url = request.form['location_url']
    admin_id = request.form['admin_id']

    db = get_db_connection()
    cur = db.cursor()
    cur.execute("""
        UPDATE storages
        SET name=%s, location=%s, location_url=%s, admin_id=%s
        WHERE storage_id=%s
    """, (name, location, location_url, admin_id, storage_id))
    db.commit()
    cur.close()
    db.close()

    message = 'تم تعديل المخزن بنجاح'
    message_type = 'success'

    return redirect(url_for('storages', message=message, message_type=message_type))





@app.route('/deleteStorage/<storage_id>', methods=['GET'])
def delete_storage(storage_id):
    db = get_db_connection()
    cur = db.cursor()
    cur.execute("DELETE FROM storages WHERE storage_id = %s", [storage_id])
    db.commit()
    cur.close()
    db.close()

    message = 'تم حذف المخزن بنجاح'
    message_type = 'success'
    return redirect(url_for('storages', message=message, message_type=message_type))


if __name__ == '__main__':
    app.run(debug=True)
