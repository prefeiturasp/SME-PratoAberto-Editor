import ue_mongodb as ue


class UnidadesEspeciaisModel(object):

    # ..ESTABELECE CONEXÃO COM O SERVIDOR MONGODB
    def connect(self):
        ue.connect(self.colecao)

    # ..INICIALIZA A ESTRUTURA DE UMA UNIDADE ESPECIAL
    def create(self):
        ue.create(self.unidade, self.dta_criacao, self.dta_ini, self.dta_fim, self.id_escolas)

    # ..APAGA UMA OU TODAS AS UNIDADES DA COLLECTION
    def delete(self):
        ue.delete(self.id_unidade)

    # ..VERIFICA SE A UNIDADE ESPECIAL ESTA ATIVA
    def isactive(self):
        ue.isactive(self.id_unidade)

    # ..ATUALIZA UM, VARIOS OU TODOS OS DADOS DE UMA UNIDADE ESPECIAL
    def set_unidade(self):
        ue.set_unidade(self.id_unidade, self.data_criacao, self.data_ini, self.data_fim, self.id_escolas)

    # ..EXTRAI TODOS OS DADOS DE UMA UNIDADE ESPECIAL
    def get_unidade(self):
        ue.get_unidade(self.unidade)

    # ..EXTRAI OS IDs E O NOME DE TODAS AS ESCOLAS
    def get_db_escolas():
        ue.get_db_escolas()
