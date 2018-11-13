# -*- coding: utf-8 -*-

import configparser
import flask_login
from flask import flash, redirect, render_template, request, url_for, Blueprint
import db_functions
import db_setup
import json

config = configparser.ConfigParser()
config.read('config/integracao.conf')
api = config.get('ENDPOINTS', 'PRATOABERTO_API')
_user = config.get('LOGIN', 'USER')
_password = config.get('LOGIN', 'PASSWORD')

users = {_user: {'password': _password}}

config_app = Blueprint('config_app', __name__)
# BLOCO DE CONFIGURAÇÕES
@config_app.route("/configuracoes_gerais", methods=['GET', 'POST'])
@flask_login.login_required
def config():
    if request.method == "GET":
        config_editor = db_functions.select_all()
        return render_template("configurações.html", config=config_editor)


@config_app.route('/atualiza_configuracoes', methods=['POST'])
@flask_login.login_required
def atualiza_configuracoes():
    headers = {'Content-type': 'application/json'}
    data = request.form.get('json_dump', request.data)

    db_functions.truncate_replacements()

    for row in json.loads(data):
        db_functions.add_replacements(row[0], row[1], row[2], row[3])

    if request.form:

        return (redirect(url_for('config')))
    else:

        return ('', 200)


@config_app.route("/configuracoes_cardapio", methods=['GET', 'POST'])
@flask_login.login_required
def config_cardapio():
    if request.method == "GET":
        config_editor = db_functions.select_all_receitas_terceirizadas()

        return render_template("configurações_receitas.html", config=config_editor)
