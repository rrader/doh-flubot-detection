FROM jupyter/scipy-notebook:python-3.10

USER root

RUN mamba install --yes \
	'modin[dask]' \
	'ray-default' \
	jupyterlab_execute_time \
	jupyterlab-favorites \
        'ipydrawio[all]' \
	'jupyterlab-lsp' 'python-lsp-server[all]' \
	papermill

RUN wget --no-check-certificate https://github.com/quarto-dev/quarto-cli/releases/download/v1.3.290/quarto-1.3.290-linux-amd64.deb -O quarto.deb && \
	apt install ./quarto.deb
	
