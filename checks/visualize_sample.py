"""Plot one KOLF training cell: the model inputs (3 reference channels, mask, FASTA) and the protein target.

Usage: python -I checks/visualize_sample.py data/raw/CM4AI-DREAM <out_dir> <seed>
"""
import io
import sys
import tarfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

root, out_dir, seed = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
release = root / "KOLF-train_v1.0"
manifest = pd.read_csv(release / "kolf_train_manifest.csv.gz")
row = manifest[manifest.locations.notna()].sample(1, random_state=seed).iloc[0]
[tar_path] = release.glob(f"tars/*/{row.tar_file}")

with tarfile.open(tar_path, "r:") as tar:
    read = lambda col: tar.extractfile(row[col]).read()
    img = {c: np.asarray(Image.open(io.BytesIO(read(f"{c}_path")))) for c in ["nucleus", "microtubules", "er", "mask", "protein"]}
    fasta = read("sequence_path").decode()
for name, a in img.items():
    assert a.shape == (512, 512) and a.dtype == np.uint8, (name, a.shape, a.dtype)

records = [r.splitlines() for r in fasta.split(">")[1:]]
seq_info = "; ".join(f"{h.split()[0]} ({len(''.join(s))} aa)" for h, *s in records)
first_seq = "".join(records[0][1:])

# HPA colour convention: nucleus blue, microtubules red, ER yellow, protein green.
f = {k: v / 255.0 for k, v in img.items()}
composite_ref = np.clip(np.stack([f["microtubules"] + f["er"], f["er"], f["nucleus"]], -1), 0, 1)
composite_all = np.clip(np.stack([f["microtubules"], f["protein"], f["nucleus"]], -1), 0, 1)

panels = [("Nucleus (input)", img["nucleus"], "Blues_r"), ("Microtubules (input)", img["microtubules"], "Reds_r"),
          ("ER (input)", img["er"], "YlOrBr_r"), ("Cell mask (input)", img["mask"], "gray"),
          ("Reference composite\nR=MT+ER  G=ER  B=nucleus", composite_ref, None),
          ("Protein (TARGET)", img["protein"], "Greens_r"),
          ("Target composite\nR=MT  G=protein  B=nucleus", composite_all, None),
          ("Protein inside mask", np.where(img["mask"] > 0, img["protein"], 0), "Greens_r")]
fig, axes = plt.subplots(2, 4, figsize=(16, 9.2))
for ax, (title, a, cmap) in zip(axes.flat, panels):
    ax.imshow(a, cmap=cmap, vmin=0, vmax=255) if cmap else ax.imshow(a)
    if title != "Cell mask (input)":
        ax.contour(img["mask"] > 0, levels=[0.5], colors="white", linewidths=0.7)
    ax.set_title(title, fontsize=11)
    ax.axis("off")
scale_px = 10 / 0.0941867  # 10 µm scale bar
axes[0, 0].plot([20, 20 + scale_px], [490, 490], color="white", lw=3)
axes[0, 0].text(20, 475, "10 µm", color="white", fontsize=9)

stats = (f"protein PNG/255: mean {f['protein'].mean():.3f}, max {f['protein'].max():.3f}, "
         f"mean inside mask {f['protein'][img['mask'] > 0].mean():.3f}; mask {int((img['mask'] > 0).sum())} px")
fig.suptitle(f"{row.image_key}   gene {row.gene_name} ({row.ensembl_gene_id})   antibody {row.antibody_id}\n"
             f"cell line {row.cell_line}   HPA location: {row.locations}   FOV {row.fov_key}\n"
             f"FASTA input: {seq_info}   {first_seq[:60]}...\n{stats}", fontsize=11)
fig.tight_layout()
out_dir.mkdir(parents=True, exist_ok=True)
for ext in ["png", "pdf"]:
    fig.savefig(out_dir / f"sample_{row.image_key}.{ext}", dpi=130)
print(row.to_string())
print("FASTA:", fasta[:400])
print(stats)
print("saved", out_dir / f"sample_{row.image_key}.png")
