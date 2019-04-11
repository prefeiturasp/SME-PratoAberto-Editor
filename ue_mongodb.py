#
# ue_mongodb.py
#
#   Funções para tratamento MongoDB das
#   unidades especiais POLO e RECREIO_FERIAS.
#

import os
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, ConnectionFailure, OperationFailure, ServerSelectionTimeoutError
from datetime import datetime


# ..ESTABELECE CONEXÃO COM O SERVIDOR MONGODB
def connect(colecao=''):
    # client = MongoClient('mongodb://localhost:27017/')

    client = MongoClient(os.environ.get('MONGO_HOST'))
    db = client.pratoaberto

    try:
        client.admin.command("ismaster")
    except (ConfigurationError, ConnectionFailure, OperationFailure, ServerSelectionTimeoutError) as e:
        print("Servidor Não Disponível.")
        print(e)
    else:
        with client:
            if colecao == 'escolas':
                db = client.pratoaberto.escolas
            else:
                if 'unidades_especiais' not in db.list_collection_names():
                    ue_init(db, client)
                db = client.pratoaberto.unidades_especiais

            return db, client

# ..INICIALIZA A ESTRUTURA DAS UNIDADES ESPECIAIS (ues)
def ue_init(db, client):
    unidades = [{"nome": "POLO", "data_inicio": "", "data_fim": "", "escolas": []},
                {"nome": "RECREIO_FERIAS", "data_inicio": "", "data_fim": "", "escolas": []}]
    try:
        db['unidades_especiais'].insert_many(unidades)
    except OperationFailure as e:
        print("Problema na inicializar as estruturas no banco de dados das unidades especiais.")
        print(e)
    client.close()
    return 1


# ..DELETA AS UNIDADES ESPECIAIS DO BANCO DE DADOS
def ue_drop():
    client = MongoClient(os.environ.get('MONGO_HOST'))
    db = client.pratoaberto
    if db is not None:
        if 'unidades_especiais' in db.client.pratoaberto.list_collection_names():
            try:
                db['unidades_especiais'].drop()
            except OperationFailure as e:
                print("Problema ao tentar deletar a collection.")
                print(e)
        client.close()
        return 1


# ..VERIFICA SE A UNIDADE ESPECIAL EXISTE
def ue_exists(unidade):
    db, client=connect()
    if db is not None:
        try:
            r = db.aggregate([{"$match":{"nome":unidade}},{"$count": "num_regs"}])
            num_regs = 0
            for i in r:
                return (i['num_regs'])

        except OperationFailure as e:
            print("Problema ao verificar se a unidade está ativa.")
            print(e)
        client.close()


# ..VERIFICA SE A UNIDADE ESPECIAL ESTA ATIVA
def ue_isactive(unidade):
    db, client=connect()
    if db is not None:
        try:
            dta_ini, dta_fim = ue_get_periodo(unidade).split(',')
            dta_now = f'{datetime.now():%Y%m%d}'
            return (dta_now >= dta_ini and dta_now <= dta_fim)
        except OperationFailure as e:
            print("Problema ao verificar se a unidade está ativa.")
            print(e)
        client.close()


# ..INSERE/ATUALIZA AS DATAS INICIO-FIM DO PERIODO DE FUNCIONAMENTO DE UMA UNIDADE ESPECIAL
def ue_set_periodo(nome_unidade, data_ini="", data_fim=""):
    db, client = connect()
    if db is not None:
        try:
            db.update_one({"nome": nome_unidade},
                          {"$set": {"data_inicio": data_ini,
                                    "data_fim": data_fim}})
        except OperationFailure as e:
            print("Problema ao inserir/atualizar o período de funcionamento do POLO ou RECREIO_REFEICAO.")
            print(e)
        client.close()
        return 1


# ..EXTRAI AS DATAS DO PERÍODO DE FUNCIONAMENTO DE UMA INIDADE ESPECIAL
def ue_get_periodo(nome_unidade):
    db, client = connect()
    periodo = ""
    if db is not None:
        try:
            dict_unidade = db.find_one({"nome": nome_unidade})
            periodo = dict_unidade["data_inicio"] + "," + dict_unidade["data_fim"]
        except OperationFailure as e:
            print("Problema ao extrair as datas do período de funcionamento do POLO ou RECREIO_FERIAS.")
            print(e)
        client.close()
        return periodo


# .. INSERE/ATUALIZA A LISTA DE ESCOLAS DE UMA UNIDADE ESPECIAL
def ue_set_escolas(unidade, id_escolas):
    db, client = connect()
    try:
        db.update_one({"nome": unidade},
                      {"$set": {"escolas": id_escolas}})
    except OperationFailure as e:
        print("Problema ao inserir/atualizar a lista das escolas do POLO ou RECREIO_REFEICAO.")
        print(e)
    return 1


