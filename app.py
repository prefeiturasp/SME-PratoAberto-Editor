import collections
import datetime
import itertools
import json
import os
from operator import itemgetter

import dateutil.parser
import flask_login
import requests
from flask import (Flask, flash, redirect, render_template,
                   request, url_for, make_response, Response, send_file, session)
from werkzeug.utils import secure_filename
from wtforms import (Form, StringField, validators, SelectField, FieldList, FormField,
                     SelectMultipleField, FloatField, IntegerField, TextAreaField)
from wtforms.fields.html5 import DateField
from wtforms.widgets import ListWidget, CheckboxInput

import cardapio_xml_para_dict
import cardapios_terceirizadas
import constants
import db_functions
import db_setup
from helpers import download_spreadsheet
from helpers.gerador_excel_cardapio_ue import GeradorExcelCardapioUE
from ue_mongodb import get_unidade
from utils import (sort_array_date_br, remove_duplicates_array, generate_csv_str,
                   sort_array_by_date_and_index, fix_date_mapa_final, generate_ranges,
                   format_datetime_array, yyyymmdd_to_date_time, convert_datetime_format)
from helpers import download_spreadsheet
from ue_mongodb import get_unidade
from helpers.download_special_unit_menu import gera_excel
from dotenv import load_dotenv

load_dotenv()

sentry_url = os.environ.get('SENTRY_URL')
if sentry_url:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration

    sentry_environment = os.environ.get('SENTRY_ENVIRONMENT')

    sentry_sdk.init(
        dsn=sentry_url,
        environment=sentry_environment,
        integrations=[FlaskIntegration()]
    )

app = Flask(__name__, static_url_path='/editor/static')
app.config['UPLOAD_FOLDER'] = './tmp'

# BLOCO GET ENDPOINT E KEYS
api = os.environ.get('PRATOABERTO_API')
raiz = os.environ.get('RAIZ', 'editor')
# api = 'http://127.0.0.1:8000'
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


@app.route(f'/{raiz}/', methods=['GET', 'POST'])
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


@app.route('/debug-sentry')
def trigger_error():
    division_by_zero = 1 / 0


@app.route(f'/{raiz}/logout')
@flask_login.login_required
def logout():
    flask_login.logout_user()
    return redirect(url_for('login'))


@login_manager.unauthorized_handler
def unauthorized_handler():
    return 'Unauthorized'


# BLOCO DE QUEBRA CARDÁPIOS
@app.route(f"/{raiz}/pendencias_publicacoes", methods=["GET", "POST"])
@flask_login.login_required
def backlog():
    semanas_pendentes = sorted(get_semanas_pendentes(), reverse=True)
    semanas = format_datetime_array(semanas_pendentes)
    unidades_especiais = get_unidades_especiais()
    ue_dict = ['NENHUMA']
    if len(unidades_especiais):
        ue_dict += set(x['nome'] for x in unidades_especiais)
    pendentes = get_pendencias(request_obj=request,
                               semana_default=semanas_pendentes[0] if len(semanas_pendentes) else current_week())
    pendentes = sort_array_date_br(pendentes)
    return render_template("pendencias_publicacao.html",
                           pendentes=pendentes,
                           semanas=semanas,
                           unidades_especiais=ue_dict)


@app.route(f"/{raiz}/pendencias_deletadas", methods=["GET", "POST"])
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


@app.route(f"/{raiz}/pendencias_publicadas", methods=["GET"])
@flask_login.login_required
def publicados():
    weeks = reversed(generate_ranges(10))
    default_week = list(weeks)[0]
    published_menus = sort_array_date_br(get_publicados(request_obj=request, default_week=default_week))
    unidades_especiais = get_unidades_especiais()
    ue_dict = ['NENHUMA']
    if len(unidades_especiais):
        ue_dict += set(x['nome'] for x in unidades_especiais)
    period = request.args.get('filtro_periodo', '365')
    weeks = reversed(generate_ranges(period)) if period == 'all' or int(period) < 0 else generate_ranges(period)
    period_ranges = {
        'próximo ano': '365',
        'próximos 6 meses': '180',
        'próximos 3 meses': '90',
        'próximo mês': '30',
        'último mês': '-30',
        'últimos 3 meses': '-90',
        'últimos 6 meses': '-180',
        'últimos 12 meses': '-365',
        'todos': 'all'
    }

    return render_template("pendencias_publicadas.html",
                           published_menus=published_menus,
                           week_ranges=list(weeks),
                           period_ranges=period_ranges,
                           default_week=default_week,
                           unidades_especiais=ue_dict)


@app.route(f"/{raiz}/pendencias_unidades_especiais", methods=["GET"])
@flask_login.login_required
def cardapios_unidades_especiais():
    semanas_unidades_especiais = sorted(get_semanas_unidades_especiais(), reverse=True)
    semanas = format_datetime_array(semanas_unidades_especiais)
    default_week = semanas[0] if len(semanas) else current_week()
    published_menus = sort_array_date_br(get_cardapios_unidades_especiais(request_obj=request,
                                                                          semana_default=default_week))
    unidades_especiais = get_unidades_especiais()
    ue_dict = ['NENHUMA']
    if len(unidades_especiais):
        ue_dict += set(x['nome'] for x in unidades_especiais)
    return render_template("pendencias_unidades_especiais.html",
                           published_menus=published_menus,
                           week_ranges=semanas,
                           default_week=default_week,
                           unidades_especiais=ue_dict)


