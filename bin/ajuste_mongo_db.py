from pymongo import MongoClient

HOST, PORT = '****', 27017

client = MongoClient(HOST, PORT)
escolas = client['pratoaberto']['escolas']

escolas_erradas = escolas.find({'idades': {'$in': ["C- 4 A 5 MESES"]}})


def find_and_replace(array, value_old, value_new):
    retval = array[:]
    for n, i in enumerate(array):
        if i == value_old:
            retval[n] = value_new
    return retval


for escola in escolas_erradas:
    print(escola)
    fixed_array = find_and_replace(array=escola['idades'],
                                   value_old='C- 4 A 5 MESES',
                                   value_new='C - 4 A 5 MESES')
    escolas.update({'_id': escola['_id']}, {'$set': {'idades': fixed_array}})
