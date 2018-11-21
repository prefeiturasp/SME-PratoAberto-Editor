# -*- coding: utf-8 -*-

import flask_login
import requests
import json
import db_functions
import os
import cardapio_xml_para_dict

from flask import Flask,flash,redirect, render_template, request, url_for, Blueprint
from werkzeug.utils import secure_filename
from utils.utils import get_config

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './tmp'

config = get_config()
api = config.get('ENDPOINTS', 'PRATOABERTO_API')

upload_app = Blueprint('upload_app', __name__)

@upload_app.route('/upload', methods=['POST'])
@flask_login.login_required
def upload_file():

    if 'file' not in request.files:

        flash('No file part')

        return redirect(request.url)

    file = request.files['file']

    if file.filename == '':

        flash('No selected file')

        return redirect(request.url)

    if file and allowed_file(file.filename):

        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        try:

            cardapio_dict = cardapio_xml_para_dict.create(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            cardapios_preview = []
            json_list = []
            responses = {}

            for tipo_atendimento, v1 in cardapio_dict.items():

                for tipo_unidade, v2 in v1.items():

                    for agrupamento, v3 in v2.items():

                        for idade, v4 in v3.items():

                            for data, v5 in v4.items():

                                query = {
                                    'tipo_atendimento': tipo_atendimento,
                                    'tipo_unidade': tipo_unidade,
                                    'agrupamento': agrupamento,
                                    'idade': idade,
                                }
                                _key = frozenset(query.items())

                                if _key not in responses:
                                    args = (api,
                                            data,
                                            data,
                                            '&'.join(['%s=%s' % item for item in query.items()]),
                                            '&'.join(
                                                ['status=%s' % item for item in
                                                 ['PUBLICADO', 'SALVO', 'PENDENTE', 'DELETADO']]))
                                    responses[_key] = requests.get(
                                        '{}/editor/cardapios?data_inicial={}&data_final={}&{}&{}'.format(*args)).json()

                                cardapio = query
                                cardapio['data'] = data

                                if responses[_key]:

                                    cardapio.update({
                                        'cardapio': {'DUPLICADO': ['DUPLICADO']},
                                        'status': 'DUPLICADO'
                                    })
                                else:

                                    cardapio.update({
                                        'cardapio_original': {k: list(map(str.strip, v.split(','))) for (k, v) in
                                                              v5.items()},
                                        'cardapio': {k: list(map(str.strip, v.split(','))) for (k, v) in v5.items()},
                                        'status': 'PENDENTE'
                                    })
                                    json_list.append(cardapio)

                                cardapios_preview.append(cardapio)

            json_dump = json.dumps(json_list)

        except:

            cardapios_preview, json_dump = [], {}

        return render_template("preview_json.html", filename=filename, cardapios_preview=cardapios_preview,
                               json_dump=json_dump)

@upload_app.route('/cria_terceirizada', methods=['GET'])
@flask_login.login_required
def cria_terceirizada():

    if request.method == "GET":

        quebras = db_functions.select_quebras_terceirizadas()
        editais = set([x[1] for x in quebras])
        tipo_unidade = set([x[0] for x in quebras])
        idade = set([x[2] for x in quebras])
        refeicao = set([x[3] for x in quebras])

        return render_template("cria_terceirizadas.html",
                               editais=editais,
                               tipo_unidade=tipo_unidade,
                               idades=idade,
                               refeicoes=refeicao)

@upload_app.route('/upload_terceirizada', methods=['POST'])
@flask_login.login_required
def upload_terceirizadas():

    headers = {'Content-type': 'application/json'}
    data = request.form.get('json_dump', request.data)
    jdata = json.loads(data)
    cardapios = []

    for refeicao in jdata:

        quebra = {
            'agrupamento': str(refeicao['agrupamento']),
            'tipo_unidade': refeicao['tipo_unidade'],
            'tipo_atendimento': refeicao['tipo_atendimento'],
            'status': refeicao['status'],
            'idade': refeicao['idade'],
            'data': refeicao['data']}

        if not cardapios:

            cardapios = caso_nao_cardapio(quebra, refeicao)

        else:
            # Filtrar os cardapios nas chaves
            cardapios_aux = [d for d in cardapios if d['agrupamento'] == str(refeicao['agrupamento'])]
            cardapios_aux = [d for d in cardapios_aux if d['tipo_unidade'] == refeicao['tipo_unidade']]
            cardapios_aux = [d for d in cardapios_aux if d['tipo_atendimento'] == refeicao['tipo_atendimento']]
            cardapios_aux = [d for d in cardapios_aux if d['status'] == refeicao['status']]
            cardapios_aux = [d for d in cardapios_aux if d['idade'] == refeicao['idade']]
            cardapios_aux = [d for d in cardapios_aux if d['data'] == refeicao['data']]

            if not cardapios_aux:

                cardapios = caso_nao_cardapio(quebra, refeicao)

            else:
                # Caso: quebra ja exista
                count = 0
                _keys = ['agrupamento', 'tipo_unidade', 'tipo_atendimento', 'status', 'idade', 'data']

                for cardapio in cardapios:

                    _flag = True

                    for _key in _keys:

                        if cardapio[_key] != quebra[_key]:
                            _flag = False

                    if _flag == True:
                        # Encontramos o cardapio
                        posicao = count
                    count += 1

                # Tendo a posicao dq quebra igual
                cardapio_aux = cardapios[posicao]
                quebra_aux = cardapio_aux
                quebra_aux['cardapio'][refeicao['tipo_refeicao']] = []
                quebra_aux['cardapio_original'][refeicao['tipo_refeicao']] = []
                cardapios[posicao] = quebra_aux

    r = requests.post(api + '/editor/cardapios', data=json.dumps(cardapios), headers=headers)

    if request.form:

        return (redirect(url_for('pendencias_app.backlog')))
    else:

        return ('', 200)

def caso_nao_cardapio(quebra, refeicao):

    cardapios = []

    quebra_aux = quebra
    quebra_aux['cardapio'] = {refeicao['tipo_refeicao']: []}
    quebra_aux['cardapio_original'] = {refeicao['tipo_refeicao']: []}
    cardapios.append(quebra_aux)

    return cardapios

def allowed_file(filename):

    ALLOWED_EXTENSIONS = set(['txt', 'XML', 'xml'])

    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS