FROM python:3.6-alpine3.8
ADD . /code
WORKDIR /code

RUN set -ex && \
    apk add --no-cache --virtual=.goss-dependencies curl ca-certificates && \
    apk update && apk add --no-cache tzdata libpq && \

    apk update && apk add --no-cache \
      --virtual=.build-dependencies \
      gcc \
      python3-dev && \
    python -m pip --no-cache install -U pip && \
    python -m pip --no-cache install -r requirements.txt && \
    apk del --purge .build-dependencies .goss-dependencies