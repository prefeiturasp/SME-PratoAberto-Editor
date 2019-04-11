import ue_mongodb


class UnidadeEspecialModel(object):

    def __init__(self):
        pass

    def get_all_escolas(self):
        return ue_mongodb.ue_get_escolas()
