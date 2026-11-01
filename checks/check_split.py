"""Check data/processed/split.csv.gz for coverage, sizes and leaks, then print its statistics.

Usage: python -I checks/check_split.py data/raw/CM4AI-DREAM data/processed/split.csv.gz
"""
import sys

import pandas as pd

root, split_path = sys.argv[1], sys.argv[2]
cols = ["image_key", "antibody_id", "ensembl_gene_id", "locations", "fov_key"]
manifests = pd.concat([pd.read_csv(f"{root}/KOLF-train_v1.0/kolf_train_manifest.csv.gz", usecols=cols).assign(source="KOLF"),
                       pd.read_csv(f"{root}/HPA-train_v1.0/hpa_train_manifest.csv.gz", usecols=cols).assign(source="HPA")])
table = pd.read_csv(split_path)
assert not table.duplicated(["source", "image_key"]).any()
df = manifests.merge(table, on=["source", "image_key"], how="outer", validate="1:1", indicator=True)
assert (df._merge == "both").all(), "table and manifests cover different cells"
kolf, hpa = df[df.source == "KOLF"], df[df.source == "HPA"]

# a gene belongs to exactly one group
genes = df.assign(gene=df.ensembl_gene_id.str.split(";")).explode("gene")
assert (genes.groupby("gene").group.nunique() == 1).all(), "a gene is in several groups"

# unseen-protein splits: whole groups, disjoint, right counts, never in KOLF train
strict = set(kolf[kolf.split == "val_u_strict"].group)
kolf_val = set(kolf[kolf.split == "val_u_kolf"].group)
assert (len(strict), len(kolf_val)) == (50, 50) and not strict & kolf_val
assert (kolf.groupby("group").split.nunique()[list(strict | kolf_val)] == 1).all(), "a val_u group leaks into KOLF train/val_s"
# HPA: strict groups excluded, everything else trains
assert set(hpa.split) == {"train", "excluded"}
assert set(hpa[hpa.split == "excluded"].group) == strict & set(hpa.group)
assert not (hpa.group.isin(strict) & (hpa.split == "train")).any()

# seen-protein split: 100 antibodies, one FOV in val_s and the other in train; FOVs never span splits
assert (kolf.groupby("fov_key").split.nunique() == 1).all(), "a FOV spans splits"
val_s_abs = set(kolf[kolf.split == "val_s"].antibody_id)
assert len(val_s_abs) == 100
fov_splits = kolf[kolf.antibody_id.isin(val_s_abs)].drop_duplicates("fov_key").groupby("antibody_id").split.apply(sorted)
assert fov_splits.map(lambda s: s == ["train", "val_s"]).all()

print(df.groupby(["source", "split"]).agg(cells=("image_key", "size"), antibodies=("antibody_id", "nunique"),
                                          groups=("group", "nunique")).to_string())
locs = kolf.drop_duplicates("antibody_id").assign(loc=lambda d: d.locations.str.split(";")).explode("loc")
print(locs.groupby(["loc", "split"]).size().unstack(fill_value=0).sort_values("train", ascending=False).to_string())
size = pd.DataFrame({"genes": genes.groupby("group").gene.nunique(),
                     "kolf_genes": genes[genes.source == "KOLF"].groupby("group").gene.nunique()}).fillna(0).astype(int)
print("largest groups:\n", size.sort_values("genes", ascending=False).head(10).to_string())
print("KOLF genes per val_u group:", size.loc[list(strict | kolf_val), "kolf_genes"].value_counts().sort_index().to_dict())
print("OK: split table is complete and leak-free")
