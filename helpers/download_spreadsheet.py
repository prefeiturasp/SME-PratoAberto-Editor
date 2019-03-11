#

# download_spreadsheet.py
#
#   Gera arquivo excel com os cardápios publicados 
#   Ref: SME - Alimentação\Sprint 4 - Correções e Melhorias do Prato, item 663.
#
#   Uso: extrac_02 <periodo> <gestão> <tipo_escola> onde:
#
#                  <periodo>         "AAAAMMDD, AAAAMMDD"  - string com a data_de e data_até 
#                  <gestão>          - string com o tipo de gestão
#                  <tipo_escola>     - string com o tipo da escola
#
#  Nome do arquivo gerado: extracao_AAAAMMDDhhmm.xlsx'
#       onde: AAAA= ano  MM= mês  DD= dia  hh= hora  mm= minutos
#

import re
import os
import sys
import pymongo
from datetime import datetime
from openpyxl import load_workbook
from openpyxl.styles import NamedStyle, Font, Border, Side, Alignment
from copy import copy
from pathlib import Path

# ----------------------------------------------------------------------------------------------------------------------
#
#  Mapeamento das refeições por faixa etária vs unidade e gestão
#

idades = {1: ['A – 0 A 1 MÊS', 'B - 1 A 3 MESES', 'C - 4 A 5 MESES', 'D - 6 A 7 MESES', 'E - 8 A 11 MESES',
              'X - 1A -1A E 11MES', 'F - 2 A 3 ANOS', 'G - 4 A 6 ANOS'],

          2: ['A – 0 A 1 MÊS', 'B - 1 A 3 MESES', 'C - 4 A 5 MESES', 'D - 6 A 7 MESES', 'E - 8 A 11 MESES',
              'X - 1A -1A E 11MES', 'F - 2 A 3 ANOS', 'G - 4 A 6 ANOS', 'H – ADULTO'],

          3: ['A – 0 A 1 MÊS', 'B - 1 A 3 MESES', 'C - 4 A 5 MESES', 'D - 6 A 7 MESES', 'E - 8 A 11 MESES',
              'X - 1A -1A E 11MES', 'F - 2 A 3 ANOS', 'G - 4 A 6 ANOS', 'W - EMEI DA CEMEI'],

          4: ['H – ADULTO', 'Z - UNIDADES SEM FAIXA'],

          5: ['D - 0 A 5 MESES', 'D - 6 MESES', 'D - 7 MESES', 'E - 8 A 11 MESES', 'X - 1A -1A E 11MESES',
              'I - 2 A 6 ANOS'],

          6: ['D - 0 A 5 MESES', 'D - 6 MESES', 'D - 7 MESES', 'E - 8 A 11 MESES', 'X - 1A -1A E 11MESES',
              'I - 2 A 6 ANOS', 'W - EMEI DA CEMEI'],

          7: ['Z – UNIDADES SEM FAIXA'] }

refeicoes = {1: 'D – DESJEJUM',
             2: 'C – COLACAO',
             3: 'A – ALMOCO',
             4: 'L – LANCHE',
             5: 'J – JANTAR',
             6: 'AA - ALMOCO ADULTO',
             7: 'L4 - LANCHE 4 HORAS',
             8: 'L5 - LANCHE 5 HORAS',
             9: 'R1 - REFEICAO 1',
             10: 'MS - MERENDA SECA',
             11: 'MI - MERENDA INICIAL',
            'WD':['D – DESJEJUM',
                  'A – ALMOCO'],
            'WT':['L5 - LANCHE 5 HORAS',
                  'R1 - REFEICAO 1'] }

