import collections
import configparser
import datetime
import itertools
from app import replace_cardapio,data_semana_format

import requests

import db_functions


# BLOCO GET ENDPOINT E KEYS
config = configparser.ConfigParser()
config.read('config/integracao.conf')
api = config.get('ENDPOINTS', 'PRATOABERTO_API')

def dia_semana(dia):
    diasemana = ('Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom')
    return diasemana[dia]

def get_cardapios_iguais():
    url = api + '/cardapios?status=PENDENTE&status=SALVO'
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

    ingredientes = collections.defaultdict(list)
    for refeicao in refeicoes:
        agrupamento = str(refeicao['agrupamento'])
        tipo_unidade = refeicao['tipo_unidade']
        tipo_atendimento = refeicao['tipo_atendimento']
        status = refeicao['status']
        idade = refeicao['idade']
        _key_semana = data_semana_format(refeicao['data'])

        for alimentos in refeicao['cardapio_original'].keys():
            _key = frozenset(replace_cardapio(refeicao['cardapio_original'][alimentos]))
            ingredientes[_key].append([agrupamento, tipo_unidade, tipo_atendimento, status, idade, _key_semana])

    return ingredientes


def open_csv():
    path = './tmp'
    file = 'Cardapios Novos.csv'

    cardapio = []
    with open(path+'/'+file, 'r', encoding='utf-8') as f:

        # REFEIÇÕES
        text = f.read().replace(' (Sopa e Fruta)', '')
        text = text.replace('(Papa Principal e Papa de Fruta)', '')
        text = text.replace('(Sopa e Fruta)', '')
        text = text.replace('(Papa de Fruta)', '')
        text = text.replace('(Papa Principal e Papa de Fruta/Suco)', '')
        text = text.replace('(Fórmula e Papa de Fruta)', '')
        text = text.replace('(Fruta)', '')
        text = text.replace('R1 - REFEICAO 1 da Tarde', 'R1 - REFEICAO 1')
        text = text.replace('A - ALMOCO (R1 - REFEICAO 1 e Fruta/Suco)', 'R1 - REFEICAO 1')
        text = text.replace('(R1 - REFEICAO 1 e Fruta/Suco)', '')

        # IDADES
        text = text.replace('7 meses', 'D - 7 MESES')
        text = text.replace('0 a 5 meses', 'D - 0 A 5 MESES')
        text = text.replace('6 meses', 'D - 6 MESES')
        text = text.replace('2 - 6 anos', 'I - 2 A 6 ANOS')
        text = text.replace('8 a 11 meses', 'E - 8 A 11 MESES')
        text = text.replace('1 ano - 1 ano e 11 meses', 'X - 1A -1A E 11MES')
        text = text.replace('TODAS', 'Z - UNIDADES SEM FAIXA')
        text = text.replace('\n', '')
        cardapio = text.split('|')

    cardapio_aux = []
    for nrow in range(0, len(cardapio), 5):
        if len(cardapio[nrow:nrow+5]) == 5:
            x = cardapio[nrow:nrow + 5]
            ingredientes = ', '.join([y.strip() for y in x[3].split(',') if y.strip() != ''])
            dsemana = datetime.datetime.strptime(x[4].strip(), '%d-%m-%Y').weekday()
            row = [x[0], x[1].strip(), x[2].strip(), ingredientes, dia_semana(dsemana)]
            cardapio_aux.append(row)

    cardapio_aux.sort()
    cardapio = list(cardapio_aux for cardapio_aux, _ in itertools.groupby(cardapio_aux))
    db_functions.truncate_receitas_terceirizadas()

    objects = []
    for row in cardapio:
        if row[3] != '':
            objects.append(['TERCEIRIZADA', row[0], 'EDITAL 78/2016', row[4], row[1], row[2], row[3]])
            # db_functions.add_cardapio('TERCEIRIZADA', row[0], 'EDITA1', row[4], row[1], row[2], row[3])

    db_functions.add_bulk_cardapio(objects)


def get_escola(cod_eol):
    url = api + '/escola/{}'.format(cod_eol)
    r = requests.get(url)
    escola = r.json()

    return escola


def get_escolas():
    url = api + '/escolas?completo'
    r = requests.get(url)
    escolas = r.json()

    return escolas


def get_escola(cod_eol):
    url = api + '/escola/{}'.format(cod_eol)
    r = requests.get(url)
    try:
        escola = r.json()
    except:
        escola = None

    return escola


