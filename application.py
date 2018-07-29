#!/usr/bin/python
# -*- coding: utf-8 -*-
import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Ensure environment variable is set

if not os.environ.get('API_KEY'):
    raise RuntimeError('API_KEY not set')

# Configure application

app = Flask(__name__)

# Ensure templates are auto-reloaded

app.config['TEMPLATES_AUTO_RELOAD'] = True

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Expires'] = 0
    response.headers['Pragma'] = 'no-cache'
    return response


# Custom filter

app.jinja_env.filters['usd'] = usd

# Configure session to use filesystem (instead of signed cookies)

app.config['SESSION_FILE_DIR'] = mkdtemp()
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Configure CS50 Library to use SQLite database

db = SQL('sqlite:///finance.db')


@app.route('/')
@login_required
def index():
    """Show portfolio of stocks"""

    if session['user_id']:

        # table data

        res = db.execute(
            """SELECT symbol, AVG(price) as avg_price, SUM(shares) as total_shares
                     FROM purchases INNER JOIN users ON purchases.userid = users.id WHERE users.id = :uid
                     GROUP BY purchases.symbol""",
            uid=session['user_id'])

        # get user's cash

        cash = db.execute(
            'SELECT cash FROM users WHERE id = :uid', uid=session['user_id'])

        # initial

        total = cash[0]['cash']

        if len(res) > 0:

            for t in res:
                api_res = lookup(t['Symbol'])
                t['cur_price'] = (usd(api_res['price'])
                                  if api_res != None else 'Error!')

                t['cur_value'] = (api_res['price'] * t['total_shares']
                                  if api_res else float(
                                      t['avg_price'] * t['total_shares']))

                total += t['avg_price'] * t['total_shares']

        return render_template(
            'index.html', data=res, total=total, usd=usd, cash=cash)
    else:

        return redirect('/login')


@app.route('/buy', methods=['GET', 'POST'])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == 'POST':

        # ensure there's a ticker

        if not request.form.get('symbol'):
            return apology('please enter a symbol', 400)

        # ensure shares is int & > 0

        try:
            if int(request.form.get('shares')) < 0:
                return apology('invalid # of shares', 400)
        except:
            return apology('invalid input for shares', 400)

        # api call

        res = lookup(request.form.get('symbol'))

        if not res:
            return apology('invalid symbol', 400)

        # get user's cash

        cash = db.execute(
            'SELECT cash FROM users WHERE id = :uid', uid=session['user_id'])

        # can't buy trade

        order = res['price'] * int(request.form.get('shares'))
        if cash[0]['cash'] < order:
            return apology('Not enough cash!', 400)

        # store order inside db

        db.execute(
            'INSERT INTO purchases ("id","UserID","Symbol","Price","Shares")VALUES (NULL, :userid, :symbol, :price, :shares)',
            userid=session['user_id'],
            symbol=request.form.get('symbol').upper(),
            price=res['price'],
            shares=request.form.get('shares'))

        # decrease user cash

        db.execute(
            'UPDATE "users" SET "cash"=:u_cash WHERE "rowid" = :rowid',
            u_cash=cash[0]['cash'] - order,
            rowid=session['user_id'])

        flash('Bought!')
        return redirect('/')
    else:

        # GET request

        return render_template('buy.html')


