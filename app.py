# -*- coding: utf-8 -*-

import collections
import configparser
import datetime
import itertools
import json
import os
from operator import itemgetter

import flask_login
import requests
from flask import Flask, flash, redirect, render_template, request, url_for, make_response
from werkzeug.utils import secure_filename

import cardapio_xml_para_dict
import cardapios_terceirizadas
import db_functions
import db_setup


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './tmp'

# BLOCO GET ENDPOINT E KEYS
config = configparser.ConfigParser()
config.read('config/integracao.conf')
api = config.get('ENDPOINTS', 'PRATOABERTO_API')
_user = config.get('LOGIN', 'USER')
_password = config.get('LOGIN', 'PASSWORD')
app.secret_key = os.urandom(16)


# BLOCO LOGIN
login_manager = flask_login.LoginManager()
login_manager.init_app(app)

# Our mock database.
# users = {'admin': {'password': 'secret'}}
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


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    email = request.form['username']
    if email in users:
        if request.form['password'] == users[email]['password']:
            user = User()
            user.id = email
            flask_login.login_user(user)
            return redirect(url_for('backlog'))

    flash('Senha ou usuario nao identificados')
    return render_template('login.html')


@app.route('/logout')
@flask_login.login_required
def logout():
    flask_login.logout_user()
    return redirect(url_for('login'))


@login_manager.unauthorized_handler
def unauthorized_handler():
    return 'Unauthorized'


@app.route("/pendencias_publicacoes", methods=["GET", "POST"])
@flask_login.login_required
def backlog():
    if request.method == "GET":
        pendentes = get_pendencias()
        semanas = sorted(set([str(x[4]) + ' - ' + str(x[5]) for x in pendentes]), reverse=True)
        return render_template("pendencias_publicacao.html",
                               pendentes=pendentes,
                               semanas=semanas)

    else:
        pendentes = get_pendencias()
        semanas = sorted(set([str(x[4]) + ' - ' + str(x[5]) for x in pendentes]), reverse=True)
        return render_template("pendencias_publicacao.html",
                               pendentes=pendentes,
                               semanas=semanas)


@app.route("/pendencias_deletadas", methods=["GET", "POST"])
@flask_login.login_required
def deletados():
    if request.method == "GET":
        deletados = get_deletados()
        semanas = sorted(set([str(x[4]) + ' - ' + str(x[5]) for x in deletados]), reverse=True)
        return render_template("pendencias_deletadas.html",
                               pendentes=deletados,
                               semanas=semanas)


@app.route("/pendencias_publicadas", methods=["GET", "POST"])
@flask_login.login_required
def publicados():
    if request.method == "GET":
        publicados = get_publicados()
        semanas = sorted(set([str(x[4]) + ' - ' + str(x[5]) for x in publicados]), reverse=True)
        return render_template("pendencias_publicadas.html",
                               pendentes=publicados,
                               semanas=semanas)


@app.route('/upload', methods=['POST'])
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
                                                ['status=%s' % item for item in ['PUBLICADO', 'SALVO', 'PENDENTE', 'DELETADO']]))
                                    responses[_key] = requests.get('{}/editor/cardapios?data_inicial={}&data_final={}&{}&{}'.format(*args)).json()

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


@app.route('/cria_terceirizada', methods=['GET'])
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


@app.route('/upload_terceirizada', methods=['POST'])
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
            quebra_aux = quebra
            quebra_aux['cardapio'] = {refeicao['tipo_refeicao']: []}
            quebra_aux['cardapio_original'] = {refeicao['tipo_refeicao']: []}
            cardapios.append(quebra_aux)

        else:
            # Filtrar os cardapios nas chaves
            cardapios_aux = [d for d in cardapios if d['agrupamento'] == str(refeicao['agrupamento'])]
            cardapios_aux = [d for d in cardapios_aux if d['tipo_unidade'] == refeicao['tipo_unidade']]
            cardapios_aux = [d for d in cardapios_aux if d['tipo_atendimento'] == refeicao['tipo_atendimento']]
            cardapios_aux = [d for d in cardapios_aux if d['status'] == refeicao['status']]
            cardapios_aux = [d for d in cardapios_aux if d['idade'] == refeicao['idade']]
            cardapios_aux = [d for d in cardapios_aux if d['data'] == refeicao['data']]

            if not cardapios_aux:
                # Caso: quebra nao existe
                quebra_aux = quebra
                quebra_aux['cardapio'] = {refeicao['tipo_refeicao']: []}
                quebra_aux['cardapio_original'] = {refeicao['tipo_refeicao']: []}
                cardapios.append(quebra_aux)

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
        return (redirect(url_for('backlog')))
    else:
        return ('', 200)

