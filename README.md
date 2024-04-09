# Metadata Explorer

## Usage

Set up conda environment

```sh
micromamba create -n metadata-explorer
micromamba activate metadata-explorer
micromamba install -c conda-forge python=3.10 --yes
```

Install dependencies

```sh
pip install -r requirements.txt
```

Run server

```
bokeh serve --show metadata-explorer.py
```