@app.route(f"/{raiz}/edicao_de_notas", methods=["GET", "POST"])
@flask_login.login_required
def edicao_de_notas():
    if request.method == 'GET':
        headers = {'Content-type': 'application/json'}
        response = requests.get(api + '/editor/editar_notas', headers=headers)
        notes = response.json()['notas']
    if request.method == "POST":
        data = request.get_data()
        notes = json.loads(data)
        headers = {'Content-type': 'application/json'}
        requests.post(api + '/editor/editar_notas', data=data, headers=headers)
    return render_template("edicao_de_notas.html", notes=notes, referrer=request.referrer)


# BLOCO DE UPLOAD DE XML E CRIAÇÃO DAS TERCEIRIZADAS
@app.route(f'/{raiz}/upload', methods=['POST'])
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


@app.route(f'/{raiz}/upload_terceirizada', methods=['POST'])
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


@app.route(f'/{raiz}/atualiza_cardapio', methods=['POST'])
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


# BLOCO DE EDIÇÃO DOS CARDÁPIOS
@app.route(f'/{raiz}/atualiza_cardapio2', methods=['POST'])
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


@app.route(f"/{raiz}/calendario", methods=["GET"])
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
        if not next((True for item in jdata_aux if item['dia_semana'] == cardapio_atual['dia_semana']), False):
            jdata_aux.append(cardapio_atual)

    jdata = jdata_aux
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


# comments = []
@app.route(f'/{raiz}/cria_terceirizada', methods=['GET'])
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


@app.route(f'/{raiz}/criar-direta-mista-sem-refeicao')
@flask_login.login_required
def cria_direta_mista_sem_refeicao():
    if request.method == "GET":
        quebras = db_functions.select_quebras_terceirizadas()

        editais = set([x[1] for x in quebras])
        tipo_unidade = set([x[0] for x in quebras])
        idade = set([x[2] for x in quebras])
        # refeicao = set([x[3] for x in quebras if 'SR - SEM REFEICAO' in x[3]])
        refeicao = set([x[3] for x in quebras])
        gestoes = set([x[-1] for x in quebras if x[-1] != 'TERCEIRIZADA'])

        return render_template("cria_direta_mista_sem_refeicao.html",
                               editais=editais,
                               tipo_unidade=tipo_unidade,
                               idades=idade,
                               refeicoes=refeicao,
                               gestoes=gestoes,
                               referrer=request.referrer)


@app.route(f'/{raiz}/criar-unidade-especial')
@flask_login.login_required
def cria_unidade_especial():
    if request.method == "GET":
        quebras = db_functions.select_quebras_unidades_especiais()

        ue_dict = [x['nome'] for x in get_unidades_especiais()]

        # editais = set([x[1] for x in quebras if x[1] == 'UE'])
        editais = ['UE']
        tipo_unidade = set(ue_dict)
        idade = set([x[2] for x in quebras])
        # refeicao = set([x[3] for x in quebras if 'SR - SEM REFEICAO' in x[3]])
        refeicao = set([x[3] for x in quebras if 'SR - SEM REFEICAO' not in x[3]])
        gestoes = set([x[-1] for x in quebras if x[-1] == 'UE'])

        return render_template("criar_unidade_especial.html",
                               editais=editais,
                               tipo_unidade=tipo_unidade,
                               idades=idade,
                               refeicoes=refeicao,
                               gestoes=gestoes,
                               referrer=request.referrer)


@app.route(f"/{raiz}/visualizador_cardapio", methods=["GET"])
@flask_login.login_required
def visualizador():
    args = request.args

    ##### Optimation referrer #####
    if args.get('status') == 'PUBLICADO':
        referrer = '/editor/pendencias_publicadas'
    else:
        referrer = '/editor/pendencias_deletadas'

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


@app.route(f"/{raiz}/calendario_editor_grupo", methods=["POST"])
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
@app.route(f"/{raiz}/configuracoes_gerais", methods=['GET', 'POST'])
@flask_login.login_required
def config():
    if request.method == "GET":
        config_editor = db_functions.select_all()
        return render_template("configurações.html", config=config_editor, referrer=request.referrer)


@app.route(f'/{raiz}/atualiza_configuracoes', methods=['POST'])
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


class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


@app.route(f"/{raiz}/configuracoes_cardapio", methods=['GET', 'POST'])
@flask_login.login_required
def config_cardapio():
    referrer = '/editor/pendencias_publicacoes'

    if 'session_referrer' in session:
        if '?' not in request.referrer and 'configuracoes_cardapio' not in request.referrer:
            session['session_referrer'] = request.referrer
            referrer = session['session_referrer']

    if request.method == "GET":
        form = OutSourcedMenuForm(request.form)
        config_editor = db_functions.select_all_receitas_terceirizadas()
        return render_template("configurações_receitas.html", config=config_editor, referrer=referrer, form=form)


