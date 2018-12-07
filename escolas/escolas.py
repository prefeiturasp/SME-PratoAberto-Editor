# -*- coding: utf-8 -*-

import flask_login
import requests
import json
import datetime
import collections
import configparser

from operator import itemgetter
from flask import flash, redirect, render_template, request, url_for, Blueprint

escolas_app = Blueprint('escolas_app', __name__)
config = configparser.ConfigParser()
config.read('config/integracao.conf')
api = config.get('ENDPOINTS', 'PRATOABERTO_API')

@escolas_app.route('/escolas', methods=['GET'])
@flask_login.login_required
def escolas():

    if request.method == "GET":

        escolas = get_escolas()

        return render_template("configurações_escolas.html", escolas=escolas)

@escolas_app.route('/atualiza_historico_escolas', methods=['POST'])
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
        return redirect(url_for('escolas_app.escolas'))

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
        return redirect(url_for('escolas_app.escolas'))

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

    mapa = []

    for row in mapa_base:
        mapa.append(row.split(', ') + [len(mapa_base[row])] + [mapa_base[row][0]])

    return mapa

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