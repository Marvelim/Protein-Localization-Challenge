#!/bin/bash
#SBATCH --job-name=cm4ai_split_stats
#SBATCH --account=eae
#SBATCH --partition=hai
#SBATCH --exclude=haic-hgx-1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:00:00
# Print manifest statistics for designing the train/validation split.
# Usage: bash checks/split_stats.sh
set -euo pipefail
if [[ ${1:-} != --slurm-run ]]; then
    repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
    printf '%s\n' 'Resources: CPU only; 4 CPUs, 32 GiB RAM, up to 1 hour; no extra disk.'
    job=$(sbatch --hold --parsable --chdir="$repo_root" \
        --output="$repo_root/runs/%j/slurm.out" --error="$repo_root/runs/%j/slurm.err" \
        "$repo_root/checks/split_stats.sh" --slurm-run)
    [[ $job =~ ^[0-9]+$ ]]
    mkdir -p "$repo_root/runs/$job"
    printf '%s\n' 'Compute KOLF/HPA manifest statistics to design a leak-free train/validation split.' > "$repo_root/runs/$job/why.txt"
    scontrol release "$job"
    printf 'Submitted %s; logs: %s/runs/%s\n' "$job" "$repo_root" "$job"
    exit 0
fi
: "${SLURM_JOB_ID:?Run through Slurm}"
cd "${SLURM_SUBMIT_DIR:?}"
exec conda run --no-capture-output -n jit python -I checks/split_stats.py data/raw/CM4AI-DREAM