@app.route('/atualiza_cardapio', methods=['POST'])
@flask_login.login_required
def atualiza_cardapio():
    headers = {'Content-type': 'application/json'}
    data = request.form.get('json_dump', request.data)
    r = requests.post(api + '/editor/cardapios', data=data, headers=headers)

    if request.form:
        return (redirect(url_for('backlog')))
    else:
        return ('', 200)


# comments = []
@app.route("/calendario", methods=["GET"])
@flask_login.login_required
def calendario():
    args = request.args
    depara = db_functions.select_all()
    depara = [x[3:5] for x in depara if x[2] == 'INGREDIENTES']

    # Monta json - Semana da requisicao
    jdata = get_cardapio(args)

    # Obtem data semana anterior
    args_semana_anterior = args.copy()
    args_semana_anterior['status'] = 'SALVO'
    args_semana_anterior.add('status', 'PUBLICADO')

    delta_dias = datetime.timedelta(days=7)
    data_final_semana_anterior = datetime.datetime.strptime(str(args['data_final']), '%Y%m%d') - delta_dias
    data_inicial_semana_anterior = datetime.datetime.strptime(str(args['data_inicial']), '%Y%m%d') - delta_dias
    args_semana_anterior['data_final'] = datetime.datetime.strftime(data_final_semana_anterior, '%Y%m%d')
    args_semana_anterior['data_inicial'] = datetime.datetime.strftime(data_inicial_semana_anterior, '%Y%m%d')
    # Monta json - Semana anterior a da requisicao
    jdata_anterior = get_cardapio(args_semana_anterior)

    jdata_aux = []
    for cardapio_atual in jdata:
        dia = datetime.datetime.strptime(str(cardapio_atual['data']), '%Y%m%d').weekday()
        cardapio_atual['dia_semana'] = dia_semana(dia)
        jdata_aux.append(cardapio_atual)

    jdata_anterior_aux = []
    for cardapio_anterior in jdata_anterior:
        dia = datetime.datetime.strptime(str(cardapio_anterior['data']), '%Y%m%d').weekday()
        cardapio_anterior['dia_semana'] = dia_semana(dia)
        jdata_anterior_aux.append(cardapio_anterior)

    jdata = jdata_aux
    jdata_anterior = jdata_anterior_aux

    # Liga o cardapio atual com o da semana anterior
    dias_da_semana = set([x['dia_semana'] for x in list(jdata + jdata_anterior)])

    cardapios = []
    for dia in dias_da_semana:
        cardapio_atual = filtro_dicionarios(jdata, 'dia_semana', dia)
        cardapio_anterior = filtro_dicionarios(jdata_anterior, 'dia_semana', dia)

        if cardapio_atual and cardapio_anterior:
            cardapio_atual['cardapio_semana_anterior'] = cardapio_anterior['cardapio']
            cardapios.append(cardapio_atual)

        else:
            if cardapio_atual:
                cardapio_atual['cardapio_semana_anterior'] = []
                cardapios.append(cardapio_atual)

            #elif cardapio_anterior:
            #    cardapio_atual['cardapio_semana_anterior'] = []
            #    cardapios.append(cardapio_atual)

    if args['tipo_atendimento'] == 'TERCEIRIZADA':
        historicos_cardapios = get_cardapios_terceirizadas(args['tipo_atendimento'],
                                                           args['tipo_unidade'],
                                                           args['agrupamento'],
                                                           args['idade'])

        return render_template("editor_terceirizadas.html",
                               url=api + '/editor/cardapios',
                               cardapios=cardapios,
                               tipo_atendimento=args['tipo_atendimento'],
                               tipo_unidade=args['tipo_unidade'],
                               idade=args['idade'],
                               agrupamento=args['agrupamento'],
                               historicos_cardapios=historicos_cardapios)

    else:
        return render_template("editor_direto_misto_conveniada.html",
                               url=api + '/editor/cardapios',
                               cardapios=jdata,
                               tipo_atendimento=args['tipo_atendimento'],
                               tipo_unidade=args['tipo_unidade'],
                               idade=args['idade'],
                               agrupamento=args['agrupamento'],
                               depara=depara)


