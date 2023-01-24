import sqlite3
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import login_required
from datetime import datetime
from validators import email as is_valid_email

# Configure application
application = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies) <----- RESEARCH THIS
application.config["SESSION_PERMANENT"] = False
application.config["SESSION_TYPE"] = "filesystem"
Session(application)


@application.route("/")
@login_required
def index():
    # --------------- GLOBAL SETUP --------------- #
    # set username via session id
    user_id = session["user_id"]

    # open db connection and cursor
    connect = sqlite3.connect("expenses.db")
    cursor = connect.cursor()

    # define username
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    username = cursor.fetchone()[0]

    # define user image - NEED TO UPDATE THIS ON ALL INNER PAGES
    cursor.execute("SELECT image FROM users WHERE user_id = ?", (user_id,))
    userimage = cursor.fetchone()[0]
    # -------------------------------------------- #

    # set current year
    year = str(datetime.now().year)

    #cursor.execute("SELECT strftime('%m.%Y', date) AS month, SUM(total) AS total_sum FROM expenses JOIN categories WHERE user_id = ? AND date BETWEEN date('now', '-6 months') AND date('now') GROUP BY month LIMIT 6", (user_id,))
    cursor.execute("SELECT months.month, COALESCE(SUM(expenses.total), 0) AS total_sum, COALESCE(symbol, '$') AS symbol FROM (SELECT strftime('%m.%Y', date('now', 'start of month', '-5 months')) AS month UNION ALL SELECT strftime('%m.%Y', date('now', 'start of month', '-4 months')) UNION ALL SELECT strftime('%m.%Y', date('now', 'start of month', '-3 months')) UNION ALL SELECT strftime('%m.%Y', date('now', 'start of month', '-2 months')) UNION ALL SELECT strftime('%m.%Y', date('now', 'start of month', '-1 months')) UNION ALL SELECT strftime('%m.%Y', date('now', 'start of month')) ) AS months LEFT JOIN (SELECT * FROM expenses JOIN currencies ON expenses.currency = currencies.currency WHERE user_id = ?) expenses ON strftime('%m.%Y', expenses.date) = months.month GROUP BY months.month ORDER BY datetime(months.month, '+1 months')", (user_id,))
    six_months = cursor.fetchall()
    cursor.execute("SELECT COALESCE(SUM(expenses.total), 0) AS total_sum FROM (SELECT strftime('%m.%Y', date('now', 'start of month', '-5 months')) AS month UNION ALL SELECT strftime('%m.%Y', date('now', 'start of month', '-4 months')) UNION ALL SELECT strftime('%m.%Y', date('now', 'start of month', '-3 months')) UNION ALL SELECT strftime('%m.%Y', date('now', 'start of month', '-2 months')) UNION ALL SELECT strftime('%m.%Y', date('now', 'start of month', '-1 months')) UNION ALL SELECT strftime('%m.%Y', date('now', 'start of month')) ) AS months LEFT JOIN (SELECT * FROM expenses JOIN currencies ON expenses.currency = currencies.currency WHERE user_id = ?) expenses ON strftime('%m.%Y', expenses.date) = months.month GROUP BY months.month ORDER BY total_sum DESC LIMIT 1", (user_id,))
    max_month = cursor.fetchone()[0]

    cursor.execute("SELECT expenses.*, strftime('%d.%m.%Y', expenses.date) AS fdate, currencies.symbol, color FROM expenses JOIN currencies ON expenses.currency = currencies.currency JOIN categories ON expenses.category = categories.category WHERE expenses.user_id = ? ORDER BY date DESC LIMIT 5", (user_id,))
    expenses = cursor.fetchall()

    cursor.execute("SELECT shop, total, symbol, color FROM expenses JOIN currencies ON expenses.currency = currencies.currency JOIN categories ON expenses.category = categories.category WHERE user_id = ? ORDER BY total DESC LIMIT 5", (user_id,))
    top_expenses = cursor.fetchall()

    cursor.execute("SELECT user_id, strftime('%Y', date) AS year, SUM(total) AS total_sum, expenses.category, color, currencies.symbol FROM expenses JOIN categories ON expenses.category = categories.category JOIN currencies ON expenses.currency = currencies.currency WHERE user_id = ? AND strftime('%Y', date) = ? GROUP BY expenses.category ORDER BY total_sum DESC LIMIT 4", (user_id, year))
    top_categories = cursor.fetchall()

    cursor.execute("SELECT SUM(total) / (strftime('%m', 'now')) FROM expenses WHERE user_id = ? AND strftime('%Y', date) = ?", (user_id, year))
    monthly_average = None
    if monthly_average:
        monthly_average = cursor.fetchall()[0][0]
    else:
        monthly_average = 0
    print("monthly_average IS: ", end="")
    print(monthly_average)

    return render_template("index.html", username=username, userimage=userimage, year=year, six_months=six_months, max_month=max_month, expenses=expenses, top_expenses=top_expenses, top_categories=top_categories, monthly_average=monthly_average)


