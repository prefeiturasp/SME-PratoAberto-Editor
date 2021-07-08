import collections

from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker

from db_setup import Replacements, ReceitasTerceirizadas, Base


# FUNCOES REPLACEMENTS
def add_replacements(substitution_group, substitution_scope, from_word, to_word):
    engine = create_engine('sqlite:///sqlite/configuracoes_editor_merenda.db')
    Base.metadata.bind = engine
    dbsession = sessionmaker(bind=engine)
    session = dbsession()
    new_rule = Replacements(substitution_group=substitution_group,
                            substitution_scope=substitution_scope,
                            from_word=from_word,
                            to_word=to_word)
    session.add(new_rule)
    session.commit()


def truncate_replacements():
    engine = create_engine('sqlite:///sqlite/configuracoes_editor_merenda.db')
    Base.metadata.bind = engine
    dbsession = sessionmaker(bind=engine)
    session = dbsession()
    session.query(Replacements).delete()
    session.commit()


def del_replacements(id):
    engine = create_engine('sqlite:///sqlite/configuracoes_editor_merenda.db')
    Base.metadata.bind = engine
    dbsession = sessionmaker(bind=engine)
    session = dbsession()
    session.query(Replacements).filter(Replacements.id == id).delete()
    session.commit()


def select_all():
    engine = create_engine('sqlite:///sqlite/configuracoes_editor_merenda.db')
    Base.metadata.bind = engine
    dbsession = sessionmaker(bind=engine)
    session = dbsession()
    res = session.query(Replacements).all()
    list = [(x.id, x.substitution_group, x.substitution_scope, x.from_word, x.to_word) for x in res]
    return list


def select_distinct_substitution_groups():
    engine = create_engine('sqlite:///sqlite/configuracoes_editor_merenda.db')
    Base.metadata.bind = engine
    dbsession = sessionmaker(bind=engine)
    session = dbsession()
    res = session.query(Replacements).all()
    grupos = list(set([x.substitution_group for x in res]))
    return grupos


def filtra_grupos_replacements(substitution_group):
    engine = create_engine('sqlite:///sqlite/configuracoes_editor_merenda.db')
    Base.metadata.bind = engine
    dbsession = sessionmaker(bind=engine)
    session = dbsession()
    res = session.query(Replacements).filter(Replacements.substitution_group == substitution_group).all()
    list = [(x.id, x.substitution_group, x.substitution_scope, x.from_word, x.to_word) for x in res]
    return list


# FUNCOES CARDAPIOS
def add_cardapio(tipo_gestao, tipo_escola, edital, diasemana, idade, refeicao, cardapio):
    engine = create_engine('sqlite:///sqlite/configuracoes_editor_merenda.db')
    Base.metadata.bind = engine
    dbsession = sessionmaker(bind=engine)
    session = dbsession()
    new_rule = ReceitasTerceirizadas(tipo_gestao=tipo_gestao,
                                     tipo_escola=tipo_escola,
                                     edital=edital,
                                     diasemana=diasemana,
                                     idade=idade,
                                     refeicao=refeicao,
                                     cardapio=cardapio)
    session.add(new_rule)
    session.commit()


def add_bulk_cardapio(bulk):
    engine = create_engine('sqlite:///sqlite/configuracoes_editor_merenda.db')
    Base.metadata.bind = engine
    dbsession = sessionmaker(bind=engine)
    session = dbsession()
    objects = []
    for args in bulk:
        objects.append(ReceitasTerceirizadas(tipo_gestao=args[0],
                                             tipo_escola=args[1],
                                             edital=args[2],
                                             diasemana=args[3],
                                             idade=args[4],
                                             refeicao=args[5],
                                             cardapio=args[6]))

    session.bulk_save_objects(objects)
    session.commit()


def truncate_receitas_terceirizadas():
    engine = create_engine('sqlite:///sqlite/configuracoes_editor_merenda.db')
    Base.metadata.bind = engine
    dbsession = sessionmaker(bind=engine)
    session = dbsession()
    session.query(ReceitasTerceirizadas).delete()
    session.commit()


def del_receitas_terceirizadas(id):
    engine = create_engine('sqlite:///sqlite/configuracoes_editor_merenda.db')
    Base.metadata.bind = engine
    dbsession = sessionmaker(bind=engine)
    session = dbsession()
    session.query(ReceitasTerceirizadas).filter(ReceitasTerceirizadas.id == id).delete()
    session.commit()


