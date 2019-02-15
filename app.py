import collections
import datetime
import json
import os
from operator import itemgetter

import flask_login
import itertools
import requests
from flask import (Flask, flash, redirect, render_template,
                   request, url_for, make_response, Response, send_file, session)
from werkzeug.utils import secure_filename

import cardapio_xml_para_dict
import cardapios_terceirizadas
import db_functions
import db_setup
from utils import (sort_array_date_br, remove_duplicates_array, generate_csv_str,
                   sort_array_by_date_and_index, fix_date_mapa_final)
from helpers import download_spreadsheet

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './tmp'

# BLOCO GET ENDPOINT E KEYS
api = os.environ.get('PRATOABERTO_API')
_user = os.environ.get('PRATO_USER')
_password = os.environ.get('PASSWORD')
app.secret_key = os.environ.get('APPLICATION_KEY')

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


# BLOCO DE QUEBRA CARDÁPIOS
@app.route("/pendencias_publicacoes", methods=["GET", "POST"])
@flask_login.login_required
def backlog():
    if request.method in ["GET", "POST"]:
        pendentes = get_pendencias()
        pendentes = sort_array_date_br(pendentes)
        # aqui tem um array com varios dados e em cada linha tem uma string com varios
        # ids mongo separados por ,
        semanas = remove_duplicates_array([(x[4] + ' - ' + x[5]) for x in pendentes])
        return render_template("pendencias_publicacao.html",
                               pendentes=pendentes,
                               semanas=semanas)


@app.route("/pendencias_deletadas", methods=["GET", "POST"])
@flask_login.login_required
def deletados():
    if request.method == "GET":
        deletados = get_deletados()
        deletados = sort_array_date_br(deletados)
        deletados_unicos = []
        d_9s = []
        for d in deletados:
            if d[:9] not in d_9s:
                d_9s.append(d[:9])
                deletados_unicos.append(d)
        semanas = remove_duplicates_array([(x[4] + ' - ' + x[5]) for x in deletados])
        return render_template("pendencias_deletadas.html",
                               pendentes=deletados_unicos,
                               semanas=semanas)


@app.route("/pendencias_publicadas", methods=["GET", "POST"])
@flask_login.login_required
def publicados():
    if request.method == "GET":
        publicados = get_publicados()
        publicados = sort_array_date_br(publicados)
        semanas = remove_duplicates_array([(x[4] + ' - ' + x[5]) for x in publicados])
        last_month = datetime.datetime.utcnow() - datetime.timedelta(days=30)
        last_three_months = datetime.datetime.utcnow() - datetime.timedelta(days=90)
        last_six_months = datetime.datetime.utcnow() - datetime.timedelta(days=180)
        last_year = datetime.datetime.utcnow() - datetime.timedelta(days=365)
        last_month_dates = []
        last_three_months_dates = []
        last_six_months_dates = []
        last_year_months_dates = []
        all = []
        for semana in semanas:
            if datetime.datetime.strptime(semana.split(' ')[0], '%d/%m/%Y') > last_month:
                last_month_dates.append(semana)
            elif datetime.datetime.strptime(semana.split(' ')[0], '%d/%m/%Y') > last_three_months:
                last_three_months_dates.append(semana)
            elif datetime.datetime.strptime(semana.split(' ')[0], '%d/%m/%Y') > last_six_months:
                last_six_months_dates.append(semana)
            elif datetime.datetime.strptime(semana.split(' ')[0], '%d/%m/%Y') > last_year:
                last_year_months_dates.append(semana)
            else:
                all.append(semana)
        last_three_months_dates += last_month_dates
        last_six_months_dates += last_three_months_dates
        last_year_months_dates += last_six_months_dates
        all += last_year_months_dates
        periodos_para_buscar = {
            'último mês': list(reversed(last_month_dates)),
            'últimos 3 meses': list(reversed(last_three_months_dates)),
            'últimos 6 meses': list(reversed(last_six_months_dates)),
            'últimos 12 meses': list(reversed(last_year_months_dates)),
            'todos': all
        }
        return render_template("pendencias_publicadas.html",
                               pendentes=publicados,
                               semanas=semanas,
                               periodos=periodos_para_buscar)


