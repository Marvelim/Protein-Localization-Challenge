"""Plot a grid of training cells (12 KOLF + 4 HPA, one per antibody) to compare the mask size with the 512x512 crop.

Each cell gets two panels: the full crop (R=microtubules, G=protein, B=nucleus, white mask outline)
and the protein channel zoomed to the mask bounding box.
Usage: python -I checks/visualize_samples_grid.py data/raw/CM4AI-DREAM <out_dir> <seed>
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

COLS = ["image_key", "antibody_id", "gene_name", "cell_line", "locations", "tar_file",
        "protein_path", "nucleus_path", "microtubules_path", "mask_path"]
root, out_dir, seed = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])


def pick(release, manifest, n):
    m = pd.read_csv(root / release / manifest, usecols=COLS)
    m = m[m.locations.notna()]
    abs_ = m.antibody_id.drop_duplicates().sample(n, random_state=seed)
    return [(release, r) for _, r in m[m.antibody_id.isin(abs_)].groupby("antibody_id").sample(1, random_state=seed).iterrows()]


def load(release, row):
    [tar_path] = (root / release).glob(f"tars/*/{row.tar_file}")
    with tarfile.open(tar_path, "r:") as tar:
        img = {c: np.asarray(Image.open(io.BytesIO(tar.extractfile(row[f"{c}_path"]).read())))
               for c in ["protein", "nucleus", "microtubules", "mask"]}
    for name, a in img.items():
        assert a.shape == (512, 512) and a.dtype == np.uint8, (row.image_key, name, a.shape, a.dtype)
    return img


cells = pick("KOLF-train_v1.0", "kolf_train_manifest.csv.gz", 12) + pick("HPA-train_v1.0", "hpa_train_manifest.csv.gz", 4)
fig, axes = plt.subplots(4, 8, figsize=(24, 13.5))
rows = []
for (release, row), (ax_full, ax_zoom) in zip(cells, axes.reshape(-1, 2)):
    img = load(release, row)
    mask = img["mask"] > 0
    frac = mask.mean()
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = max(ys.min() - 10, 0), min(ys.max() + 11, 512), max(xs.min() - 10, 0), min(xs.max() + 11, 512)
    rgb = np.stack([img["microtubules"], img["protein"], img["nucleus"]], -1)
    ax_full.imshow(rgb)
    ax_full.contour(mask, levels=[0.5], colors="white", linewidths=0.8)
    ax_full.set_title(f"{row.cell_line}  {row.gene_name}\nmask {frac:.1%} of crop", fontsize=10)
    ax_zoom.imshow(img["protein"][y0:y1, x0:x1], cmap="gray", vmin=0, vmax=255)
    ax_zoom.contour(mask[y0:y1, x0:x1], levels=[0.5], colors="lime", linewidths=0.8)
    ax_zoom.set_title(f"protein, zoom to mask\n{row.locations[:40]}", fontsize=9)
    for ax in (ax_full, ax_zoom):
        ax.axis("off")
    rows.append(dict(release=release, image_key=row.image_key, gene=row.gene_name, locations=row.locations,
                     mask_px=int(mask.sum()), mask_frac=round(float(frac), 4),
                     bbox_hw=f"{y1 - y0}x{x1 - x0}", protein_mean_in=round(img["protein"][mask].mean() / 255, 4),
                     protein_mean_out=round(img["protein"][~mask].mean() / 255, 4)))
axes[0, 0].plot([20, 20 + 10 / 0.0941867], [490, 490], color="white", lw=3)  # 10 µm scale bar
fig.suptitle("Rows 1-3: KOLF2.1J (test cell line), row 4: HPA. Left: full 512x512 crop "
             "(R=microtubules, G=protein, B=nucleus, white = mask). Right: protein channel cropped to the mask box. "
             "Scale bar 10 µm.", fontsize=12)
fig.tight_layout()
out_dir.mkdir(parents=True, exist_ok=True)
fig.savefig(out_dir / "samples_grid.png", dpi=110)
table = pd.DataFrame(rows)
table.to_csv(out_dir / "samples_grid.csv", index=False)
print(table.to_string())
print("saved", out_dir / "samples_grid.png")
