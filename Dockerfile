FROM continuumio/miniconda3:latest

ENV PYTHONUNBUFFERED=1

RUN mkdir /code
WORKDIR /code

SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get -y install gcc g++ libxrender-dev libsm6 libxext6

COPY environment.yml /code/
RUN mkdir /kms_env
ENV ENV_PREFIX=/kms_env
RUN conda env create --prefix $ENV_PREFIX --file environment.yml --force
ENV PATH /kms_env/bin:$PATH
ENV CONDA_DEFAULT_ENV /kms_env
RUN source activate /kms_env

COPY . /code/
ENTRYPOINT [ "python", "manage.py", "runserver", "0.0.0.0:8000" ]
