FROM ghcr.io/comocheng/kineticmodelssite/kms-build:latest

COPY environment.yml /app/
RUN conda config --set channel_priority strict
RUN conda env update --prefix $ENV_PREFIX --file environment.yml
RUN conda clean -afy
ENV PATH /kms_env/bin:$PATH
ENV CONDA_DEFAULT_ENV /kms_env
RUN source activate /kms_env

COPY . /app/