# BLOCO DE UPLOAD DE XML E CRIAÇÃO DAS TERCEIRIZADAS
@app.route('/upload', methods=['POST'])
@flask_login.login_required
def upload_file():
    if 'file' not in request.files:
        flash('Nenhum arquivo foi selecionado!', 'danger')
        return redirect(url_for('backlog'))

    file = request.files['file']

    if file.filename == '':
        flash('Nenhum arquivo foi selecionado!', 'danger')
        return redirect(url_for('backlog'))

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
                               refeicoes=refeicao,
                               referrer=request.referrer)


@app.route('/upload_terceirizada', methods=['POST'])
@flask_login.login_required
def upload_terceirizadas():
    headers = {'Content-type': 'application/json'}
    data = request.form.get('json_dump', request.data)
    jdata = json.loads(data)
    cardapios = []

    if len(jdata) == 0:
        flash('Nenhum cardápio foi adicionado, adicione as informações e gerar a tabela!', 'danger')
        return redirect(url_for('cria_terceirizada'))

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
    # post de dados no cardapio terceirizada
    r = requests.post(api + '/editor/cardapios', data=json.dumps(cardapios), headers=headers)

    if request.form:
        flash('Cardápio terceirizada salva com sucesso.', 'success')
        return (redirect(url_for('backlog')))
    else:
        return ('', 200)


# BLOCO DE EDIÇÃO DOS CARDÁPIOS
@app.route('/atualiza_cardapio', methods=['POST'])
@flask_login.login_required
def atualiza_cardapio():
    """Colocar o campode ultima modificação aqui..."""
    headers = {'Content-type': 'application/json'}
    data = request.form.get('json_dump', request.data)
    # post de dados nos cardapios atualiza cardapio

    r = requests.post(api + '/editor/cardapios', data=data, headers=headers)

    if request.form:
        flash('Cardápio do XML salvo com sucesso', 'success')
        return (redirect(url_for('backlog')))
    else:
        return ('', 200)


@app.route('/atualiza_cardapio2', methods=['POST'])
@flask_login.login_required
def atualiza_cardapio2():
    """Usado somente para alterar os status dos cardapios"""
    headers = {'Content-type': 'application/json'}
    data = request.form.get('json_dump', request.data)
    # post de dados nos cardapios atualiza cardapio

    r = requests.post(api + '/editor/cardapios', data=data, headers=headers)

    if request.form:
        flash('Status dos cardápios foram atualizados', 'success')
        return ('', 200)
    else:
        return ('', 200)


