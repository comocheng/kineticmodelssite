FROM continuumio/anaconda3:latest
ENV PYTHONUNBUFFERED=1
RUN mkdir /code
WORKDIR /code
COPY environment.yml /code/
RUN conda create -f environment.yml
RUN conda activate kms_env
COPY . /code/