@app.route(f"/{raiz}/configuracoes_cardapio_unidades_especiais", methods=['GET', 'POST'])
@flask_login.login_required
def config_cardapio_unidades_especiais():
    referrer = '/editor/pendencias_publicacoes'

    if 'session_referrer' in session:
        if '?' not in request.referrer and 'configuracoes_cardapio_unidades_especiais' not in request.referrer:
            session['session_referrer'] = request.referrer
            referrer = session['session_referrer']

    if request.method == "GET":
        form = OutSourcedMenuForm(request.form)
        form.special_unit.choices = get_unidades_especiais_dict()
        config_editor = db_functions.select_all_receitas_unidades_especiais()
        return render_template("configuracoes_unidades_especiais.html", config=config_editor, referrer=referrer,
                               form=form)


@app.route(f'/{raiz}/remove-lista-terceirizada/<id>')
def remove_menu_list(id):
    removed = db_functions.del_receitas_terceirizadas(id)
    return app.response_class(
        response=json.dumps({'message': 'Cardápio removido com sucesso.', 'id': id}),
        status=200,
        mimetype='application/json'
    )


@app.route(f'/{raiz}/atualiza_receitas', methods=['POST'])
@flask_login.login_required
def atualiza_config_cardapio():
    form = OutSourcedMenuForm(request.form)
    new_menu = list()
    if 'is_unidade_especial' in request.form:
        new_menu.append('UE')
        new_menu.append(form.special_unit.data)
    else:
        new_menu.append(form.management.data)
        new_menu.append(form.school_type.data)

    if 'is_direta_mista' in request.form:
        new_menu.append(request.form['grouping'])
    elif 'is_unidade_especial' not in request.form:
        new_menu.append(form.edital.data)
    else:
        new_menu.append('UE')

    if form.weekday.data:
        new_menu.append(form.weekday.data.strftime('%Y%m%d'))
    else:
        new_menu.append('')

    new_menu.append(form.ages.data)
    new_menu.append(form.meals.data)
    new_menu.append(form.menu.data)
    db_functions.add_bulk_cardapio([new_menu])

    if request.form:
        flash('Cardápio terceirizado adicionado com sucesso.', 'success')
        if 'is_unidade_especial' not in request.form:
            return redirect(url_for('config_cardapio'))
        else:
            return redirect(url_for('config_cardapio_unidades_especiais'))
    else:
        return '', 200


class EditalForm(Form):
    edital = StringField('edital')
    escola = IntegerField('escola')
    data_inicio = DateField('data_inicio')
    data_fim = DateField('data_fim')
    tipo_atendimento = StringField('tipo_atendimento')


class SchoolRegistrationForm(Form):
    cod_eol = IntegerField('Código EOL', [validators.required()])
    school_type = SelectField('Tipo de Escola', choices=constants.SCHOOL_TYPES_DICT)
    grouping = SelectField('Agrupamento', choices=constants.GROUPING_DICT)
    edital = SelectField('Edital', choices=constants.GROUPING_DICT)
    edital_data_inicio = DateField('Data início', [validators.required()])
    edital_data_fim = DateField('Data fim', [validators.optional()])
    edital_tipo_atendimento = SelectField('Gestão', choices=constants.MANAGEMENT_DICT)
    edital_2 = SelectField('Edital', choices=constants.GROUPING_DICT)
    edital_data_inicio_2 = DateField('Data início', [validators.optional()])
    edital_data_fim_2 = DateField('Data fim', [validators.optional()])
    edital_tipo_atendimento_2 = SelectField('Gestão', choices=constants.MANAGEMENT_DICT)
    school_name = StringField('Nome da Escola', [validators.required()])
    address = StringField('Endereço', [validators.required()])
    neighbourhood = StringField('Bairro', [validators.required()])
    latitude = FloatField('Latitude', [validators.optional()])
    longitude = FloatField('Longitude', [validators.optional()])
    meals = MultiCheckboxField('Refeições', choices=constants.MEALS_DICT)
    ages = MultiCheckboxField('Idades', choices=constants.AGES_DICT)


@app.route(f'/{raiz}/autocomplete', methods=['GET'])
def autocomplete():
    schools, _ = get_escolas(limit='4000')
    schools_array = []
    for s in schools:
        schools_array.append(str(s['_id']) + ' - ' + s['nome'])
    return Response(json.dumps(schools_array), mimetype='application/json')


@app.route(f'/{raiz}/unidades_especiais/<id_unidade_especial>', methods=['GET', 'POST'])
@app.route(f'/{raiz}/unidades_especiais', methods=['GET', 'POST'])
@flask_login.login_required
def unidades_especiais(id_unidade_especial=None):
    form = SpecialUnitForm(request.form)
    form_filter = FilterTypeSchoolForm(request.form)
    by_type = form_filter.school_types.data
    if id_unidade_especial:
        special_unit = get_unidade(id_unidade_especial)
        form.identifier.data = id_unidade_especial
        form.special_unit.data = special_unit[0]
        form.creation_date.data = yyyymmdd_to_date_time(special_unit[1])
        form.initial_date.data = yyyymmdd_to_date_time(special_unit[2])
        form.end_date.data = yyyymmdd_to_date_time(special_unit[3])
        form.schools.data = special_unit[4]
    if by_type:
        form.schools.data += get_escolas_dict(params=request.args, by_type=by_type, limit='4000') + \
                             [cod_eol.split(' - ')[0].strip() for cod_eol in
                              form_filter.school_autocomplete.data.split(', ')]
    else:
        form.schools.data += [cod_eol.split(' - ')[0].strip() for cod_eol
                              in form_filter.school_autocomplete.data.split(', ')]
    if request.method in ["GET", "POST"]:
        if 'refer' in session:
            if request.referrer and '?' not in request.referrer:
                session['refer'] = request.referrer
        else:
            session['refer'] = request.referrer
        escolas, pagination = get_escolas(params=request.args)
    return render_template("unidades_especiais.html", form_filter=form_filter,
                           referrer=session['refer'], form=form, special_units=get_unidades_especiais())