unidades = {'CEI MUNICIPAL':{
            'DIRETA'      : {'fx_etaria': 1, 'refeicao': [1, 2, 3, 4, 5], 'template': 'Template_1.xlsx'},
            'MISTA'       : {'fx_etaria': 1, 'refeicao': [1, 2, 3, 4, 5], 'template': 'Template_1.xlsx'},
            'TERCEIRIZADA': {'fx_etaria': 5, 'refeicao': [1, 2, 3, 4, 5], 'template': 'Template_5.xlsx'}},

            'CCI'         : {
            'DIRETA'      : {'fx_etaria': 1, 'refeicao': [1, 2, 3, 4, 5], 'template': 'Template_1.xlsx'},
            'MISTA'       : {'fx_etaria': 1, 'refeicao': [1, 2, 3, 4, 5], 'template': 'Template_1.xlsx'},
            'TERCEIRIZADA': {'fx_etaria': 5, 'refeicao': [1, 2, 3, 4, 5], 'template': 'Template_5.xlsx'}},

            'CEI PARCEIRO': {
            'DIRETA'      : {'fx_etaria': 2, 'refeicao': [1, 2, 3, 4, 6], 'template': 'Template_2.xlsx'},
            'MISTA'       : {'fx_etaria': 1, 'refeicao': [1, 2, 3, 4, 6], 'template': 'Template_2.xlsx'}},

            'PROJETO CECI': {
            'DIRETA'      : {'fx_etaria': 2, 'refeicao': [1, 2, 3, 4, 6], 'template': 'Template_2.xlsx'},
            'MISTA'       : {'fx_etaria': 1, 'refeicao': [1, 2, 3, 4, 6], 'template': 'Template_2.xlsx'}},

            'CEMEI' 	  : {
            'DIRETA'      : {'fx_etaria': 3, 'refeicao': [1, 2, 3, 4, 5, 'WD'], 'template': 'Template_3.xlsx'},
            'MISTA'       : {'fx_etaria': 3, 'refeicao': [1, 2, 3, 4, 5, 'WD'], 'template': 'Template_3.xlsx'},
            'TERCEIRIZADA': {'fx_etaria': 6, 'refeicao': [1, 2, 3, 4, 5, 'WT'], 'template': 'Template_6.xlsx'}},

            'EMEI'	  : {
            'DIREITA'     : {'fx_etaria': 4, 'refeicao': [11, 6, 7, 8, 9, 10], 'template': 'Template_4.xlsx'},
            'MISTA'       : {'fx_etaria': 4, 'refeicao': [11, 6, 7, 8, 9, 10], 'template': 'Template_4.xlsx'},
            'TERCEIRIZADA': {'fx_etaria': 7, 'refeicao': [11, 6, 7, 8, 9, 10], 'template': 'Template_7.xlsx'}},

            'EMEF'	  : {
            'DIRETA'      : {'fx_etaria': 4, 'refeicao': [11, 6, 7, 8, 9, 10], 'template': 'Template_4.xlsx'},
            'MISTA'       : {'fx_etaria': 4, 'refeicao': [11, 6, 7, 8, 9, 10], 'template': 'Template_4.xlsx'},
            'TERCEIRIZADA': {'fx_etaria': 7, 'refeicao': [11, 6, 7, 8, 9, 10], 'template': 'Template_7.xlsx'}},

            'CIEJA'	  : {
            'DIRETA'      : {'fx_etaria': 4, 'refeicao': [11, 6, 7, 8, 9, 10], 'template': 'Template_4.xlsx'},
            'MISTA'       : {'fx_etaria': 4, 'refeicao': [11, 6, 7, 8, 9, 10], 'template': 'Template_4.xlsx'},
            'TERCEIRIZADA': {'fx_etaria': 7, 'refeicao': [11, 6, 7, 8, 9, 10], 'template': 'Template_7.xlsx'}},

            'EMEBS'	  : {
            'DIRETA'      : {'fx_etaria' :4, 'refeicao': [11, 6, 7, 8, 9, 10], 'template': 'Template_4.xlsx'},
            'MISTA'       : {'fx_etaria': 4, 'refeicao': [11, 6, 7, 8, 9, 10], 'template': 'Template_4.xlsx'},
            'TERCEIRIZADA': {'fx_etaria': 7, 'refeicao': [11, 6, 7, 8, 9, 10], 'template': 'Template_7.xlsx'}},

            'SME CONVÊNIO': {
            'DIRETA'      : {'fx_etaria': 4, 'refeicao': [11, 6, 7, 8, 9, 10], 'template': 'Template_4.xlsx'},
            'MISTA'       : {'fx_etaria': 4, 'refeicao': [11, 6, 7, 8, 9, 10], 'template': 'Template_4.xlsx'},
            'TERCEIRIZADA': {'fx_etaria': 7, 'refeicao': [11, 6, 7, 8, 9, 10], 'template': 'Template_7.xlsx'}}
          }
    