@app.route("/visualizador_cardapio", methods=["GET"])
@flask_login.login_required
def visualizador():
    args = request.args
    # Monta json
    jdata = get_cardapio(args)
    jdata = [d for d in jdata if d['tipo_atendimento'] in args['tipo_atendimento']]
    jdata = [d for d in jdata if d['idade'] in args['idade']]
    jdata = [d for d in jdata if d['tipo_unidade'] in args['tipo_unidade']]
    jdata = [d for d in jdata if str(d['agrupamento']) in args['agrupamento']]

    cardapios = []
    for cardapio in jdata:
        dia = datetime.datetime.strptime(str(cardapio['data']), '%Y%m%d').weekday()
        cardapio['dia_semana'] = dia_semana(dia)
        cardapios.append(cardapio)

    return render_template("visualizador_cardapio.html",
                           url=api + '/editor/cardapios',
                           cardapios=jdata,
                           tipo_atendimento=args['tipo_atendimento'],
                           tipo_unidade=args['tipo_unidade'],
                           idade=args['idade'],
                           agrupamento=args['agrupamento'])


@app.route("/calendario_editor_grupo", methods=["POST"])
@flask_login.login_required
def calendario_grupo_cardapio():
    data = request.form.get('json_dump', request.data)

    charset = ['"', '[', ']']
    for char in charset:
        data = data.replace(char, '')
    data = data.split(',')

    # Datas compativeis (Todas as quebras precisam ter as mesmas datas no conjunto)
    lista_data_inicial = []
    lista_data_final = []
    lista_args = []
    for url in data:
        args = dict([tuple(x.split('=')) for x in url.split('?')[1].split('&')])
        lista_data_inicial.append(args['data_inicial'])
        lista_data_final.append(args['data_final'])
        lista_args.append(args)

    if (len(set(lista_data_inicial)) > 1) or (len(set(lista_data_final)) > 1):
        flash("A cópia de cardápios só é permitida para quabras com mesmo periodo")
        return redirect(url_for('backlog'))

    depara = db_functions.select_all()
    depara = [x[3:5] for x in depara if x[2] == 'INGREDIENTES']
    cardapios = []
    for url in data:
        args = dict([tuple(x.split('=')) for x in url.split('?')[1].split('&')])
        jdata = get_cardapio(args)

        # Obtem data semana anterior
        args_semana_anterior = args.copy()
        args_semana_anterior['status'] = 'SALVO&status=PUBLICADO'

        delta_dias = datetime.timedelta(days=7)
        data_final_semana_anterior = datetime.datetime.strptime(str(args['data_final']), '%Y%m%d') - delta_dias
        data_inicial_semana_anterior = datetime.datetime.strptime(str(args['data_inicial']), '%Y%m%d') - delta_dias
        args_semana_anterior['data_final'] = datetime.datetime.strftime(data_final_semana_anterior, '%Y%m%d')
        args_semana_anterior['data_inicial'] = datetime.datetime.strftime(data_inicial_semana_anterior, '%Y%m%d')
        jdata_anterior = get_cardapio(args_semana_anterior)

        jdata_aux = []
        for cardapio_atual in jdata:
            dia = datetime.datetime.strptime(str(cardapio_atual['data']), '%Y%m%d').weekday()
            cardapio_atual['dia_semana'] = dia_semana(dia)
            jdata_aux.append(cardapio_atual)

        jdata_anterior_aux = []
        for cardapio_anterior in jdata_anterior:
            dia = datetime.datetime.strptime(str(cardapio_anterior['data']), '%Y%m%d').weekday()
            cardapio_anterior['dia_semana'] = dia_semana(dia)
            jdata_anterior_aux.append(cardapio_anterior)

        jdata = jdata_aux
        jdata_anterior = jdata_anterior_aux

        # Liga o cardapio atual com o da semana anterior
        dias_da_semana = set([x['dia_semana'] for x in list(jdata + jdata_anterior)])

        for dia in dias_da_semana:
            cardapio_atual = filtro_dicionarios(jdata, 'dia_semana', dia)
            cardapio_anterior = filtro_dicionarios(jdata_anterior, 'dia_semana', dia)

            if cardapio_atual and cardapio_anterior:
                cardapio_atual['cardapio_semana_anterior'] = cardapio_anterior['cardapio']
                cardapios.append(cardapio_atual)

            else:
                if cardapio_atual:
                    cardapio_atual['cardapio_semana_anterior'] = []
                    cardapios.append(cardapio_atual)

    if lista_args[0]['tipo_atendimento'] == 'TERCEIRIZADA':
        historicos_cardapios = get_cardapios_terceirizadas(lista_args[0]['tipo_atendimento'],
                                                           lista_args[0]['tipo_unidade'],
                                                           lista_args[0]['agrupamento'],
                                                           lista_args[0]['idade'])

        return render_template("editor_grupo_terceirizadas.html",
                               url=api + '/editor/cardapios',
                               cardapios=cardapios,
                               args=lista_args,
                               historicos_cardapios=historicos_cardapios)

    else:
        return render_template("editor_grupo_direto_misto_conveniada.html",
                               url=api + '/editor/cardapios',
                               cardapios=cardapios,
                               args=lista_args,
                               depara=depara)