@application.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    
    # clear any session
    session.clear()
    
    # if GET
    if request.method == "GET":
        return render_template("login.html")

    # if POST
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Ensure username was submitted
        if not username:
            return render_template("login.html")

        # Ensure password was submitted
        if not password:
            return render_template("login.html")

        # open db connection and cursor
        connect = sqlite3.connect("expenses.db")
        cursor = connect.cursor()

        # Query database for username
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
       
        # Ensure username exists
        if result is None:
            flash("Username does not exist")
            return render_template("login.html")                    

        # Ensure password is correct
        #if not check_password_hash(result[5], password):
            #flash("Password is incorrect")
            #return render_template("login.html")

        # Remember which user has logged in
        session["user_id"] = result[0]

        # Redirect user to home page
        return redirect("/")


@application.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # if method is get, render login form
    if request.method == "GET":
        return render_template("register.html")

    # if method is post
    if request.method == "POST":
        fname = request.form.get("fname")
        lname = request.form.get("lname")
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # check all field have been filled
        if not fname:
            return render_template("register.html")
        if not lname:
            return render_template("register.html")
        if not username:
            return render_template("register.html")
        if not email:
            return render_template("register.html")
        if not password:
            return render_template("register.html")
        if not confirmation:
            return render_template("register.html")

        # check matching passwords
        if password != confirmation:
            flash("Passwords do not match")
            return render_template("register.html")

        # hash passowrd
        hash = generate_password_hash(password)

        # validate email
        if not is_valid_email(email):
            flash("Invalid email addrress")
            return render_template("register.html")

        # open db connection and cursor
        connect = sqlite3.connect("expenses.db")
        cursor = connect.cursor()

        # check username does not exist in database
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()

        # if usernames exists
        if result:
            flash("Username already exists")
            return render_template("register.html")          

        # if username does not exist, insert username and all details into database
        if not result:
            cursor.execute("INSERT INTO users(fname, lname, username, email, hash) VALUES(?, ?, ?, ?, ?)", (fname, lname, username, email, hash))
            connect.commit()

            # set session cookie for user and redirect to /
            cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
            user_id = cursor.fetchone()
            session["user_id"] = user_id[0]
            cursor.close()
            connect.close()
        return redirect("/")


@application.route("/expenses", methods=["GET", "POST"])
@login_required
def expenses():

    # --------------- GLOBAL SETUP --------------- #
    # set username via session id
    user_id = session["user_id"]

    # open db connection and cursor
    connect = sqlite3.connect("expenses.db")
    cursor = connect.cursor()

    # define username
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    username = cursor.fetchone()[0]

    # define user image - NEED TO UPDATE THIS ON ALL INNER PAGES
    cursor.execute("SELECT image FROM users WHERE user_id = ?", (user_id,))
    userimage = cursor.fetchone()[0]
    # -------------------------------------------- #

    # if method is get, render expense form with currencies and categories
    if request.method == "GET":

        # populate dropdowns with users favorite\preferred currencies\categories
        cursor.execute("SELECT currency FROM currencies")
        currencies = cursor.fetchall()
        cursor.execute("SELECT category FROM categories ORDER BY category ASC") # WHERE user_id = ?", user_id
        categories = cursor.fetchall()
        return render_template("expenses.html", username=username, userimage=userimage, currencies=currencies, categories=categories)

    # if method is post
    if request.method == "POST":

        # define input fields
        date = request.form.get("date")
        shop = request.form.get("shop")
        total = request.form.get("total")
        currency = request.form.get("currency")
        category = request.form.get("category")
        description = request.form.get("description")

        # validate all fields have been entered

        # insert into database
        cursor.execute("INSERT INTO expenses (user_id, date, shop, total, currency, category, description) VALUES (?, ?, ?, ?, ?, ?, ?)", (user_id, date, shop, total, currency, category, description))
        connect.commit()

    cursor.close()
    connect.close()
    return redirect("/")


