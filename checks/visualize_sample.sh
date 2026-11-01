#!/bin/bash
#SBATCH --job-name=cm4ai_visualize_sample
#SBATCH --account=eae
#SBATCH --partition=hai
#SBATCH --exclude=haic-hgx-1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
# Plot one KOLF training cell (inputs + protein target) into runs/<job_id>/
# Usage: bash checks/visualize_sample.sh [seed]
set -euo pipefail
if [[ ${1:-} != --slurm-run ]]; then
    repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
    printf '%s\n' 'Resources: CPU only; 2 CPUs, 8 GiB RAM, up to 15 minutes; no extra disk.'
    job=$(sbatch --hold --parsable --chdir="$repo_root" \
        --output="$repo_root/runs/%j/slurm.out" --error="$repo_root/runs/%j/slurm.err" \
        "$repo_root/checks/visualize_sample.sh" --slurm-run "${1:-0}")
    [[ $job =~ ^[0-9]+$ ]]
    mkdir -p "$repo_root/runs/$job"
    printf '%s\n' 'Visualize one KOLF training cell (reference channels, mask, FASTA, protein target) to see the challenge data format.' > "$repo_root/runs/$job/why.txt"
    scontrol release "$job"
    printf 'Submitted %s; logs: %s/runs/%s\n' "$job" "$repo_root" "$job"
    exit 0
fi
: "${SLURM_JOB_ID:?Run through Slurm}"
cd "${SLURM_SUBMIT_DIR:?}"
exec conda run --no-capture-output -n jit python -I checks/visualize_sample.py data/raw/CM4AI-DREAM "runs/$SLURM_JOB_ID" "${2:?seed}"
