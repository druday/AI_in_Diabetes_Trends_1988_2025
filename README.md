# AI in Diabetes: Temporal Institutional Collaboration Trends (1988–2025)

Reproducible analysis pipeline and supporting materials for a temporal institutional
network analysis of artificial-intelligence (AI) research in diabetes, based on
PubMed-indexed publications from **1988 to 2025**.

The pipeline retrieves AI-and-diabetes publications from PubMed, extracts institutional
affiliations, classifies them into disciplinary domains, builds period-specific
institutional collaboration networks, and computes longitudinal network,
interdisciplinarity, geographic, and funding-stratified metrics that underpin the
manuscript and its supplementary materials.

> The PubMed search is hard-capped at **2025-12-31** so that 2026 publications are excluded.

## What's in this repository

This repository holds the **code** and the **generated analytical outputs** (tables,
networks, figures, notebooks) that support the manuscript and supplement. It does **not**
contain the manuscript documents themselves, nor the raw PubMed datasets (see
[Data availability](#data-availability)).

```text
config/protocol.yaml              Frozen protocol: PubMed queries, temporal periods, keywords, domain scheme, output paths
src/ai_diabetology/               Core pipeline package (affiliation parsing, classification, networks, metrics, geography, funding)
src/ai_diabetology_llm/           Optional LLM sidecar for affiliation-domain classification
scripts/                          Data acquisition, pipeline, figure, and report-generation entry points
sidecars/                         Configuration for the LLM affiliation-classification sidecar
tests/                            Unit tests for method-critical logic
notebooks/Manuscript_Figures.ipynb  Notebook reproducing manuscript figures
outputs/
  tables/                         Result tables (CSV) behind every reported metric
  networks/                       Period institutional collaboration networks (GraphML)
  networks_funding/               Funding-stratified period networks (GraphML)
  networks_html/                  Interactive period network visualizations (HTML)
  networks_html_funding/          Interactive funding-stratified network visualizations (HTML)
  runs/                           Run manifest (provenance)
data/llm/                         Derived LLM affiliation-domain classifications + low-confidence review queue
docs/report_assets/               Code-generated analysis figures
Reports/figures/manuscript_v3/    Final manuscript and supplementary figures (PDF / PNG / TIFF)
Reports/validation/               LLM-classification validation notebook (n = 100) + labeled sample
```

## Reproducing the analysis

Requires **Python ≥ 3.12, < 3.14**.

```bash
# 1. Install dependencies
pip install -r requirements-dev.txt        # or: make install

# 2. Provide credentials (PubMed E-utilities; OpenAI only to re-run the LLM sidecar)
cp .env.example .env                        # then set NCBI_EMAIL (NCBI_API_KEY / OPENAI_API_KEY optional)

# 3. Fetch PubMed snapshots (raw data is not distributed — see Data availability)
make fetch                                  # scripts/fetch_pubmed.py --protocol config/protocol.yaml --output-dir data/raw

# 4. Run the end-to-end pipeline (preprocessing -> networks -> metrics -> funding-stratified analysis)
make run

# 5. (optional) Reproduce the manuscript figures
jupyter notebook notebooks/Manuscript_Figures.ipynb
```

Run the tests with `make test` (`pytest`) and lint with `make lint` (`ruff check .`).

## Institutional-domain classification and validation

Affiliations are assigned to one of twelve institutional domains plus a residual
"Other" category using an LLM-assisted single-label classifier
(`src/ai_diabetology_llm/`, configured under `sidecars/`). The derived labels are in
`data/llm/results/affiliation_classifications.csv`. Agreement against a blinded,
100-affiliation expert sample is reproduced in
`Reports/validation/LLM_classification_validation.ipynb`
(84% agreement, Cohen's kappa = 0.81).

## Data availability

The **raw PubMed datasets are not included** in this repository. They can be regenerated
exactly from `config/protocol.yaml` with `make fetch` (requires a valid `NCBI_EMAIL`).
All derived analytical outputs needed to reproduce the figures and tables are included.

The full interactive network for the 2016–2019 period
(`outputs/networks_html/institutions_2016_2019.html`, about 108 MB) is **omitted** because
it exceeds GitHub's 100 MB per-file limit. It is fully regenerable from the included GraphML
(`outputs/networks/institutions_2016_2019.graphml`) and is available on request.

## Citation

If you use this repository, please cite the associated manuscript and this software
(see `CITATION.cff`):

```bash
git clone https://github.com/druday/AI_in_Diabetes_Trends_1988_2025.git
```

## License

Released under the MIT License — see [`LICENSE`](LICENSE).
