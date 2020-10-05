FROM nvidia/cuda:10.2-devel-ubuntu18.04

ENV PYTHONUNBUFFERED=1

RUN mkdir /code
WORKDIR /code

SHELL ["/bin/bash", "-c"]
RUN apt-get update && apt-get -y install wget gcc g++
ENV PATH /opt/conda/bin:$PATH

# install miniconda3
RUN wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh && \
    /bin/bash ~/miniconda.sh -b -p /opt/conda && \
    rm ~/miniconda.sh && \
    ln -s /opt/conda/etc/profile.d/conda.sh /etc/profile.d/conda.sh && \
    echo ". /opt/conda/etc/profile.d/conda.sh" >> ~/.bashrc && \
    echo "conda activate base" >> ~/.bashrc

# make the environment
COPY environment.yml /code/
RUN mkdir /kms_env
ENV ENV_PREFIX=/kms_env
RUN conda env create --prefix $ENV_PREFIX --file environment.yml --force
ENV PATH /kms_env/bin:$PATH
ENV CONDA_DEFAULT_ENV /kms_env
RUN source activate /kms_env

COPY . /code
ENTRYPOINT [ "python", "manage.py", "runserver", "0.0.0.0:8000" ]