@app.route(f'/{raiz}/adicionar_unidade_especial', methods=['POST'])
@flask_login.login_required
def adicionar_unidade_especial():
    form = SpecialUnitForm(request.form)
    new_special_unit = dict()
    new_special_unit['_id'] = form.identifier.data
    new_special_unit['nome'] = form.special_unit.data
    if not form.identifier.data:
        new_special_unit['data_criacao'] = datetime.datetime.utcnow().strftime('%Y%m%d')
    new_special_unit['data_inicio'] = form.initial_date.data.strftime('%Y%m%d')
    new_special_unit['data_fim'] = form.end_date.data.strftime('%Y%m%d')
    new_special_unit['escolas'] = form.schools.data
    headers = {'Content-type': 'application/json'}
    r = requests.post(f'{api}/editor/unidade_especial/{str(new_special_unit["_id"])}',
                      data=json.dumps(new_special_unit),
                      headers=headers)
    if '200' in str(r):
        flash('Informações salvas com sucesso')
    else:
        flash('Ocorreu um erro ao salvar as informações')
    return redirect('/editor/unidades_especiais', code=302)


@app.route(f'/{raiz}/excluir_unidade_especial/<string:id_unidade_especial>', methods=['DELETE'])
@flask_login.login_required
def excluir_unidade_especial(id_unidade_especial):
    headers = {'Content-type': 'application/json'}
    requests.delete(api + '/editor/unidade_especial/{}'.format(str(id_unidade_especial), headers=headers))
    flash('Escola excluída com sucesso')
    return ('', 200)


@app.route(f'/{raiz}/escolas/<int:id_escola>', methods=['GET', 'POST'])
@app.route(f'/{raiz}/escolas', methods=['GET', 'POST'])
@flask_login.login_required
def escolas(id_escola=None):
    form = SchoolRegistrationForm(request.form)
    if id_escola:
        school = get_escola(id_escola, raw=True)
        form.cod_eol.data = id_escola
        form.school_name.data = school['nome'].upper()
        form.school_type.data = school['tipo_unidade']
        form.grouping.data = school['agrupamento']
        if len(school['editais']) > 0:
            form.edital.data = school['editais'][0]['edital']
            form.edital_data_inicio.data = datetime.datetime.strptime(
                school['editais'][0]['data_inicio'], '%Y%m%d').date()
            form.edital_tipo_atendimento.data = school['editais'][0]['tipo_atendimento']
            if school['editais'][0]['data_fim']:
                form.edital_data_fim.data = datetime.datetime.strptime(
                    school['editais'][0]['data_fim'], '%Y%m%d').date()
        if len(school['editais']) > 1:
            form.edital_2.data = school['editais'][1]['edital']
            form.edital_data_inicio_2.data = datetime.datetime.strptime(
                school['editais'][1]['data_inicio'], '%Y%m%d').date()
            form.edital_tipo_atendimento_2.data = school['editais'][1]['tipo_atendimento']
            if school['editais'][1]['data_fim']:
                form.edital_data_fim_2.data = datetime.datetime.strptime(
                    school['editais'][1]['data_fim'], '%Y%m%d').date()
        form.address.data = school['endereco'].upper()
        form.neighbourhood.data = school['bairro'].upper()
        form.latitude.data = school['lat'] if school['lat'] not in [None, ''] else ''
        form.longitude.data = school['lon'] if school['lon'] not in [None, ''] else ''
        form.ages.data = school['idades']

        # Colocando as choices na ordem que foi escolhido a alimentação
        choices = form.meals.choices
        for ind, r in enumerate(school['refeicoes']):
            try:
                ind_c = [i for i, ch in enumerate(choices) if ch[0] == r][0]
                aux = choices[ind]
                choices[ind] = choices[ind_c]
                choices[ind_c] = aux
            except IndexError as e:
                pass

        form.meals.choices = choices
        form.meals.data = school['refeicoes']

    if request.method == "GET":
        if 'refer' in session:
            if request.referrer and '?' not in request.referrer:
                session['refer'] = request.referrer
        else:
            session['refer'] = request.referrer
        escolas, pagination = get_escolas(params=request.args)
        escolas_ids = ','.join([str(escola['_id']) for escola in escolas])
        try:
            editais = sorted(get_editais(escolas_ids), key=lambda e: e['escola'])
        except KeyError:
            editais = []
    return render_template("configuracoes_escola_v2.html", escolas=escolas, editais=editais,
                           pagination=pagination, referrer=session['refer'], form=form)