# comments = []
@app.route("/calendario", methods=["GET"])
@flask_login.login_required
def calendario():
    """
    do pendencias_publicacao vem pra ca quando se clica em href="/calendario?

    """
    # aqui vem algo do tipo 'tipo_atendimento=TERCEIRIZADA&tipo_unidade=CCI&agrupamento=EDITAL 78/2016&idade=D - 0 A 5 MESES&status=PENDENTE&data_inicial=20190114&data_final=20190118'
    args = request.args

    # nao ta vindo nada...
    depara = db_functions.select_all()
    depara = [x[3:5] for x in depara if x[2] == 'INGREDIENTES']

    # Monta json - Semana da requisicao, faz requisição montando uma maluquice total...
    # url = api + '/editor/cardapios?' + '&'.join(['%s=%s' % item for item in args.items()])
    jdata = get_cardapio(args)

    # Obtem data semana anterior
    # copia args
    args_semana_anterior = args.copy()
    args_semana_anterior['status'] = 'SALVO'
    args_semana_anterior.add('status', 'PUBLICADO')  # esse trecho nao faz nada

    delta_dias = datetime.timedelta(days=7)
    data_final_semana_anterior = datetime.datetime.strptime(str(args['data_final']), '%Y%m%d') - delta_dias
    data_inicial_semana_anterior = datetime.datetime.strptime(str(args['data_inicial']), '%Y%m%d') - delta_dias
    # substitui a data final e inicial
    args_semana_anterior['data_final'] = datetime.datetime.strftime(data_final_semana_anterior, '%Y%m%d')
    args_semana_anterior['data_inicial'] = datetime.datetime.strftime(data_inicial_semana_anterior, '%Y%m%d')
    # Monta json - Semana anterior a da requisicao
    # troca os argumentos e pesquisa novamente, dessa vez com a semana anterior...
    jdata_anterior = get_cardapio(args_semana_anterior)

    # o monstrinho acima faz pesquisa de acordo com os parametros e uma pesquisa 7 dias pra tras...
    # jdata é o oficial, jdata anterior é o da semana antetior
    jdata_aux = []
    for cardapio_atual in jdata:
        dia = datetime.datetime.strptime(str(cardapio_atual['data']), '%Y%m%d').weekday()
        cardapio_atual['dia_semana'] = dia_semana(dia)  # troca um int por uma str de dia de semana
        # cardapio atual>
        # {'_id': {'$oid': '5c2de6c354e6257eebc8a2c3'}, 'tipo_unidade': 'CCI', 'tipo_atendimento': 'TERCEIRIZADA', 'data_publicacao': '2019-02-08T17:13:51.100Z', 'data': '20190118', 'idade': 'D - 0 A 5 MESES', 'cardapio': {'J - JANTAR': ['Leite Materno ou Fórmula Láctea Infantil (1º semestre)'], 'D - DESJEJUM': ['Leite Materno ou Fórmula Láctea Infantil (1º semestre)'], 'A - ALMOCO': ['Leite Materno ou Fórmula Láctea Infantil (1º semestre)'], 'L - LANCHE': ['Leite Materno ou Fórmula Láctea Infantil (1º semestre)']}, 'status': 'PENDENTE', 'agrupamento': 'EDITAL 78/2016', 'cardapio_original': {'J - JANTAR': [], 'D - DESJEJUM': [], 'A - ALMOCO': [], 'L - LANCHE': []}, 'dia_semana': 'Sex'}
        jdata_aux.append(cardapio_atual)
    # jdata_aux é um array maluco cheio de dicionarios
    # mesma coisa da maluquice acima, so que para semana anterior...
    jdata_anterior_aux = []
    for cardapio_anterior in jdata_anterior:
        dia = datetime.datetime.strptime(str(cardapio_anterior['data']), '%Y%m%d').weekday()
        cardapio_anterior['dia_semana'] = dia_semana(dia)
        jdata_anterior_aux.append(cardapio_anterior)

    jdata_anterior = jdata_anterior_aux

    # Liga o cardapio atual com o da semana anterior
    dias_da_semana = set([x['dia_semana'] for x in list(jdata + jdata_anterior)])

    cardapios = []
    for dia in dias_da_semana:
        # faz um filtro de doido.
        cardapio_atual = filtro_dicionarios(jdata, 'dia_semana', dia)
        cardapio_anterior = filtro_dicionarios(jdata_anterior, 'dia_semana', dia)

        # se os dois vierem populados o maluco faz alguma coisa
        if cardapio_atual:
            if '/' in cardapio_atual['data']:
                d = datetime.datetime.strptime(cardapio_atual['data'], '%d/%m/%Y')
            else:
                d = datetime.datetime.strptime(cardapio_atual['data'], '%Y%m%d')
            cardapio_atual['data'] = d.strftime('%d/%m/%Y')
        if cardapio_anterior:
            if '/' in cardapio_anterior['data']:
                d = datetime.datetime.strptime(cardapio_anterior['data'], '%d/%m/%Y')
            else:
                d = datetime.datetime.strptime(cardapio_anterior['data'], '%Y%m%d')
            cardapio_anterior['data'] = d.strftime('%d/%m/%Y')
        if cardapio_atual and cardapio_anterior:
            cardapio_atual['cardapio_semana_anterior'] = cardapio_anterior['cardapio']

            cardapios.append(cardapio_atual)


        else:
            if cardapio_atual:
                # faz uma limpa no campo do dicionario, mas por que?
                cardapio_atual['cardapio_semana_anterior'] = []
                cardapios.append(cardapio_atual)

    if args['tipo_atendimento'] == 'TERCEIRIZADA':
        historicos_cardapios = get_cardapios_terceirizadas(args['tipo_atendimento'],
                                                           args['tipo_unidade'],
                                                           args['agrupamento'],
                                                           args['idade'])

        # SE TIPO ATENDIMENTO EH TERCEIRIZADA...
        return render_template("editor_terceirizadas.html",
                               url=api + '/editor/cardapios',
                               cardapios=cardapios,
                               tipo_atendimento=args['tipo_atendimento'],
                               tipo_unidade=args['tipo_unidade'],
                               idade=args['idade'],
                               agrupamento=args['agrupamento'],
                               historicos_cardapios=historicos_cardapios,
                               referrer=request.referrer)
        # QUALQUER OUTRA COISA...
    else:
        return render_template("editor_direto_misto_conveniada.html",
                               url=api + '/editor/cardapios',
                               cardapios=jdata,
                               tipo_atendimento=args['tipo_atendimento'],
                               tipo_unidade=args['tipo_unidade'],
                               idade=args['idade'],
                               agrupamento=args['agrupamento'],
                               depara=depara,
                               referrer=request.referrer)