# BLOCO DE CONFIGURAÇÕES
@app.route("/configuracoes_gerais", methods=['GET', 'POST'])
@flask_login.login_required
def config():
    if request.method == "GET":
        config_editor = db_functions.select_all()
        return render_template("configurações.html", config=config_editor)


@app.route('/atualiza_configuracoes', methods=['POST'])
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


@app.route("/configuracoes_cardapio", methods=['GET', 'POST'])
@flask_login.login_required
def config_cardapio():
    if request.method == "GET":
        config_editor = db_functions.select_all_receitas_terceirizadas()
        return render_template("configurações_receitas.html", config=config_editor)


@app.route('/atualiza_receitas', methods=['POST'])
@flask_login.login_required
def atualiza_config_cardapio():
    data = request.form.get('json_dump', request.data)

    db_functions.truncate_receitas_terceirizadas()
    db_functions.add_bulk_cardapio(json.loads(data))

    if request.form:
        return (redirect(url_for('config_cardapio')))
    else:
        return ('', 200)


@app.route('/escolas', methods=['GET'])
@flask_login.login_required
def escolas():
    if request.method == "GET":
        escolas = get_escolas()
        return render_template("configurações_escolas.html", escolas=escolas)


@app.route('/atualiza_historico_escolas', methods=['POST'])
@flask_login.login_required
def atualiza_historico_escolas():
    data = request.form.get('json_dump', request.data)
    jdata = json.loads(data)
    jdata = [dict(t) for t in set([tuple(d.items()) for d in jdata])]
    flag_verificacoes = True
    mensagens = []

    # Vefificações
    if len(set([x['_id'] for x in jdata])) > 1:
        flag_verificacoes = False
        mensagens.append('Código EOL é um número unico e obrigatório por escola.')

    if len(jdata) > 1:
        for row in jdata:
            try:
                data = datetime.datetime.strptime(row['data_inicio_vigencia'], '%Y%m%d')
            except:
                flag_verificacoes = False
                mensagens.append('Data informada invalida ou faltante.')

    for row in jdata:
        if row['tipo_atendimento'] == 'TERCEIRIZADA':
            if row['edital'] == '':
                flag_verificacoes = False
                mensagens.append('Para escolas com o tipo de atendimento TERCEIRIZADA, o campo edital é obrigatório.')

    if flag_verificacoes == False:
        mensagem = '\n'.join(list(set(mensagens)))
        flash(mensagem)
        return redirect(url_for('escolas'))

    # Construção das informações da escola
    else:
        jdata = sorted(jdata, key=itemgetter('data_inicio_vigencia'), reverse=True)
        escola_atual = get_escola(jdata[0]['_id'])
        escola_atual['_id'] = int(jdata[0]['_id'])
        escola_aux = jdata[0]

        try:
            escola_aux['lat'] = float(escola_aux['lat'])
            escola_aux['lon'] = float(escola_aux['lon'])
        except:
            pass

        # Atualiza informacoes atuais da escola
        if escola_aux['tipo_atendimento'] == 'TERCEIRIZADA':
            escola_atual['agrupamento'] = escola_aux['edital']
            _keys = ['nome', 'tipo_unidade', 'endereco', 'bairro', 'lat', 'lon', 'edital', 'data_inicio_vigencia']
            for _key in _keys:
                escola_atual[_key] = escola_aux[_key]
        else:
            _keys = ['nome', 'tipo_unidade', 'agrupamento', 'endereco', 'bairro', 'lat', 'lon', 'edital', 'data_inicio_vigencia']
            for _key in _keys:
                escola_atual[_key] = escola_aux[_key]

        try:
            lista_receitas = [x.strip() for x in escola_aux['refeicoes'].split(',') if x.strip() != '']
        except:
            lista_receitas = []
        escola_atual['refeicoes'] = lista_receitas

        try:
            lista_idades = [x.strip() for x in escola_aux['idades'].split(',') if x.strip() != '']
        except:
            lista_idades = []
        escola_atual['idades'] = lista_idades

        # Constroi histórico
        if len(jdata) == 1:
            escola_atual['historico'] = []
            pass
        else:
            escola_atual['historico'] = []
            for escola in jdata[1:]:
                # Atualiza informacoes atuais da escola
                if escola['tipo_atendimento'] == 'TERCEIRIZADA':
                    escola['agrupamento_regiao'] = escola['agrupamento']
                    escola['agrupamento'] = escola['edital']
                    # escola['idades'] = escola_atual['idades']
                    try:
                        lista_receitas = [x.strip() for x in escola['refeicoes'].split(',') if x.strip() != '']
                    except:
                        lista_receitas = []
                    escola['refeicoes'] = lista_receitas
                    try:
                        lista_idades = [x.strip() for x in escola['idades'].split(',') if x.strip() != '']
                    except:
                        lista_idades = []
                    escola['idades'] = lista_idades
                    try:
                        escola['lat'] = float(escola['lat'])
                        escola['lon'] = float(escola['lon'])
                    except:
                        pass

                else:
                    escola['agrupamento_regiao'] = escola['agrupamento']
                    escola['edital'] = ''
                    # escola['idades'] = escola_atual['edital']
                    try:
                        lista_receitas = [x.strip() for x in escola['refeicoes'].split(',') if x.strip() != '']
                    except:
                        lista_receitas = []
                    escola['refeicoes'] = lista_receitas
                    try:
                        lista_idades = [x.strip() for x in escola['idades'].split(',') if x.strip() != '']
                    except:
                        lista_idades = []
                    escola['idades'] = lista_idades
                    try:
                        escola['lat'] = float(escola['lat'])
                        escola['lon'] = float(escola['lon'])
                    except:
                        pass


                escola_atual['historico'].append(escola)


        headers = {'Content-type': 'application/json'}
        r = requests.post(api + '/editor/escola/{}'.format(str(escola_atual['_id'])),
                          data=json.dumps(escola_atual),
                          headers=headers)

        flash('Informações salvas com sucesso')
        return redirect(url_for('escolas'))