@app.route(f'/{raiz}/adicionar_escola', methods=['POST'])
@flask_login.login_required
def adicionar_escola():
    form = SchoolRegistrationForm(request.form)
    if not form.validate():
        flash('Ocorreu um erro ao salvar as informações')
        return redirect('editor/escolas?nome=&tipo_unidade=&limit=100&agrupamento=TODOS&tipo_atendimento=TODOS', code=302)
    new_school = dict()
    new_school['_id'] = form.cod_eol.data
    new_school['nome'] = form.school_name.data.upper()
    new_school['tipo_unidade'] = form.school_type.data
    new_school['agrupamento'] = form.grouping.data
    new_school['endereco'] = form.address.data.upper()
    new_school['bairro'] = form.neighbourhood.data.upper()
    new_school['lat'] = form.latitude.data if form.latitude.data is not None else ''
    new_school['lon'] = form.longitude.data if form.longitude.data is not None else ''
    new_school['telefone'] = ' '
    if form.edital.data and form.edital_data_inicio.data:
        edital_1 = {'edital': form.edital.data,
                    'escola': int(form.cod_eol.data),
                    'data_inicio': str(form.edital_data_inicio.data).replace('-', ''),
                    'data_fim': str(form.edital_data_fim.data).replace('-', '') if form.edital_data_fim.data else None,
                    'tipo_atendimento': form.edital_tipo_atendimento.data}
        new_school['edital_1'] = edital_1
    if form.edital_2.data and form.edital_data_inicio_2.data:
        edital_2 = {'edital': form.edital_2.data,
                    'escola': int(form.cod_eol.data),
                    'data_inicio': str(form.edital_data_inicio_2.data).replace('-', ''),
                    'data_fim': str(form.edital_data_fim_2.data).replace('-', '') if form.edital_data_fim_2.data else None,
                    'tipo_atendimento': form.edital_tipo_atendimento_2.data}
        new_school['edital_2'] = edital_2
    new_school['idades'] = form.ages.data
    new_school['refeicoes'] = form.meals.data
    new_school['data_inicio_vigencia'] = ''
    new_school['historico'] = []
    new_school['status'] = 'ativo'

    headers = {'Content-type': 'application/json'}
    r = requests.post(api + '/editor/escola/{}'.format(str(new_school['_id'])),
                      data=json.dumps(new_school),
                      headers=headers)
    if '200' in str(r):
        flash('Informações salvas com sucesso')
    else:
        flash('Ocorreu um erro ao salvar as informações')
    return redirect('editor/escolas?nome=&tipo_unidade=&limit=100&agrupamento=TODOS&tipo_atendimento=TODOS', code=302)


@app.route(f'/{raiz}/excluir_escola/<int:id_escola>', methods=['DELETE'])
@flask_login.login_required
def excluir_escola(id_escola):
    headers = {'Content-type': 'application/json'}
    r = requests.delete(api + '/editor/escola/{}'.format(str(id_escola)),
                        headers=headers)

    flash('Escola excluída com sucesso')
    return ('', 200)


@app.route(f'/{raiz}/atualiza_historico_escolas', methods=['POST'])
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
@app.route(f"/{raiz}/download_publicacao", methods=["GET", "POST"])
@flask_login.login_required
def publicacao():
    opt_status = ('STATUS', 'PUBLICADO', 'PENDENTE', 'SALVO', 'DELETADO')

    if 'refer' in session:
        if '/download_publicacao' not in request.referrer:
            session['refer'] = request.referrer
    else:
        session['refer'] = request.referrer

    if request.method == "GET":
        return render_template("download_publicações.html", referrer=session['refer'], data_inicio_fim='disabled',
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
                                   referrer=session['refer'],
                                   data_inicio_fim=str(data_inicial + '-' + data_final),
                                   filtro_selected=filtro, status=opt_status)

        else:
            params_dict = {
                'data_inicial': data_inicial,
                'data_final': data_final,
                'tipo_unidade': tipo_unidade,
                'tipo_atendimento': tipo_atendimento,
                'filtro': filtro
            }
            cardapio_aux = filtrar_cardapios(params_dict)
            data_inicial = datetime.datetime.strptime(data_inicial, '%Y%m%d').strftime('%d/%m/%Y')
            data_final = datetime.datetime.strptime(data_final, '%Y%m%d').strftime('%d/%m/%Y')
            return render_template("download_publicações.html", referrer=session['refer'],
                                   publicados=sort_array_by_date_and_index(cardapio_aux),
                                   data_inicio_fim=str(data_inicial + '-' + data_final), tipo_unidade=tipo_unidade,
                                   tipo_atendimento=tipo_atendimento, filtro_selected=filtro,
                                   inicio=data_inicial, fim=data_final, status=opt_status, selected=filtro)


