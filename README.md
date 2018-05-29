[![Maintainability](https://api.codeclimate.com/v1/badges/91db18f57ab71fb8f602/maintainability)](https://codeclimate.com/github/prefeiturasp/SME-PratoAberto-Editor/maintainability)



### Instalação
Pré requisitos:

Python
pip

Instale os requisitos através do requirements.txt

```
pip install -r requirements.txt
```
Para executar o editor:

```
FLASK_APP=hello.py flask run
```
Caso alguma dependência esteja faltando após o processo instale com:

```
pip install nomeDependecia
```
Repita o processo até não faltar mais nenhuma dependência.

# Editor

Este é o painel de edição de cardápios da Secretária Municipal de Educação.

A fonte principal de informação são os arquivos XMLs da operação logística
da secretária, gerados na aplicação PAPA, e carregados no editor.

A interface permite a revisão dos ingredientes, substituição das strings e
sua publicação por categoria de escola (agrupamento, tipo de atendimento,
data, etc).
