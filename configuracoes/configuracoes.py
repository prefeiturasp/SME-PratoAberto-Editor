# -*- coding: utf-8 -*-

import flask_login
import db_functions
import json
import datetime

from flask import redirect, render_template, request, url_for, Blueprint
from utils.utils import get_semana
from cardapios.cardapios import get_cardapio
from escolas.escolas import get_quebras_escolas

config_app = Blueprint('config_app', __name__)

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


# BLOCO MAPA DE PENDENCIAS
@config_app.route('/mapa_pendencias', methods=['GET', 'POST'])
@flask_login.login_required
def mapa_pendencias():
    if request.method == "GET":

        mapa = get_quebras_escolas()

        delta_dias = datetime.timedelta(days=7)
        dia_semana_seguinte = datetime.datetime.now() + delta_dias
        semana = get_semana(dia_semana_seguinte)
        data_inicial = min(semana).strftime("%Y%m%d")
        data_final = max(semana).strftime("%Y%m%d")

        # Por padrão, sempre colocaremos o cardápio da semana seguinte
        mapa_final = []

        for row in mapa:

            args = {'agrupamento': row[0],
                    'tipo_unidade': row[1],
                    'tipo_atendimento': row[2],
                    'idade': row[3],
                    'status': 'SALVO',
                    'data_inicial': data_inicial,
                    'data_final': data_final}

            cardapio = get_cardapio(args)
            if cardapio == []:

                args['status_publicacao'] = 'Pendente'
                mapa_final.append(args)
            else:

                args['status_publicacao'] = 'Feito'
                mapa_final.append(args)

        return render_template("mapa_pendencias.html", publicados=mapa_final,
                               data_inicio_fim=str(data_inicial + '-' + data_final))

    if request.method == "POST":

        mapa = get_quebras_escolas()
        request.form.get('datas', request.data)
        data_inicial = request.form.get('data-inicial', request.data)
        data_final = request.form.get('data-final', request.data)
        data_inicial = datetime.datetime.strptime(data_inicial, '%d/%m/%Y').strftime('%Y%m%d')
        data_final = datetime.datetime.strptime(data_final, '%d/%m/%Y').strftime('%Y%m%d')
        filtro = request.form.get('filtro', request.data)

        # Por padrão, sempre colocaremos o cardápio da semana seguinte
        mapa_final = []

        for row in mapa:

            args = {'agrupamento': row[0],
                    'tipo_unidade': row[1],
                    'tipo_atendimento': row[2],
                    'idade': row[3],
                    'status': filtro,
                    'data_inicial': data_inicial,
                    'data_final': data_final}

            cardapio = get_cardapio(args)

            if cardapio == []:

                args['status_publicacao'] = 'Pendente'
                mapa_final.append(args)
            else:

                args['status_publicacao'] = 'Feito'
                mapa_final.append(args)

        return render_template("mapa_pendencias.html", publicados=mapa_final,
                               data_inicio_fim=str(data_inicial + '-' + data_final))
