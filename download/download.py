import datetime
import flask_login
import requests
import configparser

from flask import render_template, request, Blueprint, make_response
from utils.utils import get_grupo_publicacoes


download_app = Blueprint('download_app', __name__)

# BLOCO GET ENDPOINT E KEYS
config = configparser.ConfigParser()
config.read('config/integracao.conf')
api = config.get('ENDPOINTS', 'PRATOABERTO_API')

# BLOCO DE DOWNLOAD DAS PUBLICAÇÕES
@download_app.route("/download_publicacao", methods=["GET", "POST"])
@flask_login.login_required
def publicacao():

    if request.method == "GET":

        return render_template("download_publicações.html", data_inicio_fim='disabled')

    else:

        data_inicial = request.form.get('data-inicial', request.data)
        data_final = request.form.get('data-final', request.data)
        data_inicial = datetime.datetime.strptime(data_inicial, '%d/%m/%Y').strftime('%Y%m%d')
        data_final = datetime.datetime.strptime(data_final, '%d/%m/%Y').strftime('%Y%m%d')
        filtro = request.form.get('filtro', request.data)

        if filtro == 'STATUS':

            return render_template("download_publicações.html",
                                   data_inicio_fim=str(data_inicial + '-' + data_final),
                                   filtro_selected=filtro)

        else:

            cardapio_aux = []

            for cardapio in get_grupo_publicacoes(filtro):

                if (data_inicial <= cardapio[4]) or (data_inicial <= cardapio[5]):

                    if (cardapio[4] <= data_final) or (cardapio[5] <= data_final):

                        url = api + '/editor/cardapios?' + '&' + cardapio[7]
                        r = requests.get(url)
                        refeicoes = r.json()

                        for refeicoes_dia in refeicoes:

                            _keys = ['tipo_atendimento', 'tipo_unidade', 'agrupamento', 'idade', 'data', 'status']
                            refeicao_dia_aux = [refeicoes_dia[_key] for _key in _keys]

                            for refeicao in refeicoes_dia['cardapio'].keys():
                                cardapio_aux.append(
                                    refeicao_dia_aux + [refeicao] + [', '.join(refeicoes_dia['cardapio'][refeicao])])

            return render_template("download_publicações.html", publicados=cardapio_aux,
                                   data_inicio_fim=str(data_inicial + '-' + data_final),
                                   filtro_selected=filtro)


@download_app.route('/download_csv', methods=['POST'])
@flask_login.login_required
def download_csv():

    data_inicio_fim_str = request.form.get('datas', request.data)
    data_inicial = data_inicio_fim_str.split('-')[0]
    data_final = data_inicio_fim_str.split('-')[1]
    filtro = request.form.get('filtro_selected', request.data)

    if filtro == 'STATUS':

        return render_template("download_publicações.html",
                               data_inicio_fim=str(data_inicial + '-' + data_final))
    else:

        cardapio_aux = []

        for cardapio in get_grupo_publicacoes(filtro):

            if (data_inicial <= cardapio[4]) or (data_inicial <= cardapio[5]):

                if (cardapio[4] <= data_final) or (cardapio[5] <= data_final):

                    url = api + '/editor/cardapios?' + '&' + cardapio[7]
                    r = requests.get(url)
                    refeicoes = r.json()

                    for refeicoes_dia in refeicoes:

                        _keys = ['tipo_atendimento', 'tipo_unidade', 'agrupamento', 'idade', 'data', 'status']
                        refeicao_dia_aux = [refeicoes_dia[_key] for _key in _keys]

                        for refeicao in refeicoes_dia['cardapio'].keys():
                            cardapio_aux.append(
                                refeicao_dia_aux + [refeicao] + [', '.join(refeicoes_dia['cardapio'][refeicao])])

        header = [['ATENDIMENTO', 'UNIDADE', 'AGRUPAMENTO', 'IDADE', 'DATA', 'STATUS', 'REFEICÃO', 'CARDÁPIO']]
        cardapio_aux = header + cardapio_aux
        csvlist = '\n'.join(['"' + str('";"'.join(row)) + '"' for row in cardapio_aux])
        output = make_response(csvlist)
        output.headers["Content-Disposition"] = "attachment; filename=agrupamento_publicações" + str(
            data_inicio_fim_str) + ".csv"
        output.headers["Content-type"] = "text/csv; charset=utf-8'"

        if request.form:

            return output
        else:

            return ('', 200)