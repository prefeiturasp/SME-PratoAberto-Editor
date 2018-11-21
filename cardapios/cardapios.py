# -*- coding: utf-8 -*-

import datetime
import db_functions
import flask_login
import requests
import configparser
import collections
import itertools

from flask import flash, redirect, render_template, request, url_for,Blueprint
from utils.utils import data_semana_format,dia_semana,get_depara,filtro_dicionarios

config = configparser.ConfigParser()
config.read('config/integracao.conf')
api = config.get('ENDPOINTS', 'PRATOABERTO_API')

cardapios_app = Blueprint('cardapios_app', __name__)

@cardapios_app.route('/atualiza_cardapio', methods=['POST'])
@flask_login.login_required
def atualiza_cardapio():

    headers = {'Content-type': 'application/json'}
    data = request.form.get('json_dump', request.data)
    r = requests.post(api + '/editor/cardapios', data=data, headers=headers)

    if request.form:

        return (redirect(url_for('pendencias_app.backlog')))
    else:

        return ('', 200)

@cardapios_app.route("/visualizador_cardapio", methods=["GET"])
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

def get_args(url):

    return dict([tuple(x.split('=')) for x in url.split('?')[1].split('&')])


@cardapios_app.route("/calendario_editor_grupo", methods=["POST"])
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

        args = get_args(url)
        lista_data_inicial.append(args['data_inicial'])
        lista_data_final.append(args['data_final'])
        lista_args.append(args)

    if (len(set(lista_data_inicial)) > 1) or (len(set(lista_data_final)) > 1):

        flash("A cópia de cardápios só é permitida para quabras com mesmo periodo")
        return redirect(url_for('pendencias_app.backlog'))

    depara = db_functions.select_all()
    depara = get_depara(depara)
    cardapios = []

    for url in data:

        args = get_args(url)
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

            jdata_aux = get_cardapio_lista(cardapio_atual)

        jdata_anterior_aux = []

        for cardapio_anterior in jdata_anterior:

            jdata_anterior_aux = get_cardapio_lista(cardapio_anterior)

        jdata = jdata_aux
        jdata_anterior = jdata_anterior_aux

        # Liga o cardapio atual com o da semana anterior
        dias_da_semana = set([x['dia_semana'] for x in list(jdata + jdata_anterior)])

        for dia in dias_da_semana:

            cardapio_atual = get_cardapio_atual(jdata, dia)
            cardapio_anterior = get_cardapio_anterior(jdata_anterior, dia)

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

def get_cardapio(args):

    url = api + '/editor/cardapios?' + '&'.join(['%s=%s' % item for item in args.items()])
    r = requests.get(url)
    refeicoes = r.json()

    return refeicoes

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

def get_cardapio_atual(jdata, dia):

    return filtro_dicionarios(jdata, 'dia_semana', dia)


def get_cardapio_anterior(jdata_anterior, dia):

    return filtro_dicionarios(jdata_anterior, 'dia_semana', dia)


def get_cardapio_lista(cardapio_atual):

    jdata_aux = []

    dia = datetime.datetime.strptime(str(cardapio_atual['data']), '%Y%m%d').weekday()
    cardapio_atual['dia_semana'] = dia_semana(dia)
    jdata_aux.append(cardapio_atual)

    return jdata_aux

def get_cardapios_terceirizadas(tipo_gestao, tipo_escola, edital, idade):

    return db_functions.select_receitas_terceirizadas(tipo_gestao, tipo_escola, edital, idade)