@app.route("/visualizador_cardapio", methods=["GET"])
@flask_login.login_required
def visualizador():
    args = request.args

    ##### Optimation referrer #####
    if args.get('status') == 'PUBLICADO':
        referrer = '/pendencias_publicadas'
    else:
        referrer = '/pendencias_deletadas'

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
        if '/' in cardapio['data']:
            d = datetime.datetime.strptime(cardapio['data'], '%d/%m/%Y')
        else:
            d = datetime.datetime.strptime(cardapio['data'], '%Y%m%d')
        cardapio['data'] = d.strftime('%d/%m/%Y')
        cardapios.append(cardapio)

    return render_template("visualizador_cardapio.html",
                           url=api + '/editor/cardapios',
                           cardapios=jdata,
                           tipo_atendimento=args['tipo_atendimento'],
                           tipo_unidade=args['tipo_unidade'],
                           idade=args['idade'],
                           agrupamento=args['agrupamento'],
                           referrer=referrer)


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
        flash('A cópia de cardápios só é permitida para quabras com mesmo periodo')
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
        for cardapio in cardapios:
            if '/' in cardapio['data']:
                d = datetime.datetime.strptime(cardapio['data'], '%d/%m/%Y')
            else:
                d = datetime.datetime.strptime(cardapio['data'], '%Y%m%d')
            cardapio['data'] = d.strftime('%d/%m/%Y')

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
        return render_template("configurações.html", config=config_editor, referrer=request.referrer)


@app.route('/atualiza_configuracoes', methods=['POST'])
@flask_login.login_required
def atualiza_configuracoes():
    headers = {'Content-type': 'application/json'}
    data = request.form.get('json_dump', request.data)

    db_functions.truncate_replacements()
    for row in json.loads(data):
        db_functions.add_replacements(row[0], row[1], row[2], row[3])

    if request.form:
        flash('Novo ingrediente adicionado com sucesso', 'success')
        return (redirect(url_for('config')))
    else:
        return ('', 200)


@app.route("/configuracoes_cardapio", methods=['GET', 'POST'])
@flask_login.login_required
def config_cardapio():
    if request.method == "GET":
        config_editor = db_functions.select_all_receitas_terceirizadas()
        return render_template("configurações_receitas.html", config=config_editor, referrer=request.referrer)


@app.route('/atualiza_receitas', methods=['POST'])
@flask_login.login_required
def atualiza_config_cardapio():
    data = request.form.get('json_dump', request.data)

    db_functions.truncate_receitas_terceirizadas()
    db_functions.add_bulk_cardapio(json.loads(data))

    if request.form:
        flash('Cardápio terceirizado adicionado com sucesso.', 'success')
        return (redirect(url_for('config_cardapio')))
    else:
        return ('', 200)


@app.route('/escolas', methods=['GET'])
@flask_login.login_required
def escolas():
    if request.method == "GET":

        if 'refer' in session:
            if '?' not in request.referrer:
                session['refer'] = request.referrer
        else:
            session['refer'] = request.referrer

        escolas, pagination = get_escolas(params=request.args)
        return render_template("configuracoes_escola_v2.html", escolas=escolas,
                               pagination=pagination, referrer=session['refer'])


@app.route('/excluir_escola/<int:id_escola>', methods=['DELETE'])
@flask_login.login_required
def excluir_escola(id_escola):
    headers = {'Content-type': 'application/json'}
    r = requests.delete(api + '/editor/escola/{}'.format(str(id_escola)),
                        headers=headers)

    flash('Escola excluída com sucesso')
    return ('', 200)


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
        if not jdata:
            # caso a lista venha vazia, faz um redirect para tela de escolas
            return redirect(url_for('escolas'))
        escola_atual = get_escola(jdata[0]['_id'])
        escola_atual['_id'] = int(jdata[0]['_id'])
        escola_aux = jdata[0]

        try:
            escola_aux['lat'] = float(escola_aux['lat'])
            escola_aux['lon'] = float(escola_aux['lon'])
        except:
            pass

        escola_atual['status'] = escola_aux.get('status', 'ativo')

        # Atualiza informacoes atuais da escola
        if escola_aux['tipo_atendimento'] == 'TERCEIRIZADA':
            escola_atual['agrupamento'] = escola_aux['edital']
            _keys = ['nome', 'tipo_unidade', 'tipo_atendimento', 'endereco', 'bairro', 'lat', 'lon', 'edital',
                     'data_inicio_vigencia']
            for _key in _keys:
                escola_atual[_key] = escola_aux[_key]
        else:
            _keys = ['nome', 'tipo_unidade', 'tipo_atendimento', 'agrupamento', 'endereco', 'bairro', 'lat', 'lon',
                     'edital',
                     'data_inicio_vigencia']
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
        return redirect('escolas?nome=&tipo_unidade=&limit=100&agrupamento=TODOS&tipo_atendimento=TODOS', code=302)