# ----------------------------------------------------------------------------------------------------------------------
def get_num_semana(s_data):
    dta = s_data[:4]+'-'+s_data[4:][:2]+'-'+s_data[6:]
    tz_dta = datetime.strptime(dta,'%Y-%m-%d')
    return (tz_dta.isocalendar()[1])

# ----------------------------------------------------------------------------------------------------------------------
def estilo(n_cels, pl):
   bd = Side(style='thick', color="000000")
   c=2
   while c < n_cels:
      pl.cell(row=1, column=c).border = Border(left=bd, top=bd, right=bd, bottom=bd)
      pl.cell(row=3, column=c).border = Border(left=bd, top=bd, right=bd, bottom=bd)
      c +=1
      
# ----------------------------------------------------------------------------------------------------------------------
def merge_cels(n_faixas,n_refeicoes,pl):
    #..Dia
    pl.merge_cells(start_row=1, start_column=1, end_row=3, end_column=1)

    #..Titulo
    n_col = (n_faixas * n_refeicoes) + 1
    pl.merge_cells(start_row=1, start_column=2, end_row=1, end_column=n_col)

    #..Faixas etárias
    fx=0
    while fx < n_faixas:
        pl.merge_cells(start_row=2, start_column=2+(n_refeicoes * fx), end_row=2, end_column=1+n_refeicoes+(fx*n_refeicoes))
        fx += 1
    
# ----------------------------------------------------------------------------------------------------------------------
def titulos(n_faixas, n_refeicoes, escola, gestao, dt_publicacao, pl):
    f=0
    fx=0
    while f < (n_faixas * n_refeicoes):
       pl.cell(row=2, column=2+f).value = idades[unidades[escola][gestao]['fx_etaria']][fx] + ' Publicação: ' + dt_publicacao
       c=0
       while c < n_refeicoes:
          pl.cell(row=3, column=c+2+f).value = refeicoes[unidades[escola][gestao]['refeicao'][c]]
          c +=1
       f += n_refeicoes
       fx +=1

