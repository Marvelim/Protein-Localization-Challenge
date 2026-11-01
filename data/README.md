# Data

```text
data/
  raw/CM4AI-DREAM/            read-only mirror of huggingface.co/datasets/LundbergLab/CM4AI-DREAM
    README.md  LICENSE.md     upstream dataset card and license note
    HPA-train_v1.0/           HPA v25 single-cell crops, 609 GB, CC BY 4.0
      hpa_train_manifest.csv.gz   1,245,396 cells, 15,674 antibodies, 39 cell lines
      tars/<prefix>/<AntibodyID>.tar   17 prefix folders (CAB00-08, HPA00-07)
      LICENSE.txt
    KOLF-train_v1.0/          CM4AI KOLF2.1J iPSC crops (the test cell line), 80 GB, CC BY 4.0
      kolf_train_manifest.csv.gz  104,352 cells, 495 antibodies (494 genes)
      tars/<prefix>/<AntibodyID>.tar   10 prefix folders
      LICENSE.txt
  processed/                  everything derived from raw/ (splits, indexes, caches)
    split.csv.gz              train/validation split of every KOLF and HPA cell (see below)
```

Source: Hugging Face revision `b5b90b3131430a8458ff5f87b3dfbc859c245f76`, downloaded by
`bash slurm_jobs/download_data.sh` (rerun to resume). Verify with `bash checks/verify_data.sh`
(sizes, SHA-256, every manifest member present in its tar).

Tars are kept packed on purpose: HPA cannot be extracted within the scratch quota, and reading
from a few large tars is faster on NFS than 6.2M loose PNGs.

## One cell

Each manifest row is one cell. `tar_file` is the tar basename (look under `tars/*/`); the path columns
are members inside that tar:

| Member | Content |
|---|---|
| `protein_path` | protein of interest, the prediction target (green) |
| `nucleus_path`, `microtubules_path`, `er_path` | reference channels, the model inputs |
| `mask_path` | dilated whole-cell mask of the centre cell (255/0) |
| `sequence_path` | `<AntibodyID>.faa`, one FASTA record per target gene (Ensembl 109) |

All images are 512x512 8-bit grayscale PNGs at 0.0941867 µm/px; channels are unmasked, so
neighbouring cells appear. Other columns: `antibody_id`, `ensembl_protein_id`, `ensembl_gene_id`,
`gene_name` (`;`-separated for multi-target antibodies), `cell_line`, `locations` (per-image HPA
annotation, empty = negative), `fov_key` (crops from one FOV overlap).

## Things that matter for modelling

- Test set: ~50k KOLF2.1J cells, ~500 proteins, same format; the model sees only the three
  reference channels, the FASTA and (optionally) the mask. Scoring is on PNG/255 floats
  (MAE, RMSE, max error, cosine).
- KOLF vs HPA: KOLF is normalized per well (higher background), has no edge padding, and its
  cells are ~4.5x smaller in the crop (median mask 22k vs 99k px).
- 484 KOLF antibodies also appear in HPA-train with identical FASTA files.
- Validation splits: split by gene (expand the `;` lists) or by sequence similarity, never by
  antibody or FOV.
- Use only these HPA v25 crops; earlier HPA releases and Kaggle HPA data are disallowed.
- Attribution: HPA (Thul et al., Science 2017) and CM4AI (Clark et al., bioRxiv 2024); see each
  `LICENSE.txt`.

## Train/validation split

`processed/split.csv.gz` has one row per cell of both manifests, with columns `source` (`KOLF`/`HPA`),
`image_key`, `split` and `group`. Join it with a manifest on `image_key` to get the tar members:

```python
split = pd.read_csv("data/processed/split.csv.gz")
kolf = pd.read_csv("data/raw/CM4AI-DREAM/KOLF-train_v1.0/kolf_train_manifest.csv.gz").merge(
    split[split.source == "KOLF"], on="image_key")
```

Validation uses KOLF cells only, because only KOLF2.1J is scored. Each part mimics one part of the
hidden test set (500 disclosed proteins in new cells, 400 undisclosed proteins):

| `split` | Mimics | Rule | KOLF cells | Antibodies | Groups |
|---|---|---|---|---|---|
| `train` | — | everything below not held out | 69,940 | 384 | 340 |
| `val_s` | disclosed proteins, new FOV | 100 antibodies; one of their two FOVs | 10,576 | 100 | 93 |
| `val_u_kolf` | undisclosed proteins that are in HPA | 50 groups; out of KOLF train, HPA cells kept in train | 10,885 | 53 | 50 |
| `val_u_strict` | undisclosed proteins not in HPA | 50 groups; out of KOLF train and HPA train | 12,951 | 58 | 50 |

HPA cells are `train` (1,234,234) or `excluded` (11,162 cells, 141 antibodies: the HPA cells of the
50 `val_u_strict` groups). Train on `split == "train"` rows of both sources; never use `excluded`.

- **Group**: a connected component of genes linked by a shared antibody, or by an MMseqs2 hit
  (>=30% identity, >=80% coverage of both sequences) between any of their stained isoforms;
  named by its smallest gene id. Different antibodies of one gene can stain different isoforms
  (94 genes), so sequences are keyed by ENSP and each isoform is linked to its gene.
  13,464 sequences, 13,370 genes, 9,538 groups; the largest has 321 genes (7 in KOLF).
- **Sampling**: units are sorted by the KOLF frequency of their rarest location (ties random)
  and drawn by systematic sampling, so rare localizations land in validation. Order:
  `val_u_strict`, then `val_u_kolf` from the remaining groups, then `val_s` antibodies from the
  remaining groups. Seed 0; rerunning gives the same table.
- **Leak-free**: no FOV spans two splits, no `val_u` group has a KOLF `train` or `val_s` cell, and
  no `val_u_strict` group has an HPA `train` cell.
- Score each validation part with the official metric on full 512x512 images (PNG/255), with sums
  pooled over all cells of the part; the headline is the 50/50 mix of `val_s` and `val_u`. For
  the final submission, retrain on all cells, including `excluded` and the validation parts.

Build: `bash slurm_jobs/make_split.sh` (CPU, ~20 min; job 156739). Check:
`bash checks/check_split.sh` (job 156744: OK).
