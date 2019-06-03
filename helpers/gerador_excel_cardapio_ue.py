import os
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Border, Side, Alignment

import requests

XLSX_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tmp'))
DATA_GERACAO = str(datetime.now()).replace(' ', '_').replace(':', '_').replace('.', '_')
ORDENS_REFEICOES = {
    "D - DESJEJUM": "Desjejum",
    "C - COLACAO": "Colação",
    "A - ALMOCO": "Almoço",
    "L - LANCHE": "Lanche",
    "J - JANTAR": "Refeição da Tarde",
    "L4 - LANCHE 4 HORAS": "Lanche - Permanência de 4 ou 8 horas",
    "L5 - LANCHE 5 HORAS": "Lanche - Permanência de 5 ou 6 horas",
    "L5 - LANCHE 5 OU 6 HORAS": "Lanche - Permanência de 5 ou 6 horas",
    "LPI - LANCHE PERIODO INTEG": "Lanche Período Integral",
    "R1 - REFEICAO 1": "Refeição",
    "MS - MERENDA SECA": "Merenda Seca",
    "MI - MERENDA INICIAL": "Merenda Inicial",
    "RP - REFEIÇÃO PROFESSOR": "Refeição - Professor",
    "FPJ - FILHOS PRO JOVEM": "Pro Jovem (filhos)",
    "AP - ALMOÇO PROFESSOR": "Almoço - Professor",
    "JP - JANTAR PROFESSOR": "Jantar - Professor",
    "AA - ALMOCO ADULTO": "Refeição",
    "SR - SEM REFEICAO": "Sem Refeição",
    "MES - MERENDA ESPEC SECA": "Merenda Especial Seca"
}