# BLOCO DE DOWNLOAD DAS PUBLICAÇÕES
@app.route("/download_publicacao", methods=["GET", "POST"])
@flask_login.login_required
def publicacao():
    if request.method == "GET":
        return render_template("download_publicações.html", data_inicio_fim='disabled')

    else:
        data_inicial = request.form.get('data-inicial', request.data)
        data_final = request.form.get('data-final', request.data)
        data_inicial = datetime.datetime.strptime(data_inicial, '%d/%m/%Y').strftime('%Y%m%d')
        data_final = datetime.datetime.strptime(data_final, '%d/%m/%Y').strftime('%Y%m%d')
        filtro = request.form.get('filtro', request.data)

        if filtro == 'STATUS':
            return render_template("download_publicações.html",
                                   data_inicio_fim=str(data_inicial + '-' + data_final),
                                   filtro_selected=filtro)

        else:
            cardapio_aux = []
            for cardapio in get_grupo_publicacoes(filtro):
                if (data_inicial <= cardapio[4]) or (data_inicial <= cardapio[5]):
                    if (cardapio[4] <= data_final) or (cardapio[5] <= data_final):
                        url = api + '/editor/cardapios?' + '&' + cardapio[7]
                        r = requests.get(url)
                        refeicoes = r.json()

                        for refeicoes_dia in refeicoes:
                            _keys = ['tipo_atendimento', 'tipo_unidade', 'agrupamento', 'idade', 'data', 'status']
                            refeicao_dia_aux = [refeicoes_dia[_key] for _key in _keys]
                            for refeicao in refeicoes_dia['cardapio'].keys():
                                cardapio_aux.append(
                                    refeicao_dia_aux + [refeicao] + [', '.join(refeicoes_dia['cardapio'][refeicao])])

            return render_template("download_publicações.html", publicados=cardapio_aux,
                                   data_inicio_fim=str(data_inicial + '-' + data_final),
                                   filtro_selected=filtro)


@app.route('/download_csv', methods=['POST'])
@flask_login.login_required
def download_csv():
    data_inicio_fim_str = request.form.get('datas', request.data)
    data_inicial = data_inicio_fim_str.split('-')[0]
    data_final = data_inicio_fim_str.split('-')[1]
    filtro = request.form.get('filtro_selected', request.data)

    if filtro == 'STATUS':
        return render_template("download_publicações.html",
                               data_inicio_fim=str(data_inicial + '-' + data_final))
    else:
        cardapio_aux = []
        for cardapio in get_grupo_publicacoes(filtro):
            if (data_inicial <= cardapio[4]) or (data_inicial <= cardapio[5]):
                if (cardapio[4] <= data_final) or (cardapio[5] <= data_final):
                    url = api + '/editor/cardapios?' + '&' + cardapio[7]
                    r = requests.get(url)
                    refeicoes = r.json()

                    for refeicoes_dia in refeicoes:
                        _keys = ['tipo_atendimento', 'tipo_unidade', 'agrupamento', 'idade', 'data', 'status']
                        refeicao_dia_aux = [refeicoes_dia[_key] for _key in _keys]
                        for refeicao in refeicoes_dia['cardapio'].keys():
                            cardapio_aux.append(
                                refeicao_dia_aux + [refeicao] + [', '.join(refeicoes_dia['cardapio'][refeicao])])

        header = [['ATENDIMENTO', 'UNIDADE', 'AGRUPAMENTO', 'IDADE', 'DATA', 'STATUS', 'REFEICÃO', 'CARDÁPIO']]
        cardapio_aux = header + cardapio_aux
        csvlist = '\n'.join(['"' + str('";"'.join(row)) + '"' for row in cardapio_aux])
        output = make_response(csvlist)
        output.headers["Content-Disposition"] = "attachment; filename=agrupamento_publicações" + str(data_inicio_fim_str) + ".csv"
        output.headers["Content-type"] = "text/csv; charset=utf-8'"

        if request.form:
            return output
        else:
            return ('', 200)


