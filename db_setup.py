from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class Replacements(Base):
    __tablename__ = 'replacements'
    # Here we define columns for the table person
    # Notice that each column is also a normal Python instance attribute.
    id = Column(Integer, primary_key=True)
    substitution_group = Column(String(250), nullable=False)
    substitution_scope = Column(String(250), nullable=False)
    from_word = Column(String(250), nullable=False)
    to_word = Column(String(250), nullable=False)


class ReceitasTerceirizadas(Base):
    __tablename__ = 'receitas_terceirizadas'
    # Here we define columns for the table person
    # Notice that each column is also a normal Python instance attribute.
    id = Column(Integer, primary_key=True)
    tipo_gestao = Column(String(250), nullable=False)
    tipo_escola = Column(String(250), nullable=False)
    edital = Column(String(250), nullable=False)
    diasemana = Column(String(250), nullable=False)
    idade = Column(String(250), nullable=False)
    refeicao = Column(String(250), nullable=False)
    cardapio = Column(String(1000), nullable=False)


# Create an engine that stores data in the local directory'scardapio
# sqlalchemy_example.db file.
def set():
    engine = create_engine('sqlite:///configuracoes_editor_merenda.db')

    # Create all tables in the engine. This is equivalent to "Create Table"
    # statements in raw SQL.
    Base.metadata.create_all(engine)

if __name__ == '__main__':
    set()
