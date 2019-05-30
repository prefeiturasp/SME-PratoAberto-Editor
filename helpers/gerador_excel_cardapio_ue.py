import os
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Border, Side, Alignment

import requests

xls_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tmp'))


class GeradorExcelCardapioUE(object):

    def __init__(self, id_unidade_especial):
        # self.api = os.environ.get('PRATOABERTO_API')
        self.api = 'http://localhost:8000'
        self.id_unidade_especial = id_unidade_especial

    def _get_semana(self, numero_semana):
        semana = {
            0: 'Segunda',
            1: 'Terça',
            2: 'Quarta',
            3: 'Quinta',
            4: 'Sexta',
            5: 'Sábado',
            6: 'Domingo',
        }
        return semana[numero_semana]

    def _get_unidade_especial_by_id(self):
        url = '{}/editor/unidade-especial/{}'.format(self.api, self.id_unidade_especial)
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return {}

    def _get_cardapio_unidade_especial(self, data_inicio, data_fim):
        url = '{}/editor/cardapios-unidade-especial/?unidade={}&inicio={}&fim={}'.format(self.api,
                                                                                         self.id_unidade_especial,
                                                                                         data_inicio, data_fim)
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return {}

    def _get_numero_semana_ano(self, str_date):
        try:
            semana = datetime.strptime(str_date, '%Y%m%d').isocalendar()[1]
            return semana
        except ValueError:
            return False

    def _get_abas_planinha(self, cardapios):
        semanas = []
        for cardapio in cardapios:
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

    def _get_faixas_etarias(self, cardapios):
        faixas_etaria = []
        for cardapio in cardapios:
            if cardapio.get('idade') not in faixas_etaria:
                faixas_etaria.append(cardapio.get('idade'))
        return faixas_etaria

    def running(self):
        unidade_especial = self._get_unidade_especial_by_id()
        data_inicio = unidade_especial['data_inicio']
        data_final = unidade_especial['data_fim']
        cardapios = self._get_cardapio_unidade_especial(data_inicio, data_final)
        teste = self._get_faixas_etarias(cardapios)
        print(teste)


if __name__ == '__main__':
    id_ue = '5cf007848a689b00071cb4be'
    gerador = GeradorExcelCardapioUE(id_ue)
    gerador.running()
