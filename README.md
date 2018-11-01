[![Maintainability](https://api.codeclimate.com/v1/badges/91db18f57ab71fb8f602/maintainability)](https://codeclimate.com/github/prefeiturasp/SME-PratoAberto-Editor)

# Pátio Digital

_“Recurso público retorna ao público”._

Nós somos o **pátio digital**, uma iniciativa da Secretaria Municipal de Educação de São Paulo que, por meio do fortalecimento da transparência, da participação social e do desenvolvimento de novas tecnologias, aproxima diferentes grupos da sociedade civil por um objetivo maior: a melhoria da educação na cidade de São Paulo. 

# Prato Aberto

"Prato Aberto – Comida Boa Não Tem Segredo".

## Conteúdo

1. [Sobre o prato aberto](#sobre-o-prato-aberto)
2. [Comunicação](#comunicação)
3. [Roadmap de tecnologia](#roadmap-de-tecnologia)
4. [Como contribuir](#como-contribuir)
5. [Instalação](#instalação)

 Sobre o prato aberto

Projetada para funcionar em computadores e dispositivos móveis como tablets e celulares. A ferramenta permite a consulta dos cardápios por dia e por escola, com visualização no mapa. É a primeira vez que os cardápios 
são divulgados por unidade escolar. Além de facilitar a consulta dos cardápios,a plataforma permite a avaliação da qualidade das refeições e prevê interação com usuários via Facebook e Telegram, por meio de um assistente virtual, o Robô Edu.

# Editor

Este é o painel de edição de cardápios da Secretária Municipal de Educação.

A fonte principal de informação são os arquivos XMLs da operação logística
da secretária, gerados na aplicação PAPA, e carregados no editor.

A interface permite a revisão dos ingredientes, substituição das strings e
sua publicação por categoria de escola (agrupamento, tipo de atendimento,
data, etc).

### Nossos outros repositórios

1. [Robô Edu](https://github.com/prefeiturasp/SME-PratoAberto-Edu)
2. [API](https://github.com/prefeiturasp/SME-PratoAberto-API)
3. [Editor](https://github.com/prefeiturasp/SME-PratoAberto-Editor)
  
  ## Comunicação


| Canal de comunicação | Objetivos |
|----------------------|-----------|
| [Issues do Github](https://github.com/prefeiturasp/SME-PratoAberto-Editor/issues) | - Sugestão de novas funcionalidades<br> - Reportar bugs<br> - Discussões técnicas |
| [Telegram](https://t.me/patiodigital ) | - Comunicar novidades sobre os projetos<br> - Movimentar a comunidade<br>  - Falar tópicos que **não** demandem discussões profundas |

Qualquer outro grupo de discussão não é reconhecido oficialmente.

## Roadmap de tecnologia


### Passos iniciais
- Melhorar a qualidade de código
- Iniciar a escrita de testes unitários
- Configurar Docker
- Iniciar escrita de testes funcionais
- Melhorar documentação de maneira enxuta
-Configurar CI - Jenkins


## Como contribuir

Contribuições são **super bem vindas**! Se você tem vontade de construir o
prato aberto conosco, veja o nosso [guia de contribuição](./CONTRIBUTING.md)
onde explicamos detalhadamente como trabalhamos e de que formas você pode nos
ajudar a alcançar nossos objetivos. Lembrando que todos devem seguir 
nosso [código de conduta](./CODEOFCONDUCT.md).


### Instalação
Pré requisitos:

Python

pip

virtualenv (Passo a passo da instalação virtualenv+flask [aqui.](http://flask.pocoo.org/docs/0.12/installation/))

Instale os requisitos através do requirements.txt

```
pip install -r requirements.txt
```
Para executar o editor:

```
FLASK_APP=app.py flask run
```
Caso alguma dependência esteja faltando após o processo instale com:

```
pip install nomeDependecia
```
Repita o processo até não faltar mais nenhuma dependência.

Baseado no Readme do [i-educar](https://github.com/portabilis/i-educar)
