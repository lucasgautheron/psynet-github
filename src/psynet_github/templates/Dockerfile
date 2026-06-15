# This Dockerfile supports PsyNet/Dallinger SSH deployments.

FROM python:3.13-bookworm

RUN pip install uv

RUN mkdir /experiment
WORKDIR /experiment

COPY requirements.txt requirements.txt
COPY *constraints.txt constraints.txt

ENV SKIP_DEPENDENCY_CHECK=""
ENV DALLINGER_NO_EGG_BUILD=1

RUN if [ -f constraints.txt ]; then \
      uv pip install -r constraints.txt --system; \
    else \
      uv pip install -r requirements.txt --system; \
    fi

COPY *prepare_docker_image.sh prepare_docker_image.sh
RUN if [ -f prepare_docker_image.sh ]; then bash prepare_docker_image.sh; fi

COPY . /experiment