@application.route("/categories", methods=["GET", "POST"])
@login_required
def categories():

    # --------------- GLOBAL SETUP --------------- #
    # set username via session id
    user_id = session["user_id"]

    # open db connection and cursor
    connect = sqlite3.connect("expenses.db")
    cursor = connect.cursor()

    # define username
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    username = cursor.fetchone()[0]

    # define user image - NEED TO UPDATE THIS ON ALL INNER PAGES
    cursor.execute("SELECT image FROM users WHERE user_id = ?", (user_id,))
    userimage = cursor.fetchone()[0]
    # -------------------------------------------- #

    # populate color pickers with categories
    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()

    # if method is get, render expense form with currencies and categories
    if request.method == "GET":
        return render_template("categories.html", username=username, userimage=userimage, categories=categories)

    # if method is post
    if request.method == "POST":

        # define input fields for category add\remove - stage 2

        # define input fields for color change
        for row in categories:
            if row[1] in request.form:
                category = row[1]
        new_color = request.form.get(category)
        cursor.execute("UPDATE categories SET color = ? WHERE category = ?", (new_color, category))
        connect.commit()

    cursor.close()
    connect.close()
    return redirect("/categories")


@application.route("/summary", methods=["GET", "POST"])
@login_required
def summary():

    # --------------- GLOBAL SETUP --------------- #
    # set username via session id
    user_id = session["user_id"]

    # open db connection and cursor
    connect = sqlite3.connect("expenses.db")
    cursor = connect.cursor()

    # define username
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    username = cursor.fetchone()[0]

    # define user image - NEED TO UPDATE THIS ON ALL INNER PAGES
    cursor.execute("SELECT image FROM users WHERE user_id = ?", (user_id,))
    userimage = cursor.fetchone()[0]
    # -------------------------------------------- #

    # define expenses
    cursor.execute("SELECT expenses.*, strftime('%d.%m.%Y', expenses.date) AS fdate, currencies.symbol, color FROM expenses JOIN currencies ON expenses.currency = currencies.currency JOIN categories ON expenses.category = categories.category WHERE expenses.user_id = ? ORDER BY date DESC", (user_id,))
    expenses = cursor.fetchall()
    print("EXPENSES IS: ", end="")
    print(expenses)

    # if method is GET
    if request.method == "GET":
        return render_template("summary.html", username=username, userimage=userimage, expenses=expenses)

    # if method is post
    if request.method == "POST":

        # define delete-entry to delete expense from talbe
        expense_id = 0
        for row in expenses:
            eid = "eid"+str(row[0])
            if eid in request.form:
                expense_id = row[0]
        cursor.execute("DELETE FROM expenses WHERE expense_id = ?", (expense_id,))
        connect.commit()
        return redirect("/summary")