@app.route(f'/{raiz}/download_csv', methods=['POST'])
@flask_login.login_required
def download_csv():
    data_inicio_fim_str = request.form.get('datas', request.data)
    data_inicial = convert_datetime_format(data_inicio_fim_str.split('-')[0], '%d/%m/%Y', '%Y%m%d')
    data_final = convert_datetime_format(data_inicio_fim_str.split('-')[1], '%d/%m/%Y', '%Y%m%d')
    filtro = request.form.get('filtro_selected', request.data)
    tipo_unidade = request.form.get('tipo_unidade_download', request.data)
    tipo_atendimento = request.form.get('tipo_atendimento_download', request.data)

    if filtro == 'STATUS':
        return render_template("download_publicações.html",
                               data_inicio_fim=str(data_inicial + '-' + data_final))
    else:
        params_dict = {
            'data_inicial': data_inicial,
            'data_final': data_final,
            'tipo_unidade': tipo_unidade,
            'tipo_atendimento': tipo_atendimento,
            'filtro': filtro
        }
        cardapio_aux = filtrar_cardapios(params_dict)
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
@app.route(f'/{raiz}/mapa_pendencias', methods=['GET', 'POST'])
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


@app.route(f'/{raiz}/remove-cardapio', methods=['DELETE'])
@flask_login.login_required
def remove_menus():
    if request.method == 'DELETE':
        req = request.form['data']
        resp = remover_menus_api(req)

        return Response(resp, 200, mimetype='text/json')


@app.route(f'/{raiz}/download-planilha', methods=['POST'])
@flask_login.login_required
def download_speadsheet():
    if request.method == 'POST':
        _from = request.form['from'].replace('-', '')
        _to = request.form['to'].replace('-', '')
        management = request.form['management']
        type_school = request.form['type_school']
        xlsx_file = download_spreadsheet.gera_excel(_from + ',' + _to + ',' + management + ',' + type_school)

        if xlsx_file:

            return send_file(str(xlsx_file), attachment_filename=str(xlsx_file).split('/')[-1], as_attachment=True)
        else:
            return redirect(request.referrer)


@app.route(f'/{raiz}/download-unidade-especial', methods=['POST'])
@flask_login.login_required
def dowload_special_unit():
    if request.method == 'POST':
        try:
            ue_id = request.form['unit_special']

            xlsx_file = GeradorExcelCardapioUE(ue_id).produzir_excel()
            if xlsx_file:
                return send_file(xlsx_file, attachment_filename=xlsx_file.split('/')[-1], as_attachment=True)
            else:
                flash('Nenhum cardápio encontrado!', 'danger')
                return redirect(request.referrer)
        except UnicodeEncodeError('Erro no unicode do arquivo!'):
            flash('Error no unicode do arquivo!', 'danger')
            return redirect(request.referrer)
        except IOError('Error ao tentar escrever no arquivo!'):
            flash('Error ao tentar escrever no arquivo!', 'danger')
            return redirect(request.referrer)


@app.context_processor
def get_all_special_unit():
    ue_dict = []
    for ue in get_unidades_especiais():
        try:
            ue_item = {'id': ue['_id']['$oid'],
                       'label': ue['nome'],
                       'range': convert_datetime_format(ue['data_inicio'], '%Y%m%d', '%d/%m/%Y') +
                       ' - ' + convert_datetime_format(ue['data_fim'], '%Y%m%d', '%d/%m/%Y')}
            ue_dict.append(ue_item)
        except TypeError:
            pass
    return dict(ue_dict=ue_dict)


# FUNÇÕES AUXILIARES
def filtrar_cardapios(params_dict):
    cardapio_aux = []
    url = api + '/editor/cardapios?data_inicial={}&data_final={}'.format(params_dict['data_inicial'], params_dict['data_final'])
    # filtro de  tipo de unidade e tipo de atendimento.
    if params_dict['tipo_unidade'] != 'TODOS':
        url += '&tipo_unidade={}'.format(params_dict['tipo_unidade'])
    if params_dict['tipo_atendimento'] != 'TODOS':
        url += '&tipo_atendimento={}'.format(params_dict['tipo_atendimento'])
    if params_dict['filtro'] != 'STATUS':
        url += '&status={}'.format(params_dict['filtro'])

    r = requests.get(url)
    refeicoes = r.json()

    for refeicoes_dia in refeicoes:
        _keys = ['tipo_atendimento', 'tipo_unidade', 'agrupamento', 'idade', 'data', 'status']
        refeicao_dia_aux = [refeicoes_dia[_key] for _key in _keys]
        for refeicao in refeicoes_dia['cardapio'].keys():
            cardapio_aux.append(
                refeicao_dia_aux + [refeicao] + [', '.join(refeicoes_dia['cardapio'][refeicao])])
    return cardapio_aux


def data_semana_format(text):
    date = datetime.datetime.strptime(text, "%Y%m%d").isocalendar()
    return str(date[0]) + "-" + str(date[1])


def get_cardapio(args):
    url = api + '/editor/cardapios?' + '&'.join(['%s=%s' % item for item in args.items()])
    r = requests.get(url)
    refeicoes = r.json()

    return refeicoes


def get_cardapio_unidade_especial_by_api(unidade, inicio, fim):
    url = api + '/editor/cardapios-unidade-especial/?unidade={}&inicio={}&fim={}'.format(unidade, inicio, fim)
    r = requests.get(url)

    return r.json()


