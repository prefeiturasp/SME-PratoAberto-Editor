import os
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Border, Side, Alignment

import requests

xls_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tmp'))
data_geracao = str(datetime.now()).replace(' ', '_').replace(':', '_').replace('.', '_')


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

    def _get_dias_cardapio(self, cardapios):
        dias_cardapio = []
        for cardapio in cardapios:
            if cardapio.get('data') not in dias_cardapio:
                dias_cardapio.append(cardapio.get('data'))
        return sorted(dias_cardapio)

    def _get_faixas_etarias(self):
        faixas_etaria = []
        for cardapio in self.cardapios:
            if cardapio.get('faixa') not in faixas_etaria:
                faixas_etaria.append(cardapio.get('faixa'))
        return faixas_etaria

    def _criar_estrutura_planilha(self):
        workbook = Workbook()
        semanas = self._get_abas_planinha()
        titulo_polo = self.cardapios[0]['polo']
        contador = 0
        for semana in semanas:
            aba_planilha = workbook.create_sheet('Semana {}'.format(semana), contador)
            contador += 1
            self._criar_titulos(aba_planilha, semanas, titulo_polo)
            self._criar_faixa_etarias(semana, aba_planilha)
            self._cria_categorias_cardapio(semana, aba_planilha)

        arquivo_excel = '{}/CARDAPIOS_UNIDADE_ESPCIAL_{}.xlsx'.format(xls_file_path, data_geracao)
        # workbook.save(arquivo_excel)

    def _criar_titulos(self, aba_planilha, semanas, titulo_polo):
        colunas = aba_planilha
        data_inicio_formatada = self._converte_str_to_date(self.data_inicio, format='%d/%m/%Y')
        data_fim_formatada = self._converte_str_to_date(self.data_final, format='%d/%m/%Y')
        titulo_semanas = ' à '.join([str(value) for value in semanas])
        colunas['A1'] = 'DIA'
        colunas['B1'] = 'CARDÁPIOS {} - Período: {} até {} - Semanas: {}'.format(titulo_polo, data_inicio_formatada,
                                                                                 data_fim_formatada,
                                                                                 titulo_semanas)

    def _criar_faixa_etarias(self, semana, aba_planilha):
        colunas = aba_planilha
        coluna_faixas_etaria = 2
        verificador_duplicidade = []  # Utilizado somente para anular duplicidades
        for faixa_etaria in self._get_faixas_etarias():
            for cardapio in self.cardapios:
                if cardapio['semana'] == semana and cardapio['faixa'] == faixa_etaria:
                    if faixa_etaria not in verificador_duplicidade:  # somente para checar se já existe
                        verificador_duplicidade.append(faixa_etaria)
                        colunas.cell(row=2, column=coluna_faixas_etaria).value = faixa_etaria
                        coluna_faixas_etaria += 1

    def _cria_categorias_cardapio(self, semana, aba_planilha):
        for faixa in self._get_faixas_etarias():
            for cardapio in self.cardapios:
                if cardapio.get('faixa') == faixa and cardapio.get('semana') == semana:
                    print(semana, cardapio.get('data'), cardapio.get('cardapio'))

    def _converte_str_to_date(self, data_inicio, format='%Y%m%d'):
        data = datetime.strptime(data_inicio, '%Y%m%d')
        return datetime.strftime(data, format)

    def produzir_excel(self):
        unidade_especial = self._get_unidade_especial()
        self.data_inicio = unidade_especial['data_inicio']
        self.data_final = unidade_especial['data_fim']
        self.cardapios = self._get_cardapio_unidade_especial()
        self._criar_estrutura_planilha()


if __name__ == '__main__':
    id_ue = '5cf007848a689b00071cb4be'
    gerador = GeradorExcelCardapioUE(id_ue)
    gerador.produzir_excel()
