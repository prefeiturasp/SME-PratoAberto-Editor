import datetime
import itertools


def create(FILE):
    pendentes = []
    with open(FILE, 'r') as f:
        for row in f.readlines()[1:]:
            row_info = row.split(';')
            print(row_info)
            for agrupamento in ["EDITAL 1", "EDITAL 2"]:
                tipo_unidade = row_info[1]
                idade = row_info[3]
                tipo_atendimento = 'TERCEIRIZADA'
                data_inicial = (datetime.datetime.now() + datetime.timedelta(days=7)).date().strftime('%Y-%m-%d')
                data_final = (datetime.datetime.now() + datetime.timedelta(days=14)).date().strftime('%Y-%m-%d')
                pendentes.append([tipo_atendimento, tipo_unidade, agrupamento, idade, data_inicial, data_final])



        pendentes.sort()
        pendentes = list(pendentes for pendentes, _ in itertools.groupby(pendentes))

        return pendentes

if __name__ == "__main__":
    FILE = './tmp/Cardapio_Terceirizadas.txt'
    print(create(FILE))