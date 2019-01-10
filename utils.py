import datetime


def datetime_to_brstring(dt):
    return dt.strftime('%d/%m/%Y')


def yyyymmdd_to_date_time(dt_str):
    return datetime.datetime.strptime(dt_str, '%Y%m%d')


def sort_array_by_datetime(unsorted_array, reverse=False):
    sorted_array = sorted(
        unsorted_array,
        key=lambda x: x[4], reverse=reverse
    )
    return sorted_array


def sort_array_date_br(data_array):
    """
    recebe um array, transforma a coluna 4 e 5 para datetime
    ordena
    passa as colunas pra formato string br

    :param data_array: array
    :param index: int
    :return: aray
        """
    # passa para datetime
    for i in range(len(data_array)):
        data_array[i][4] = yyyymmdd_to_date_time(data_array[i][4])
        data_array[i][5] = yyyymmdd_to_date_time(data_array[i][5])

    # ordena por datetime
    data_array = sort_array_by_datetime(data_array, reverse=True)

    # passa para data br str
    for i in range(len(data_array)):
        data_array[i][4] = datetime_to_brstring(data_array[i][4])
        data_array[i][5] = datetime_to_brstring(data_array[i][5])
    return data_array


def sort_array_by_date_and_index(data_array, index=4):
    """
    recebe um array, transforma uma coluna especifica pra datetime
    ordena
    passa o a coluna pra formato string br
    :param data_array: array
    :param index: int
    :return: aray
    """
    # passa para datetime
    for i in range(len(data_array)):
        data_array[i][index] = yyyymmdd_to_date_time(data_array[i][index])

    # ordena por datetime
    data_array = sort_array_by_datetime(data_array, reverse=True)

    # passa para data br str
    for i in range(len(data_array)):
        data_array[i][index] = datetime_to_brstring(data_array[i][index])
    return data_array


def remove_duplicates_array(array):
    """Este método está seendo usado no lugar de set porque o set tira a ordem"""
    retval = []
    for i in array:
        if i not in retval:
            retval.append(i)
    return retval


def fix_date_mapa_final(array):
    retval = []
    for i in array:
        if i not in retval:
            data_ini_br = yyyymmdd_to_date_time(i['data_inicial']).strftime('%d/%m/%Y')
            data_fim_br = yyyymmdd_to_date_time(i['data_final']).strftime('%d/%m/%Y')
            i['data_inicial'] = data_ini_br
            i['data_final'] = data_fim_br
            retval.append(i)
    return retval


def generate_csv_str(cardapio_aux):
    header = [['ATENDIMENTO', 'UNIDADE', 'AGRUPAMENTO', 'IDADE', 'DATA', 'STATUS', 'REFEICÃO', 'CARDÁPIO']]
    cardapio_aux = header + cardapio_aux
    csvlist = '\n'.join(['"' + str('";"'.join(row)) + '"' for row in cardapio_aux])
    return csvlist