# BLOCO MAPA DE PENDENCIAS
@app.route('/mapa_pendencias', methods=['GET', 'POST'])
@flask_login.login_required
def mapa_pendencias():
    if request.method == "GET":
        mapa = get_quebras_escolas()

        delta_dias = datetime.timedelta(days=7)
        dia_semana_seguinte = datetime.datetime.now() + delta_dias
        semana = [dia_semana_seguinte + datetime.timedelta(days=i) for i in range(0 - dia_semana_seguinte.weekday(), 7 - dia_semana_seguinte.weekday())]
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


# FUNÇÕES AUXILIARES
def data_semana_format(text):
    date = datetime.datetime.strptime(text, "%Y%m%d").isocalendar()
    return str(date[0]) + "-" + str(date[1])


def get_cardapio(args):
    url = api + '/editor/cardapios?' + '&'.join(['%s=%s' % item for item in args.items()])
    r = requests.get(url)
    refeicoes = r.json()

    return refeicoes


def get_pendencias():
    url = api + '/editor/cardapios?status=PENDENTE&status=SALVO'
    r = requests.get(url)
    refeicoes = r.json()

    # Formatar as chaves
    semanas = {}
    for refeicao in refeicoes:
        _key_semana = data_semana_format(refeicao['data'])
        if _key_semana in semanas.keys():
            semanas[_key_semana].append(refeicao['data'])
        else:
            semanas[_key_semana] = [refeicao['data']]

    pendentes = []
    _ids = collections.defaultdict(list)
    for refeicao in refeicoes:
        agrupamento = str(refeicao['agrupamento'])
        tipo_unidade = refeicao['tipo_unidade']
        tipo_atendimento = refeicao['tipo_atendimento']
        status = refeicao['status']
        idade = refeicao['idade']
        _key_semana = data_semana_format(refeicao['data'])
        _key = frozenset([agrupamento, tipo_unidade, tipo_atendimento, status, idade, _key_semana])
        _ids[_key].append(refeicao['_id']['$oid'])
        data_inicial = min(semanas[_key_semana])
        data_final = max(semanas[_key_semana])

        _args = (tipo_atendimento, tipo_unidade, agrupamento, idade, status, data_inicial, data_final)
        query_str = 'tipo_atendimento={}&tipo_unidade={}&agrupamento={}&idade={}&status={}&data_inicial={}&data_final={}'
        href = query_str.format(*_args)

        pendentes.append(
            [tipo_atendimento, tipo_unidade, agrupamento, idade, data_inicial, data_final, status, href, _key_semana])

    pendentes.sort()
    pendentes = list(pendentes for pendentes, _ in itertools.groupby(pendentes))

    for pendente in pendentes:
        _key = frozenset([pendente[2],
                          pendente[1],
                          pendente[0],
                          pendente[6],
                          pendente[3],
                          pendente[8]])
        pendente.append(','.join(_ids[_key]))

    return pendentes


