# -*- coding: utf-8 -*-

import db_setup
import flask_login

from flask import Flask
from login.login import login_app
from configuracoes.configuracoes import config_app
from upload.upload import upload_app
from pendencias.pendencias import pendencias_app
from download.download import download_app
from escolas.escolas import escolas_app
from cardapios.cardapios import cardapios_app
from outros.outros import outros_app

from utils.utils import get_config

def create_app():

    app = Flask(__name__)
    app.config['UPLOAD_FOLDER'] = './tmp'
    app.register_blueprint(pendencias_app)
    app.register_blueprint(login_app)
    app.register_blueprint(config_app)
    app.register_blueprint(upload_app)
    app.register_blueprint(download_app)
    app.register_blueprint(escolas_app)
    app.register_blueprint(cardapios_app)
    app.register_blueprint(outros_app)

    return app

app = create_app()

# BLOCO GET ENDPOINT E KEYS
config = get_config()
api = config.get('ENDPOINTS', 'PRATOABERTO_API')
_user = config.get('LOGIN', 'USER')
_password = config.get('LOGIN', 'PASSWORD')
app.secret_key = config.get("TOKENS", "APPLICATION_KEY")

# BLOCO LOGIN
login_manager = flask_login.LoginManager()
login_manager.init_app(app)

users = {_user: {'password': _password}}


class User(flask_login.UserMixin):

    pass


@login_manager.user_loader
def user_loader(email):

    if email not in users:

        return

    user = User()
    user.id = email

    return user


@login_manager.request_loader
def request_loader(request):

    email = request.form.get('email')
    if email not in users:

        return

    user = User()
    user.id = email

    # DO NOT ever store passwords in plaintext and always compare password
    # hashes using constant-time comparison!
    user.is_authenticated = request.form['password'] == users[email]['password']

    return user

@login_manager.unauthorized_handler
def unauthorized_handler():

    return 'Unauthorized'

if __name__ == "__main__":

    app = create_app()
    db_setup.set()
    app.run(debug=True)