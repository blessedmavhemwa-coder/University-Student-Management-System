# School-Management-System
This is a project on the development of a web application which is used to manage the school logistics such as students intake, students details and lecturer's activities

## Application Pages / Dashboard
1. Login Page

   <img width="1365" height="719" alt="Screenshot 2026-05-08 101937" src="https://github.com/user-attachments/assets/e2b3bf0a-bd87-4ab8-811f-4e0ef39fd0ba" />

   This is the login page, where the users input their email and password to access the university management system. The page features a clean form with fields for email address and
   password, a “Login” button, and a link for new users to register. Below the form, demo credentials are provided for testing purposes: a student account (kudzai.m@hmu.ac.zw /
   pass123), a lecturer account (sibongile.d@hmu.ac.zw / password123), and an admin account (admin@university.com / admin123). The credentials for Student and Lecturer vary every the
   application is launched, this is because I used the random function which gives a random user everytime. The page also includes a navigation bar with “Dashboard” and “Logout” options
   (though logout is active only after login) and a header indicating the system name, “University MS – Student Management System”. This serves as the entry point for all users
   students, lecturers, and administrators—to securely access their respective dashboards.

2. Admin Dashboard

   <img width="1365" height="717" alt="Screenshot 2026-05-08 102642" src="https://github.com/user-attachments/assets/64f328a0-ebd5-4ff1-98a8-8c19cbab10c0" />

   This is the Admin's Dashboard what the admin will see after logging in, its features are displayed through a clean overview of key statistics and quick management tools. The
   dashboard shows four summary cards: Total Students (5), Pending Applications (1), Total Lecturers (6), and Active Modules (6), giving the admin an instant snapshot of the
   institution’s data. A System Overview section provides technical and academic context, including Database Status (“Connected”), Current Semester (“Fall 2024”), Registration Period
   (“Active”), and System Version (“1.0”). Below that, Quick Actions buttons allow direct navigation to "Manage Students", "Manage Lecturers", and "View Reports" for common
   administrative tasks. This dashboard serves as the central command center for administrators to monitor system health, track enrollment metrics and perform essential management
   functions.

3. Student Dashboard

   <img width="1365" height="722" alt="Screenshot 2026-05-08 102823" src="https://github.com/user-attachments/assets/4929d218-a780-46eb-8849-4c210e7a8138" />

   This is the Student Dashboard where they are greeted by their name, department, level of study, and student ID in a prominent welcome banner at the top of the page. The dashboard
   provides a quick overview of the student's academic status through four summary cards displaying their current number of enrolled modules, outstanding fees, upcoming lectures, and
   available results. Below the summary cards, the student can view their currently registered modules for the Fall 2024 semester — in this case, no modules have been registered yet,
   with a prompt to do so. Further down, the upcoming lectures section lists scheduled classes such as Operating Systems (CS201) and Software Engineering (CS301), although the time and
   venue details are yet to be confirmed. The left-hand sidebar offers easy navigation to key sections of the system, including the Financial Statement, Coursework Assessment,
   Accommodation, Module Registration, Exam Timetable, Lecture Schedule, and My Results, making it a centralized hub for all student-related academic and administrative activities.

4. Lecturer Dashboard

   <img width="1365" height="719" alt="Screenshot 2026-05-08 102921" src="https://github.com/user-attachments/assets/f6e0f511-be4d-4f15-bf5d-a916d3829b2e" />

   This is the Lecturer Dashboard, designed to give academic staff a concise and functional overview of their teaching responsibilities. Upon logging in, the lecturer is greeted by
   their name in the top right corner — in this case, Dr. Tendai Ncube — alongside a logout button. Three summary cards at the top of the page display key statistics at a glance: the
   number of upcoming lectures, total courses assigned, and the total number of students under their supervision. Below the summary cards, three quick-access tiles provide direct
   navigation to the most commonly used features — My Courses, which allows the lecturer to view all courses they are currently teaching; Enter Marks, which enables them to record and
   update student grades; and Grade Reports, which provides the ability to view and download grade sheets for their modules. Further down the page, a Lecturer Information section
   displays the lecturer's personal and departmental details, including their full name, institutional email address, department, and department code. The sidebar on the left offers
   streamlined navigation with links to the Dashboard, My Courses, Enter Marks, and Logout, keeping the interface clean and focused on the core tasks of a lecturer within the University
   Management System.
   
## Application Directory

```
university-management-system/
├── lication.py                  # Main Flask application (complete code)
├── README.md                       # Project documentation (this file)
├── uploads/                        # Folder for student document uploads (O/A level results)
│
└── templates/                      # Jinja2 HTML templates
    ├── base.html                   # Base layout template
    ├── login.html                  # Login page
    ├── register.html               # Student registration page
    ├── student_home.html           # Student home (fallback, not main)
    ├── lecturer_home.html          # Lecturer dashboard
    ├── admin_home.html             # Admin dashboard
    ├── results.html                # View results (student)
    ├── register_module.html        # Module registration (student)
    ├── my_applications.html        # View submitted applications
    ├── error.html                  # Generic error page
    │
    ├── student/                    # Student-specific templates
    │   ├── dashboard.html
    │   ├── financial_statement.html
    │   ├── coursework.html
    │   ├── accommodation.html
    │   ├── exam_timetable.html
    │   └── lecture_schedule.html
    │
    ├── lecturer/                   # Lecturer-specific templates
    │   ├── courses.html
    │   ├── enter_marks.html
    │   └── course_students.html
    │
    └── admin/                      # Admin-specific templates
        ├── manage_students.html
        ├── manage_lecturers.html
        ├── manage_modules.html
        ├── manage_fees.html
        ├── manage_accommodation.html
        └── pending_applications.html
```

## Relational Schema

<img width="1444" height="1231" alt="Relational Schema" src="https://github.com/user-attachments/assets/fc93045f-1129-4524-a30d-df58989f0e2e" />

Above is the relational schema of the entire system with all the tables to be created by the application.
