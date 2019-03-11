FROM python:3.6-slim-jessie

ADD . /code
WORKDIR /code

RUN apt-get update -y && \
    apt-get install \
     build-essential \
     python3-dev \
     python3-pip \
     python3-setuptools \
     python3-wheel -y && \
    apt-get clean && \
    python -m pip --no-cache install -r requirements.txt