@app.route('/history')
@login_required
def history():
    """Show history of transactions"""

    # get user data from db

    rows = db.execute(
        """SELECT symbol, price, shares, createdat FROM purchases
                      INNER JOIN users ON purchases.userid = users.id
                      WHERE users.id = :uid ORDER BY createdat DESC""",
        uid=session['user_id'])

    return render_template('history.html', data=rows, usd=usd)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Log user in"""

    # Forget any user_id

    session.clear()

    # User reached route via POST (as by submitting a form via POST)

    if request.method == 'POST':

        # Ensure username was submitted

        if not request.form.get('username'):
            return apology('must provide username', 403)
        elif not request.form.get('password'):

            # Ensure password was submitted

            return apology('must provide password', 403)

        # Query database for username

        rows = db.execute(
            'SELECT * FROM users WHERE username = :username',
            username=request.form.get('username'))

        # Ensure username exists and password is correct

        if len(rows) != 1 or not check_password_hash(
                rows[0]['hash'], request.form.get('password')):
            return apology('invalid username and/or password', 403)

        # Remember which user has logged in

        session['user_id'] = rows[0]['id']

        # Redirect user to home page

        return redirect('/')
    else:

        # User reached route via GET (as by clicking a link or via redirect)

        return render_template('login.html')


@app.route('/logout')
def logout():
    """Log user out"""

    # Forget any user_id

    session.clear()

    # Redirect user to login form

    return redirect('/')


@app.route('/quote', methods=['GET', 'POST'])
@login_required
def quote():
    """Get stock quote."""

    # POST request from a form

    if request.method == 'POST':

        # ensure there's a symbol

        if not request.form.get('symbol'):
            return apology('must provide symbol', 400)

        # api call

        res = lookup(request.form.get('symbol'))

        # not found

        if not res:
            return apology('invalid symbol', 400)
        else:
            return render_template(
                'quote.html', symbol=res['symbol'], price=usd(res['price']))
    else:

        # a GET request response

        return render_template('quote.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Register user"""

    # Forget any user_id

    session.clear()

    # User reached route via POST (as by submitting a form via POST)

    if request.method == 'POST':

        # Ensure username was submitted

        if not request.form.get('username'):
            return apology('must provide username', 400)
        elif not request.form.get('password') or not request.form.get(
                'confirmation'):

            # Ensure password was submitted

            return apology('must provide both password', 400)
        elif request.form.get('password') != request.form.get('confirmation'):

            return apology("passwords don't match", 400)

        # Query database for username

        rows = db.execute(
            'SELECT * FROM users WHERE username = :username',
            username=request.form.get('username'))

        # Ensure unique username

        if len(rows) > 0:
            return apology('username already exists!', 400)

        # add user to db

        rows = db.execute(
            'INSERT INTO users ("id","username","hash") VALUES (NULL,:username,:p_hash)',
            username=request.form.get('username'),
            p_hash=generate_password_hash(request.form.get('password')))

        # Remember which user has logged in

        session['user_id'] = rows

        # flash registered msg

        flash('Registered!')

        # Redirect user to home page

        return redirect('/')
    else:

        # User reached route via GET (as by clicking a link or via redirect)

        return render_template('register.html')


@app.route('/sell', methods=['GET', 'POST'])
@login_required
def sell():
    """Sell shares of stock"""

    # POST sell order

    if request.method == 'POST':

        if int(request.form.get('shares')) < 0:
            return apology('enter positive # of shares', 400)

        # get user data from db

        rows = db.execute(
            """SELECT purchases.id, symbol, price, shares, cash FROM purchases
                          INNER JOIN users ON purchases.userid = users.id
                          WHERE users.id = :uid AND purchases.symbol = :symbol
                          ORDER BY createdat""",
            uid=session['user_id'],
            symbol=request.form.get('symbol'))

        amount = int(request.form.get('shares'))
        total = 0

        # amount valiidation

        for row in rows:
            total += int(row['Shares'])

        if total < amount:
            return apology('not enough shares!', 400)

        # api call

        cur_price = lookup(request.form.get('symbol'))

        # api error

        if not cur_price:
            return apology("couldn't sell right now, try again", 424)

        # store order inside db

        db.execute(
            'INSERT INTO purchases ("id","UserID","Symbol","Price","Shares")VALUES (NULL, :userid, :symbol, :price, :shares)',
            userid=session['user_id'],
            symbol=request.form.get('symbol').upper(),
            price=cur_price['price'],
            shares=-amount)

        # decrease user cash

        db.execute(
            'UPDATE "users" SET "cash"=:u_cash WHERE "rowid" = :rowid',
            u_cash=rows[0]['cash'] + cur_price['price'] * amount,
            rowid=session['user_id'])

        flash('Sold!')
        return redirect('/')
    else:

        # GET request

        # grab user data from db

        rows = db.execute(
            """SELECT symbol FROM purchases
                            INNER JOIN users ON purchases.userid = users.id
                            WHERE users.id = :uid GROUP BY purchases.symbol""",
            uid=session['user_id'])

        return render_template('sell.html', data=rows)


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Settings for the account"""

    # POST sell order

    if request.method == 'POST':

        # ensure form is filled

        if not request.form.get('password') or not request.form.get(
                'new_password') or not request.form.get('confirmation'):
            return apology('enter all the fields', 403)

        # ensure new passwords are same

        if request.form.get('new_password') != request.form.get(
                'confirmation'):
            return apology("password don't match!", 403)

        # Query database for username

        rows = db.execute(
            'SELECT * FROM users WHERE id = :uid', uid=session['user_id'])

        # Ensure current password is correct

        if len(rows) != 1 or not check_password_hash(
                rows[0]['hash'], request.form.get('password')):
            return apology('invalid current password', 403)

        res = db.execute(
            'UPDATE "users" SET "hash"=:newhash WHERE "rowid" = :uid',
            newhash=generate_password_hash(request.form.get('new_password')),
            uid=session['user_id'])

        # all is well

        if res:
            flash('Password Changed!')

        return redirect('/')
    else:

        return render_template('settings.html')


def errorhandler(e):
    """Handle error"""

    return apology(e.name, e.code)


# listen for errors

for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