@application.route("/search", methods=["GET", "POST"])
@login_required
def search():

    # --------------- GLOBAL SETUP --------------- #
    # set username via session id
    user_id = session["user_id"]

    # open db connection and cursor
    connect = sqlite3.connect("expenses.db")
    cursor = connect.cursor()

    # define username
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    username = cursor.fetchone()[0]

    # define user image - NEED TO UPDATE THIS ON ALL INNER PAGES
    cursor.execute("SELECT image FROM users WHERE user_id = ?", (user_id,))
    userimage = cursor.fetchone()[0]
    # -------------------------------------------- #

    # if method is get, render search page
    if request.method == "GET":
        return render_template("search.html", username=username, userimage=userimage)

    # if method is post
    if request.method == "POST":

        # define input fields
        #dropdown = request.form.get("search-dropdown")
        #description = request.form.get("search-description")
        #category = request.form.get("search-category")
        #shop = request.form.get("search-shop")
        #date_start = request.form.get("search-date-start")
        #date_end = request.form.get("search-date-end")
        #price_start = request.form.get("search-price-start")
        #price_end = request.form.get("search-price-end")

        print("------------")
        dropdown_value = str(request.form.get("search-dropdown"))

        if dropdown_value == "description" or dropdown_value == "category" or dropdown_value == "shop":
            input_value = str(request.form.get("search-"+dropdown_value))
            print(dropdown_value)
            print(input_value)

            # query the search from the database
            #cursor.execute("SELECT expenses.*, strftime('%d.%m.%Y', expenses.date) AS fdate, currencies.symbol, color FROM expenses JOIN currencies ON expenses.currency = currencies.currency JOIN categories ON expenses.category = categories.category WHERE expenses.user_id = ? AND ? = ? ORDER BY date DESC", (user_id, dropdown_value, input_value))
            sql = "SELECT * FROM expenses WHERE user_id = "+str(user_id)+" AND "+dropdown_value+" = '"+input_value+"'"
            print("SQL IS: ", end="")
            print(sql)
            cursor.execute(sql)
            search_results = cursor.fetchall()
            print(search_results)
            print("------------")

        if dropdown_value == "date" or dropdown_value == "total":
            input_value1 = request.form.get("search-"+dropdown_value+"-start")
            input_value2 = request.form.get("search-"+dropdown_value+"-end")
            #cursor.execute("SELECT * FROM expenses WHERE date BETWEEN ? AND ?", (dropdown_value, input_value1, input_value2))
            sql = "SELECT expenses.*, strftime('%d.%m.%Y', expenses.date) AS fdate, symbol FROM expenses JOIN currencies ON expenses.currency = currencies.currency WHERE user_id = "+str(user_id)+" AND "+dropdown_value+" BETWEEN '"+input_value1+"' AND '"+input_value2+"'"
            print("SQL IS: ", end="")
            print(sql)
            cursor.execute(sql)
            search_results = cursor.fetchall()
            print(search_results)
            print("------------")

        cursor.close()
        connect.close()
        return render_template("search.html", username=username, userimage=userimage, search_results=search_results, expenses=expenses)


@application.route("/settings", methods=["GET", "POST"])
def settings():
    # --------------- GLOBAL SETUP --------------- #
    # set username via session id
    user_id = session["user_id"]

    # open db connection and cursor
    connect = sqlite3.connect("expenses.db")
    cursor = connect.cursor()

    # define username
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    username = cursor.fetchone()[0]

    # define user image - NEED TO UPDATE THIS ON ALL INNER PAGES
    cursor.execute("SELECT image FROM users WHERE user_id = ?", (user_id,))
    userimage = cursor.fetchone()[0]
    # -------------------------------------------- #

    # if method is get, render search page
    if request.method == "GET":
        return render_template("settings.html", username=username, userimage=userimage)

    # if method is post
    if request.method == "POST":

        # create a dictionary for the name and value of the input fields
        form_data = {}

        # populate the inputs dictionary
        form_data["fname"] = request.form.get("fname")
        form_data["lname"] = request.form.get("lname")
        form_data["username"] = request.form.get("username")
        form_data["email"] = request.form.get("email")
        form_data["password"] = request.form.get("password")
        form_data["image"] = request.form.get("profile-image")

        # check that username is available
        cursor.execute("SELECT * FROM users WHERE username = ?", (form_data["username"],))
        username_check = cursor.fetchone()
        if username_check:
            flash("Username is not available")
            return render_template("settings.html")

        
        # create sql query
        sql = "UPDATE users SET "

        # iterate through the form data and create a list of inputs
        inputs =  []
        for input, value in form_data.items():
            # only add the input if the value is not empty
            if value:
                inputs.append(f"{input} = '{value}'")

        # join the inputs with a comma and append it to the query
        sql += ", ".join(inputs)

        sql += " WHERE user_id = ?"
        print("SQL IS: ", end="")
        print(sql)
        # execute the query with the appropriate parameters
        cursor.execute(sql, (user_id,))
        connect.commit()
        return redirect("/")


@application.route("/logout")
def logout():

    # clear session
    session.clear()

    # Redirect user to login form
    return redirect("/")