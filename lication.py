from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import os
import hashlib
from werkzeug.utils import secure_filename
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes in seconds

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Database configuration
db_config = {
    'host': os.environ.get('DB_HOST'),
    'database': os.environ.get('DB_NAME'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASSWORD'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'auth_plugin': 'mysql_native_password',
    'use_pure': True
}


def get_db_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        return connection
    except Error as e:
        print(f"Connection error: {e}")
        return None


def init_database():
    """Initialize database with proper schema"""
    conn = get_db_connection()
    if not conn:
        print("Cannot connect to database")
        return False

    cursor = conn.cursor()

    # Create tables if they don't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS DEPARTMENT (
            department_id INT PRIMARY KEY AUTO_INCREMENT,
            department_name VARCHAR(100) NOT NULL UNIQUE,
            department_code VARCHAR(10) NOT NULL UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS STUDENT (
            student_id INT PRIMARY KEY AUTO_INCREMENT,
            student_name VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            level VARCHAR(20),
            department_id INT,
            registration_date DATE,
            is_self_sponsored BOOLEAN DEFAULT FALSE,
            application_status VARCHAR(20) DEFAULT 'Pending',
            FOREIGN KEY (department_id) REFERENCES DEPARTMENT(department_id) ON DELETE SET NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS STUDENT_APPLICATIONS (
            application_id INT PRIMARY KEY AUTO_INCREMENT,
            student_id INT,
            department_id INT,
            priority_order INT,
            application_date DATE,
            FOREIGN KEY (student_id) REFERENCES STUDENT(student_id) ON DELETE CASCADE,
            FOREIGN KEY (department_id) REFERENCES DEPARTMENT(department_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS NEXT_OF_KIN (
            kin_id INT PRIMARY KEY AUTO_INCREMENT,
            student_id INT,
            name VARCHAR(100) NOT NULL,
            relationship VARCHAR(50),
            phone VARCHAR(20),
            email VARCHAR(100),
            address TEXT,
            FOREIGN KEY (student_id) REFERENCES STUDENT(student_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS STUDENT_DOCUMENTS (
            document_id INT PRIMARY KEY AUTO_INCREMENT,
            student_id INT,
            document_type VARCHAR(50),
            file_path VARCHAR(255),
            upload_date DATE,
            FOREIGN KEY (student_id) REFERENCES STUDENT(student_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS LECTURER (
            lecturer_id INT PRIMARY KEY AUTO_INCREMENT,
            lecturer_name VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            office_hours VARCHAR(200),
            department_id INT,
            FOREIGN KEY (department_id) REFERENCES DEPARTMENT(department_id) ON DELETE SET NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS MODULE (
            module_id INT PRIMARY KEY AUTO_INCREMENT,
            module_name VARCHAR(100) NOT NULL,
            module_code VARCHAR(20) NOT NULL UNIQUE,
            credits INT,
            department_id INT,
            FOREIGN KEY (department_id) REFERENCES DEPARTMENT(department_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ENROLLMENT (
            enrollment_id INT PRIMARY KEY AUTO_INCREMENT,
            student_id INT,
            module_id INT,
            semester VARCHAR(20),
            enrollment_date DATE,
            FOREIGN KEY (student_id) REFERENCES STUDENT(student_id) ON DELETE CASCADE,
            FOREIGN KEY (module_id) REFERENCES MODULE(module_id) ON DELETE CASCADE,
            UNIQUE KEY unique_enrollment (student_id, module_id, semester)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS TEACHES (
            teaches_id INT PRIMARY KEY AUTO_INCREMENT,
            lecturer_id INT,
            module_id INT,
            semester VARCHAR(20),
            lecture_day VARCHAR(10),
            lecture_time TIME,
            venue VARCHAR(50),
            lecture_date DATE,
            duration INT,
            FOREIGN KEY (lecturer_id) REFERENCES LECTURER(lecturer_id) ON DELETE CASCADE,
            FOREIGN KEY (module_id) REFERENCES MODULE(module_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS FEES (
            fee_id INT PRIMARY KEY AUTO_INCREMENT,
            student_id INT,
            amount_due DECIMAL(10,2),
            amount_paid DECIMAL(10,2) DEFAULT 0,
            status VARCHAR(20),
            due_date DATE,
            FOREIGN KEY (student_id) REFERENCES STUDENT(student_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS RESULT (
            result_id INT PRIMARY KEY AUTO_INCREMENT,
            student_id INT,
            module_id INT,
            grade CHAR(1),
            semester VARCHAR(20),
            FOREIGN KEY (student_id) REFERENCES STUDENT(student_id) ON DELETE CASCADE,
            FOREIGN KEY (module_id) REFERENCES MODULE(module_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ACCOMMODATION (
            accommodation_id INT PRIMARY KEY AUTO_INCREMENT,
            student_id INT UNIQUE,
            room_number VARCHAR(10),
            building_name VARCHAR(50),
            space_id INT,
            FOREIGN KEY (student_id) REFERENCES STUDENT(student_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ACCOMMODATION_SPACES (
            space_id INT PRIMARY KEY AUTO_INCREMENT,
            building_name VARCHAR(50),
            room_number VARCHAR(10),
            is_available BOOLEAN DEFAULT TRUE
        )
    """)

    # Insert default departments if none exist
    cursor.execute("SELECT COUNT(*) FROM DEPARTMENT")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
                INSERT INTO DEPARTMENT (department_name, department_code) VALUES
                ('Computer Science', 'CS'),
                ('Engineering', 'ENG'),
                ('Business', 'BUS'),
                ('Medicine', 'MED'),
                ('Law', 'LAW')
            """)
        cursor.execute("SELECT COUNT(*) FROM LECTURER WHERE email != 'admin@university.com'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                    INSERT INTO LECTURER (lecturer_name, email, password, department_id, office_hours) VALUES
                    ('Dr. Alan Turing', 'lecturer1@university.edu', 'password123', 1, 'Mon-Wed 10AM-12PM'),
                    ('Prof. Marie Curie', 'lecturer2@university.edu', 'password123', 2, 'Tue-Thu 2PM-4PM'),
                    ('Dr. Adam Smith', 'lecturer3@university.edu', 'password123', 3, 'Mon-Fri 9AM-11AM')
                """)
    conn.commit()
    cursor.close()
    conn.close()
    print("Database initialized successfully!")
    return True



# Initialize database
init_database()


def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function


def admin_required(f):
    def decorated_function(*args, **kwargs):
        if session.get('user_role') != 'admin':
            flash('Admin access required', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/heartbeat', methods=['POST'])
@login_required
def heartbeat():
    """Endpoint to keep session alive"""
    # Just touch the session to reset timeout
    session['last_activity'] = datetime.now().isoformat()
    return jsonify({'status': 'ok'})


@app.route('/refresh_session', methods=['POST'])
@login_required
def refresh_session():
    """Manually refresh the session"""
    # Reset session timeout
    session.permanent = True
    session['last_activity'] = datetime.now().isoformat()
    return jsonify({'status': 'ok', 'message': 'Session extended'})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            try:
                # Admin check
                if email == 'admin@university.com' and password == 'admin123':
                    session.permanent = True
                    session['user_id'] = 999
                    session['user_name'] = 'Administrator'
                    session['user_email'] = email
                    session['user_role'] = 'admin'
                    session['last_activity'] = datetime.now().isoformat()
                    flash('Welcome back, Administrator!', 'success')
                    cursor.close()
                    conn.close()
                    return redirect(url_for('home'))

                # Student check
                cursor.execute("""
                    SELECT student_id as user_id, student_name as name, email, 'student' as role, password
                    FROM STUDENT WHERE email = %s
                """, (email,))
                user = cursor.fetchone()
                if user and user['password'] == password:
                    session.permanent = True
                    session['user_id'] = user['user_id']
                    session['user_name'] = user['name']
                    session['user_email'] = user['email']
                    session['user_role'] = 'student'
                    session['last_activity'] = datetime.now().isoformat()
                    flash(f'Welcome back, {user["name"]}!', 'success')
                    cursor.close()
                    conn.close()
                    return redirect(url_for('home'))

                # Lecturer check
                cursor.execute("""
                    SELECT lecturer_id as user_id, lecturer_name as name, email, 'lecturer' as role, password
                    FROM LECTURER WHERE email = %s AND email != 'admin@university.com'
                """, (email,))
                user = cursor.fetchone()
                if user and user['password'] == password:
                    session.permanent = True
                    session['user_id'] = user['user_id']
                    session['user_name'] = user['name']
                    session['user_email'] = user['email']
                    session['user_role'] = 'lecturer'
                    session['last_activity'] = datetime.now().isoformat()
                    flash(f'Welcome back, {user["name"]}!', 'success')
                    cursor.close()
                    conn.close()
                    return redirect(url_for('home'))

                flash('Invalid email or password', 'error')
            except Error as e:
                flash(f'Database error: {str(e)}', 'error')
            finally:
                cursor.close()
                conn.close()
        else:
            flash('Database connection error', 'error')

        # If login fails, re-render the login page (will generate new random credentials)
        # Fall through to GET logic

    # --- GET request (or failed POST) – show login page with random demo credentials ---

    # Initialize variables to None (safe default)
    random_student = None
    random_lecturer = None

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Random student
            cursor.execute("SELECT email, password FROM STUDENT ORDER BY RAND() LIMIT 1")
            random_student = cursor.fetchone()

            # Random lecturer (exclude admin if inadvertently in lecturers table)
            cursor.execute(
                "SELECT email, password FROM LECTURER WHERE email != 'admin@university.com' ORDER BY RAND() LIMIT 1")
            random_lecturer = cursor.fetchone()
        except Error as e:
            print(f"Error fetching random credentials: {e}")
        finally:
            cursor.close()
            conn.close()

    # If no student exists in DB, provide fallback dummy data so template doesn't break
    if not random_student:
        random_student = {'email': 'student@example.com', 'password': 'demo123'}
    if not random_lecturer:
        random_lecturer = {'email': 'lecturer@example.com', 'password': 'demo123'}

    return render_template('login.html',
                           random_student=random_student,
                           random_lecturer=random_lecturer)

@app.route('/register', methods=['GET', 'POST'])
def register():
    conn = get_db_connection()
    departments = []

    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT department_id, department_name, department_code FROM DEPARTMENT")
        departments = cursor.fetchall()
        cursor.close()
        conn.close()

    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        level = request.form['level']
        is_self_sponsored = request.form.get('is_self_sponsored') == 'on'

        program1 = request.form.get('program1')
        program2 = request.form.get('program2')
        program3 = request.form.get('program3')

        kin_name = request.form['kin_name']
        kin_relationship = request.form['kin_relationship']
        kin_phone = request.form['kin_phone']
        kin_email = request.form['kin_email']
        kin_address = request.form['kin_address']

        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('register.html', departments=departments)

        o_level_file = request.files.get('o_level_results')
        a_level_file = request.files.get('a_level_results')

        o_level_path = None
        a_level_path = None

        if o_level_file and allowed_file(o_level_file.filename):
            filename = secure_filename(f"olevel_{email}_{o_level_file.filename}")
            o_level_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            o_level_file.save(o_level_path)

        if a_level_file and allowed_file(a_level_file.filename):
            filename = secure_filename(f"alevel_{email}_{a_level_file.filename}")
            a_level_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            a_level_file.save(a_level_path)

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    INSERT INTO STUDENT (student_name, email, password, level, department_id, registration_date, is_self_sponsored, application_status)
                    VALUES (%s, %s, %s, %s, %s, CURDATE(), %s, 'Pending')
                """, (full_name, email, password, level, None, is_self_sponsored))

                student_id = cursor.lastrowid

                programs = [p for p in [program1, program2, program3] if p]
                for idx, prog_id in enumerate(programs, 1):
                    cursor.execute("""
                        INSERT INTO STUDENT_APPLICATIONS (student_id, department_id, priority_order, application_date)
                        VALUES (%s, %s, %s, CURDATE())
                    """, (student_id, prog_id, idx))

                cursor.execute("""
                    INSERT INTO NEXT_OF_KIN (student_id, name, relationship, phone, email, address)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (student_id, kin_name, kin_relationship, kin_phone, kin_email, kin_address))

                if o_level_path:
                    cursor.execute("""
                        INSERT INTO STUDENT_DOCUMENTS (student_id, document_type, file_path, upload_date)
                        VALUES (%s, 'O Level Results', %s, CURDATE())
                    """, (student_id, o_level_path))

                if a_level_path:
                    cursor.execute("""
                        INSERT INTO STUDENT_DOCUMENTS (student_id, document_type, file_path, upload_date)
                        VALUES (%s, 'A Level Results', %s, CURDATE())
                    """, (student_id, a_level_path))

                conn.commit()
                flash('Registration successful! Your application is pending review.', 'success')
                return redirect(url_for('login'))

            except Error as e:
                conn.rollback()
                flash(f'Registration error: {str(e)}', 'error')
            finally:
                cursor.close()
                conn.close()
        else:
            flash('Database connection error', 'error')

    return render_template('register.html', departments=departments)


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))


@app.route('/home')
@login_required
def home():
    role = session.get('user_role')
    print(f"User role: {role}")  # Debug print
    print(f"Session contents: {dict(session)}")  # Debug print

    if role == 'student':
        return redirect(url_for('student_dashboard'))
    elif role == 'lecturer':
        return lecturer_home()
    elif role == 'admin':
        return admin_home()
    else:
        flash('Invalid user role', 'error')
        return redirect(url_for('logout'))


def student_home():
    student_id = session['user_id']
    conn = get_db_connection()

    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html', message="Cannot connect to database")

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT s.student_name, s.level, s.email, s.application_status, s.is_self_sponsored,
                   d.department_name,
                   a.accommodation_id, a.room_number, a.building_name
            FROM STUDENT s
            LEFT JOIN DEPARTMENT d ON s.department_id = d.department_id
            LEFT JOIN ACCOMMODATION a ON s.student_id = a.student_id
            WHERE s.student_id = %s
        """, (student_id,))
        student_info = cursor.fetchone()

        cursor.execute("""
            SELECT e.enrollment_id, m.module_name, m.module_code, m.credits,
                   l.lecturer_name, l.email as lecturer_email,
                   e.semester, e.enrollment_date
            FROM ENROLLMENT e
            JOIN MODULE m ON e.module_id = m.module_id
            LEFT JOIN TEACHES t ON m.module_id = t.module_id AND t.semester = e.semester
            LEFT JOIN LECTURER l ON t.lecturer_id = l.lecturer_id
            WHERE e.student_id = %s AND e.semester = 'Fall 2024'
        """, (student_id,))
        current_modules = cursor.fetchall()

        cursor.execute("""
            SELECT SUM(amount_due) as total_due, SUM(amount_paid) as total_paid
            FROM FEES WHERE student_id = %s
        """, (student_id,))
        fee_data = cursor.fetchone()

        total_due = fee_data['total_due'] if fee_data and fee_data['total_due'] else 0
        total_paid = fee_data['total_paid'] if fee_data and fee_data['total_paid'] else 0
        outstanding = total_due - total_paid

        cursor.execute("""
            SELECT COUNT(*) as result_count FROM RESULT 
            WHERE student_id = %s AND grade IS NOT NULL
        """, (student_id,))
        result_count = cursor.fetchone()
        results_available = result_count['result_count'] > 0 if result_count else False

        cursor.execute("""
            SELECT COUNT(*) as total_spaces, COUNT(a.student_id) as occupied_spaces
            FROM ACCOMMODATION_SPACES acs
            LEFT JOIN ACCOMMODATION a ON acs.space_id = a.space_id
            WHERE acs.is_available = TRUE
        """)
        spaces = cursor.fetchone()

        total_spaces = spaces['total_spaces'] if spaces else 0
        occupied_spaces = spaces['occupied_spaces'] if spaces else 0
        available_spaces = total_spaces - occupied_spaces

    except Error as e:
        flash(f'Error: {str(e)}', 'error')
        print(f"Error: {e}")
        student_info = None
        current_modules = []
        total_due = total_paid = outstanding = 0
        results_available = False
        available_spaces = 0
    finally:
        cursor.close()
        conn.close()

    return render_template('student_home.html',
                           student=student_info,
                           modules=current_modules,
                           total_due=total_due,
                           total_paid=total_paid,
                           outstanding=outstanding,
                           results_available=results_available,
                           available_spaces=available_spaces)


def lecturer_home():
    lecturer_id = session['user_id']
    conn = get_db_connection()

    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html', message="Cannot connect to database")

    cursor = conn.cursor(dictionary=True)

    try:
        # Get lecturer department
        cursor.execute("""
            SELECT l.lecturer_name, l.email, l.office_hours,
                   d.department_name, d.department_code
            FROM LECTURER l
            LEFT JOIN DEPARTMENT d ON l.department_id = d.department_id
            WHERE l.lecturer_id = %s AND l.email != 'admin@university.com'
        """, (lecturer_id,))
        lecturer_info = cursor.fetchone()

        # If no lecturer found (maybe admin trying to access), redirect to admin home
        if not lecturer_info:
            flash('Redirecting to admin dashboard...', 'info')
            return redirect(url_for('admin_home'))

        # Get upcoming lectures (next 7 days)
        cursor.execute("""
            SELECT m.module_name, m.module_code, 
                   t.lecture_day, t.lecture_time, t.venue,
                   t.lecture_date, t.duration
            FROM TEACHES t
            JOIN MODULE m ON t.module_id = m.module_id
            WHERE t.lecturer_id = %s 
            AND (t.lecture_date >= CURDATE() OR t.lecture_date IS NULL)
            ORDER BY t.lecture_date ASC, t.lecture_time ASC
            LIMIT 10
        """, (lecturer_id,))
        upcoming_lectures = cursor.fetchall()

        # Get statistics for the dashboard
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT t.module_id) as total_courses,
                COUNT(DISTINCT e.student_id) as total_students
            FROM TEACHES t
            LEFT JOIN MODULE m ON t.module_id = m.module_id
            LEFT JOIN ENROLLMENT e ON m.module_id = e.module_id
            WHERE t.lecturer_id = %s
        """, (lecturer_id,))
        stats = cursor.fetchone()

    except Error as e:
        flash(f'Error: {str(e)}', 'error')
        print(f"Error: {e}")
        lecturer_info = None
        upcoming_lectures = []
        stats = {'total_courses': 0, 'total_students': 0}
    finally:
        cursor.close()
        conn.close()

    return render_template('lecturer_home.html',
                           lecturer=lecturer_info,
                           lectures=upcoming_lectures,
                           stats=stats)


def admin_home():
    # Verify admin role
    if session.get('user_role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))

    conn = get_db_connection()

    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html', message="Cannot connect to database")

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT COUNT(*) as count FROM STUDENT")
        student_count = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) as count FROM STUDENT WHERE application_status = 'Pending'")
        pending_count = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) as count FROM LECTURER WHERE email != 'admin@university.com'")
        lecturer_count = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) as count FROM MODULE")
        module_count = cursor.fetchone()
    except Error as e:
        flash(f'Error: {str(e)}', 'error')
        student_count = lecturer_count = module_count = pending_count = {'count': 0}
    finally:
        cursor.close()
        conn.close()

    return render_template('admin_home.html',
                           student_count=student_count['count'] if student_count else 0,
                           pending_count=pending_count['count'] if pending_count else 0,
                           lecturer_count=lecturer_count['count'] if lecturer_count else 0,
                           module_count=module_count['count'] if module_count else 0)


# ==================== STUDENT ROUTES ====================

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    """Student main dashboard"""
    if session.get('user_role') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('home'))

    student_id = session['user_id']
    conn = get_db_connection()

    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html', message="Cannot connect to database")

    cursor = conn.cursor(dictionary=True)

    try:
        # Get student info
        cursor.execute("""
            SELECT s.*, d.department_name,
                   a.accommodation_id, a.room_number, a.building_name
            FROM STUDENT s
            LEFT JOIN DEPARTMENT d ON s.department_id = d.department_id
            LEFT JOIN ACCOMMODATION a ON s.student_id = a.student_id
            WHERE s.student_id = %s
        """, (student_id,))
        student = cursor.fetchone()

        # Get current modules
        cursor.execute("""
            SELECT m.module_name, m.module_code, m.credits,
                   l.lecturer_name, e.semester
            FROM ENROLLMENT e
            JOIN MODULE m ON e.module_id = m.module_id
            LEFT JOIN TEACHES t ON m.module_id = t.module_id
            LEFT JOIN LECTURER l ON t.lecturer_id = l.lecturer_id
            WHERE e.student_id = %s AND e.semester = 'Fall 2024'
            LIMIT 4
        """, (student_id,))
        current_modules = cursor.fetchall()

        # Get fee summary
        cursor.execute("""
            SELECT SUM(amount_due) as total_due, SUM(amount_paid) as total_paid,
                   COUNT(CASE WHEN status = 'Paid' THEN 1 END) as paid_count,
                   COUNT(CASE WHEN status = 'Pending' THEN 1 END) as pending_count
            FROM FEES WHERE student_id = %s
        """, (student_id,))
        fee_summary = cursor.fetchone()

        # Get upcoming lectures
        cursor.execute("""
            SELECT DISTINCT m.module_name, m.module_code, t.lecture_day, 
                   t.lecture_time, t.venue, t.lecture_date
            FROM ENROLLMENT e
            JOIN MODULE m ON e.module_id = m.module_id
            JOIN TEACHES t ON m.module_id = t.module_id
            WHERE e.student_id = %s AND (t.lecture_date >= CURDATE() OR t.lecture_date IS NULL)
            ORDER BY t.lecture_date ASC, t.lecture_time ASC
            LIMIT 5
        """, (student_id,))
        upcoming_lectures = cursor.fetchall()

        # Get recent results
        cursor.execute("""
            SELECT m.module_name, r.grade, r.semester
            FROM RESULT r
            JOIN MODULE m ON r.module_id = m.module_id
            WHERE r.student_id = %s AND r.grade IS NOT NULL
            ORDER BY r.semester DESC
            LIMIT 5
        """, (student_id,))
        recent_results = cursor.fetchall()

    except Error as e:
        flash(f'Error: {str(e)}', 'error')
        student = None
        current_modules = []
        fee_summary = {'total_due': 0, 'total_paid': 0, 'paid_count': 0, 'pending_count': 0}
        upcoming_lectures = []
        recent_results = []
    finally:
        cursor.close()
        conn.close()

    return render_template('student/dashboard.html',
                           student=student,
                           current_modules=current_modules,
                           fee_summary=fee_summary,
                           upcoming_lectures=upcoming_lectures,
                           recent_results=recent_results)


@app.route('/student/financial-statement')
@login_required
def student_financial_statement():
    """View detailed financial statement"""
    if session.get('user_role') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('home'))

    student_id = session['user_id']
    conn = get_db_connection()

    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html', message="Cannot connect to database")

    cursor = conn.cursor(dictionary=True)

    try:
        # Get student info
        cursor.execute("SELECT student_name, email FROM STUDENT WHERE student_id = %s", (student_id,))
        student = cursor.fetchone()

        # Get all fee records
        cursor.execute("""
            SELECT fee_id, amount_due, amount_paid, 
                   (amount_due - amount_paid) as outstanding,
                   status, due_date
            FROM FEES 
            WHERE student_id = %s
            ORDER BY due_date DESC
        """, (student_id,))
        fee_records = cursor.fetchall()

        # Get summary
        cursor.execute("""
            SELECT 
                SUM(amount_due) as total_due,
                SUM(amount_paid) as total_paid,
                SUM(amount_due - amount_paid) as total_outstanding,
                COUNT(CASE WHEN status = 'Paid' THEN 1 END) as paid_invoices,
                COUNT(CASE WHEN status = 'Partial' THEN 1 END) as partial_invoices,
                COUNT(CASE WHEN status = 'Pending' THEN 1 END) as pending_invoices
            FROM FEES 
            WHERE student_id = %s
        """, (student_id,))
        summary = cursor.fetchone()

        # Get payment history
        cursor.execute("""
            SELECT amount_paid as amount, status, due_date as date
            FROM FEES 
            WHERE student_id = %s AND amount_paid > 0
            ORDER BY due_date DESC
            LIMIT 10
        """, (student_id,))
        payment_history = cursor.fetchall()

    except Error as e:
        flash(f'Error: {str(e)}', 'error')
        student = None
        fee_records = []
        summary = {'total_due': 0, 'total_paid': 0, 'total_outstanding': 0}
        payment_history = []
    finally:
        cursor.close()
        conn.close()

    return render_template('student/financial_statement.html',
                           student=student,
                           fee_records=fee_records,
                           summary=summary,
                           payment_history=payment_history)


@app.route('/student/coursework')
@login_required
def student_coursework():
    """View coursework assessments and grades"""
    if session.get('user_role') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('home'))

    student_id = session['user_id']
    conn = get_db_connection()

    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html', message="Cannot connect to database")

    cursor = conn.cursor(dictionary=True)

    try:
        # Get all modules with coursework
        cursor.execute("""
            SELECT DISTINCT m.module_id, m.module_name, m.module_code, m.credits,
                   l.lecturer_name, e.semester
            FROM ENROLLMENT e
            JOIN MODULE m ON e.module_id = m.module_id
            LEFT JOIN TEACHES t ON m.module_id = t.module_id
            LEFT JOIN LECTURER l ON t.lecturer_id = l.lecturer_id
            WHERE e.student_id = %s
            ORDER BY m.module_name
        """, (student_id,))
        modules = cursor.fetchall()

        # For each module, get assessments (you can create an ASSESSMENTS table)
        # For now, we'll use a sample structure
        for module in modules:
            # Get final grade if available
            cursor.execute("""
                SELECT grade FROM RESULT 
                WHERE student_id = %s AND module_id = %s
                ORDER BY semester DESC LIMIT 1
            """, (student_id, module['module_id']))
            result = cursor.fetchone()
            module['final_grade'] = result['grade'] if result else 'Not Available'

            # Sample assessment structure - you can expand this with a proper ASSESSMENTS table
            module['assessments'] = [
                {'name': 'Assignment 1', 'weight': 20, 'score': None, 'status': 'Pending'},
                {'name': 'Mid-term Exam', 'weight': 30, 'score': None, 'status': 'Pending'},
                {'name': 'Assignment 2', 'weight': 20, 'score': None, 'status': 'Pending'},
                {'name': 'Final Exam', 'weight': 30, 'score': None, 'status': 'Pending'}
            ]

    except Error as e:
        flash(f'Error: {str(e)}', 'error')
        modules = []
    finally:
        cursor.close()
        conn.close()

    return render_template('student/coursework.html', modules=modules)


@app.route('/student/accommodation')
@login_required
def student_accommodation():
    """View and register for accommodation"""
    if session.get('user_role') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('home'))

    student_id = session['user_id']
    conn = get_db_connection()

    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html', message="Cannot connect to database")

    cursor = conn.cursor(dictionary=True)

    try:
        # Get current accommodation
        cursor.execute("""
            SELECT a.*, s.building_name, s.room_number as space_room
            FROM ACCOMMODATION a
            JOIN ACCOMMODATION_SPACES s ON a.space_id = s.space_id
            WHERE a.student_id = %s
        """, (student_id,))
        current_accommodation = cursor.fetchone()

        # Get available spaces
        cursor.execute("""
            SELECT space_id, building_name, room_number
            FROM ACCOMMODATION_SPACES
            WHERE is_available = TRUE
            ORDER BY building_name, room_number
        """)
        available_spaces = cursor.fetchall()

        # Check if student is on waitlist
        cursor.execute("""
            SELECT * FROM ACCOMMODATION_WAITLIST 
            WHERE student_id = %s AND status = 'Waiting'
        """, (student_id,))
        on_waitlist = cursor.fetchone()

        # Get waitlist position (count of people ahead)
        waitlist_position = 0
        if on_waitlist:
            cursor.execute("""
                SELECT COUNT(*) as position
                FROM ACCOMMODATION_WAITLIST 
                WHERE status = 'Waiting' AND request_date <= (
                    SELECT request_date FROM ACCOMMODATION_WAITLIST 
                    WHERE student_id = %s AND status = 'Waiting'
                )
            """, (student_id,))
            result = cursor.fetchone()
            waitlist_position = result['position'] if result else 0

    except Error as e:
        flash(f'Error: {str(e)}', 'error')
        print(f"Error: {e}")
        current_accommodation = None
        available_spaces = []
        on_waitlist = None
        waitlist_position = 0
    finally:
        cursor.close()
        conn.close()

    return render_template('student/accommodation.html',
                           current_accommodation=current_accommodation,
                           available_spaces=available_spaces,
                           waitlist_position=waitlist_position,
                           on_waitlist=on_waitlist)


@app.route('/student/join_waitlist', methods=['POST'])
@login_required
def student_join_waitlist():
    """Join accommodation waiting list"""
    if session.get('user_role') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('home'))

    student_id = session['user_id']
    conn = get_db_connection()

    if conn:
        cursor = conn.cursor()
        try:
            # Check if already on waitlist
            cursor.execute("SELECT * FROM ACCOMMODATION_WAITLIST WHERE student_id = %s AND status = 'Waiting'",
                           (student_id,))
            existing = cursor.fetchone()

            if not existing:
                cursor.execute("""
                    INSERT INTO ACCOMMODATION_WAITLIST (student_id, request_date, status)
                    VALUES (%s, CURDATE(), 'Waiting')
                """, (student_id,))
                conn.commit()
                flash('You have been added to the waiting list!', 'success')
            else:
                flash('You are already on the waiting list!', 'info')
        except Error as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()

    return redirect(url_for('student_accommodation'))

@app.route('/student/apply_accommodation', methods=['POST'])
@login_required
def student_apply_accommodation():
    """Apply for accommodation"""
    if session.get('user_role') != 'student':
        return jsonify({'success': False, 'error': 'Access denied'})

    student_id = session['user_id']
    space_id = request.form.get('space_id')

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Check if space is still available
            cursor.execute("SELECT is_available FROM ACCOMMODATION_SPACES WHERE space_id = %s", (space_id,))
            result = cursor.fetchone()

            if result and result[0]:
                # Create accommodation
                cursor.execute("""
                    INSERT INTO ACCOMMODATION (student_id, space_id, room_number, building_name)
                    SELECT %s, space_id, room_number, building_name
                    FROM ACCOMMODATION_SPACES WHERE space_id = %s
                """, (student_id, space_id))

                # Mark space as unavailable
                cursor.execute("UPDATE ACCOMMODATION_SPACES SET is_available = FALSE WHERE space_id = %s", (space_id,))

                conn.commit()
                flash('Accommodation application successful!', 'success')
            else:
                flash('Space no longer available', 'error')
        except Error as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()

    return redirect(url_for('student_accommodation'))


@app.route('/student/exam-timetable')
@login_required
def student_exam_timetable():
    """View exam timetable"""
    if session.get('user_role') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('home'))

    student_id = session['user_id']
    conn = get_db_connection()

    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html', message="Cannot connect to database")

    cursor = conn.cursor(dictionary=True)

    try:
        # Get exam timetable (you can create an EXAM_SCHEDULE table)
        # For now, we'll create sample data based on enrolled modules
        cursor.execute("""
            SELECT DISTINCT m.module_id, m.module_name, m.module_code, e.semester
            FROM ENROLLMENT e
            JOIN MODULE m ON e.module_id = m.module_id
            WHERE e.student_id = %s
        """, (student_id,))
        modules = cursor.fetchall()

        # Sample exam schedule - replace with actual data from EXAM_SCHEDULE table
        exam_schedule = []
        for idx, module in enumerate(modules):
            exam_schedule.append({
                'module_name': module['module_name'],
                'module_code': module['module_code'],
                'exam_date': f'2024-12-{10 + idx}',
                'exam_time': '09:00:00',
                'duration': 3,
                'venue': f'Exam Hall {idx + 1}',
                'semester': module['semester']
            })

    except Error as e:
        flash(f'Error: {str(e)}', 'error')
        exam_schedule = []
    finally:
        cursor.close()
        conn.close()

    return render_template('student/exam_timetable.html', exam_schedule=exam_schedule)


@app.route('/student/lecture-schedule')
@login_required
def student_lecture_schedule():
    """View lecture schedule/timetable"""
    if session.get('user_role') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('home'))

    student_id = session['user_id']
    conn = get_db_connection()

    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html', message="Cannot connect to database")

    cursor = conn.cursor(dictionary=True)

    try:
        # Get lecture schedule
        cursor.execute("""
            SELECT DISTINCT m.module_name, m.module_code, t.lecture_day, 
                   t.lecture_time, t.venue, t.duration, t.lecture_date,
                   l.lecturer_name
            FROM ENROLLMENT e
            JOIN MODULE m ON e.module_id = m.module_id
            JOIN TEACHES t ON m.module_id = t.module_id
            LEFT JOIN LECTURER l ON t.lecturer_id = l.lecturer_id
            WHERE e.student_id = %s AND e.semester = 'Fall 2024'
            ORDER BY FIELD(t.lecture_day, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'), t.lecture_time
        """, (student_id,))
        lectures = cursor.fetchall()

        # Group by day
        schedule_by_day = {
            'Monday': [],
            'Tuesday': [],
            'Wednesday': [],
            'Thursday': [],
            'Friday': [],
            'Saturday': [],
            'Sunday': []
        }

        for lecture in lectures:
            day = lecture['lecture_day'] or 'TBD'
            if day in schedule_by_day:
                schedule_by_day[day].append(lecture)

    except Error as e:
        flash(f'Error: {str(e)}', 'error')
        schedule_by_day = {}
    finally:
        cursor.close()
        conn.close()

    return render_template('student/lecture_schedule.html', schedule_by_day=schedule_by_day)

# ==================== LECTURER ROUTES ====================

@app.route('/lecturer/courses')
@login_required
def lecturer_courses():
    """Display courses taught by the lecturer"""
    if session.get('user_role') != 'lecturer':
        flash('Access denied. Lecturer privileges required.', 'error')
        return redirect(url_for('home'))

    lecturer_id = session['user_id']
    conn = get_db_connection()

    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html', message="Cannot connect to database")

    cursor = conn.cursor(dictionary=True)

    try:
        # Get lecturer's courses with enrollment counts
        cursor.execute("""
            SELECT 
                m.module_id,
                m.module_name, 
                m.module_code, 
                m.credits,
                d.department_name,
                COUNT(DISTINCT e.student_id) as enrolled_students,
                t.semester,
                t.lecture_day,
                t.lecture_time,
                t.venue
            FROM TEACHES t
            JOIN MODULE m ON t.module_id = m.module_id
            JOIN DEPARTMENT d ON m.department_id = d.department_id
            LEFT JOIN ENROLLMENT e ON m.module_id = e.module_id AND e.semester = t.semester
            WHERE t.lecturer_id = %s
            GROUP BY m.module_id, m.module_name, m.module_code, m.credits, d.department_name, t.semester, t.lecture_day, t.lecture_time, t.venue
            ORDER BY m.module_name
        """, (lecturer_id,))
        courses = cursor.fetchall()

        # Get teaching statistics
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT m.module_id) as total_courses,
                COUNT(DISTINCT e.student_id) as total_students,
                COUNT(DISTINCT CASE WHEN r.grade IS NOT NULL THEN e.student_id END) as graded_students
            FROM TEACHES t
            JOIN MODULE m ON t.module_id = m.module_id
            LEFT JOIN ENROLLMENT e ON m.module_id = e.module_id
            LEFT JOIN RESULT r ON e.student_id = r.student_id AND e.module_id = r.module_id
            WHERE t.lecturer_id = %s
        """, (lecturer_id,))
        stats = cursor.fetchone()

    except Error as e:
        flash(f'Error: {str(e)}', 'error')
        courses = []
        stats = {'total_courses': 0, 'total_students': 0, 'graded_students': 0}
    finally:
        cursor.close()
        conn.close()

    return render_template('lecturer/courses.html', courses=courses, stats=stats)


@app.route('/lecturer/enter_marks', methods=['GET', 'POST'])
@login_required
def lecturer_enter_marks():
    """Allow lecturer to enter/update student marks"""
    if session.get('user_role') != 'lecturer':
        flash('Access denied. Lecturer privileges required.', 'error')
        return redirect(url_for('home'))

    lecturer_id = session['user_id']
    conn = get_db_connection()

    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html', message="Cannot connect to database")

    cursor = conn.cursor(dictionary=True)

    # Get lecturer's courses for dropdown
    cursor.execute("""
        SELECT DISTINCT 
            m.module_id, 
            m.module_name, 
            m.module_code,
            t.semester
        FROM TEACHES t
        JOIN MODULE m ON t.module_id = m.module_id
        WHERE t.lecturer_id = %s
        ORDER BY m.module_name
    """, (lecturer_id,))
    courses = cursor.fetchall()

    if request.method == 'POST':
        module_id = request.form['module_id']
        semester = request.form['semester']
        student_id = request.form['student_id']
        grade = request.form['grade'].upper()

        try:
            # Check if grade is valid
            valid_grades = ['A', 'B', 'C', 'D', 'E', 'F']
            if grade not in valid_grades:
                flash('Invalid grade. Please enter A, B, C, D, E, or F', 'error')
                return redirect(url_for('lecturer_enter_marks'))

            # Check if student is enrolled in this module
            cursor.execute("""
                SELECT * FROM ENROLLMENT 
                WHERE module_id = %s AND student_id = %s AND semester = %s
            """, (module_id, student_id, semester))
            enrollment = cursor.fetchone()

            if not enrollment:
                flash('Student is not enrolled in this module for the selected semester', 'error')
                return redirect(url_for('lecturer_enter_marks'))

            # Check if result already exists
            cursor.execute("""
                SELECT * FROM RESULT 
                WHERE module_id = %s AND student_id = %s AND semester = %s
            """, (module_id, student_id, semester))
            existing = cursor.fetchone()

            if existing:
                # Update existing result
                cursor.execute("""
                    UPDATE RESULT 
                    SET grade = %s 
                    WHERE module_id = %s AND student_id = %s AND semester = %s
                """, (grade, module_id, student_id, semester))
                flash(f'Grade updated successfully for student ID: {student_id}', 'success')
            else:
                # Insert new result
                cursor.execute("""
                    INSERT INTO RESULT (student_id, module_id, grade, semester)
                    VALUES (%s, %s, %s, %s)
                """, (student_id, module_id, grade, semester))
                flash(f'Grade entered successfully for student ID: {student_id}', 'success')

            conn.commit()

        except Error as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('lecturer_enter_marks'))

    # GET request - show form
    selected_module = request.args.get('module_id')
    selected_semester = request.args.get('semester')
    students = []

    if selected_module and selected_semester:
        try:
            # Get students enrolled in the selected module with their current grades
            cursor.execute("""
                SELECT 
                    s.student_id,
                    s.student_name,
                    s.email,
                    r.grade as current_grade
                FROM ENROLLMENT e
                JOIN STUDENT s ON e.student_id = s.student_id
                LEFT JOIN RESULT r ON e.student_id = r.student_id 
                    AND e.module_id = r.module_id 
                    AND e.semester = r.semester
                WHERE e.module_id = %s AND e.semester = %s
                ORDER BY s.student_name
            """, (selected_module, selected_semester))
            students = cursor.fetchall()
        except Error as e:
            flash(f'Error loading students: {str(e)}', 'error')

    cursor.close()
    conn.close()

    return render_template('lecturer/enter_marks.html',
                           courses=courses,
                           students=students,
                           selected_module=selected_module,
                           selected_semester=selected_semester)


@app.route('/lecturer/course/<int:module_id>/students')
@login_required
def lecturer_course_students(module_id):
    """View all students in a specific course"""
    if session.get('user_role') != 'lecturer':
        flash('Access denied. Lecturer privileges required.', 'error')
        return redirect(url_for('home'))

    lecturer_id = session['user_id']
    conn = get_db_connection()

    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html', message="Cannot connect to database")

    cursor = conn.cursor(dictionary=True)

    try:
        # Verify lecturer teaches this course
        cursor.execute("""
            SELECT * FROM TEACHES WHERE lecturer_id = %s AND module_id = %s
        """, (lecturer_id, module_id))
        if not cursor.fetchone():
            flash('You do not have permission to view this course', 'error')
            return redirect(url_for('lecturer_courses'))

        # Get course details
        cursor.execute("""
            SELECT m.*, d.department_name
            FROM MODULE m
            JOIN DEPARTMENT d ON m.department_id = d.department_id
            WHERE m.module_id = %s
        """, (module_id,))
        course = cursor.fetchone()

        # Get students enrolled in the course with their grades
        cursor.execute("""
            SELECT 
                s.student_id,
                s.student_name,
                s.email,
                s.level,
                e.enrollment_date,
                r.grade,
                r.semester
            FROM ENROLLMENT e
            JOIN STUDENT s ON e.student_id = s.student_id
            LEFT JOIN RESULT r ON e.student_id = r.student_id 
                AND e.module_id = r.module_id 
                AND e.semester = r.semester
            WHERE e.module_id = %s
            ORDER BY s.student_name
        """, (module_id,))
        students = cursor.fetchall()

    except Error as e:
        flash(f'Error: {str(e)}', 'error')
        course = None
        students = []
    finally:
        cursor.close()
        conn.close()

    return render_template('lecturer/course_students.html', course=course, students=students)


@app.route('/lecturer/update_grade', methods=['POST'])
@login_required
def lecturer_update_grade():
    """AJAX endpoint to update a single student's grade"""
    if session.get('user_role') != 'lecturer':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    data = request.get_json()
    student_id = data.get('student_id')
    module_id = data.get('module_id')
    semester = data.get('semester')
    grade = data.get('grade', '').upper()

    valid_grades = ['A', 'B', 'C', 'D', 'E', 'F', '']
    if grade not in valid_grades:
        return jsonify({'success': False, 'error': 'Invalid grade'})

    lecturer_id = session['user_id']
    conn = get_db_connection()

    if not conn:
        return jsonify({'success': False, 'error': 'Database connection error'})

    cursor = conn.cursor(dictionary=True)

    try:
        # Verify lecturer teaches this module
        cursor.execute("""
            SELECT * FROM TEACHES WHERE lecturer_id = %s AND module_id = %s
        """, (lecturer_id, module_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'error': 'You do not teach this module'})

        # Check if student is enrolled
        cursor.execute("""
            SELECT * FROM ENROLLMENT 
            WHERE module_id = %s AND student_id = %s AND semester = %s
        """, (module_id, student_id, semester))
        if not cursor.fetchone():
            return jsonify({'success': False, 'error': 'Student not enrolled'})

        # Update or insert grade
        if grade:
            cursor.execute("""
                INSERT INTO RESULT (student_id, module_id, grade, semester)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE grade = %s
            """, (student_id, module_id, grade, semester, grade))
        else:
            # Remove grade if empty
            cursor.execute("""
                DELETE FROM RESULT 
                WHERE student_id = %s AND module_id = %s AND semester = %s
            """, (student_id, module_id, semester))

        conn.commit()
        return jsonify({'success': True})

    except Error as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/lecturer/download_grade_sheet/<int:module_id>/<semester>')
@login_required
def lecturer_download_grade_sheet(module_id, semester):
    """Download grade sheet as CSV"""
    if session.get('user_role') != 'lecturer':
        flash('Access denied', 'error')
        return redirect(url_for('home'))

    lecturer_id = session['user_id']
    conn = get_db_connection()

    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('home'))

    cursor = conn.cursor(dictionary=True)

    try:
        # Verify lecturer teaches this module
        cursor.execute("""
            SELECT * FROM TEACHES WHERE lecturer_id = %s AND module_id = %s
        """, (lecturer_id, module_id))
        if not cursor.fetchone():
            flash('You do not have permission', 'error')
            return redirect(url_for('lecturer_courses'))

        # Get course info
        cursor.execute("SELECT module_name, module_code FROM MODULE WHERE module_id = %s", (module_id,))
        module = cursor.fetchone()

        # Get students and grades
        cursor.execute("""
            SELECT 
                s.student_id,
                s.student_name,
                s.email,
                COALESCE(r.grade, 'Not Entered') as grade
            FROM ENROLLMENT e
            JOIN STUDENT s ON e.student_id = s.student_id
            LEFT JOIN RESULT r ON e.student_id = r.student_id 
                AND e.module_id = r.module_id 
                AND e.semester = r.semester
            WHERE e.module_id = %s AND e.semester = %s
            ORDER BY s.student_name
        """, (module_id, semester))
        students = cursor.fetchall()

        # Create CSV
        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(['Student ID', 'Student Name', 'Email', 'Grade'])

        # Write data
        for student in students:
            writer.writerow([student['student_id'], student['student_name'], student['email'], student['grade']])

        # Prepare response
        from flask import make_response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename={module["module_code"]}_{semester}_grades.csv'

        return response

    except Error as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('lecturer_courses'))
    finally:
        cursor.close()
        conn.close()

# ==================== ADMIN ROUTES ====================

# Manage Students
@app.route('/admin/manage_students')
@admin_required
def admin_manage_students():
    conn = get_db_connection()
    students = []
    departments = []

    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.*, d.department_name 
            FROM STUDENT s
            LEFT JOIN DEPARTMENT d ON s.department_id = d.department_id
            ORDER BY s.student_id DESC
        """)
        students = cursor.fetchall()

        cursor.execute("SELECT * FROM DEPARTMENT")
        departments = cursor.fetchall()
        cursor.close()
        conn.close()

    return render_template('admin/manage_students.html', students=students, departments=departments)


@app.route('/admin/get_student/<int:student_id>')
@admin_required
def admin_get_student(student_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM STUDENT WHERE student_id = %s", (student_id,))
        student = cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify(student)
    return jsonify({'error': 'Student not found'}), 404


@app.route('/admin/save_student', methods=['POST'])
@admin_required
def admin_save_student():
    student_id = request.form.get('student_id')
    student_name = request.form['student_name']
    email = request.form['email']
    password = request.form.get('password')
    level = request.form['level']
    department_id = request.form.get('department_id') or None
    application_status = request.form['application_status']

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            if student_id:  # Update
                if password:
                    cursor.execute("""
                        UPDATE STUDENT SET student_name=%s, email=%s, password=%s, 
                        level=%s, department_id=%s, application_status=%s
                        WHERE student_id=%s
                    """, (student_name, email, password, level, department_id, application_status, student_id))
                else:
                    cursor.execute("""
                        UPDATE STUDENT SET student_name=%s, email=%s, 
                        level=%s, department_id=%s, application_status=%s
                        WHERE student_id=%s
                    """, (student_name, email, level, department_id, application_status, student_id))
                flash('Student updated successfully!', 'success')
            else:  # Insert
                cursor.execute("""
                    INSERT INTO STUDENT (student_name, email, password, level, department_id, registration_date, application_status)
                    VALUES (%s, %s, %s, %s, %s, CURDATE(), %s)
                """, (student_name, email, password, level, department_id, application_status))
                flash('Student added successfully!', 'success')

            conn.commit()
        except Error as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()

    return redirect(url_for('admin_manage_students'))


@app.route('/admin/approve_student/<int:student_id>', methods=['POST'])
@admin_required
def admin_approve_student(student_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE STUDENT SET application_status = 'Approved' WHERE student_id = %s", (student_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True})
    return jsonify({'success': False})


@app.route('/admin/delete_student/<int:student_id>', methods=['DELETE'])
@admin_required
def admin_delete_student(student_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM STUDENT WHERE student_id = %s", (student_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True})
    return jsonify({'success': False})


# Manage Lecturers
@app.route('/admin/manage_lecturers')
@admin_required
def admin_manage_lecturers():
    conn = get_db_connection()
    lecturers = []
    departments = []

    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT l.*, d.department_name,
                   (SELECT COUNT(*) FROM TEACHES t WHERE t.lecturer_id = l.lecturer_id) as course_count
            FROM LECTURER l
            LEFT JOIN DEPARTMENT d ON l.department_id = d.department_id
            ORDER BY l.lecturer_id DESC
        """)
        lecturers = cursor.fetchall()

        cursor.execute("SELECT * FROM DEPARTMENT")
        departments = cursor.fetchall()
        cursor.close()
        conn.close()

    return render_template('admin/manage_lecturers.html', lecturers=lecturers, departments=departments)


@app.route('/admin/get_lecturer/<int:lecturer_id>')
@admin_required
def admin_get_lecturer(lecturer_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM LECTURER WHERE lecturer_id = %s", (lecturer_id,))
        lecturer = cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify(lecturer)
    return jsonify({'error': 'Lecturer not found'}), 404


@app.route('/admin/save_lecturer', methods=['POST'])
@admin_required
def admin_save_lecturer():
    lecturer_id = request.form.get('lecturer_id')
    lecturer_name = request.form['lecturer_name']
    email = request.form['email']
    password = request.form.get('password')
    department_id = request.form.get('department_id') or None
    office_hours = request.form.get('office_hours')

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            if lecturer_id:  # Update
                if password:
                    cursor.execute("""
                        UPDATE LECTURER SET lecturer_name=%s, email=%s, password=%s, 
                        department_id=%s, office_hours=%s
                        WHERE lecturer_id=%s
                    """, (lecturer_name, email, password, department_id, office_hours, lecturer_id))
                else:
                    cursor.execute("""
                        UPDATE LECTURER SET lecturer_name=%s, email=%s, 
                        department_id=%s, office_hours=%s
                        WHERE lecturer_id=%s
                    """, (lecturer_name, email, department_id, office_hours, lecturer_id))
                flash('Lecturer updated successfully!', 'success')
            else:  # Insert
                cursor.execute("""
                    INSERT INTO LECTURER (lecturer_name, email, password, department_id, office_hours)
                    VALUES (%s, %s, %s, %s, %s)
                """, (lecturer_name, email, password, department_id, office_hours))
                flash('Lecturer added successfully!', 'success')

            conn.commit()
        except Error as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()

    return redirect(url_for('admin_manage_lecturers'))


@app.route('/admin/delete_lecturer/<int:lecturer_id>', methods=['DELETE'])
@admin_required
def admin_delete_lecturer(lecturer_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM LECTURER WHERE lecturer_id = %s", (lecturer_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True})
    return jsonify({'success': False})


# Manage Modules
@app.route('/admin/manage_modules')
@admin_required
def admin_manage_modules():
    conn = get_db_connection()
    modules = []
    departments = []
    all_lecturers = []

    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT m.*, d.department_name,
                   (SELECT COUNT(*) FROM ENROLLMENT e WHERE e.module_id = m.module_id) as enrolled_count,
                   (SELECT l.lecturer_name FROM TEACHES t JOIN LECTURER l ON t.lecturer_id = l.lecturer_id 
                    WHERE t.module_id = m.module_id LIMIT 1) as lecturer_name
            FROM MODULE m
            LEFT JOIN DEPARTMENT d ON m.department_id = d.department_id
            ORDER BY m.module_id DESC
        """)
        modules = cursor.fetchall()

        cursor.execute("SELECT * FROM DEPARTMENT")
        departments = cursor.fetchall()

        cursor.execute(
            "SELECT l.*, d.department_name FROM LECTURER l LEFT JOIN DEPARTMENT d ON l.department_id = d.department_id")
        all_lecturers = cursor.fetchall()
        cursor.close()
        conn.close()

    return render_template('admin/manage_modules.html', modules=modules, departments=departments,
                           all_lecturers=all_lecturers)


@app.route('/admin/get_module/<int:module_id>')
@admin_required
def admin_get_module(module_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM MODULE WHERE module_id = %s", (module_id,))
        module = cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify(module)
    return jsonify({'error': 'Module not found'}), 404


@app.route('/admin/save_module', methods=['POST'])
@admin_required
def admin_save_module():
    module_id = request.form.get('module_id')
    module_name = request.form['module_name']
    module_code = request.form['module_code']
    credits = request.form['credits']
    department_id = request.form['department_id']

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            if module_id:  # Update
                cursor.execute("""
                    UPDATE MODULE SET module_name=%s, module_code=%s, credits=%s, department_id=%s
                    WHERE module_id=%s
                """, (module_name, module_code, credits, department_id, module_id))
                flash('Module updated successfully!', 'success')
            else:  # Insert
                cursor.execute("""
                    INSERT INTO MODULE (module_name, module_code, credits, department_id)
                    VALUES (%s, %s, %s, %s)
                """, (module_name, module_code, credits, department_id))
                flash('Module added successfully!', 'success')

            conn.commit()
        except Error as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()

    return redirect(url_for('admin_manage_modules'))


@app.route('/admin/assign_lecturer', methods=['POST'])
@admin_required
def admin_assign_lecturer():
    module_id = request.form['module_id']
    lecturer_id = request.form['lecturer_id']
    semester = request.form['semester']

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Check if assignment already exists
            cursor.execute("""
                SELECT * FROM TEACHES WHERE module_id = %s AND semester = %s
            """, (module_id, semester))
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE TEACHES SET lecturer_id = %s WHERE module_id = %s AND semester = %s
                """, (lecturer_id, module_id, semester))
            else:
                cursor.execute("""
                    INSERT INTO TEACHES (lecturer_id, module_id, semester)
                    VALUES (%s, %s, %s)
                """, (lecturer_id, module_id, semester))

            conn.commit()
            flash('Lecturer assigned successfully!', 'success')
        except Error as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()

    return redirect(url_for('admin_manage_modules'))


@app.route('/admin/delete_module/<int:module_id>', methods=['DELETE'])
@admin_required
def admin_delete_module(module_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM MODULE WHERE module_id = %s", (module_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True})
    return jsonify({'success': False})


# Fee Management
@app.route('/admin/manage_fees')
@admin_required
def admin_manage_fees():
    conn = get_db_connection()
    fees = []
    students = []
    total_revenue = 0
    total_outstanding = 0
    paid_count = 0
    pending_count = 0

    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT f.*, s.student_name 
            FROM FEES f
            JOIN STUDENT s ON f.student_id = s.student_id
            ORDER BY f.fee_id DESC
        """)
        fees = cursor.fetchall()

        cursor.execute("SELECT student_id, student_name FROM STUDENT ORDER BY student_name")
        students = cursor.fetchall()

        # Calculate totals
        cursor.execute("SELECT SUM(amount_paid) as total FROM FEES")
        total_revenue = cursor.fetchone()['total'] or 0

        cursor.execute("SELECT SUM(amount_due - amount_paid) as total FROM FEES")
        total_outstanding = cursor.fetchone()['total'] or 0

        cursor.execute("SELECT COUNT(*) as count FROM FEES WHERE amount_paid >= amount_due")
        paid_count = cursor.fetchone()['count'] or 0

        cursor.execute("SELECT COUNT(*) as count FROM FEES WHERE amount_paid = 0")
        pending_count = cursor.fetchone()['count'] or 0

        cursor.close()
        conn.close()

    return render_template('admin/manage_fees.html',
                           fees=fees,
                           students=students,
                           total_revenue=total_revenue,
                           total_outstanding=total_outstanding,
                           paid_count=paid_count,
                           pending_count=pending_count)


@app.route('/admin/add_fee', methods=['POST'])
@admin_required
def admin_add_fee():
    student_id = request.form['student_id']
    amount_due = request.form['amount_due']
    due_date = request.form.get('due_date')

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO FEES (student_id, amount_due, amount_paid, status, due_date)
                VALUES (%s, %s, 0, 'Pending', %s)
            """, (student_id, amount_due, due_date))
            conn.commit()
            flash('Fee record added successfully!', 'success')
        except Error as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()

    return redirect(url_for('admin_manage_fees'))


@app.route('/admin/record_payment', methods=['POST'])
@admin_required
def admin_record_payment():
    fee_id = request.form['fee_id']
    payment_amount = float(request.form['payment_amount'])

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM FEES WHERE fee_id = %s", (fee_id,))
            fee = cursor.fetchone()

            new_paid = fee['amount_paid'] + payment_amount
            status = 'Paid' if new_paid >= fee['amount_due'] else 'Partial'

            cursor.execute("""
                UPDATE FEES SET amount_paid = %s, status = %s WHERE fee_id = %s
            """, (new_paid, status, fee_id))
            conn.commit()
            flash('Payment recorded successfully!', 'success')
        except Error as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()

    return redirect(url_for('admin_manage_fees'))


# Accommodation Management
@app.route('/admin/manage_accommodation')
@admin_required
def admin_manage_accommodation():
    conn = get_db_connection()
    spaces = []
    accommodated_students = []
    students_without_accommodation = []
    total_spaces = 0
    available_spaces = 0
    occupied_spaces = 0
    waiting_count = 0

    if conn:
        cursor = conn.cursor(dictionary=True)

        # Get all spaces with occupancy info
        cursor.execute("""
            SELECT s.*, a.student_id, stu.student_name
            FROM ACCOMMODATION_SPACES s
            LEFT JOIN ACCOMMODATION a ON s.space_id = a.space_id
            LEFT JOIN STUDENT stu ON a.student_id = stu.student_id
            ORDER BY s.building_name, s.room_number
        """)
        spaces = cursor.fetchall()

        # Get accommodated students
        cursor.execute("""
            SELECT a.*, s.student_name, s.email
            FROM ACCOMMODATION a
            JOIN STUDENT s ON a.student_id = s.student_id
        """)
        accommodated_students = cursor.fetchall()

        # Get students without accommodation
        cursor.execute("""
            SELECT student_id, student_name, email 
            FROM STUDENT 
            WHERE student_id NOT IN (SELECT student_id FROM ACCOMMODATION WHERE student_id IS NOT NULL)
            AND application_status = 'Approved'
        """)
        students_without_accommodation = cursor.fetchall()

        # Count statistics
        cursor.execute("SELECT COUNT(*) as count FROM ACCOMMODATION_SPACES")
        total_spaces = cursor.fetchone()['count'] or 0

        cursor.execute("SELECT COUNT(*) as count FROM ACCOMMODATION_SPACES WHERE is_available = TRUE")
        available_spaces = cursor.fetchone()['count'] or 0

        cursor.execute("SELECT COUNT(*) as count FROM ACCOMMODATION")
        occupied_spaces = cursor.fetchone()['count'] or 0

        cursor.execute(
            "SELECT COUNT(*) as count FROM STUDENT WHERE student_id NOT IN (SELECT student_id FROM ACCOMMODATION WHERE student_id IS NOT NULL)")
        waiting_count = cursor.fetchone()['count'] or 0

        cursor.close()
        conn.close()

    return render_template('admin/manage_accommodation.html',
                           spaces=spaces,
                           accommodated_students=accommodated_students,
                           students_without_accommodation=students_without_accommodation,
                           total_spaces=total_spaces,
                           available_spaces=available_spaces,
                           occupied_spaces=occupied_spaces,
                           waiting_count=waiting_count)


@app.route('/admin/add_space', methods=['POST'])
@admin_required
def admin_add_space():
    building_name = request.form['building_name']
    room_number = request.form['room_number']

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO ACCOMMODATION_SPACES (building_name, room_number, is_available)
                VALUES (%s, %s, TRUE)
            """, (building_name, room_number))
            conn.commit()
            flash('Accommodation space added successfully!', 'success')
        except Error as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()

    return redirect(url_for('admin_manage_accommodation'))


@app.route('/admin/assign_space', methods=['POST'])
@admin_required
def admin_assign_space():
    space_id = request.form['space_id']
    student_id = request.form['student_id']

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Get space details
            cursor.execute("SELECT * FROM ACCOMMODATION_SPACES WHERE space_id = %s", (space_id,))
            space = cursor.fetchone()

            # Create accommodation record
            cursor.execute("""
                INSERT INTO ACCOMMODATION (student_id, room_number, building_name, space_id)
                VALUES (%s, %s, %s, %s)
            """, (student_id, space[2], space[1], space_id))

            # Mark space as unavailable
            cursor.execute("UPDATE ACCOMMODATION_SPACES SET is_available = FALSE WHERE space_id = %s", (space_id,))

            conn.commit()
            flash('Space assigned successfully!', 'success')
        except Error as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()

    return redirect(url_for('admin_manage_accommodation'))


@app.route('/admin/vacate_space/<int:space_id>', methods=['POST'])
@admin_required
def admin_vacate_space(space_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Delete accommodation record
            cursor.execute("DELETE FROM ACCOMMODATION WHERE space_id = %s", (space_id,))
            # Mark space as available
            cursor.execute("UPDATE ACCOMMODATION_SPACES SET is_available = TRUE WHERE space_id = %s", (space_id,))
            conn.commit()
            return jsonify({'success': True})
        except Error as e:
            conn.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            cursor.close()
            conn.close()
    return jsonify({'success': False})


@app.route('/admin/remove_accommodation/<int:accommodation_id>', methods=['DELETE'])
@admin_required
def admin_remove_accommodation(accommodation_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT space_id FROM ACCOMMODATION WHERE accommodation_id = %s", (accommodation_id,))
            result = cursor.fetchone()
            if result:
                space_id = result[0]
                cursor.execute("UPDATE ACCOMMODATION_SPACES SET is_available = TRUE WHERE space_id = %s", (space_id,))
            cursor.execute("DELETE FROM ACCOMMODATION WHERE accommodation_id = %s", (accommodation_id,))
            conn.commit()
            return jsonify({'success': True})
        except Error as e:
            conn.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            cursor.close()
            conn.close()
    return jsonify({'success': False})


@app.route('/admin/delete_space/<int:space_id>', methods=['DELETE'])
@admin_required
def admin_delete_space(space_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM ACCOMMODATION_SPACES WHERE space_id = %s", (space_id,))
            conn.commit()
            return jsonify({'success': True})
        except Error as e:
            conn.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            cursor.close()
            conn.close()
    return jsonify({'success': False})


# Pending Applications
@app.route('/admin/pending_applications')
@admin_required
def admin_pending_applications():
    conn = get_db_connection()
    applications = []
    pending_count = 0
    total_applications = 0

    if conn:
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT * FROM STUDENT WHERE application_status = 'Pending' ORDER BY registration_date DESC
        """)
        pending_students = cursor.fetchall()

        for student in pending_students:
            # Get programs
            cursor.execute("""
                SELECT d.department_name, d.department_code, sa.priority_order
                FROM STUDENT_APPLICATIONS sa
                JOIN DEPARTMENT d ON sa.department_id = d.department_id
                WHERE sa.student_id = %s
                ORDER BY sa.priority_order
            """, (student['student_id'],))
            student['programs'] = cursor.fetchall()

            # Get next of kin
            cursor.execute("""
                SELECT * FROM NEXT_OF_KIN WHERE student_id = %s
            """, (student['student_id'],))
            kin = cursor.fetchone()
            if kin:
                student['kin_name'] = kin['name']
                student['kin_relationship'] = kin['relationship']
                student['kin_phone'] = kin['phone']
                student['kin_email'] = kin['email']
                student['kin_address'] = kin['address']

            # Get documents
            cursor.execute("""
                SELECT * FROM STUDENT_DOCUMENTS WHERE student_id = %s
            """, (student['student_id'],))
            student['documents'] = cursor.fetchall()

            applications.append(student)

        cursor.execute("SELECT COUNT(*) as count FROM STUDENT WHERE application_status = 'Pending'")
        pending_count = cursor.fetchone()['count'] or 0

        cursor.execute("SELECT COUNT(*) as count FROM STUDENT")
        total_applications = cursor.fetchone()['count'] or 0

        cursor.close()
        conn.close()

    return render_template('admin/pending_applications.html',
                           applications=applications,
                           pending_count=pending_count,
                           total_applications=total_applications)


@app.route('/admin/approve_application/<int:student_id>', methods=['POST'])
@admin_required
def admin_approve_application(student_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE STUDENT SET application_status = 'Approved' WHERE student_id = %s", (student_id,))
            conn.commit()
            return jsonify({'success': True})
        except Error as e:
            conn.rollback()
            return jsonify({'success': False, 'message': str(e)})
        finally:
            cursor.close()
            conn.close()
    return jsonify({'success': False, 'message': 'Database connection error'})


@app.route('/admin/reject_application/<int:student_id>', methods=['POST'])
@admin_required
def admin_reject_application(student_id):
    reason = request.json.get('reason', '')
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE STUDENT SET application_status = 'Rejected' WHERE student_id = %s", (student_id,))
            conn.commit()
            # Here you could also save the rejection reason in a separate table
            return jsonify({'success': True})
        except Error as e:
            conn.rollback()
            return jsonify({'success': False, 'message': str(e)})
        finally:
            cursor.close()
            conn.close()
    return jsonify({'success': False, 'message': 'Database connection error'})


@app.route('/admin/get_application_details/<int:student_id>')
@admin_required
def admin_get_application_details(student_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM STUDENT WHERE student_id = %s", (student_id,))
        student = cursor.fetchone()

        cursor.execute("""
            SELECT d.department_name, sa.priority_order
            FROM STUDENT_APPLICATIONS sa
            JOIN DEPARTMENT d ON sa.department_id = d.department_id
            WHERE sa.student_id = %s
        """, (student_id,))
        programs = cursor.fetchall()

        cursor.execute("SELECT * FROM NEXT_OF_KIN WHERE student_id = %s", (student_id,))
        kin = cursor.fetchone()

        cursor.close()
        conn.close()

        return jsonify({
            'student_name': student['student_name'],
            'email': student['email'],
            'level': student['level'],
            'registration_date': str(student['registration_date']),
            'programs': programs,
            'kin_name': kin['name'] if kin else '',
            'kin_relationship': kin['relationship'] if kin else '',
            'kin_phone': kin['phone'] if kin else '',
            'kin_email': kin['email'] if kin else '',
            'kin_address': kin['address'] if kin else ''
        })

    return jsonify({'error': 'Student not found'}), 404


# Other routes
@app.route('/results')
@login_required
def view_results():
    if session.get('user_role') != 'student':
        flash('Only students can view results', 'error')
        return redirect(url_for('home'))

    student_id = session['user_id']
    conn = get_db_connection()

    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html', message="Cannot connect to database")

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT s.student_name, m.module_name, r.grade, r.semester, l.lecturer_name
            FROM RESULT r
            JOIN STUDENT s ON r.student_id = s.student_id
            JOIN MODULE m ON r.module_id = m.module_id
            LEFT JOIN TEACHES t ON m.module_id = t.module_id AND t.semester = r.semester
            LEFT JOIN LECTURER l ON t.lecturer_id = l.lecturer_id
            WHERE r.student_id = %s
        """, (student_id,))
        results = cursor.fetchall()
    except Error as e:
        flash(f'Error: {str(e)}', 'error')
        results = []
    finally:
        cursor.close()
        conn.close()

    return render_template('results.html', results=results)


@app.route('/register_module', methods=['GET', 'POST'])
@login_required
def register_module():
    if session.get('user_role') != 'student':
        flash('Only students can register for modules', 'error')
        return redirect(url_for('home'))

    student_id = session['user_id']
    conn = get_db_connection()

    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html', message="Cannot connect to database")

    if request.method == 'POST':
        module_id = request.form['module_id']
        semester = request.form['semester']
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT SUM(amount_due - amount_paid) as outstanding FROM FEES WHERE student_id = %s",
                           (student_id,))
            result = cursor.fetchone()
            outstanding = result[0] if result and result[0] else 0

            if outstanding > 0:
                flash('Outstanding fees detected - registration blocked', 'error')
            else:
                cursor.execute("""
                    SELECT COUNT(*) FROM ENROLLMENT 
                    WHERE student_id = %s AND module_id = %s AND semester = %s
                """, (student_id, module_id, semester))
                existing = cursor.fetchone()[0]

                if existing > 0:
                    flash('Already registered for this module in this semester', 'error')
                else:
                    cursor.execute("""
                        INSERT INTO ENROLLMENT (student_id, module_id, semester, enrollment_date)
                        VALUES (%s, %s, %s, CURDATE())
                    """, (student_id, module_id, semester))
                    conn.commit()
                    flash('Registration successful!', 'success')
        except Error as e:
            conn.rollback()
            flash(f'Registration error: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('home'))

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT m.module_id, m.module_name, m.module_code, m.credits, d.department_name,
                   GROUP_CONCAT(DISTINCT l.lecturer_name) as lecturers
            FROM MODULE m
            JOIN DEPARTMENT d ON m.department_id = d.department_id
            LEFT JOIN TEACHES t ON m.module_id = t.module_id
            LEFT JOIN LECTURER l ON t.lecturer_id = l.lecturer_id
            WHERE m.module_id NOT IN (
                SELECT module_id FROM ENROLLMENT 
                WHERE student_id = %s AND semester = 'Fall 2024'
            )
            GROUP BY m.module_id
        """, (student_id,))
        available_modules = cursor.fetchall()
    except Error as e:
        flash(f'Error loading modules: {str(e)}', 'error')
        available_modules = []
    finally:
        cursor.close()
        conn.close()

    return render_template('register_module.html', modules=available_modules)


@app.route('/my_applications')
@login_required
def my_applications():
    if session.get('user_role') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('home'))

    student_id = session['user_id']
    conn = get_db_connection()

    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html', message="Cannot connect to database")

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT sa.priority_order, d.department_name, d.department_code, sa.application_date
            FROM STUDENT_APPLICATIONS sa
            JOIN DEPARTMENT d ON sa.department_id = d.department_id
            WHERE sa.student_id = %s
            ORDER BY sa.priority_order
        """, (student_id,))
        applications = cursor.fetchall()

        cursor.execute("""
            SELECT name, relationship, phone, email, address
            FROM NEXT_OF_KIN WHERE student_id = %s
        """, (student_id,))
        next_of_kin = cursor.fetchone()

        cursor.execute("""
            SELECT document_type, file_path, upload_date
            FROM STUDENT_DOCUMENTS WHERE student_id = %s
        """, (student_id,))
        documents = cursor.fetchall()
    except Error as e:
        flash(f'Error: {str(e)}', 'error')
        applications = []
        next_of_kin = None
        documents = []
    finally:
        cursor.close()
        conn.close()

    return render_template('my_applications.html',
                           applications=applications,
                           next_of_kin=next_of_kin,
                           documents=documents)


@app.route('/download/<filename>')
@login_required
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/test_db')
def test_db_connection():
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM STUDENT")
            count = cursor.fetchone()
            cursor.close()
            conn.close()
            return f"Database connection successful! Found {count[0]} students in database."
        return "Database connection failed!"
    except Exception as e:
        return f"Error: {e}"


if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("Starting University Management System...")
    print("=" * 50)
    print(f"Access at: http://localhost:5000")
    print("\nDemo Accounts:")
    print("Student: student1@university.edu / password123")
    print("Lecturer: lecturer1@university.edu / password123")
    print("Admin: admin@university.com / admin123")
    print("=" * 50 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