# BLOCO DE DOWNLOAD DAS PUBLICAÇÕES
@app.route("/download_publicacao", methods=["GET", "POST"])
@flask_login.login_required
def publicacao():
    opt_status = ('STATUS', 'PUBLICADO', 'PENDENTE', 'SALVO', 'DELETADO')

    if request.method == "GET":
        return render_template("download_publicações.html", referrer=request.referrer, data_inicio_fim='disabled',
                               status=opt_status)

    else:
        data_inicial = request.form.get('data-inicial', request.data)
        data_final = request.form.get('data-final', request.data)

        try:
            data_inicial = datetime.datetime.strptime(data_inicial, '%d/%m/%Y').strftime('%Y%m%d')
            data_final = datetime.datetime.strptime(data_final, '%d/%m/%Y').strftime('%Y%m%d')
        except Exception as e:
            print(e)
            flash('Data de inicio ou fim não foram informadas!', 'danger')

        filtro = request.form.get('filtro', request.data)

        tipo_unidade = request.form.get('tipo_unidade', request.data)
        tipo_atendimento = request.form.get('tipo_atendimento', request.data)

        if filtro == 'STATUS' and tipo_unidade == 'TODOS' and tipo_atendimento == 'TODOS':
            return render_template("download_publicações.html",
                                   referrer=request.referrer,
                                   data_inicio_fim=str(data_inicial + '-' + data_final),
                                   filtro_selected=filtro, status=opt_status)

        else:
            cardapio_aux = []
            url = api + '/editor/cardapios?data_inicial={}&data_final={}'.format(data_inicial, data_final)
            # filtro de  tipo de unidade e tipo de atendimento.
            if tipo_unidade != 'TODOS':
                url += '&tipo_unidade={}'.format(tipo_unidade)
            if tipo_atendimento != 'TODOS':
                url += '&tipo_atendimento={}'.format(tipo_atendimento)
            if filtro != 'STATUS':
                url += '&status={}'.format(filtro)
            r = requests.get(url)
            refeicoes = r.json()

            for refeicoes_dia in refeicoes:
                _keys = ['tipo_atendimento', 'tipo_unidade', 'agrupamento', 'idade', 'data', 'status']
                refeicao_dia_aux = [refeicoes_dia[_key] for _key in _keys]
                for refeicao in refeicoes_dia['cardapio'].keys():
                    cardapio_aux.append(
                        refeicao_dia_aux + [refeicao] + [', '.join(refeicoes_dia['cardapio'][refeicao])])
            data_inicial = datetime.datetime.strptime(data_inicial, '%Y%m%d').strftime('%d/%m/%Y')
            data_final = datetime.datetime.strptime(data_final, '%Y%m%d').strftime('%d/%m/%Y')
            return render_template("download_publicações.html", referrer=request.referrer,
                                   publicados=sort_array_by_date_and_index(cardapio_aux),
                                   data_inicio_fim=str(data_inicial + '-' + data_final), tipo_unidade=tipo_unidade,
                                   tipo_atendimento=tipo_atendimento, filtro_selected=filtro,
                                   inicio=data_inicial, fim=data_final, status=opt_status, selected=filtro)


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
            try:
                # transforma as datas em formato br para o formato que ta no bd...
                data_inicial = datetime.datetime.strptime(data_inicial, '%d/%m/%Y').strftime('%Y%m%d')
                data_final = datetime.datetime.strptime(data_final, '%d/%m/%Y').strftime('%Y%m%d')
            except Exception as e:
                pass  # XXX
                # print(data_final, data_inicial)
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

        csvlist = generate_csv_str(cardapio_aux)
        output = make_response(csvlist)
        output.headers["Content-Disposition"] = "attachment; filename=agrupamento_publicacoes" + str(
            data_inicio_fim_str) + ".csv"
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
        semana = [dia_semana_seguinte + datetime.timedelta(days=i) for i in range(0 - dia_semana_seguinte.weekday(),
                                                                                  7 - dia_semana_seguinte.weekday())]
        data_inicial = min(semana).strftime("%Y%m%d")
        data_final = max(semana).strftime("%Y%m%d")

        # Por padrão, sempre colocaremos o cardápio da semana seguinte teste
        mapa_final = []
        for row in mapa:
            args = {'agrupamento': row[0],
                    'tipo_unidade': row[1],
                    'tipo_atendimento': row[2],
                    'idade': row[3].replace('C- 4 A 5 MESES', 'C - 4 A 5 MESES'),
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
        mapa_final = fix_date_mapa_final(mapa_final)
        return render_template("mapa_pendencias.html", publicados=mapa_final,
                               data_inicio_fim=str(data_inicial + '-' + data_final),
                               referrer=request.referrer)

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


@app.route('/remove-cardapio', methods=['DELETE'])
@flask_login.login_required
def remove_menus():
    if request.method == 'DELETE':
        req = request.form['data']
        resp = remover_menus_api(req)

        return Response(resp, 200, mimetype='text/json')


@app.route('/download-planilha', methods=['POST'])
@flask_login.login_required
def download_speadsheet():
    if request.method == 'POST':

        month = request.form['month']
        year = request.form['year']
        xlsx_file = download_spreadsheet.gera_excel(year + month)

        if xlsx_file:
            return send_file(xlsx_file, attachment_filename=xlsx_file.split('/')[-1], as_attachment=True)
        else:
            return redirect(request.referrer)


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
    url = api + '/editor/cardapios?status={}&status={}&status={}&status={}'.format(
        'PENDENTE', 'SALVO', 'A_CONFERIR', 'CONFERIDO')
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
        id_mongo = refeicao['_id']['$oid']

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
            [tipo_atendimento, tipo_unidade, agrupamento, idade, data_inicial, data_final, status, href, _key_semana,
             id_mongo])

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
        # print(pendente)

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
        data_publicacao = refeicao.get('data_publicacao', '')

        _args = (tipo_atendimento, tipo_unidade, agrupamento, idade, status, data_inicial, data_final)
        query_str = 'tipo_atendimento={}&tipo_unidade={}&agrupamento={}&idade={}&status={}&data_inicial={}&data_final={}'
        href = query_str.format(*_args)

        pendentes.append(
            [tipo_atendimento, tipo_unidade, agrupamento, idade, data_inicial,
             data_final, status, href, _key_semana, data_publicacao])

    for pendente in pendentes:
        _key = frozenset([pendente[2],
                          pendente[1],
                          pendente[0],
                          pendente[6],
                          pendente[3],
                          pendente[8]])
        pendente.append(','.join(_ids[_key]))

    pendentes.sort()
    pendentes = list(pendentes for pendentes, _ in itertools.groupby(pendentes))

    return pendentes