def get_deletados():
    url = api + '/editor/cardapios?status=DELETADO'
    r = requests.get(url)
    refeicoes = r.json()

    # Formatar as chaves
    semanas = {}
    for refeicao in refeicoes:
        _key_semana = data_semana_format(refeicao['data'])
        if _key_semana in semanas.keys():
            semanas[_key_semana].append(refeicao['data'])
        else:
            semanas[_key_semana] = [refeicao['data']]

    pendentes = []
    _ids = collections.defaultdict(list)
    for refeicao in refeicoes:
        agrupamento = str(refeicao['agrupamento'])
        tipo_unidade = refeicao['tipo_unidade']
        tipo_atendimento = refeicao['tipo_atendimento']
        status = refeicao['status']
        idade = refeicao['idade']
        _key_semana = data_semana_format(refeicao['data'])
        _key = frozenset([agrupamento, tipo_unidade, tipo_atendimento, status, idade, _key_semana])
        _ids[_key].append(refeicao['_id']['$oid'])
        data_inicial = min(semanas[_key_semana])
        data_final = max(semanas[_key_semana])

        _args = (tipo_atendimento, tipo_unidade, agrupamento, idade, status, data_inicial, data_final)
        query_str = 'tipo_atendimento={}&tipo_unidade={}&agrupamento={}&idade={}&status={}&data_inicial={}&data_final={}'
        href = query_str.format(*_args)

        pendentes.append(
            [tipo_atendimento, tipo_unidade, agrupamento, idade, data_inicial, data_final, status, href, _key_semana])

    pendentes.sort()
    pendentes = list(pendentes for pendentes, _ in itertools.groupby(pendentes))

    for pendente in pendentes:
        _key = frozenset([pendente[2],
                          pendente[1],
                          pendente[0],
                          pendente[6],
                          pendente[3],
                          pendente[8]])
        pendente.append(','.join(_ids[_key]))

    return pendentes


def get_publicados():
    url = api + '/editor/cardapios?status=PUBLICADO'
    r = requests.get(url)
    refeicoes = r.json()

    # Formatar as chaves
    semanas = {}
    for refeicao in refeicoes:
        _key_semana = data_semana_format(refeicao['data'])
        if _key_semana in semanas.keys():
            semanas[_key_semana].append(refeicao['data'])
        else:
            semanas[_key_semana] = [refeicao['data']]

    pendentes = []
    _ids = collections.defaultdict(list)
    for refeicao in refeicoes:
        agrupamento = str(refeicao['agrupamento'])
        tipo_unidade = refeicao['tipo_unidade']
        tipo_atendimento = refeicao['tipo_atendimento']
        status = refeicao['status']
        idade = refeicao['idade']
        _key_semana = data_semana_format(refeicao['data'])
        _key = frozenset([agrupamento, tipo_unidade, tipo_atendimento, status, idade, _key_semana])
        _ids[_key].append(refeicao['_id']['$oid'])
        data_inicial = min(semanas[_key_semana])
        data_final = max(semanas[_key_semana])

        _args = (tipo_atendimento, tipo_unidade, agrupamento, idade, status, data_inicial, data_final)
        query_str = 'tipo_atendimento={}&tipo_unidade={}&agrupamento={}&idade={}&status={}&data_inicial={}&data_final={}'
        href = query_str.format(*_args)

        pendentes.append(
            [tipo_atendimento, tipo_unidade, agrupamento, idade, data_inicial, data_final, status, href, _key_semana])

    pendentes.sort()
    pendentes = list(pendentes for pendentes, _ in itertools.groupby(pendentes))

    for pendente in pendentes:
        _key = frozenset([pendente[2],
                          pendente[1],
                          pendente[0],
                          pendente[6],
                          pendente[3],
                          pendente[8]])
        pendente.append(','.join(_ids[_key]))

    return pendentes


def get_escolas():
    url = api + '/editor/escolas'
    r = requests.get(url)
    escolas = r.json()

    return escolas


def get_escola(cod_eol):
    url = api + '/escola/{}'.format(cod_eol)
    r = requests.get(url)
    escola = r.json()

    return escola


def get_grupo_publicacoes(status):
    url = api + '/editor/cardapios?status=' + status
    r = requests.get(url)
    refeicoes = r.json()

    # Formatar as chaves
    semanas = {}
    for refeicao in refeicoes:
        _key_semana = data_semana_format(refeicao['data'])
        if _key_semana in semanas.keys():
            semanas[_key_semana].append(refeicao['data'])
        else:
            semanas[_key_semana] = [refeicao['data']]

    pendentes = []
    _ids = collections.defaultdict(list)
    for refeicao in refeicoes:
        agrupamento = str(refeicao['agrupamento'])
        tipo_unidade = refeicao['tipo_unidade']
        tipo_atendimento = refeicao['tipo_atendimento']
        status = refeicao['status']
        idade = refeicao['idade']
        _key_semana = data_semana_format(refeicao['data'])
        _key = frozenset([agrupamento, tipo_unidade, tipo_atendimento, status, idade, _key_semana])
        _ids[_key].append(refeicao['_id']['$oid'])
        data_inicial = min(semanas[_key_semana])
        data_final = max(semanas[_key_semana])

        _args = (tipo_atendimento, tipo_unidade, agrupamento, idade, status, data_inicial, data_final)
        query_str = 'tipo_atendimento={}&tipo_unidade={}&agrupamento={}&idade={}&status={}&data_inicial={}&data_final={}'
        href = query_str.format(*_args)

        pendentes.append(
            [tipo_atendimento, tipo_unidade, agrupamento, idade, data_inicial, data_final, status, href, _key_semana])

    pendentes.sort()
    pendentes = list(pendentes for pendentes, _ in itertools.groupby(pendentes))

    for pendente in pendentes:
        _key = frozenset([pendente[2],
                          pendente[1],
                          pendente[0],
                          pendente[6],
                          pendente[3],
                          pendente[8]])
        pendente.append(','.join(_ids[_key]))

    return pendentes


