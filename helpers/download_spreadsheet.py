#
# extrac_cardapios_01.py
#
#   Gera arquivo excel com os cardápios publicados das terceirizadas para as escolas tipo CEI, EMEI, EMEF e EJA
#   Ref: SME - Alimentação\Sprint 4 - Correções e Melhorias do Prato, item 663.
#
#   Uso: extrac_cardapios_01 <ano> <mes>   onde: ano=AAAA  mes=MM
#
#   Nome do arquivo gerado: Cardapios_CEI_EMEI_EMEF_EJA_AAAAMMDDhhmm.xlsx'
#     onde: AAAA= ano  MM= mês  DD= dia  hh= hora  mm= minutos
#

import re
import os
from pathlib import Path
from datetime import datetime
from openpyxl import load_workbook
from pymongo import MongoClient


# ----------------------------------------------------------------------------------------------------------------------
def gera_excel(ano_mes):
    try:
        # ..Acesso ao banco de dados
        client = MongoClient('localhost', 27017)
        db = client.pratoaberto
        collection = db.cardapios

        # ..Path para o Template e arquivo gerado
        # path_template = os.path.join('../static/speadsheet','Template_w.xlsx',)
        path_template = Path(os.path.abspath('static/speadsheet')) /'Template_w.xlsx'
        path_arquivo = Path(os.path.abspath('tmp/'))


        # ..Parámetros para extração
        tipo_terceirizada = 'TERCEIRIZADA'
        tipo_cei = 'CEI'
        tipo_eja = 'CIEJA'
        tipo_emei = 'EMEI'
        tipo_emef = 'EMEF'
        tipo_cemei = 'CEMEI'

        data = (datetime.now().isoformat(timespec='minutes')).split('T')
        hoje, hora = data[0], data[1]

        meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junio', 'Julio', 'Agosto', 'Setembro', 'Outubro',
                 'Novembro', 'Dezemnbro']
        dias_semana = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']

        cardapio1 = {'D - 0 A 5 MESES': {'A - ALMOCO': [], 'C - COLACAO': [], 'D - DESJEJUM': [], 'L - LANCHE': [],
                                         'L5 - LANCHE 5 HORAS': []},
                     'D - 6 MESES': {'A - ALMOCO': [], 'C - COLACAO': [], 'D - DESJEJUM': [], 'L - LANCHE': [],
                                     'L5 - LANCHE 5 HORAS': []},
                     'D - 7 MESES': {'A - ALMOCO': [], 'C - COLACAO': [], 'D - DESJEJUM': [], 'L - LANCHE': [],
                                     'L5 - LANCHE 5 HORAS': []},
                     'E - 8 A 11 MESES': {'A - ALMOCO': [], 'C - COLACAO': [], 'D - DESJEJUM': [], 'L - LANCHE': [],
                                          'L5 - LANCHE 5 HORAS': []},
                     'X - 1A -1A E 11MES': {'A - ALMOCO': [], 'C - COLACAO': [], 'D - DESJEJUM': [], 'L - LANCHE': [],
                                            'L5 - LANCHE 5 HORAS': []},
                     'I - 2 A 6 ANOS': {'A - ALMOCO': [], 'C - COLACAO': [], 'D - DESJEJUM': [], 'L - LANCHE': [],
                                        'L5 - LANCHE 5 HORAS': []}}

        cardapio2 = {'L4 - LANCHE 4 HORAS': [], 'L5 - LANCHE 5 HORAS': [], 'R1 - REFEICAO 1': [],
                     'AA - ALMOCO ADULTO': [], 'MS - MERENDA SECA': []}

        titulos = {0: "Cardápio de CEI - Terceirizadas - " + meses[int(ano_mes[4:]) - 1].upper() + " " + ano_mes[
                                                                                                         :4] + " (PRM)                 ** Emissão: " + hoje + ' ' + hora,
                   1: ["0 a 5 meses", "6 meses", "7 meses", "8 A 11 meses", "1 ano a 1 ano e 11 meses", "2 a 6 anos"],
                   2: ["DIA", "Desjejum", "Almoço", "Lanche", "Ref da Tarde",
                       "Desjejum", "Colação (Papa de Fruta)", "Almoço (Papa Principal e Papa de Fruta/Suco)", "Lanche",
                       "Refeição da Tarde (Fórmula e Papa de Fruta)",
                       "Desjejum", "Colação (Papa de Fruta)", "Almoço (Papa Principal e Papa de Fruta/Suco)", "Lanche",
                       "Refeição da Tarde (Fórmula e Papa de Fruta)",
                       "Desjejum", "Colação (Fruta)", "Almoço (Refeição e Fruta/Suco)", "Lanche",
                       "Refeição da Tarde (Sopa e Fruta)",
                       "Desjejum", "Colação (Fruta)", "Almoço (Refeição e Fruta/Suco)", "Lanche",
                       "Refeição da Tarde (Sopa e Fruta)",
                       "Desjejum", "Colação (Fruta)", "Almoço (Refeição e Fruta/Suco)", "Lanche",
                       "Refeição da Tarde (Sopa e Fruta)"],
                   3: "Cardápio de EMEI, EMEF e EJA - Terceirizadas - " + meses[
                       int(ano_mes[4:]) - 1].upper() + " " + ano_mes[
                                                             :4] + " (PRM)       ** Emissão: " + hoje + ' ' + hora,
                   4: ["DIA", "Lanche de 4hs ou 8hs", "Lanche de 5hs ou 6 hs", "Lanche", "Refeição", "Almoço Adulto",
                       "Merenda Seca"]}

        # ..Cursor com os cardápios das terceirizadas para escolas tipo CEI
        cursor1 = collection.find({"$and": [{"data": {"$regex": '^' + re.escape(ano_mes)}},
                                            {"tipo_atendimento": tipo_terceirizada},
                                            {"status": "PUBLICADO"},
                                            {"tipo_unidade": {"$regex": '^' + re.escape(tipo_cei)}},
                                            {"idade": {"$in": ["D - 0 A 5 MESES", "D - 6 MESES", "D - 7 MESES",
                                                               "E - 8 A 11 MESES", "X - 1A -1A E 11MES",
                                                               "I - 2 A 6 ANOS"]}}
                                            ]}).sort([("data", 1), ("cardapio", 1)])

        # ..Cursor com os cardápios das terceirizadas para escolas tipo EMEI, EMEF e EJA
        cursor2 = collection.find({"data": {"$regex": '^' + re.escape(ano_mes)},
                                   "$or": [{"tipo_unidade": {"$regex": '^' + re.escape(tipo_eja)}},
                                           {"tipo_unidade": {"$regex": '^' + re.escape(tipo_cemei)}},
                                           {"tipo_unidade": {"$regex": '^' + re.escape(tipo_emei)}},
                                           {"tipo_unidade": {"$regex": '^' + re.escape(tipo_emef)}}],
                                   "$and": [{"status": "PUBLICADO"},
                                            {"tipo_atendimento": tipo_terceirizada}]
                                   }).sort([("data", 1), ("cardapio", 1)])

        try:
            # ..Abre o arquivo excel template
            wb = load_workbook(filename=path_template)
        except Exception as e:
            print('Arquivo template não encontrado.')
            return False

        # ..Processa extração para as CEI
        if cursor1.count() == 0:
            print("Não há cardápios cadastrados de terceirizadas para as CEI no mês de {0} de {1}.".format(
                meses[int(ano_mes[4:]) - 1], ano_mes[:4]))
        else:

            ws = wb["CEI"]

            # ..Preenche a planilha
            num_recs = 0
            lin, col = 5, 2

            cursor1.rewind()
            doc = cursor1.next()

            # ..Titulos
            ws.cell(row=1, column=1).value = titulos[0]

            dta_pub = doc['data'][4:][2:] + '/' + doc['data'][4:][:2] + '/' + doc['data'][:4]
            meses[int(ano_mes[4:]) - 1].upper() + " " + ano_mes[:4]
            ws.cell(row=2, column=1).value = 'Data de Publicação do Cardápio: ' + dta_pub

            cursor1.rewind()
            dta_ant = doc['data']

            while num_recs <= cursor1.count():
                try:
                    doc = cursor1.next()
                except Exception:
                    num_recs += 1
                    cursor1.close()
                else:
                    if dta_ant != doc['data']:
                        # ..Grava cardápio do dia
                        num_dia = datetime.weekday(datetime(int(dta_ant[:4]), int(dta_ant[4:][:2]), int(dta_ant[6:])))
                        nom_dia = dias_semana[num_dia]
                        dia = nom_dia + ' ' + dta_ant[6:] + '/' + meses[int(dta_ant[4:][:2]) - 1][:3]

                        ws.cell(row=lin, column=1).value = dia
                        ws.cell(row=lin, column=2).value = (
                            cardapio1['D - 0 A 5 MESES']['D - DESJEJUM'] if cardapio1['D - 0 A 5 MESES'][
                                'D - DESJEJUM'] else 'n/a')
                        ws.cell(row=lin, column=3).value = (
                            cardapio1['D - 0 A 5 MESES']['A - ALMOCO'] if cardapio1['D - 0 A 5 MESES'][
                                'A - ALMOCO'] else 'n/a')
                        ws.cell(row=lin, column=4).value = (
                            cardapio1['D - 0 A 5 MESES']['L - LANCHE'] if cardapio1['D - 0 A 5 MESES'][
                                'L - LANCHE'] else 'n/a')
                        ws.cell(row=lin, column=5).value = (
                            cardapio1['D - 0 A 5 MESES']['L5 - LANCHE 5 HORAS'] if cardapio1['D - 0 A 5 MESES'][
                                'L5 - LANCHE 5 HORAS'] else 'n/a')

                        ws.cell(row=lin, column=6).value = (
                            cardapio1['D - 6 MESES']['D - DESJEJUM'] if cardapio1['D - 6 MESES'][
                                'D - DESJEJUM'] else 'n/a')
                        ws.cell(row=lin, column=7).value = (
                            cardapio1['D - 6 MESES']['C - COLACAO'] if cardapio1['D - 6 MESES'][
                                'C - COLACAO'] else 'n/a')
                        ws.cell(row=lin, column=8).value = (
                            cardapio1['D - 6 MESES']['A - ALMOCO'] if cardapio1['D - 6 MESES']['A - ALMOCO'] else 'n/a')
                        ws.cell(row=lin, column=9).value = (
                            cardapio1['D - 6 MESES']['L - LANCHE'] if cardapio1['D - 6 MESES']['L - LANCHE'] else 'n/a')
                        ws.cell(row=lin, column=10).value = (
                            cardapio1['D - 6 MESES']['L5 - LANCHE 5 HORAS'] if cardapio1['D - 6 MESES'][
                                'L5 - LANCHE 5 HORAS'] else 'n/a')

                        ws.cell(row=lin, column=11).value = (
                            cardapio1['D - 7 MESES']['D - DESJEJUM'] if cardapio1['D - 7 MESES'][
                                'D - DESJEJUM'] else 'n/a')
                        ws.cell(row=lin, column=12).value = (
                            cardapio1['D - 7 MESES']['C - COLACAO'] if cardapio1['D - 7 MESES'][
                                'C - COLACAO'] else 'n/a')
                        ws.cell(row=lin, column=13).value = (
                            cardapio1['D - 7 MESES']['A - ALMOCO'] if cardapio1['D - 7 MESES']['A - ALMOCO'] else 'n/a')
                        ws.cell(row=lin, column=14).value = (
                            cardapio1['D - 7 MESES']['L - LANCHE'] if cardapio1['D - 7 MESES']['L - LANCHE'] else 'n/a')
                        ws.cell(row=lin, column=15).value = (
                            cardapio1['D - 7 MESES']['L5 - LANCHE 5 HORAS'] if cardapio1['D - 7 MESES'][
                                'L5 - LANCHE 5 HORAS'] else 'n/a')

                        ws.cell(row=lin, column=16).value = (
                            cardapio1['E - 8 A 11 MESES']['D - DESJEJUM'] if cardapio1['E - 8 A 11 MESES'][
                                'D - DESJEJUM'] else 'n/a')
                        ws.cell(row=lin, column=17).value = (
                            cardapio1['E - 8 A 11 MESES']['C - COLACAO'] if cardapio1['E - 8 A 11 MESES'][
                                'C - COLACAO'] else 'n/a')
                        ws.cell(row=lin, column=18).value = (
                            cardapio1['E - 8 A 11 MESES']['A - ALMOCO'] if cardapio1['E - 8 A 11 MESES'][
                                'A - ALMOCO'] else 'n/a')
                        ws.cell(row=lin, column=19).value = (
                            cardapio1['E - 8 A 11 MESES']['L - LANCHE'] if cardapio1['E - 8 A 11 MESES'][
                                'L - LANCHE'] else 'n/a')
                        ws.cell(row=lin, column=20).value = (
                            cardapio1['E - 8 A 11 MESES']['L5 - LANCHE 5 HORAS'] if cardapio1['E - 8 A 11 MESES'][
                                'L5 - LANCHE 5 HORAS'] else 'n/a')

                        ws.cell(row=lin, column=21).value = (
                            cardapio1['X - 1A -1A E 11MES']['D - DESJEJUM'] if cardapio1['X - 1A -1A E 11MES'][
                                'D - DESJEJUM'] else 'n/a')
                        ws.cell(row=lin, column=22).value = (
                            cardapio1['X - 1A -1A E 11MES']['C - COLACAO'] if cardapio1['X - 1A -1A E 11MES'][
                                'C - COLACAO'] else 'n/a')
                        ws.cell(row=lin, column=23).value = (
                            cardapio1['X - 1A -1A E 11MES']['A - ALMOCO'] if cardapio1['X - 1A -1A E 11MES'][
                                'A - ALMOCO'] else 'n/a')
                        ws.cell(row=lin, column=24).value = (
                            cardapio1['X - 1A -1A E 11MES']['L - LANCHE'] if cardapio1['X - 1A -1A E 11MES'][
                                'L - LANCHE'] else 'n/a')
                        ws.cell(row=lin, column=25).value = (
                            cardapio1['X - 1A -1A E 11MES']['L5 - LANCHE 5 HORAS'] if cardapio1['X - 1A -1A E 11MES'][
                                'L5 - LANCHE 5 HORAS'] else 'n/a')

                        ws.cell(row=lin, column=26).value = (
                            cardapio1['I - 2 A 6 ANOS']['D - DESJEJUM'] if cardapio1['I - 2 A 6 ANOS'][
                                'D - DESJEJUM'] else 'n/a')
                        ws.cell(row=lin, column=27).value = (
                            cardapio1['I - 2 A 6 ANOS']['C - COLACAO'] if cardapio1['I - 2 A 6 ANOS'][
                                'C - COLACAO'] else 'n/a')
                        ws.cell(row=lin, column=28).value = (
                            cardapio1['I - 2 A 6 ANOS']['A - ALMOCO'] if cardapio1['I - 2 A 6 ANOS'][
                                'A - ALMOCO'] else 'n/a')
                        ws.cell(row=lin, column=29).value = (
                            cardapio1['I - 2 A 6 ANOS']['L - LANCHE'] if cardapio1['I - 2 A 6 ANOS'][
                                'L - LANCHE'] else 'n/a')
                        ws.cell(row=lin, column=30).value = (
                            cardapio1['I - 2 A 6 ANOS']['L5 - LANCHE 5 HORAS'] if cardapio1['I - 2 A 6 ANOS'][
                                'L5 - LANCHE 5 HORAS'] else 'n/a')

                        cardapio1 = {
                            'D - 0 A 5 MESES': {'A - ALMOCO': [], 'C - COLACAO': [], 'D - DESJEJUM': [],
                                                'L - LANCHE': [], 'L5 - LANCHE 5 HORAS': []},
                            'D - 6 MESES': {'A - ALMOCO': [], 'C - COLACAO': [], 'D - DESJEJUM': [], 'L - LANCHE': [],
                                            'L5 - LANCHE 5 HORAS': []},
                            'D - 7 MESES': {'A - ALMOCO': [], 'C - COLACAO': [], 'D - DESJEJUM': [], 'L - LANCHE': [],
                                            'L5 - LANCHE 5 HORAS': []},
                            'E - 8 A 11 MESES': {'A - ALMOCO': [], 'C - COLACAO': [], 'D - DESJEJUM': [],
                                                 'L - LANCHE': [], 'L5 - LANCHE 5 HORAS': []},
                            'X - 1A -1A E 11MES': {'A - ALMOCO': [], 'C - COLACAO': [], 'D - DESJEJUM': [],
                                                   'L - LANCHE': [], 'L5 - LANCHE 5 HORAS': []},
                            'I - 2 A 6 ANOS': {'A - ALMOCO': [], 'C - COLACAO': [], 'D - DESJEJUM': [],
                                               'L - LANCHE': [], 'L5 - LANCHE 5 HORAS': []}}

                        lin += 1

                    else:
                        idade = doc['idade']
                        l_refeicoes = list(doc['cardapio'].keys())
                        for refeicao in l_refeicoes:
                            if idade in cardapio1:
                                if refeicao in cardapio1[idade]:
                                    cardapio1[idade][refeicao] = ', '.join(doc['cardapio'][refeicao])

                        num_recs += 1

                    dta_ant = doc['data']

        # ..Processa extração das EMEI, EMEF e EJA
        if cursor2.count() == 0:
            print(
                "Não há cardápios cadastrados de terceirizadas para as EMEI, EMEF e EJA cadastrados no mês de {0} de {1}.".format(
                    meses[int(ano_mes[4:]) - 1], ano_mes[:4]))
        else:
            # ..Seleciona a aba do template
            ws = wb["EI, EF e EJ"]

            # ..Preenche a planilha
            lin, col = 5, 2

            cursor2.rewind()
            doc = cursor2.next()

            # ..Titulos
            ws.cell(row=1, column=1).value = titulos[3]

            dta_pub = doc['data'][4:][2:] + '/' + doc['data'][4:][:2] + '/' + doc['data'][:4]
            meses[int(ano_mes[4:]) - 1].upper() + " " + ano_mes[:4]
            ws.cell(row=2, column=1).value = 'Data de Publicação do Cardápio: ' + dta_pub

            cursor2.rewind()
            dta_ant = doc['data']

            num_recs = 0

            while num_recs <= cursor2.count():
                try:
                    doc = cursor2.next()
                except Exception:
                    num_recs += 1
                    cursor2.close()
                else:
                    if dta_ant != doc['data']:
                        # ..Grava cardápio do dia
                        num_dia = datetime.weekday(datetime(int(dta_ant[:4]), int(dta_ant[4:][:2]), int(dta_ant[6:])))
                        nom_dia = dias_semana[num_dia]
                        dia = nom_dia + ' ' + dta_ant[6:] + '/' + meses[int(dta_ant[4:][:2]) - 1][:3]

                        ws.cell(row=lin, column=1).value = dia
                        ws.cell(row=lin, column=2).value = (
                            cardapio2['L4 - LANCHE 4 HORAS'] if cardapio2['L4 - LANCHE 4 HORAS'] else 'n/a')
                        ws.cell(row=lin, column=3).value = (
                            cardapio2['L5 - LANCHE 5 HORAS'] if cardapio2['L5 - LANCHE 5 HORAS'] else 'n/a')
                        ws.cell(row=lin, column=4).value = (
                            cardapio2['R1 - REFEICAO 1'] if cardapio2['R1 - REFEICAO 1'] else 'n/a')
                        ws.cell(row=lin, column=5).value = (
                            cardapio2['AA - ALMOCO ADULTO'] if cardapio2['AA - ALMOCO ADULTO'] else 'n/a')
                        ws.cell(row=lin, column=6).value = (
                            cardapio2['MS - MERENDA SECA'] if cardapio2['MS - MERENDA SECA'] else 'n/a')

                        cardapio2 = {'L4 - LANCHE 4 HORAS': [], 'L5 - LANCHE 5 HORAS': [],
                                     'R1 - REFEICAO 1': [], 'AA - ALMOCO ADULTO': [], 'MS - MERENDA SECA': []}

                        lin += 1

                    else:
                        l_refeicoes = list(doc['cardapio'].keys())

                        for refeicao in l_refeicoes:
                            if refeicao in cardapio2:
                                cardapio2[refeicao] = ', '.join(doc['cardapio'][refeicao])

                        num_recs += 1

                    dta_ant = doc['data']

        dt = ''.join(x for x in hoje.split('-'))
        hr = ''.join(x for x in hora.split(':'))

        nome_arquivo = 'Cardapios_CEI_EMEI_EMEF_EJA_' + dt + hr + '.xlsx'

        path_absolute = '{}/{}'.format(path_arquivo,nome_arquivo)
        wb.save( path_absolute )

        return path_absolute

    except Exception as e:
        print('Não foi possível gerar o arquivo excel.')
        print(e)
        return False
