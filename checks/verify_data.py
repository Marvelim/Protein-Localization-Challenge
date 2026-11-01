"""Verify data/raw/CM4AI-DREAM against the pinned Hugging Face revision.

Checks: every repo file exists locally with the right size and (for LFS files) SHA-256;
every manifest row's six members exist in its tar; row/antibody counts match the challenge docs.
Usage: python -I checks/verify_data.py data/raw/CM4AI-DREAM <workers>
"""
import csv
import gzip
import hashlib
import sys
import tarfile
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

from huggingface_hub import HfApi

REVISION = "b5b90b3131430a8458ff5f87b3dfbc859c245f76"
MEMBER_COLUMNS = ["protein_path", "nucleus_path", "microtubules_path", "er_path", "mask_path", "sequence_path"]
# From the challenge Data page: (rows, antibodies, tar folder count).
EXPECTED = {"HPA-train_v1.0": (1_245_396, 15_674, 17), "KOLF-train_v1.0": (104_352, 495, 10)}


def check_file(job):
    path, size, sha256, wanted_members = job
    assert path.stat().st_size == size, f"size mismatch: {path}"
    if sha256 is not None:
        with open(path, "rb") as f:
            assert hashlib.file_digest(f, "sha256").hexdigest() == sha256, f"sha256 mismatch: {path}"
    if wanted_members:
        with tarfile.open(path, "r:") as tar:
            missing = wanted_members - set(tar.getnames())
        assert not missing, f"{path} lacks {len(missing)} manifest members, e.g. {sorted(missing)[:3]}"
    return size


def main(root, workers):
    root = Path(root)
    remote = [f for f in HfApi().list_repo_tree("LundbergLab/CM4AI-DREAM", repo_type="dataset",
                                                revision=REVISION, recursive=True) if hasattr(f, "size")]
    remote_paths = {f.path for f in remote}
    local_paths = {p.relative_to(root).as_posix() for p in root.rglob("*")
                   if p.is_file() and ".cache" not in p.relative_to(root).parts}
    assert local_paths == remote_paths, (f"missing {sorted(remote_paths - local_paths)[:5]}, "
                                         f"extra {sorted(local_paths - remote_paths)[:5]}")

    members = defaultdict(set)  # repo path of tar -> member names required by the manifest
    for release, (n_rows, n_antibodies, n_folders) in EXPECTED.items():
        tar_dirs = {p.name: p.parent.name for p in (root / release / "tars").glob("*/*.tar")}
        assert len(set(tar_dirs.values())) == n_folders, f"{release}: tar folder count"
        manifest = next((root / release).glob("*_manifest.csv.gz"))
        rows, antibodies = 0, set()
        with gzip.open(manifest, "rt", newline="") as stream:
            for row in csv.DictReader(stream):
                rows += 1
                antibodies.add(row["antibody_id"])
                key = f"{release}/tars/{tar_dirs[row['tar_file']]}/{row['tar_file']}"
                members[key].update(row[c] for c in MEMBER_COLUMNS)
        assert (rows, len(antibodies)) == (n_rows, n_antibodies), f"{release}: {rows} rows, {len(antibodies)} antibodies"
        assert len(antibodies) == len(tar_dirs), f"{release}: {len(tar_dirs)} tars for {len(antibodies)} antibodies"
        print(f"{release}: {rows} rows, {len(antibodies)} antibodies, {len(tar_dirs)} tars", flush=True)

    jobs = [(root / f.path, f.size, f.lfs.sha256 if f.lfs else None, members.get(f.path)) for f in remote]
    jobs.sort(key=lambda j: -j[1])  # largest first for better load balance
    done = 0
    with Pool(workers) as pool:
        for i, size in enumerate(pool.imap_unordered(check_file, jobs), 1):
            done += size
            if i % 1000 == 0 or i == len(jobs):
                print(f"verified {i}/{len(jobs)} files, {done / 1e9:.1f} GB", flush=True)
    print("OK: all files match the pinned revision and every manifest member is present")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
