# -*- coding: utf-8 -*-

import collections
import itertools
import requests
import flask_login
import app

from flask import render_template, request,Blueprint
from utils.utils import data_semana_format,get_url_json

pendencias_app = Blueprint('pendencias_app',__name__)

@pendencias_app.route("/pendencias_publicacoes", methods=["GET", "POST"])
@flask_login.login_required
def backlog():

    if request.method == "GET" or request.method == "POST":

        status = "pendencias"

        return get_publicacao(status)


@pendencias_app.route("/pendencias_deletadas", methods=["GET", "POST"])
@flask_login.login_required
def deletados():

    if request.method == "GET":

        status = "deletados"

        return get_publicacao(status)


@pendencias_app.route("/pendencias_publicadas", methods=["GET", "POST"])
@flask_login.login_required
def publicados():

    if request.method == "GET":

        status = "publicadas"

        return get_publicacao(status)

def get_publicacao(status):

    if status == "pendencias":

        condicoes = "publicacao"
        condicao = get_pendencias()

    elif status == "deletados":

        condicoes = "deletadas"
        condicao = get_deletados()

    elif status == "publicadas":

        condicoes = "publicadas"
        condicao = get_publicados()

    semanas = sorted(set([str(x[4]) + ' - ' + str(x[5]) for x in condicao]), reverse=True)

    return render_template("pendencias_" + condicoes + ".html",
                           pendentes=condicao,
                           semanas=semanas)

def get_pendencias():

    url = app.api + '/editor/cardapios?status=PENDENTE&status=SALVO'

    r = requests.get(url, timeout=300)
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

    refeicoes = get_url_json("DELETADO")

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

    refeicoes = get_url_json("PUBLICADO")

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