def get_pendencias(request_obj, semana_default=None):
    params = request_obj.query_string.decode('utf-8')
    if 'filtro_semana' in params:
        week_filter = request_obj.args.get('filtro_semana')
        initial_date = datetime.datetime.strptime(week_filter.split(' - ')[0], '%d/%m/%Y').strftime('%Y%m%d')
        end_date = datetime.datetime.strptime(week_filter.split(' - ')[1], '%d/%m/%Y').strftime('%Y%m%d')
        dates_str = '&data_inicial=' + initial_date + '&data_final=' + end_date
        params += dates_str
    else:
        params += '&data_inicial=' + semana_default.split(' - ')[0] + '&data_final=' + semana_default.split(' - ')[1]
    if 'status' not in params:
        params += '&status=PENDENTE&status=SALVO&status=A_CONFERIR&status=CONFERIDO'
    elif 'status=TODOS' in params:
        params = params.replace('status=TODOS', 'status=PENDENTE&status=SALVO&status=A_CONFERIR&status=CONFERIDO')
    url = api + '/editor/cardapios?' + params
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


def get_semanas_pendentes():
    url = api + '/editor/cardapios?status=PENDENTE&status=SALVO&status=A_CONFERIR&status=CONFERIDO'
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

    return [min(s) + ' - ' + max(s) for s in semanas.values()]


def get_semanas_unidades_especiais():
    url = api + '/editor/cardapios?status=PENDENTE&status=SALVO&status=A_CONFERIR&status=CONFERIDO&status=PUBLICADO' + \
          '&agrupamento=UE'
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

    return [min(s) + ' - ' + max(s) for s in semanas.values()]


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


def get_publicados(request_obj, default_week):
    params = request_obj.query_string.decode('utf-8')

    if 'filtro_semana_mes' in params:
        week_filter = request_obj.args.get('filtro_semana_mes')
    else:
        week_filter = default_week
    initial_date = datetime.datetime.strptime(week_filter.split(' - ')[0], '%d/%m/%Y').strftime('%Y%m%d')
    end_date = datetime.datetime.strptime(week_filter.split(' - ')[1], '%d/%m/%Y').strftime('%Y%m%d')
    params += '&data_inicial=' + initial_date + '&data_final=' + end_date
    url = api + '/editor/cardapios?status=PUBLICADO&' + params
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
        data_publicacao = _set_datetime(refeicao.get('data_publicacao', ''))

        _args = (tipo_atendimento, tipo_unidade, agrupamento, idade, status, data_inicial, data_final)
        query_str = 'tipo_atendimento={}&tipo_unidade={}&agrupamento={}&idade={}&status={}&data_inicial={}&data_final={}'
        href = query_str.format(*_args)

        values_list = [tipo_atendimento, tipo_unidade, agrupamento, idade, data_inicial,
                       data_final, status, href, _key_semana, data_publicacao]

        pendentes.append(values_list)

    for pendente in pendentes:
        _key = frozenset([pendente[2],
                          pendente[1],
                          pendente[0],
                          pendente[6],
                          pendente[3],
                          pendente[8]])
        ids = ','.join(_ids[_key])

        pendente.append(ids)

    pendentes.sort()
    pendentes = list(pendentes for pendentes, _ in itertools.groupby(pendentes))
    return pendentes


def get_cardapios_unidades_especiais(request_obj, semana_default=None):
    params = request_obj.query_string.decode('utf-8')
    if 'filtro_semana' in params:
        week_filter = request_obj.args.get('filtro_semana')
        initial_date = datetime.datetime.strptime(week_filter.split(' - ')[0], '%d/%m/%Y').strftime('%Y%m%d')
        end_date = datetime.datetime.strptime(week_filter.split(' - ')[1], '%d/%m/%Y').strftime('%Y%m%d')
        dates_str = '&data_inicial=' + initial_date + '&data_final=' + end_date
        params += dates_str
    else:
        params += '&data_inicial=' + semana_default.split(' - ')[0] + '&data_final=' + semana_default.split(' - ')[1]
    if 'status' not in params:
        params += '&status=PENDENTE&status=SALVO&status=A_CONFERIR&status=CONFERIDO&status=PUBLICADO'
    elif 'status=TODOS' in params:
        params = params.replace('status=TODOS',
                                'status=PENDENTE&status=SALVO&status=A_CONFERIR&status=CONFERIDO&status=PUBLICADO')
    url = api + '/editor/cardapios-unidades-especiais?' + params
    r = requests.get(url)
    refeicoes = r.json()

    unidades_especiais = get_unidades_especiais()

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
        escolas = []
        params_escola = {'limit': 4000}
        agrupamento = request.args.get('agrupamento', None)
        if agrupamento and agrupamento != 'TODOS':
            params_escola.update({'agrupamento': agrupamento})
        tipo_atendimento = request.args.get('tipo_atendimento', None)
        if tipo_atendimento and tipo_atendimento != 'TODOS':
            params_escola.update({'tipo_atendimento': tipo_atendimento})
        tipo_unidade = request.args.get('tipo_unidade', None)
        if tipo_unidade and tipo_unidade != 'TODOS':
            params_escola.update({'tipo_unidade': tipo_unidade})
        for unidade_especial in unidades_especiais:
            if refeicao['tipo_unidade'] == unidade_especial['nome']:
                escolas_api = get_escolas(params_escola)[0]
                ids = [_id['_id'] for _id in escolas_api]
                escolas = ', '.join(escola for escola in unidade_especial['escolas'] if int(escola) in ids)
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
            # [tipo_atendimento, tipo_unidade, agrupamento, idade, data_inicial, data_final, status, href, _key_semana])
            [tipo_unidade, escolas, '', idade, data_inicial, data_final, status, href, _key_semana])

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