def get_pendencias_terceirizadas():
    FILE = './tmp/Cardapio_Terceirizadas.txt'
    return cardapios_terceirizadas.create(FILE)


def get_cardapios_iguais():
    url = api + '/editor/cardapios?status=PENDENTE&status=SALVO'
    r = requests.get(url)
    refeicoes = r.json()

    # Formatar as chaves
    semanas = {}
    for refeicao in refeicoes:
        _key_semana = data_semana_format(refeicao['data'])
        if _key_semana in semanas.keys():
            semanas[_key_semana].append(refeicao['data'])
        else:
            semanas[_key_semana] = [refeicao['data']]

    pendentes = []
    ingredientes = {}
    _ids = collections.defaultdict(list)
    for refeicao in refeicoes:
        agrupamento = str(refeicao['agrupamento'])
        tipo_unidade = refeicao['tipo_unidade']
        tipo_atendimento = refeicao['tipo_atendimento']
        status = refeicao['status']
        idade = refeicao['idade']
        _key_semana = data_semana_format(refeicao['data'])

        for alimentos in refeicao['cardapio_original'].keys():
            [agrupamento, tipo_unidade, tipo_atendimento, status, idade, _key_semana]
            _key = frozenset(alimentos)
            _ids[_key].append(refeicao['_id']['$oid'])
            data_inicial = min(semanas[_key_semana])
            data_final = max(semanas[_key_semana])

        _args = (tipo_atendimento, tipo_unidade, agrupamento, idade, status, data_inicial, data_final)
        query_str = 'tipo_atendimento={}&tipo_unidade={}&agrupamento={}&idade={}&status={}&data_inicial={}&data_final={}'
        href = query_str.format(*_args)

        pendentes.append(
            [tipo_atendimento, tipo_unidade, agrupamento, idade, data_inicial, data_final, status, href, _key_semana])

    pendentes.sort()
    pendentes = list(pendentes for pendentes, _ in itertools.groupby(pendentes))

    for pendente in pendentes:
        _key = frozenset([pendente[2],
                          pendente[1],
                          pendente[0],
                          pendente[6],
                          pendente[3],
                          pendente[8]])
        pendente.append(','.join(_ids[_key]))

    return pendentes


def allowed_file(filename):
    ALLOWED_EXTENSIONS = set(['txt', 'XML', 'xml'])
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def dia_semana(dia):
    diasemana = ('Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom')
    return diasemana[dia]


def replace_cardapio(cardapio):
    config_editor = db_functions.select_all()

    for de_para in config_editor:
        cardapio = [de_para[4] if x == de_para[3] else x for x in cardapio]

    cardapio = [x for x in cardapio if x != '']
    return cardapio


def filtro_dicionarios(dictlist, key, valuelist):
    lista_filtrada = [dictio for dictio in dictlist if dictio[key] in valuelist]
    if lista_filtrada:
        return lista_filtrada[0]
    else:
        return None


def get_cardapios_terceirizadas(tipo_gestao, tipo_escola, edital, idade):
    return db_functions.select_receitas_terceirizadas(tipo_gestao, tipo_escola, edital, idade)


def get_quebras_escolas():
    escolas = get_escolas()
    mapa_base = collections.defaultdict(list)
    for escola in escolas:
        agrupamento = str(escola['agrupamento'])
        tipo_unidade = escola['tipo_unidade']
        tipo_atendimento = escola['tipo_atendimento']
        if 'idades' in escola.keys():
            for idade in escola['idades']:
                _key = ', '.join([agrupamento, tipo_unidade, tipo_atendimento, idade])
                mapa_base[_key].append(escola['_id'])
        else:
            pass
            # print(escola)

    mapa = []
    for row in mapa_base:
        mapa.append(row.split(', ') + [len(mapa_base[row])] + [mapa_base[row][0]])

    return mapa


if __name__ == "__main__":
    db_setup.set()
    app.run(debug=True,host='0.0.0.0',port=5001)
