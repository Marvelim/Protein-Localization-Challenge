#!/bin/bash
#SBATCH --job-name=cm4ai_verify
#SBATCH --account=eae
#SBATCH --partition=hai
#SBATCH --exclude=haic-hgx-1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=12:00:00
# Verify data/raw/CM4AI-DREAM (sizes, SHA-256, manifest members) on a CPU node.
# Usage: bash checks/verify_data.sh
set -euo pipefail
if [[ ${1:-} != --slurm-run ]]; then
    repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
    printf '%s\n' 'Resources: CPU only; 32 CPUs, 64 GiB RAM, up to 12 hours; no extra disk.'
    job=$(sbatch --hold --parsable --chdir="$repo_root" \
        --output="$repo_root/runs/%j/slurm.out" --error="$repo_root/runs/%j/slurm.err" \
        "$repo_root/checks/verify_data.sh" --slurm-run)
    [[ $job =~ ^[0-9]+$ ]]
    mkdir -p "$repo_root/runs/$job"
    printf '%s\n' 'Verify the downloaded CM4AI-DREAM data against the pinned Hugging Face revision and the manifests.' > "$repo_root/runs/$job/why.txt"
    scontrol release "$job"
    printf 'Submitted %s; logs: %s/runs/%s\n' "$job" "$repo_root" "$job"
    exit 0
fi
: "${SLURM_JOB_ID:?Run through Slurm}"
cd "${SLURM_SUBMIT_DIR:?}"
export HF_HOME="$PWD/.cache/huggingface"
exec conda run --no-capture-output -n jit python -I checks/verify_data.py data/raw/CM4AI-DREAM 32