def _set_datetime(str_date):
    try:
        ndate = dateutil.parser.parse(str_date)
        return ndate.strftime('%d/%m/%Y - %H:%M:%S')
    except Exception as e:
        pass


def get_escolas(params=None, limit=None):
    url = api + '/v2/editor/escolas'
    if params:
        extra = "?" + "&".join([("{}={}".format(p[0], p[1])) for p in params.items()])
        url += extra
    if limit:
        if '?' in url:
            url += '&limit=' + limit
        else:
            url += '?limit=' + limit
    r = requests.get(url)
    if 'erro' in r.json():
        return r.json()
    else:
        escolas = r.json()[0]
        pagination = r.json()[1]
        return escolas, pagination


def get_escola(cod_eol, raw=False):
    url = api + '/escola/{}?raw={}'.format(cod_eol, raw)
    r = requests.get(url)
    escola = r.json()
    if r.status_code != 200:
        escola = {}

    return escola


def get_editais(ids_escolas=None):
    url = api + '/editor/escolas_editais'
    if ids_escolas:
        url += f'/{ids_escolas}'
    r = requests.get(url)
    editais = r.json()
    if r.status_code != 200:
        editais = {}
    return editais


def get_escolas_dict(params=None, by_type=None, limit=None):
    schools, _ = get_escolas(params=params, limit=limit)
    schools_dict = []
    if by_type and len(by_type):
        if 'TODOS' in by_type:
            for s in schools:
                schools_dict.append(str(s['_id']))
            return schools_dict
        elif 'NENHUMA' in by_type:
            return schools_dict
        else:
            for s in schools:
                if s['tipo_unidade'] in by_type:
                    schools_dict.append(str(s['_id']))
            return schools_dict
    else:
        for s in schools:
            schools_dict.append((str(s['_id']), str(s['_id']) + ' - ' + s['nome']))
        return schools_dict


def get_unidades_especiais():
    url = api + '/editor/unidades_especiais'
    r = requests.get(url)
    return r.json()


def get_unidades_especiais_by_id(id):
    url = api + '/editor/unidades_especiais/' + id
    r = requests.get(url)
    return r.json()


def get_unidades_especiais_dict():
    url = api + '/editor/unidades_especiais'
    r = requests.get(url)
    special_unities = r.json()
    special_unities_dict = []
    for special_unit in special_unities:
        special_unities_dict.append((special_unit['nome'], special_unit['nome']))
    return special_unities_dict


def get_grupo_publicacoes(status, data_inicial, data_final):
    url = api + '/editor/cardapios?status=' + status + '&data_inicial=' + data_inicial + '&data_final=' + data_final
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


def current_week():
    d = datetime.datetime.utcnow()
    days_gap = 4 - d.weekday()
    return (d - datetime.timedelta(days=d.weekday())).strftime('%Y%m%d') + ' - ' + (
            d + datetime.timedelta(days=days_gap)).strftime('%Y%m%d')


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


class OutSourcedMenuForm(Form):
    menu_id = IntegerField('ID')
    management = SelectField('Gestão', choices=[('TERCEIRIZADA', 'TERCEIRIZADA')])
    school_type = SelectField('Tipo de Escola', choices=constants.SCHOOL_TYPES_DICT)
    special_unit = SelectField('Unidade Especial', choices=get_unidades_especiais_dict())
    edital = SelectField('Edital', choices=[
        ('EDITAL 78/2016', 'EDITAL 78/2016'),
        ('Novo Edital', 'Novo Edital'),
        ('Edital 2024', 'Edital 2024')
    ])
    weekday = DateField('Dia Semana', format='%Y%m%d')
    ages = SelectField('Idades', choices=constants.AGES_DICT)
    meals = SelectField('Refeições', choices=constants.MEALS_DICT)
    menu = TextAreaField('Cardápio')
    grouping = SelectField('Agrupamento', choices=constants.GROUPING_DICT)


class SpecialUnitForm(Form):
    identifier = StringField('Identificador')
    special_unit = StringField('Unidade Especial')
    creation_date = DateField('Data Criacao', format='%Y-%m-%d')
    initial_date = DateField('Data Inicial', format='%Y-%m-%d')
    end_date = DateField('Data Final', format='%Y-%m-%d')
    schools = MultiCheckboxField('Escolas', choices=get_escolas_dict(limit='4000'))


class FilterTypeSchoolForm(Form):
    school_types = MultiCheckboxField('Incluir por tipo de escola', choices=constants.SCHOOL_TYPES_FILTER_DICT)
    school_autocomplete = TextAreaField('Incluir uma escola', id='autocomplete_school')


if __name__ == "__main__":
    db_setup.set()
    app.run()
