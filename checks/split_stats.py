"""Print manifest statistics that decide the train/validation split (KOLF and HPA)."""
import sys

import pandas as pd

root = sys.argv[1]
kolf = pd.read_csv(f"{root}/KOLF-train_v1.0/kolf_train_manifest.csv.gz")
hpa = pd.read_csv(f"{root}/HPA-train_v1.0/hpa_train_manifest.csv.gz",
                  usecols=["image_key", "antibody_id", "ensembl_gene_id", "cell_line", "locations", "fov_key"])

print("KOLF columns:", list(kolf.columns))
print(kolf.head(3).T.to_string())
print("KOLF fov_key examples:", kolf.fov_key.drop_duplicates().sample(8, random_state=0).tolist())
print("KOLF cells", len(kolf), "abs", kolf.antibody_id.nunique(), "fovs", kolf.fov_key.nunique())

g = kolf.groupby("antibody_id")
print("cells/antibody:", g.size().describe().to_string())
print("fovs/antibody:", g.fov_key.nunique().value_counts().sort_index().to_string())
print("antibodies/fov:", kolf.groupby("fov_key").antibody_id.nunique().value_counts().to_string())

kg = kolf.assign(gene=kolf.ensembl_gene_id.str.split(";")).explode("gene")
print("multi-target KOLF antibodies:", (kolf.drop_duplicates("antibody_id").ensembl_gene_id.str.contains(";")).sum())
abs_per_gene = kg.groupby("gene").antibody_id.nunique()
print("KOLF genes with >1 antibody:", (abs_per_gene > 1).sum(), abs_per_gene[abs_per_gene > 1].to_dict())
# connected components of the antibody<->gene graph = minimal leak-free split units
parent = {}
def find(x):
    while parent.setdefault(x, x) != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x
for ab, gene in kg[["antibody_id", "gene"]].drop_duplicates().itertuples(index=False):
    parent[find("ab:" + ab)] = find("g:" + gene)
print("KOLF antibody-gene components:", len({find("ab:" + a) for a in kolf.antibody_id.unique()}))

print("KOLF location counts (per antibody, exploded):")
loc = kolf.drop_duplicates("antibody_id").locations.fillna("NEGATIVE").str.split(";").explode()
print(loc.value_counts().to_string())
print("KOLF antibodies with empty locations in some cells:", kolf[kolf.locations.isna()].antibody_id.nunique())
print("per-antibody distinct location strings >1:", (g.locations.nunique() > 1).sum())

hg = hpa.assign(gene=hpa.ensembl_gene_id.str.split(";")).explode("gene")
kolf_abs, kolf_genes = set(kolf.antibody_id), set(kg.gene)
print("HPA cells", len(hpa), "abs", hpa.antibody_id.nunique(), "genes", hg.gene.nunique(), "cell lines", hpa.cell_line.nunique())
print("KOLF abs in HPA:", len(kolf_abs & set(hpa.antibody_id)), "KOLF genes in HPA:", len(kolf_genes & set(hg.gene)))
print("HPA cells of KOLF genes:", hg[hg.gene.isin(kolf_genes)].image_key.nunique())
print("HPA genes not in KOLF:", hg.gene.nunique() - len(kolf_genes & set(hg.gene)))
print("HPA cells/cell_line:", hpa.cell_line.value_counts().to_string())
