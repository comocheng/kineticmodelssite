FROM continuumio/anaconda3:latest

ENV PYTHONUNBUFFERED=1

RUN mkdir /code
WORKDIR /code

COPY environment.yml /code/
RUN conda env create -f environment.yml

COPY . /code/
