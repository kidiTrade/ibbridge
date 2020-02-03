FROM python:3.8-slim as base

ARG APP_USER=appuser
RUN groupadd -r ${APP_USER} && useradd --no-log-init -r -g ${APP_USER} ${APP_USER}

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN mkdir /code/
WORKDIR /code/

FROM base as build

COPY *.proto ./
RUN set -ex \
    && pip install --no-cache-dir betterproto[compiler] \
    && python3 -m grpc_tools.protoc -I. --python_out=. --python_grpc_out=. ib_loader.proto

FROM base

EXPOSE 8443

COPY --from=build /code/*.py ./
COPY . ./

USER ${APP_USER}:${APP_USER}

ENTRYPOINT ["python3", "server.py"]
