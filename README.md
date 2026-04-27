# Citi Bike E-Bike Performance Repo

Repositório autónomo com dados reais do Citi Bike para estudar:

- performance operacional de estações;
- utilização de bicicletas elétricas vs clássicas;
- perfis de viagem e grupos comportamentais;
- OLTP, OLAP, dbt, SQL, Machine Learning e Streamlit;
- preparação para publicação em GitHub.

## Main Entry Points

- Project hub: [index.html](index.html)
- Handbook: [docs/citibike_handbook.html](docs/citibike_handbook.html)

## Fontes oficiais

- Citi Bike System Data: `https://citibikenyc.com/system-data`
- Trip history bucket: `https://s3.amazonaws.com/tripdata/`
- GBFS discovery feed: `https://gbfs.citibikenyc.com/gbfs/2.3/gbfs.json`
- GBFS specification: `https://gbfs.org/specification`

## Repository Structure

```text
.
├── data/
├── dbt_citibike/
├── docs/
├── python/
├── sql/
├── streamlit/
├── .gitignore
├── README.md
├── index.html
└── requirements.txt
```

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## GitHub CLI (`gh`)

Com Homebrew:

```bash
brew install gh
```

Sem Homebrew, instalação local no utilizador:

```bash
mkdir -p ~/.local/gh ~/bin
cd ~/.local/gh
curl -fL -o gh.zip https://github.com/cli/cli/releases/download/v2.91.0/gh_2.91.0_macOS_arm64.zip
unzip -o gh.zip
ln -sf ~/.local/gh/gh_2.91.0_macOS_arm64/bin/gh ~/bin/gh
printf '\nexport PATH="$HOME/bin:$PATH"\n' >> ~/.zprofile
```

Depois abre um novo terminal:

```bash
gh --version
gh auth login
```

## Quick Start

Modo rápido com dados reais:

```bash
python python/run_pipeline.py --months 1 --sample-rows-per-file 20000
python python/ml_citibike.py
streamlit run streamlit/app.py
```

Modo mais completo:

```bash
python python/run_pipeline.py --months 3
```

## dbt

```bash
cd dbt_citibike
cp profiles.example.yml profiles.yml
export DBT_PROFILES_DIR=.
dbt run
dbt test
```

## Validation

```bash
python python/validate_project.py
```

## GitHub

```bash
git init
git add .
git commit -m "Initial Citi Bike e-bike performance case"
gh auth login
gh repo create citibike-ebike-performance-repo --public --source . --remote origin --push
```
