#
# ue_mongodb.py
#   Funções para tratamento das unidades especiais
#

import os
from bson.objectid import ObjectId
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, ConnectionFailure, OperationFailure, ServerSelectionTimeoutError
from datetime import datetime


# ..CONNECTS WITH MONGODB
def connect(colecao=None):
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
                    db.createCollection('unidades_especiais')

                db = client.pratoaberto.unidades_especiais

            return db, client


# ..SPECIAL UNIT STRUCTURE INITIALIZATION
def create(unidade, dta_criacao, dta_ini, dta_fim, id_escolas):
    db, client = connect()
    if db is not None:
        unidade = {"nome": unidade,
                   "data_criacao": dta_criacao,
                   "data_inicio": dta_ini,
                   "data_fim": dta_fim,
                   "escolas": id_escolas}
        try:
            db.insert_one(unidade)
        except OperationFailure as e:
            print("Problema ao tentar criar a estrutura da unidade.")
            print(e)
    client.close()
    return 1


# ..DELETES ONE OR ALL SPECIAL UNITS FROM THE COLLECTION
def delete(id_unidade=None):
    client = MongoClient(os.environ.get('MONGO_HOST'))
    db = client.pratoaberto
    if db is not None:
        if 'unidades_especiais' in db.list_collection_names():
            try:
                if id_unidade:
                    db.unidades_especiais.delete_one({"_id": ObjectId(id_unidade)})
                else:
                    db.unidades_especiais.delete_many({})
            except OperationFailure as e:
                print("Problema ao tentar deletar uma ou todas as unidades da collection.")
                print(e)
        client.close()
        return 1


# ..CHECKS IF THE SPECIAL UNIT IS ACTIVE
def isactive(id_unidade):
    db, client=connect()
    if db is not None:
        try:
            nome, datas, escolas = get_unidade(id_unidade)
            dta_criacao, dta_ini, dta_fim = datas.split(',')
            dta_now = f'{datetime.now():%Y%m%d}'
            return (dta_now >= dta_ini and dta_now <= dta_fim)

        except OperationFailure as e:
            print("Problema ao verificar se a unidade está ativa.")
            print(e)
        client.close()


# ..UPDATES ONE, SOME OR ALL ATTRIBUTES OF THE SPECIAL UNIT
def set_unidade(id_unidade, data_criacao=None, data_ini=None, data_fim=None, id_escolas=[]):
    db, client = connect()
    if db is not None:
        try:
            if data_criacao:
                db.update_one({"_id": ObjectId(id_unidade)}, {"$set": {"data_criacao": data_criacao}})

            if data_ini:
                db.update_one({"_id": ObjectId(id_unidade)}, {"$set": {"data_inicio": data_ini}})

            if data_fim:
                db.update_one({"_id": ObjectId(id_unidade)}, {"$set": {"data_fim": data_fim}})

            if len(id_escolas) > 0:
                db.update_one({"_id": ObjectId(id_unidade)}, {"$set": {"escolas": id_escolas}})

        except OperationFailure as e:
            print("Problema ao atualizar o período de funcionamento do POLO ou RECREIO_REFEICAO.")
            print(e)
        client.close()
        return 1


# ..RETRIEVES ALL ATTRIBUTES OF THE SPECIAL UNIT
def get_unidade(id_unidade):
    db, client = connect()
    if db is not None:
        try:
            cursor = db.find({"_id": ObjectId(id_unidade)})

            if cursor.count() == 0:
                print('Unidade não encontrada.')
                return -1

            doc = cursor.next()
            datas = doc['data_criacao']+ "," + doc['data_inicio']+ "," +doc['data_fim']
            cursor.close()
            return doc['nome'], datas, doc['escolas']

        except OperationFailure as e:
            print("Problema ao procurar a unidade.")
            print(e)
        client.close()
        return 1


# ..RETRIEVES THE IDs OF ALL SCHOOLS
def get_db_escolas():
    """Retorna lista de todas as escolas ordenadas alfabeticamente.Formato id:nome_escola"""
    ids_escolas = []
    db, client=connect('escolas')
    if db is not None:
        try:
            a=db.aggregate([{"$match": {"nome": {"$gt": ''}}}, {"$sort": {"nome": 1}}])
            ids_escolas = [str(e['_id']).strip()+':'+e['nome'].strip() for e in a]
        except OperationFailure as e:
            print("Problema ao extrair os ids da tabela escolas.")
            print(e)
        client.close()
        return ids_escolas


# ..CHECKS IF THE SCHOOL BELONGS FROM A UNIDADE ESPECIAL
def check_school(id_school):
    """If the school belongs to a UE, return the UE's id"""
    num_recs = 0
    id_ue = ''
    db, client=connect()
    if db is not None:
        try:
            cursor = db.find()
            doc = cursor.next()
            while num_recs < cursor.count():
                if isactive(doc['_id']):
                    if id_school in doc['escolas']:
                        id_ue = doc['_id']
                num_recs += 1
                try:
                    doc = cursor.next()
                except Exception as e:
                    print(e)

            cursor.close()
            client.close()

        except OperationFailure as e:
            print("Problema ao extrair os ids da tabela escolas.")
            print(e)
        client.close()
        return id_ue


# - Main ---------------------------------------------------------------------------------------------------------------
#if __name__ == "__main__":
    # print(".. ",check_school('10'))

    # .. Criação
    # print(create('POLO','20190401','20190415','20190430',[1,2,3]))
    # print(create('RECREIO_FERIAS', '20190401', '20190415', '20190430', [1, 2, 3]))

    # .. Apaga uma ou todas as unidades especiais
    # print(delete("POLO"))
    # print(delete(""))

    # .. Atualiza dados da unidade
    # data_criacao=""
    # data_ini="11112233"
    # data_fim=""
    # id_escolas=[10,20,30]
    # print(set_unidade("5cb5ed414619f0726f26a351", data_criacao, data_ini, data_fim, id_escolas))

    # .. Extrai os dados da unidade
    #datas, escolas = get_unidade("5cb5ed414619f0726f26a351")

    #data_criacao, data_inicio, data_fim = datas.split(',')

    #print(data_criacao, data_inicio, data_fim, escolas)

    # # .. Verifica se a unidade está ativa
    # print(isactive("5cb5ed414619f0726f26a351"))

    # .. Extrai o id + nome de todas as escolas da tabela escolas
    # print(get_db_escolas())