def post_cardapio():
    escolas = get_escolas()
    headers = {'Content-type': 'application/json'}
    count = 0
    for escola in escolas:
        print(count)
        count += 1
        # 1. Criar o agrupamento_regiao
        # escola['agrupamento_regiao'] = escola['agrupamento']
        # 2. Se terceirizada, acrescentar o 'EDITAL 78/2016'
        if escola['tipo_atendimento'] == 'TERCEIRIZADA':
            escola['agrupamento'] = 'EDITAL 78/2016'
            escola['edital'] = 'EDITAL 78/2016'

        # 4. Criar o status com o valor 'ativo'
        escola['status'] = 'ativo'

        r = requests.post(api + '/editor/escola/{}'.format(str(escola['_id'])),
                          data=json.dumps(escola),
                          headers=headers)


def post_idades_idades():
    escolas = get_escolas()
    headers = {'Content-type': 'application/json'}
    count = 0
    dic_refeicoes = {
        'A - ALMOCO': 'A - ALMOCO',
        'AA - ALMOCO ADULTO': 'AA - ALMOCO ADULTO',
        'C - COLACAO': 'C - COLACAO',
        'D - DESJEJUM': 'D - DESJEJUM',
        'FPJ - FILHOS PRO JOVEM': 'FPJ - FILHOS PRO JOVEM',
        'J - JANTAR': 'J - JANTAR',
        'L - LANCHE': 'L - LANCHE',
        'L4 - LANCHE 4 OU LANCHE 8 HORAS': 'L4 - LANCHE 4 HORAS',
        'L5 - LANCHE 5 OU 6 HORAS': 'L5 - LANCHE 5 HORAS',
        'L5 - LANCHE 5 OU LANCHE 6 HORAS': 'L5 - LANCHE 5 HORAS',
        'MI - MERENDA INICIAL': 'MI - MERENDA INICIAL',
        'MS - MERENDA SECA': 'MS - MERENDA SECA',
        'R1 - REFEICAO 1': 'R1 - REFEICAO 1'
    }

    for escola in escolas:
        count += 1
        if 'refeicoes' in escola.keys():

            refeicao_aux = []
            for refeicao in escola['refeicoes']:
                if refeicao in dic_refeicoes.keys():
                    refeicao_aux.append(dic_refeicoes[refeicao])
                else:
                    refeicao_aux.append(refeicao)
            if refeicao_aux != escola['refeicoes']:
                print(count, escola['_id'], refeicao_aux, escola['refeicoes'])
            escola['refeicoes'] = refeicao_aux

            refeicao_aux = []
            if 'historico' in escola.keys():
                if escola['historico'] != []:
                    for refeicao in escola['historico']['refeicoes']:
                        if refeicao in dic_refeicoes.keys():
                            refeicao_aux.append(dic_refeicoes[refeicao])
                        else:
                            refeicao_aux.append(refeicao)
                        escola['historico']['refeicoes'] = refeicao_aux


            r = requests.post(api + '/editor/escola/{}'.format(str(escola['_id'])),
                              data=json.dumps(escola),
                              headers=headers)


def post_ordenar_refeicoes():
    escolas = get_escolas()
    headers = {'Content-type': 'application/json'}
    count = 0

    refeicoes_ordenadas = ['MI - MERENDA INICIAL',
                           'D - DESJEJUM',
                           'C - COLACAO',
                           'AA - ALMOCO ADULTO',
                           'A - ALMOCO',
                           'L - LANCHE',
                           'L4 - LANCHE 4 HORAS',
                           'L5 - LANCHE 5 HORAS',
                           'R1 - REFEICAO 1',
                           'MS - MERENDA SECA',
                           'FPJ - FILHOS PRO JOVEM',
                           'J - JANTAR']

    for escola in escolas:
        count += 1
        print(escola['_id'], count)
        if 'refeicoes' in escola.keys():
            lista_ordenada = [x for x in refeicoes_ordenadas if x in escola['refeicoes']]
            print(escola['refeicoes'], lista_ordenada)
            escola['refeicoes'] = lista_ordenada


        if 'historico' in escola.keys():
            if escola['historico'] != []:
                if 'refeicoes' in escola['historico'].keys():
                    lista_ordenada = [x for x in refeicoes_ordenadas if x in escola['refeicoes']]
                    escola['historico']['refeicoes'] = lista_ordenada

        r = requests.post(api + '/editor/escola/{}'.format(str(escola['_id'])),
                          data=json.dumps(escola),
                          headers=headers)