def select_all_receitas_terceirizadas():
    engine = create_engine('sqlite:///sqlite/configuracoes_editor_merenda.db')
    Base.metadata.bind = engine
    dbsession = sessionmaker(bind=engine)
    session = dbsession()
    res = session.query(ReceitasTerceirizadas).all()
    list = [(x.id, x.tipo_gestao, x.tipo_escola, x.edital, x.diasemana, x.idade, x.refeicao, x.cardapio) for x in res]
    return list


def select_all_receitas_unidades_especiais():
    engine = create_engine('sqlite:///sqlite/configuracoes_editor_merenda.db')
    Base.metadata.bind = engine
    dbsession = sessionmaker(bind=engine)
    session = dbsession()
    res = session.query(ReceitasTerceirizadas).filter(ReceitasTerceirizadas.tipo_gestao == 'UE')
    list = [(x.id, x.tipo_gestao, x.tipo_escola, x.edital, x.diasemana, x.idade, x.refeicao, x.cardapio) for x in res]
    return list

def select_receitas_terceirizadas(tipo_gestao, tipo_escola, edital, idade):
    engine = create_engine('sqlite:///sqlite/configuracoes_editor_merenda.db')
    Base.metadata.bind = engine
    dbsession = sessionmaker(bind=engine)
    session = dbsession()
    res = session.query(ReceitasTerceirizadas).filter(and_(ReceitasTerceirizadas.tipo_gestao == tipo_gestao,
                                                           ReceitasTerceirizadas.tipo_escola == tipo_escola,
                                                           ReceitasTerceirizadas.edital == edital,
                                                           ReceitasTerceirizadas.idade == idade)).all()

    # Constroi o dicionario
    _lista = [(x.diasemana, x.refeicao, x.cardapio) for x in res]
    dict_refeicao = {}
    for cardapio in _lista:
        if cardapio[0] in dict_refeicao.keys():
            if cardapio[1] in dict_refeicao[cardapio[0]].keys():
                if dict_refeicao[cardapio[0]][cardapio[1]]:
                    dict_refeicao[cardapio[0]][cardapio[1]].append(cardapio[2])
                else:
                    dict_refeicao[cardapio[0]][cardapio[1]] = []
                    dict_refeicao[cardapio[0]][cardapio[1]].append(cardapio[2])
            else:
                dict_refeicao[cardapio[0]][cardapio[1]] = []
                dict_refeicao[cardapio[0]][cardapio[1]].append(cardapio[2])
        else:
            dict_refeicao[cardapio[0]] = {}
            dict_refeicao[cardapio[0]][cardapio[1]] = []
            dict_refeicao[cardapio[0]][cardapio[1]].append(cardapio[2])

    return dict_refeicao


def select_quebras_terceirizadas():
    engine = create_engine('sqlite:///sqlite/configuracoes_editor_merenda.db')
    Base.metadata.bind = engine
    dbsession = sessionmaker(bind=engine)
    session = dbsession()
    res = session.query(ReceitasTerceirizadas).all()
    list = set([(x.tipo_escola, x.edital, x.idade, x.refeicao, x.tipo_gestao) for x in res])
    return list


def select_quebras_unidades_especiais():
    engine = create_engine('sqlite:///sqlite/configuracoes_editor_merenda.db')
    Base.metadata.bind = engine
    dbsession = sessionmaker(bind=engine)
    session = dbsession()
    res = session.query(ReceitasTerceirizadas).filter(ReceitasTerceirizadas.tipo_gestao == 'UE')
    list = set([(x.tipo_escola, x.edital, x.idade, x.refeicao, x.tipo_gestao) for x in res])
    return list


if __name__ == '__main__':
    # add_replacements('TEMPEROS', 'Ingredientes', 'ALHO', '')
    # a = select_receitas_terceirizadas('TERCEIRIZADA', 'CEI', 'EDITAL 1', 'D - 6 MESES')
    a = select_quebras_terceirizadas()
    print(a)

    b = select_all()
    print(b)
    # print(filtra_grupos_replacements('TEMPEROS'))
    # print(select_distinct_substitution_groups())
    # for row in select_all():
    #    print(row.id, row.substitution_group)
    # del_replacements(1)