class GeradorExcelCardapioUE(object):

    def __init__(self, id_unidade_especial):
        # self.api = os.environ.get('PRATOABERTO_API')
        self.api = 'http://localhost:8000'
        self.id_unidade_especial = id_unidade_especial
        self.data_inicio = None
        self.data_final = None
        self.cardapios = []

    def _get_unidade_especial(self):
        url = '{}/editor/unidade-especial/{}'.format(self.api, self.id_unidade_especial)
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return {}

    def _get_cardapio_unidade_especial(self):
        url = '{}/editor/cardapios-unidade-especial/?unidade={}&inicio={}&fim={}'.format(self.api,
                                                                                         self.id_unidade_especial,
                                                                                         self.data_inicio,
                                                                                         self.data_final)
        response = requests.get(url)
        if response.status_code == 200:
            return self._extrai_dados_importantes(response.json())
        return {}

    def _extrai_dados_importantes(self, cardapios):
        novo_cardapio = []
        if cardapios:
            for cardapio in cardapios:
                novos_dados = {'semana': self._get_numero_semana_ano(cardapio.get('data')),
                               'faixa': cardapio.get('idade'),
                               'data': cardapio.get('data'),
                               'polo': cardapio.get('tipo_unidade'),
                               'cardapio': cardapio.get('cardapio')}
                novo_cardapio.append(novos_dados)
        return sorted(novo_cardapio, key=lambda v: v.get('data'))

    def _get_numero_semana_ano(self, str_date):
        try:
            semana = datetime.strptime(str_date, '%Y%m%d').isocalendar()[1]
            return semana
        except ValueError:
            return False

    def _get_abas_planinha(self):
        semanas = []
        for cardapio in self.cardapios:
            semana_ano = self._get_numero_semana_ano(cardapio.get('data'))
            if semana_ano not in semanas:
                semanas.append(semana_ano)
        return sorted(semanas)

    def _get_faixas_etarias_by_semana(self, semana):
        faixas_set = set()
        [faixas_set.add(cardapio.get('faixa')) for cardapio in self.cardapios if cardapio.get('semana') == semana]
        return list(faixas_set)

    def _get_categorias_by_faixa_etaria(self, semana, faixa_etaria):
        cardapio_list = []
        cardapios_dict = [cardapio.get('cardapio').keys() for cardapio in self.cardapios if
                          cardapio.get('semana') == semana and cardapio.get('faixa') in faixa_etaria]
        [cardapio_list.append(categorias) for categorias in cardapios_dict if categorias not in cardapio_list]
        return self._ordernar_categorias(list(cardapio_list[0]))

    def _get_datas_cardapios(self, semana):
        return [cardapio.get('data') for cardapio in self.cardapios if cardapio.get('semana') == semana]

    def _criar_estrutura_planilha(self):
        workbook = Workbook()
        semanas = self._get_abas_planinha()
        titulo_polo = self.cardapios[0]['polo']
        contador_coluna = 0
        for semana in semanas:
            aba_planilha = workbook.create_sheet('Semana {}'.format(semana), contador_coluna)
            contador_coluna += 1
            faixa_etarias = self._get_faixas_etarias_by_semana(semana)
            categorias = self._get_categorias_by_faixa_etaria(semana, faixa_etarias)
            datas_cardapio = self._get_datas_cardapios(semana)
            self._criar_titulos(aba_planilha, semanas, titulo_polo)
            self._criar_faixa_etarias(faixa_etarias, aba_planilha)
            self._cria_categorias_cardapio(categorias, aba_planilha)
            self._criar_datas_cardapio(datas_cardapio, aba_planilha)
            for faixa in faixa_etarias:
                self._criar_refeicoes_cardapio_by_faixa_categoria_data_semana(semana, faixa, categorias,
                                                                              datas_cardapio)

        arquivo_excel = '{}/CARDAPIOS_UNIDADE_ESPCIAL_{}.xlsx'.format(XLSX_FILE_PATH, DATA_GERACAO)
        workbook.save(arquivo_excel)

    def _criar_titulos(self, aba_planilha, semanas, titulo_polo):
        colunas = aba_planilha
        data_inicio_formatada = self._converte_str_to_date(self.data_inicio, format='%d/%m/%Y')
        data_fim_formatada = self._converte_str_to_date(self.data_final, format='%d/%m/%Y')
        titulo_semanas = ' à '.join([str(value) for value in semanas])
        colunas['A1'] = 'DIA'
        colunas['B1'] = 'CARDÁPIOS {} - Período: {} até {} - Semanas: {}'.format(titulo_polo, data_inicio_formatada,
                                                                                 data_fim_formatada,
                                                                                 titulo_semanas)

    def _criar_faixa_etarias(self, faixa_etaria, aba_planilha):
        colunas = aba_planilha
        coluna_faixas_etaria = 2
        for faixa in faixa_etaria:
            colunas.cell(row=2, column=coluna_faixas_etaria).value = faixa
            coluna_faixas_etaria += 1

    def _cria_categorias_cardapio(self, categorias, aba_planilha):
        contador_colunas = 2
        for categoria in categorias:
            aba_planilha.cell(row=3, column=contador_colunas).value = categoria
            contador_colunas += 1

    def _criar_datas_cardapio(self, datas_cardapio, aba_planilha):
        contador_linha = 4
        for data in datas_cardapio:
            data_formatada = self._formatar_data_planilha(data)
            aba_planilha.cell(row=contador_linha, column=1).value = data_formatada
            contador_linha += 1

    def _criar_refeicoes_cardapio_by_faixa_categoria_data_semana(self, semana, faixa_etaria, categorias,
                                                                 datas_cardapio):
        cardapios_list = list(
            filter(lambda cardapio: cardapio.get('semana') == semana and cardapio.get('faixa') == faixa_etaria,
                   self.cardapios)
        )
        for categoria in categorias:
            cardapio_categoria = [cardapio.get('cardapio') for cardapio in cardapios_list if
                                  categoria in cardapio.get('cardapio').keys()]

        cardapio_planilha = self._ordena_dicionario_cardapio(cardapio_categoria)

    def _ordena_dicionario_cardapio(self, cardapio_dict):
        lista_ordenada = []
        for key, value in ORDENS_REFEICOES.items():
            for val in cardapio_dict:
                if key in val:
                    lista_ordenada.append(val[key])
        return lista_ordenada

    def _formatar_data_planilha(self, data_planilha):
        data = datetime.strptime(data_planilha, '%Y%m%d')
        dia_semana = self._get_dia_semana(data.weekday())
        mes = self._get_mes(data.month)
        return '%s %02d/%s' % (dia_semana, data.day, mes)

    def _get_dia_semana(self, dia_semana):
        semana = {
            0: 'Segunda',
            1: 'Terça',
            2: 'Quarta',
            3: 'Quinta',
            4: 'Sexta',
            5: 'Sábado',
            6: 'Domingo',
        }
        return semana[dia_semana]

    def _get_mes(self, numero_mes):
        meses = {
            1: 'Jan',
            2: 'Fev',
            3: 'Mar',
            4: 'Abr',
            5: 'Mai',
            6: 'Jun',
            7: 'Jul',
            8: 'Ago',
            9: 'Set',
            10: 'Out',
            11: 'Nov',
            12: 'Dez'
        }
        return meses[numero_mes]

    def _converte_str_to_date(self, data_inicio, format='%Y%m%d'):
        data = datetime.strptime(data_inicio, '%Y%m%d')
        return datetime.strftime(data, format)

    def produzir_excel(self):
        unidade_especial = self._get_unidade_especial()
        self.data_inicio = unidade_especial['data_inicio']
        self.data_final = unidade_especial['data_fim']
        self.cardapios = self._get_cardapio_unidade_especial()
        self._criar_estrutura_planilha()

    def _ordernar_categorias(self, refeicoes_desord):
        ordenado = []
        [ordenado.append(key) for key, value in ORDENS_REFEICOES.items() if key in refeicoes_desord]
        return ordenado


if __name__ == '__main__':
    id_ue = '5cf007848a689b00071cb4be'
    gerador = GeradorExcelCardapioUE(id_ue)
    gerador.produzir_excel()
