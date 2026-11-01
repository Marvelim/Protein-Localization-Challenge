#!/bin/bash
#SBATCH --job-name=cm4ai_check_split
#SBATCH --account=eae
#SBATCH --partition=hai
#SBATCH --exclude=haic-hgx-1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:00:00
# Check data/processed/split.csv.gz for coverage, sizes and leaks.
# Usage: bash checks/check_split.sh
set -euo pipefail
if [[ ${1:-} != --slurm-run ]]; then
    repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
    printf '%s\n' 'Resources: CPU only; 4 CPUs, 32 GiB RAM, up to 1 hour; no extra disk.'
    job=$(sbatch --hold --parsable --chdir="$repo_root" \
        --output="$repo_root/runs/%j/slurm.out" --error="$repo_root/runs/%j/slurm.err" \
        "$repo_root/checks/check_split.sh" --slurm-run)
    [[ $job =~ ^[0-9]+$ ]]
    mkdir -p "$repo_root/runs/$job"
    printf '%s\n' 'Check the split table for coverage, sizes and leaks, and print its statistics.' > "$repo_root/runs/$job/why.txt"
    scontrol release "$job"
    printf 'Submitted %s; logs: %s/runs/%s\n' "$job" "$repo_root" "$job"
    exit 0
fi
: "${SLURM_JOB_ID:?Run through Slurm}"
cd "${SLURM_SUBMIT_DIR:?}"
exec conda run --no-capture-output -n jit python -I checks/check_split.py data/raw/CM4AI-DREAM data/processed/split.csv.gz
