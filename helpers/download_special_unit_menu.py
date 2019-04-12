#
#  download_special_unit_menu.py
#
#   Uso:  <unidade> onde:
#
#                       <unidade> = string: 'POLO' ou 'RECREIO_FERIAS'
#
#   Nome do arquivo gerado: Cardapio_<unidade>_AAAAMMDDhhmm.xlsx' onde:
#                       AAAA= ano  MM= mês  DD= dia  hh= hora  mm= minutos
#

import os
import pymongo
import ue_mongodb as une

# ----------------------------------------------------------------------------------------------------------------------
idades=[]
refeicoes=[]
x_cardapios={}

def gera_excel(unidade):
    # ..Acesso ao banco de dados
    # client = pymongo.MongoClient('localhost', 27017)
    # db = client.pratoaberto
    # collection = db.cardapaios

    # .. check if unidade is active
    if une.ue_exists(unidade) is None:
        print('A unidade especial {0} não existe.'.format(unidade))
        return -1


    client = pymongo.MongoClient(os.environ.get('MONGO_HOST'))
    db = client.pratoaberto
    collection = db.cardapios

    # ..Parámetros para a extração e gravação
    t_status = 'PUBLICADO'

    # ..Verifica a existência de cardápios com os parámetros fornecidos
    consulta = [{"$match": {"tipo_unidade": unidade,
                            "status": t_status}}, {"$sort": {"data": 1}}, {"$count": "num_regs"}]

    num_regs = 0
    for i in collection.aggregate(consulta):
        num_regs = i['num_regs']

    # ..Extrai os cardápios do banco de dados
    cursor = collection.find({"tipo_unidade": unidade, "status": t_status}).sort([("data", 1)])

    # ..Processa os cardápios extraidos
    num_recs = 0
    doc = cursor.next()

    cursor.rewind()
    while num_recs <= cursor.count():
        l_refeicoes = list(doc[r'cardapio'].keys())

        for refeicao in l_refeicoes:
            # if doc['idade'] not in idades:
            #     idades.append(doc['idade'])

            if refeicao not in refeicoes:
                refeicoes.append(refeicao)

            if doc['idade'] not in x_cardapios:
                x_cardapios[doc['idade']]={}

            if refeicao not in x_cardapios[doc['idade']]:
                x_cardapios[doc['idade']][refeicao] = ', '.join(doc[r'cardapio'][refeicao])

            alimentos = ', '.join(doc[r'cardapio'][refeicao])

            print(doc['data']+ " Idade: "+doc['idade'] + " Refeição: "+refeicao + " Cardápio: "+ alimentos)

        num_recs += 1

        try:
            doc = cursor.next()
        except Exception:
            num_recs += 1
            cursor.close()

    cursor.close()

    # faixas_etarias = sorted(idades)
    # print(faixas_etarias)

    lista_refeicoes = sorted(refeicoes)
    print(lista_refeicoes)

    l_keys = sorted(x_cardapios)
    print(l_keys)

    cardapios={}
    for k in l_keys:
        cardapios[k]=x_cardapios[k]
    print(x_cardapios)
    print(cardapios)

    num_faixas_etareas = len(l_keys)
    print("Num Faixas:",num_faixas_etareas)

    # TODO criar template da planilha: merge das celulas, titulo, faixas e refeições
    # TODO preencher a planilha com os cardapios de cada dia
    # TODO retocar bordas



# - Main ---------------------------------------------------------------------------------------------------------------


if __name__ == "__main__":
    gera_excel('RECR')
