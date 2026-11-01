"""Show why one gene has different FASTA sequences across antibodies, and how common that is.

Usage: python -I checks/diff_sequences.py data/raw/CM4AI-DREAM <gene_id>
"""
import sys
import tarfile
from pathlib import Path

import pandas as pd

root, gene = Path(sys.argv[1]), sys.argv[2]
cols = ["antibody_id", "ensembl_protein_id", "ensembl_gene_id", "gene_name"]
m = pd.concat([pd.read_csv(root / f"{r}-train_v1.0/{r.lower()}_train_manifest.csv.gz", usecols=cols) for r in ["HPA", "KOLF"]])
m = m.drop_duplicates("antibody_id")
pairs = pd.DataFrame([(a, g, p) for a, gs, ps in zip(m.antibody_id, m.ensembl_gene_id.str.split(";"), m.ensembl_protein_id.str.split(";"))
                      for g, p in zip(gs, ps)], columns=["antibody", "gene", "protein"])
n_prot = pairs.groupby("gene").protein.nunique()
print("genes:", len(n_prot), "genes with >1 ENSP across antibodies:", (n_prot > 1).sum())
print(pairs[pairs.gene == gene].to_string())
for ab in pairs[pairs.gene == gene].antibody:
    tar_path = next(root.glob(f"*-train_v1.0/tars/*/{ab}.tar"))
    with tarfile.open(tar_path) as tar:
        faa = next(t for t in tar if t.name.endswith(".faa"))
        text = tar.extractfile(faa).read().decode()
    for rec in text.split(">")[1:]:
        head, seq = rec.split("\n", 1)
        print(ab, head, len(seq.replace("\n", "")), seq.replace("\n", "")[:40])
