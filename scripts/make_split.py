"""Build the train/validation split table for KOLF-train and HPA-train.

Split unit for unseen proteins: a sequence group, i.e. a connected component of genes linked by a
shared antibody, or by an MMseqs2 hit with >=30% identity and >=80% coverage of both sequences between
any of their stained isoforms (ENSPs).
- val_u_strict: 50 groups; their KOLF cells validate, their HPA cells are excluded.
- val_u_kolf:   50 groups; their KOLF cells validate, their HPA cells stay in train.
- val_s:        100 KOLF antibodies of the other groups; one random FOV of each validates.
- train:        everything else.
Units are drawn by systematic sampling over (rarest KOLF location, random) order so rare
localizations land in validation.
Output columns: source (KOLF/HPA), image_key, split, group; join with the manifests on image_key.
Usage: python -I scripts/make_split.py data/raw/CM4AI-DREAM data/processed/split.csv.gz <workers>
"""
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 0
N_STRICT, N_KOLF, N_S = 50, 50, 100


def read_fasta(tar_path):
    with tarfile.open(tar_path, "r:") as tar:
        for member in tar:
            if member.name.endswith(".faa"):
                return tar_path.stem, tar.extractfile(member).read().decode()
    raise AssertionError(f"no .faa in {tar_path}")


def protein_sequences(manifest, tar_paths, workers):
    """ENSP -> (gene id, sequence), from each antibody's FASTA (records follow the manifest order).
    Antibodies of one gene may stain different isoforms, so sequences are keyed by ENSP."""
    antibodies = manifest.drop_duplicates("antibody_id").set_index("antibody_id")
    seqs = {}
    with Pool(workers) as pool:
        for i, (antibody, text) in enumerate(pool.imap_unordered(read_fasta, tar_paths, chunksize=8), 1):
            records = [r.split("\n", 1) for r in text.split(">")[1:]]
            proteins = antibodies.ensembl_protein_id[antibody].split(";")
            genes = antibodies.ensembl_gene_id[antibody].split(";")
            assert [h.split("|")[1] for h, _ in records] == [f"ensembl_protein_id={p}" for p in proteins], antibody
            for gene, protein, (_, seq) in zip(genes, proteins, records):
                entry = (gene, seq.replace("\n", ""))
                assert seqs.setdefault(protein, entry) == entry, f"{protein} has different genes or sequences"
            if i % 2000 == 0:
                print(f"read {i}/{len(tar_paths)} FASTA files", flush=True)
    return seqs


def similar_pairs(seqs, workers):
    with tempfile.TemporaryDirectory() as tmp:
        fasta, hits = Path(tmp, "proteins.fasta"), Path(tmp, "hits.tsv")
        fasta.write_text("".join(f">{g}\n{s}\n" for g, s in seqs.items()))
        subprocess.run(["mmseqs", "easy-search", fasta, fasta, hits, Path(tmp, "work"),
                        "--min-seq-id", "0.3", "-c", "0.8", "--cov-mode", "0",
                        "--format-output", "query,target", "--threads", str(workers), "-v", "1"], check=True)
        return pd.read_csv(hits, sep="\t", names=["query", "target"])


def components(edges):
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        parent[find(a)] = find(b)
    members = pd.Series({x: find(x) for x in parent})
    return members.map(members.groupby(members).apply(lambda s: min(s.index)))  # name = smallest id, a gene (ENSG < ENSP)


def systematic_pick(strata, k, rng):
    """Pick k units evenly spaced over the units sorted by (stratum rarity, random)."""
    order = sorted(strata.index, key=lambda u: (strata[u], rng.random()))
    return [order[i] for i in ((np.arange(k) + rng.random()) * len(order) / k).astype(int)]


def main(root, out, workers):
    root, rng = Path(root), np.random.default_rng(SEED)
    kolf = pd.read_csv(root / "KOLF-train_v1.0/kolf_train_manifest.csv.gz",
                       usecols=["image_key", "antibody_id", "ensembl_protein_id", "ensembl_gene_id", "locations", "fov_key"])
    hpa = pd.read_csv(root / "HPA-train_v1.0/hpa_train_manifest.csv.gz",
                      usecols=["image_key", "antibody_id", "ensembl_protein_id", "ensembl_gene_id"])
    both = pd.concat([kolf, hpa])
    tar_paths = sorted(root.glob("*-train_v1.0/tars/*/*.tar"))
    assert {p.stem for p in tar_paths} == set(both.antibody_id)

    seqs = protein_sequences(both, tar_paths, workers)
    pairs = similar_pairs({protein: seq for protein, (_, seq) in seqs.items()}, workers)
    antibody_genes = both.drop_duplicates("antibody_id").set_index("antibody_id").ensembl_gene_id.str.split(";")
    edges = [(gene, protein) for protein, (gene, _) in seqs.items()] + list(pairs.itertuples(index=False, name=None))
    edges += [(gs[0], g) for gs in antibody_genes for g in gs[1:]]
    group_of_gene = components(edges)
    group_of_antibody = antibody_genes.str[0].map(group_of_gene)
    print(f"{len(seqs)} proteins, {len({g for g, _ in seqs.values()})} genes, {len(pairs)} MMseqs2 hits, {group_of_gene.nunique()} groups", flush=True)

    # Stratum of a unit: frequency (over KOLF antibodies) of its rarest location; rarer sorts first.
    ab_locs = kolf.drop_duplicates("antibody_id").set_index("antibody_id").locations.str.split(";")
    freq = Counter(loc for locs in ab_locs for loc in locs)
    ab_rarity = ab_locs.map(lambda locs: min(freq[loc] for loc in locs))
    kolf_groups = ab_rarity.groupby(group_of_antibody[ab_rarity.index]).min()

    strict = set(systematic_pick(kolf_groups, N_STRICT, rng))
    kolf_val = set(systematic_pick(kolf_groups.drop(list(strict)), N_KOLF, rng))
    seen = ab_rarity[~group_of_antibody[ab_rarity.index].isin(strict | kolf_val)]
    fovs = kolf.groupby("antibody_id").fov_key.unique().map(sorted)
    val_s_fovs = {fovs[ab][rng.integers(len(fovs[ab]))] for ab in systematic_pick(seen, N_S, rng)}

    kolf["group"] = kolf.antibody_id.map(group_of_antibody)
    kolf["split"] = np.select([kolf.group.isin(strict), kolf.group.isin(kolf_val), kolf.fov_key.isin(val_s_fovs)],
                              ["val_u_strict", "val_u_kolf", "val_s"], "train")
    hpa["group"] = hpa.antibody_id.map(group_of_antibody)
    hpa["split"] = np.where(hpa.group.isin(strict), "excluded", "train")
    table = pd.concat([kolf.assign(source="KOLF"), hpa.assign(source="HPA")])[["source", "image_key", "split", "group"]]
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out, index=False)
    print(table.groupby(["source", "split"]).size().to_string())
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))
