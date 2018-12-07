import datetime
import db_functions
import json
import flask_login

from flask import render_template,request,Blueprint,redirect,url_for
from utils.utils import get_depara,get_config
from cardapios.cardapios import get_cardapio,get_cardapio_lista,get_cardapio_anterior,get_cardapio_atual,\
                                get_cardapios_terceirizadas

config = get_config()
api = config.get('ENDPOINTS', 'PRATOABERTO_API')

outros_app = Blueprint('outros_app', __name__)

@outros_app.route("/calendario", methods=["GET"])
@flask_login.login_required
def calendario():
    args = request.args
    depara = db_functions.select_all()
    depara = get_depara(depara)

    # Monta json - Semana da requisicao
    jdata = get_cardapio(args)

    # Obtem data semana anterior
    args_semana_anterior = args.copy()
    args_semana_anterior['status'] = 'SALVO'
    args_semana_anterior.add('status', 'PUBLICADO')

    delta_dias = datetime.timedelta(days=7)
    data_final_semana_anterior = datetime.datetime.strptime(str(args['data_final']), '%Y%m%d') - delta_dias
    data_inicial_semana_anterior = datetime.datetime.strptime(str(args['data_inicial']), '%Y%m%d') - delta_dias
    args_semana_anterior['data_final'] = datetime.datetime.strftime(data_final_semana_anterior, '%Y%m%d')
    args_semana_anterior['data_inicial'] = datetime.datetime.strftime(data_inicial_semana_anterior, '%Y%m%d')
    # Monta json - Semana anterior a da requisicao
    jdata_anterior = get_cardapio(args_semana_anterior)

    jdata_aux = []

    for cardapio_atual in jdata:
        jdata_aux = get_cardapio_lista(cardapio_atual)

    jdata_anterior_aux = []

    for cardapio_anterior in jdata_anterior:
        jdata_anterior_aux = get_cardapio_lista(cardapio_anterior)

    jdata = jdata_aux
    jdata_anterior = jdata_anterior_aux

    # Liga o cardapio atual com o da semana anterior
    dias_da_semana = set([x['dia_semana'] for x in list(jdata + jdata_anterior)])

    cardapios = []

    for dia in dias_da_semana:

        cardapio_atual = get_cardapio_atual(jdata, dia)
        cardapio_anterior = get_cardapio_anterior(jdata_anterior, dia)

        if cardapio_atual and cardapio_anterior:

            cardapio_atual['cardapio_semana_anterior'] = cardapio_anterior['cardapio']
            cardapios.append(cardapio_atual)

        else:

            if cardapio_atual:
                cardapio_atual['cardapio_semana_anterior'] = []
                cardapios.append(cardapio_atual)

    if args['tipo_atendimento'] == 'TERCEIRIZADA':

        historicos_cardapios = get_cardapios_terceirizadas(args['tipo_atendimento'],
                                                           args['tipo_unidade'],
                                                           args['agrupamento'],
                                                           args['idade'])

        return render_template("editor_terceirizadas.html",
                               url=api + '/editor/cardapios',
                               cardapios=cardapios,
                               tipo_atendimento=args['tipo_atendimento'],
                               tipo_unidade=args['tipo_unidade'],
                               idade=args['idade'],
                               agrupamento=args['agrupamento'],
                               historicos_cardapios=historicos_cardapios)

    else:

        return render_template("editor_direto_misto_conveniada.html",
                               url=api + '/editor/cardapios',
                               cardapios=jdata,
                               tipo_atendimento=args['tipo_atendimento'],
                               tipo_unidade=args['tipo_unidade'],
                               idade=args['idade'],
                               agrupamento=args['agrupamento'],
                               depara=depara)


@outros_app.route('/atualiza_receitas', methods=['POST'])
@flask_login.login_required
def atualiza_config_cardapio():

    data = request.form.get('json_dump', request.data)

    db_functions.truncate_receitas_terceirizadas()
    db_functions.add_bulk_cardapio(json.loads(data))

    if request.form:

        return (redirect(url_for('outros_app.config_cardapio')))
    else:

        return ('', 200)