def get_escolas(params=None):
    url = api + '/v2/editor/escolas'
    if params:
        extra = "?" + "&".join([("{}={}".format(p[0], p[1])) for p in params.items()])
        url += extra
    r = requests.get(url)
    if 'erro' in r.json():
        return r.json()
    else:
        escolas = r.json()[0]
        pagination = r.json()[1]
        return escolas, pagination


def get_escola(cod_eol):
    url = api + '/escola/{}'.format(cod_eol)
    r = requests.get(url)
    escola = r.json()
    if r.status_code != 200:
        escola = {}

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


def remover_menus_api(params):
    url = api + '/editor/remove-cardapio'
    r = requests.post(url, data={'ids': params})
    return r.text


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
    escolas, paginacao = get_escolas()
    mapa_base = collections.defaultdict(list)
    for escola in escolas:
        try:
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
        except:
            pass

    mapa = []
    for row in mapa_base:
        mapa.append(row.split(', ') + [len(mapa_base[row])] + [mapa_base[row][0]])

    return mapa


def normaliza_str(lista_str):
    """
    Essa funçao serve para normalizar a lista de ingredientes,
    que podem possuir espaço duplo entre palavras, dificultando a
    funcionalidade DE-PARA
    :param lista_str: Lista de strings
    :return: Lista de strings normalizadas, com espaço unico entre palavras
    """
    lf = []
    for palavra in lista_str:
        lf.append(' '.join(palavra.split()))
    return lf


if __name__ == "__main__":
    db_setup.set()
    app.run(host='0.0.0.0', port=5002)