# ..EXTRAI AS ESCOLAS DE UMA UNIDADE ESPECIAL
def ue_get_escolas(unidade):
    id_nome_escolas = []
    db, client = connect()
    if db is not None:
        try:
            id_escolas = (db.find_one({"nome": unidade}))['escolas']
            if len(id_escolas) > 0:
                try:
                    db_escolas, client_escolas = connect('escolas')
                    if db_escolas is not None:
                        for id in id_escolas:
                            e = db_escolas.find_one({'_id':id})
                            id_nome_escolas.append(str(e['_id']).strip() + ':' + e['nome'].strip())
                    client_escolas.close()
                except OperationFailure as e:
                    print("Problema ao extrair as escolas do banco de dados.")
                    print(e)
        except OperationFailure as e:
            print("Problema ao extrair as escolas que compoem a unidade POLO ou RECREIO_FERIAS.")
            print(e)
        client.close()
        return id_nome_escolas


# ..GRAVA/ATUALIZA OS DADOS DE UMA UNIDADE ESPECIAL
def ue_save_unidade(unidade, dta_de, dta_ate, id_escolas):
    db, client = connect()
    if db is not None:
        try:
            ue_set_periodo(unidade, dta_de, dta_ate)
            ue_set_escolas(unidade, id_escolas)
        except OperationFailure as e:
            print("Problema na gravação/atualização da unidade POLO ou RECRIO_FERIAS.")
            print(e)
        return 1


# ..EXTRAI AS ESCOLAS DO BANCO DE DADOS
def ue_get_db_escolas():
    """Retorna lista de todas as escolas ordenadas alfabeticamente no formato id:nome_escola"""
    id_nome_escolas = []
    db, client=connect('escolas')
    if db is not None:
        try:
            a=db.aggregate([{"$match": {"nome":{"$gt":''}}}, {"$sort": {"nome": 1}}])
            id_nome_escolas = [str(e['_id']).strip()+':'+e['nome'].strip() for e in a]
        except OperationFailure as e:
            print("Problema ao extrair a lista id:nome das escolas.")
            print(e)
        client.close()
        return id_nome_escolas


# ..DESATIVA UNIDADE ESPECIAL
def ue_deactivate(unidade):
    db, client=connect()
    if db is not None:
        try:
            ue_set_periodo(unidade)
            ue_set_escolas(unidade, [])
        except OperationFailure as e:
            print("Problema ao desativar a unidade especial.")
            print(e)
        client.close()


# .. Main ......................................................................................
# if __name__ == '__main__':
#     pass
#
#
#
# # CREATE THE COLLECTIONS
# colecao = 'unidades_especiais'
unidade1 = 'POLO'
# unidade2 = 'RECREIO_FERIAS'
#
# unidades = [{"nome": "POLO", "data_inicio": "", "data_fim": "", "escolas": []},
#             {"nome": "RECREIO_FERIAS", "data_inicio": "", "data_fim": "", "escolas": []}]


# ..INICIALIZA AS ESTRUTURAS DAS UNIDADES NO BANCO DE DADOS
# a = ue_set_periodo(unidade1, '20190311', "20190315")
# b = ue_set_periodo(unidade2, '20190311', "20190315")
# print(a)

# ..DELETA AS UNIDADES ESPECIAIS DO BANCO DE DADOS
# ue_drop()

# ..VERIFICA SE A UNIDADE ESPECIAL EXISTE
# if ue_exists('POLO'):
#     print('s')
# else: print('n')


# a = ue_get_db_escolas()
# for escola in a:
#     a,b = escola.split(':')
#     print(a, b)


# 92622 EMEF ARLINDO CAETANO FILHO, PROF. (TERC.)
# 95265 EMEF ARMANDO ARRUDA PEREIRA - (MIST)
# 93891 EMEF ARMANDO CRIDEY RIGHETTI (TERC.)

# id_escolas=[92622, 95265, 93891]

# ..EXTRAI AS ESCOLAS DA UNIDADE ESPECIAL
# ue_set_escolas(unidade1, id_escolas )
#
a = ue_get_escolas('RECREIO_FERIAS')
print(a)
for i in a:
    a, b=i.split(':')
    print(b)

# ue_set_escolas(unidade2, id_escolas )
#
# a = ue_get_escolas(unidade2)
# print(a)
# for i in a:
#     a, b=i.split(':')
#     print(b)


# ..INSERE/ATUALIZA AS DATAS INICIO-FIM DO PERIODO DE FUNCIONAMENTO
# a=set_periodo(unidade1, "20190401", "20190428")
# print(a)
#
# a=set_periodo(unidade2, "20190401", "20190428")
# print(a)


# ..EXTRAI AS DATAS DO PERÍODO DE FUNCIONAMENTO
# a = ue_get_periodo(unidade1)
# print(a)
#
# a = ue_get_periodo(unidade2)
# print(a)


# ..ATUALIZA/RESETA UMA DAS UNIDADES ESPECIAIS
# ue_deactivate(unidade1)

# ..VERIFICA SE A UNIDADE ESPECIAL ESTA ATIVA
# print(ue_isactive(unidade1))

# ..EXTRAI AS ESCOLAS DO BANCO DE DADOS
# print(ue_get_db_escolas())