# ----------------------------------------------------------------------------------------------------------------------
def gera_excel(parametros):
    try:
        #..Acesso ao banco de dados
        client = pymongo.MongoClient('localhost', 27017)
        db = client.pratoaberto
        collection = db.cardapios

        #..Data e hora da emissão
        data = (datetime.now().isoformat(timespec='minutes')).split('T')
        hoje, hora = data[0], data[1]
        dt = ''.join(x for x in hoje.split('-'))
        hr = ''.join(x for x in hora.split(':'))

        #..Parámetros para a extração e gravação
        data_de = parametros.split(',')[0].strip()
        data_ate= parametros.split(',')[1].strip()
        tipo_gestao = parametros.split(',')[2].strip()
        tipo_escola = parametros.split(',')[3].strip()
        t_status = 'PUBLICADO'

        #..Templates
        arq_nome = unidades[tipo_escola][tipo_gestao]['template']
        #..template = os.path.dirname(__file__) + '\\' + arq_nome
        template = Path(os.path.abspath('static/spreadsheet'))/arq_nome

        #..Arquivo excel de saída
        arq_nome = 'Cardapios_'+tipo_escola + '_'+ dt + hr + '.xlsx'
        #..xls = os.path.dirname(__file__)+arq_nome
        xls = Path(os.path.abspath('tmp/'))/arq_nome

        #..Datas do período e numero das semanas
        dta_de = data_de[6:] + '-' + data_de[4:][:2] + '-' + data_de[:4]
        dta_ate = data_ate[6:] + '-' + data_ate[4:][:2] + '-' + data_ate[:4]
        w_de, w_ate = str(get_num_semana(data_de)), str(get_num_semana(data_ate))

        #..Meses e dias da semana
        meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junio', 'Julio', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezemnbro']
        dias_semana = ['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo']

        #..Elementos
        num_faixas=len(idades[unidades[tipo_escola][tipo_gestao]['fx_etaria']])
        num_refeicoes=len(unidades[tipo_escola][tipo_gestao]['refeicao'])
        cabecalho = 'CARDÁPIOS ' +tipo_escola+ ' - ' +tipo_gestao+ ' - Período: ' +dta_de+ ' até ' +dta_ate+ ' - Semanas: ' +w_de+ ' a ' +w_ate
        #..Verificação de existência de dados
        consulta = [{"$match":{"tipo_unidade":tipo_escola,"data":{"$gte":data_de,"$lte":data_ate},"status":t_status,"tipo_atendimento":tipo_gestao,"data_publicacao":{"$exists":"true"}}},{"$sort":{"data":1}},{"$count":"num_regs"}]
        num_regs = 0
        for i in collection.aggregate(consulta):
            num_regs = i['num_regs']

        num_semanas = int(w_ate) - int(w_de) + 1
        ns = 2

        if num_regs > 0:
           while ns <= num_semanas:
              try:
                 #..Abre o template
                 wb = load_workbook(filename=template)
                 new_wb = wb.create_sheet('Semana '+str(ns))
                 default_sheet = wb['Semana 1']

                 for row in default_sheet.rows:
                    for cell in row:
                       new_cell = new_wb.cell(row=cell.row, column=cell.col_idx, value=cell.value)
                       if cell.has_style:
                          new_cell.font = copy(cell.font)
                          new_cell.border = copy(cell.border)
                          new_cell.fill = copy(cell.fill)
                          new_cell.number_format = copy(cell.number_format)
                          new_cell.protection = copy(cell.protection)
                          new_cell.alignment = copy(cell.alignment)
              except Exception as e:
                 print('Arquivo template {0} não encontrado.'.format(template))
                 return -1

              #..Formata celulas dos titulos
              merge_cels(num_faixas,num_refeicoes,new_wb)

              #..Grava mais uma semana no teplate
              #arq_nome = 'x' + unidades[tipo_escola][tipo_gestao]['template']
              #template = os.path.dirname(__file__) + '\\' + arq_nome

              arq_nome = 'x' + unidades[tipo_escola][tipo_gestao]['template']
              template = Path(os.path.abspath('static/spreadsheet'))/arq_nome

              wb.save(template)
              ns +=1

           #..Formata aba 'Semana 1'
           wb = load_workbook(filename=template)
           ws = wb['Semana 1']
           merge_cels(num_faixas, num_refeicoes, ws)
           wb.save(template)

           # ..Abre o template com todas as semanas
           wb = load_workbook(filename=template)

           #..Preenche a planilha
           consulta = [{"$match":{"tipo_unidade":tipo_escola,"data":{"$gte": data_de,"$lte": data_ate},"status":t_status,"tipo_atendimento":tipo_gestao,"data_publicacao":{"$exists":"true"}}},{"$sort":{"data": 1}}]

           #..Monta a estrutura para receber os cardápios do dia
           cardapios_dia = {}
           cf = 0
           cr = 0
           while cf < num_faixas:
               cardapios_dia[idades[unidades[tipo_escola][tipo_gestao]['fx_etaria']][cf]] = {}
               while cr < num_refeicoes:
                   ref_n = refeicoes[unidades[tipo_escola][tipo_gestao]['refeicao'][cr]]
                   cardapios_dia[idades[unidades[tipo_escola][tipo_gestao]['fx_etaria']][cf]][ref_n]=[]
                   cr += 1
               cf += 1
               cr = 0

           np = 0
           ini = 1

           semana_ref = ''
           n_semana_ref = 0
              
           for doc in collection.aggregate(consulta):

               #..Dia, semana
               dta_ref = doc['data']
               
               num_dia = datetime.weekday(datetime(int(dta_ref[:4]), int(dta_ref[4:][:2]), int(dta_ref[6:])))
               nom_dia = dias_semana[num_dia]

               dta_pub = doc['data_publicacao'][:9]
               dia = nom_dia + ' ' + dta_ref[6:] + '/' + meses[int(dta_ref[4:][:2]) - 1][:3]

               if semana_ref != str(get_num_semana(dta_ref)) + dta_ref:
                      
                   if n_semana_ref != get_num_semana(dta_ref):   #..mudou a semana

                       n_semana_ref = get_num_semana(dta_ref)
                       semana_ref = str(get_num_semana(dta_ref)) + dta_ref
                       
                       np +=1
                       ws = wb['Semana '+str(np)]
                       lin = 4

                       #..Titulos e formatação
                       ws.cell(row=1, column=2).value = cabecalho
                       titulos(num_faixas,num_refeicoes,tipo_escola,tipo_gestao,dta_pub,ws)
                       estilo((num_refeicoes * num_faixas)+2,ws)

                       wb.save(template)

                       #..limpa es cardapios do dia
                       cf = 0
                       cr = 0
                       while cf < num_faixas:
                           while cr < num_refeicoes:
                               ref_n = refeicoes[unidades[tipo_escola][tipo_gestao][r'refeicao'][cr]]
                               cardapios_dia[idades[unidades[tipo_escola][tipo_gestao][r'fx_etaria']][cf]][ref_n]=[]
                               cr += 1
                           cf += 1
                           cr = 0

                   else:    #..mudou o dia, preenche a planilha com os cardapios do dia
                       semana_ref = str(get_num_semana(dta_ref)) + dta_ref
                       col = 1
                       ws.cell(row=lin, column=col).value = dia
                       col += 1
                       #..Preenche a planilha com os cardápios
                       cf = 0
                       cr = 0
                       while cf < num_faixas:
                           while cr < num_refeicoes:
                               ref_n = refeicoes[unidades[tipo_escola][tipo_gestao][r'refeicao'][cr]]
                               if len(cardapios_dia[idades[unidades[tipo_escola][tipo_gestao][r'fx_etaria']][cf]][ref_n]) >0:
                                  ws.cell(row=lin, column=col).value = cardapios_dia[idades[unidades[tipo_escola][tipo_gestao][r'fx_etaria']][cf]][ref_n][0]
                               else:
                                  ws.cell(row=lin, column=col).value = 'N/D'
                               col += 1
                               cr += 1
                           cf += 1
                           cr = 0

                       lin +=1
                       wb.save(template)

                       #..limpa os cardapios do dia
                       cf = 0
                       cr = 0
                       while cf < num_faixas:
                           while cr < num_refeicoes:
                               ref_n = refeicoes[unidades[tipo_escola][tipo_gestao][r'refeicao'][cr]]
                               cardapios_dia[idades[unidades[tipo_escola][tipo_gestao][r'fx_etaria']][cf]][ref_n]=[]
                               cr += 1
                           cf += 1
                           cr = 0


               #..Preenche a estrutura com os cardápios do dia
               faixa = doc[r'idade'].strip()
               l_refeicoes = list(doc[r'cardapio'].keys())

               for r in l_refeicoes:
                   if faixa in cardapios_dia:
                       if r in cardapios_dia[faixa]:
                           cardapios_dia[faixa][r].append(', '.join(doc[r'cardapio'][r]))


           #..Apaga planilhas vazias
           num_semanas = int(w_ate) - int(w_de) + 1
           ns = 1

           while ns <= num_semanas:
               ws=wb['Semana '+str(ns)]
               v = ws['B3'].value
               if v == None:
                   wb.remove(wb['Semana '+str(ns)])
               ns += 1
         
           wb.save(xls)
        else:
           print('Não há cardápios cadastrados nesse período.')
           
    except Exception as e:
        print('Não foi possível gerar o arquivo excel.')
        print(e)


# - Main ---------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":

    if len(sys.argv) != 4:
        print(len(sys.argv))
        print('Uso: extrac_cardapios <periodo> <gestão> <tipo_escola>   onde:')
        print('          periodo = string: "AAAAMMDD, AAAAMMDD"')
        print('          gestão  = string: tipo de gestão')
        print('      tipo_escola = string: tipo da escola')
    else:
        params = [p for p in sys.argv]
        params.__delitem__(0)

    gera_excel(params)






