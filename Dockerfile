FROM continuumio/miniconda3:latest

ENV PYTHONUNBUFFERED=1

WORKDIR /app
SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get -y install \
    gcc \
    g++ \
    libxrender-dev \
    libsm6 \
    libxext6

COPY environment.yml /app/
RUN mkdir /kms_env
ENV ENV_PREFIX=/kms_env
RUN conda env create --prefix $ENV_PREFIX --file environment.yml --force
ENV PATH /kms_env/bin:$PATH
ENV CONDA_DEFAULT_ENV /kms_env
RUN source activate /kms_env

COPY . /app/
RUN [ "chmod", "+x", "./bin/entrypoint.sh" ]
ENTRYPOINT [ "./bin/entrypoint.sh" ]