def post_cardapio_add_merendas():
    FILE = './tmp/Escolas x Tipo Refeição_Texto'

    with open(FILE, 'r', encoding="ISO-8859-1") as f:
        refeicao_escola = {}
        for row in f.readlines():
            data = row.replace("'", '').replace('\n', '').split(', ')
            if data[0] in refeicao_escola.keys():
                refeicao_escola[data[0]].append(data[1])
            else:
                refeicao_escola[data[0]] = []
                refeicao_escola[data[0]].append(data[1])

    headers = {'Content-type': 'application/json'}
    count = 0
    for _id in refeicao_escola.keys():
        print(str(count) + ' - ' + api + '/editor/escola/{}'.format(str(_id)))
        escola = get_escola(_id)
        if escola == None:
            print(_id)
            pass
        else:
            escola['_id'] = int(_id)
            escola['refeicoes'] = refeicao_escola[_id]
            # print(str(count) + ' - ' + api + '/editor/escola/{}'.format(str(escola['_id'])))
            r = requests.post(api + '/editor/escola/{}'.format(str(escola['_id'])),
                          data=json.dumps(escola),
                          headers=headers)
        count += 1


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


def get_cardapio(args):
    url = api + '/editor/cardapios?' + '&'.join(['%s=%s' % item for item in args.items()])
    r = requests.get(url)
    refeicoes = r.json()

    return refeicoes


def mapa_pendencias():
    mapa = get_quebras_escolas()

    delta_dias = datetime.timedelta(days=7)
    dia_semana_seguinte = datetime.datetime.now() + delta_dias
    semana = [dia_semana_seguinte + datetime.timedelta(days=i) for i in range(0 - dia_semana_seguinte.weekday(), 7 - dia_semana_seguinte.weekday())]
    dia_inicial = min(semana).strftime("%Y%m%d")
    dia_final = max(semana).strftime("%Y%m%d")

    dia_inicial = 20170918
    dia_final = 20170922

    # Por padrão, sempre colocaremos o cardápio da semana seguinte
    mapa_final = []
    for row in mapa:
        args = {'agrupamento': row[0],
                'tipo_unidade': row[1],
                'tipo_atendimento': row[2],
                'idade': row[3],
                'status': 'SALVO',
                'status': 'PUBLICADO',
                'data_inicial': dia_inicial,
                'data_final': dia_final}

        cardapio = get_cardapio(args)
        if cardapio == []:
            args['status_publicacao'] = 0
            mapa_final.append(args)
            print(str(0), row)
        else:
            args['status_publicacao'] = 1
            mapa_final.append(args)
            print(str(1), row)


def update_receitas_terceirizadas():
    r = db_functions.select_all_receitas_terceirizadas()
    modificacoes = []
    for row in r:
        row_aux = list(row[1:])
        # Atualiza
        if row_aux[1] == 'CEI':
            # row_aux = list(row_aux)
            row_aux[1] = 'CEI_MUNICIPAL'
            if row_aux[5] == 'R1 - REFEICAO 1':
                row_aux[5] = 'J - JANTAR'

            if row_aux[5] == 'L4 - LANCHE 4 HORAS':
                row_aux[5] = 'L - LANCHE'

            # Adiciona CCI - Cópia CEI
            row_aux_CCI = row_aux.copy()
            row_aux_CCI[1] = 'CCI'
            modificacoes.append(row_aux_CCI)
        modificacoes.append(row_aux)

    modificacoes.sort()
    modificacoes = list(modificacoes for modificacoes, _ in itertools.groupby(modificacoes))

    db_functions.truncate_receitas_terceirizadas()
    db_functions.add_bulk_cardapio(modificacoes)


def get_cardapios():
    url = api + '/editor/cardapios?status=PENDENTE&status=SALVO&status=PUBLICADO'
    r = requests.get(url)
    refeicoes = r.json()

    for refeicao in refeicoes:
        if refeicao['tipo_atendimento'] == 'TERCEIRIZADA':
            if refeicao['tipo_unidade'] == 'CEI':
                refeicao['tipo_unidade'] = 'CEI_MUNICIPAL'
                print(refeicao['status'], refeicao)
                headers = {'Content-type': 'application/json'}
                data = json.dumps([refeicao])
                res = requests.post(api + '/editor/cardapios', data=data, headers=headers)

if __name__ == '__main__':
    # open_csv()
    import json

    get_cardapios()

