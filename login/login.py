# -*- coding: utf-8 -*-

import configparser
import flask_login
from flask import flash, redirect, render_template, request, url_for, Blueprint

config = configparser.ConfigParser()
config.read('config/integracao.conf')
api = config.get('ENDPOINTS', 'PRATOABERTO_API')
_user = config.get('LOGIN', 'USER')
_password = config.get('LOGIN', 'PASSWORD')

users = {_user: {'password': _password}}
login_app = Blueprint('login_app', __name__)

class User(flask_login.UserMixin):

    pass

@login_app.route('/', methods=['GET', 'POST'])
def login():

    if request.method == 'GET':

        return render_template('login.html')

    email = request.form['username']

    if email in users:

        if request.form['password'] == users[email]['password']:

            user = User()
            user.id = email
            flask_login.login_user(user)

            return redirect(url_for('pendencias_app.backlog'))

    flash('Senha ou usuario nao identificados')

    return render_template('login.html')


@login_app.route('/logout')
@flask_login.login_required
def logout():

    flask_login.logout_user()

    return redirect('/')