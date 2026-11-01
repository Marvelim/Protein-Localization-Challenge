#!/bin/bash
#SBATCH --job-name=cm4ai_make_split
#SBATCH --account=eae
#SBATCH --partition=hai
#SBATCH --exclude=haic-hgx-1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=04:00:00
# Build data/processed/split.csv.gz (train/val_s/val_u_kolf/val_u_strict) on a CPU node.
# Usage: bash slurm_jobs/make_split.sh
set -euo pipefail
if [[ ${1:-} != --slurm-run ]]; then
    repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
    printf '%s\n' 'Resources: CPU only; 32 CPUs, 64 GiB RAM, up to 4 hours; disk ~50 MB (split table) plus MMseqs2 scratch in /tmp.'
    job=$(sbatch --hold --parsable --chdir="$repo_root" \
        --output="$repo_root/runs/%j/slurm.out" --error="$repo_root/runs/%j/slurm.err" \
        "$repo_root/slurm_jobs/make_split.sh" --slurm-run)
    [[ $job =~ ^[0-9]+$ ]]
    mkdir -p "$repo_root/runs/$job"
    printf '%s\n' 'Build the leak-free train/validation split table (100 val_s antibodies, 50+50 val_u sequence groups).' > "$repo_root/runs/$job/why.txt"
    scontrol release "$job"
    printf 'Submitted %s; logs: %s/runs/%s\n' "$job" "$repo_root" "$job"
    exit 0
fi
: "${SLURM_JOB_ID:?Run through Slurm}"
cd "${SLURM_SUBMIT_DIR:?}"
exec conda run --no-capture-output -n jit python -I scripts/make_split.py data/raw/CM4AI-DREAM data/processed/split.csv.gz 32
