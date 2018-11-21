import datetime
import json

import bs4
import dateutil.parser


def data_format(text):
    date = datetime.datetime.strptime(text, '%d/%m/%y').date()
    date = datetime.datetime.strftime(date, "%Y%m%d")
    return str(date)


def create(FILE):
    cardapio_dict = {}
    with open(FILE, 'r', encoding="ISO-8859-1") as f:

        soup = bs4.BeautifulSoup(f.read(), "lxml")

        for blocos in soup.find_all('g_cod_faxa_etra'):
            cod_agrupamento = blocos.find('cod_agrm_regl').text.strip()
            cod_tipo_unidade = blocos.find('cod_tip_unid').text.strip()
            # cod_faixa_etaria = blocos.find('cod_faxa_etra').text.strip()
            # cod_tipo_refeicao = blocos.find('cod_tip_rfca').text.strip()
            txt_tipo_refeicao = blocos.find('txt_tip_rfca').text.strip()
            txt_faixa_etaria = blocos.find('txt_faxa_etra').text.strip()
            txt_dcr_unidade = blocos.find('txt_dcr_unid').text.split('-')[-1].strip().replace(' ', '_')

            if cod_tipo_unidade == 11:
                txt_tip_atendimento = 'CONVENIADA'
            else:
                txt_tip_atendimento = blocos.find('tip_atend').text.replace('UNIDADES', '').strip()


            for informacao_dia in blocos.find_all('g_sgl_dia_sema'):
                # cod_dia_semana = informacao_dia.find('cod_dia_sema').text.strip()
                # sigla_dia_semana = informacao_dia.find('sgl_dia_sema').text.strip()
                # txt_dia_semana = informacao_dia.find('dcr_dia_sema').text.strip()
                data_merenda = data_format(informacao_dia.find('dt_csmo_card').text.strip())


                lista = []
                for ingrediente in informacao_dia.find_all('g_txt_dcr_rcta'):
                    subs = ingrediente.find("subs_por_nada")
                    item = ingrediente.find("txt_dcr_almn")

                    fullName = ""
                    if subs is not None and subs.text is not None and len(subs.text):
                    	fullName = subs.text
                    if item is not None and item.text is not None:
                    	fullName += item.text
		
                    lista.append(fullName.strip())

                # Constroi o dicionario
                if txt_tip_atendimento in cardapio_dict.keys():
                    if txt_dcr_unidade in cardapio_dict[txt_tip_atendimento].keys():
                        if cod_agrupamento in cardapio_dict[txt_tip_atendimento][txt_dcr_unidade].keys():
                            if txt_faixa_etaria in cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento].keys():
                                if data_merenda in cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento][txt_faixa_etaria].keys():
                                    cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento][txt_faixa_etaria][data_merenda][txt_tipo_refeicao] = ', '.join(lista)
                                else:
                                    
                                    cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento][txt_faixa_etaria][data_merenda] = {}
                                    cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento][txt_faixa_etaria][data_merenda][txt_tipo_refeicao] = ', '.join(lista)
                            else:
                                cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento][txt_faixa_etaria] = {}
                                cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento][txt_faixa_etaria][data_merenda] = {}
                                cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento][txt_faixa_etaria][data_merenda][txt_tipo_refeicao] = ', '.join(lista)
                        else:
                            cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento] = {}
                            cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento][txt_faixa_etaria] = {}
                            cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento][txt_faixa_etaria][data_merenda] = {}
                            cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento][txt_faixa_etaria][data_merenda][txt_tipo_refeicao] = ', '.join(lista)
                    else:
                        cardapio_dict[txt_tip_atendimento][txt_dcr_unidade] = {}
                        cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento] = {}
                        cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento][txt_faixa_etaria] = {}
                        cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento][txt_faixa_etaria][data_merenda] = {}
                        cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento][txt_faixa_etaria][data_merenda][txt_tipo_refeicao] = ', '.join(lista)
                else:
                    cardapio_dict[txt_tip_atendimento] = {}
                    cardapio_dict[txt_tip_atendimento][txt_dcr_unidade] = {}
                    cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento] = {}
                    cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento][txt_faixa_etaria] = {}
                    cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento][txt_faixa_etaria][data_merenda] = {}
                    cardapio_dict[txt_tip_atendimento][txt_dcr_unidade][cod_agrupamento][txt_faixa_etaria][data_merenda][txt_tipo_refeicao] = ', '.join(lista)


    return cardapio_dict


if __name__ == '__main__':
    FILE = './tmp/explodido04a0809direta3.XML'
    print(create(FILE))
    # with open(FILE.lower().replace('.xml', '.json'), 'r') as outfile:
    #     data = json.loads(outfile.read())