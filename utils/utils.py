import collections
import datetime
import itertools
import requests
import cardapios_terceirizadas
import db_functions
import configparser

import app

def get_config():

    config = configparser.ConfigParser()
    config.read('config/integracao.conf')

    return config

def get_depara(depara):
    depara = [x[3:5] for x in depara if x[2] == 'INGREDIENTES']

    return depara

def filtro_dicionarios(dictlist, key, valuelist):

    lista_filtrada = [dictio for dictio in dictlist if dictio[key] in valuelist]

    if lista_filtrada:

        return lista_filtrada[0]
    else:

        return None

# FUNÇÕES AUXILIARES
def data_semana_format(text):

    date = datetime.datetime.strptime(text, "%Y%m%d").isocalendar()

    return str(date[0]) + "-" + str(date[1])

def get_url_json(status):

    if status == "PUBLICADO" or status == "DELETADO":
        url = app.api + '/editor/cardapios?status=' + status
        r = requests.get(url)
        refeicoes = r.json()

        return refeicoes

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

def dia_semana(dia):

    diasemana = ('Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom')

    return diasemana[dia]


def replace_cardapio(cardapio):

    config_editor = db_functions.select_all()

    for de_para in config_editor:
        cardapio = [de_para[4] if x == de_para[3] else x for x in cardapio]

    cardapio = [x for x in cardapio if x != '']

    return cardapio


def get_semana(dia_semana_seguinte):

    semana = [dia_semana_seguinte + datetime.timedelta(days=i) for i in
              range(0 - dia_semana_seguinte.weekday(), 7 - dia_semana_seguinte.weekday())]

    return semana