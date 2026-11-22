# olist-ecommerce-sql-analysis

SQL analysis of the Brazilian e-commerce dataset (Kaggle Olist): revenue categories, delivery trends, and customer ratings.

**Status: work in progress, built in stages.**

- Stage 1 (done): reproducible data pipeline - fetch the nine Olist CSVs,
  load them into a local SQLite database (`data/processed/olist.db`) and run
  integrity checks (20 passing tests). Methods and results:
  [docs/data-pipeline.md](docs/data-pipeline.md).
- Stage 2 (next): first SQL analysis tables - revenue by product category,
  delivery performance and review scores.

## Data source and license

- Dataset: [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
  (Kaggle, Version 2): ~100k real, anonymised orders from 2016-2018 across
  Brazilian marketplaces.
- License: [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
  Attribution: data provided by Olist. Non-commercial use only, derivatives
  under the same license.
- CSVs are pulled from a public GitHub mirror because Kaggle requires a
  signed-in account for downloads; the mirror content is verified against
  the canonical row counts in `src/build_dataset.py`.
- Raw CSVs and the built database are not committed (121 MB); they are
  regenerated with the two commands below.

## Reproduce

```bash
pip install -r requirements.txt
python src/fetch_data.py     # downloads raw CSVs into data/raw/
python src/build_dataset.py  # builds data/processed/olist.db + checks
python -m pytest tests/ -q   # 20 integrity tests
```
