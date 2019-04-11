import ue_mongodb as uedb


class UnidadeEspecialModel(object):

    def __init__(self):
        self.db = None
        self.colecao = None
        self.unidade = None
        self.client = None
        self.data_ini = None
        self.data_fim = None
        self.id_escolas = None

    # ..ESTABELECE CONEXÃO COM O SERVIDOR MONGODB
    def connect(self):
        return uedb.connect(self.colecao)

    # ..INICIALIZA A ESTRUTURA DAS UNIDADES ESPECIAIS (ues)
    def init(self):
        return uedb.ue_init(self.db, self.client)

    # ..DELETA AS UNIDADES ESPECIAIS DO BANCO DE DADOS
    def drop():
        return uedb.ue_drop()

    # ..VERIFICA SE A UNIDADE ESPECIAL EXISTE
    def exists(self):
        return uedb.ue_exists(self.unidade)

    # ..VERIFICA SE A UNIDADE ESPECIAL ESTA ATIVA
    def isactive(self):
        return uedb.ue_isactive(self.unidade)

    # ..INSERE/ATUALIZA AS DATAS INICIO-FIM DO PERIODO DE FUNCIONAMENTO DE UMA UNIDADE ESPECIAL
    def set_periodo(self):
        return uedb.ue_set_periodo(self.unidade, self.data_ini, self.data_fim)

    # ..EXTRAI AS DATAS DO PERÍODO DE FUNCIONAMENTO DE UMA INIDADE ESPECIAL
    def get_periodo(self):
        return uedb.ue_get_periodo(self.unidade)

    # .. INSERE/ATUALIZA A LISTA DE ESCOLAS DE UMA UNIDADE ESPECIAL
    def set_escolas(self):
        return uedb.ue_set_escolas(self.unidade, self.id_escolas)

    # ..EXTRAI AS ESCOLAS DE UMA UNIDADE ESPECIAL
    def get_escolas(self):
        return uedb.ue_get_escolas(self.unidade)

    # ..GRAVA/ATUALIZA OS DADOS DE UMA UNIDADE ESPECIAL
    def save_unidade(self):
        return uedb.ue_save_unidade(self.unidade, self.data_ini, self.data_fim)

    # ..EXTRAI AS ESCOLAS DO BANCO DE DADOS
    def get_db_escolas():
        return uedb.ue_get_db_escolas()
