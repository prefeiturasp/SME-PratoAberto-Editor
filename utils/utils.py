import collections
import datetime
import itertools
import requests
import cardapios_terceirizadas
import db_functions

import app

from flask import render_template

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

def caso_nao_cardapio(quebra, refeicao):

    cardapios = []

    quebra_aux = quebra
    quebra_aux['cardapio'] = {refeicao['tipo_refeicao']: []}
    quebra_aux['cardapio_original'] = {refeicao['tipo_refeicao']: []}
    cardapios.append(quebra_aux)

    return cardapios


def get_depara(depara):
    depara = [x[3:5] for x in depara if x[2] == 'INGREDIENTES']

    return depara


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

    mapa = []

    for row in mapa_base:
        mapa.append(row.split(', ') + [len(mapa_base[row])] + [mapa_base[row][0]])

    return mapa

# FUNÇÕES AUXILIARES
def data_semana_format(text):

    date = datetime.datetime.strptime(text, "%Y%m%d").isocalendar()

    return str(date[0]) + "-" + str(date[1])


def get_cardapio(args):

    url = app.api + '/editor/cardapios?' + '&'.join(['%s=%s' % item for item in args.items()])
    r = requests.get(url)
    refeicoes = r.json()

    return refeicoes


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


def get_url_json(status):

    if status == "PUBLICADO" or status == "DELETADO":
        url = app.api + '/editor/cardapios?status=' + status
        r = requests.get(url)
        refeicoes = r.json()

        return refeicoes


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


def get_escolas():

    url = app.api + '/editor/escolas'
    r = requests.get(url)
    escolas = r.json()

    return escolas


def get_escola(cod_eol):

    url = app.api + '/escola/{}'.format(cod_eol)
    r = requests.get(url)
    escola = r.json()

    return escola


def get_grupo_publicacoes(status):

    url = app.api + '/editor/cardapios?status=' + status
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

    url = app.api + '/editor/cardapios?status=PENDENTE&status=SALVO'
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