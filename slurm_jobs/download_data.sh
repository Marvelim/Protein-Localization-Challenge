#!/bin/bash
#SBATCH --job-name=cm4ai_download
#SBATCH --account=eae
#SBATCH --partition=hai
#SBATCH --exclude=haic-hgx-1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=2-00:00:00
# Download the CM4AI-DREAM training data (HPA-train + KOLF-train, 689 GB) from Hugging Face,
# pinned to one revision, into data/raw/CM4AI-DREAM. Rerunning resumes and skips finished files.
# Usage: bash slurm_jobs/download_data.sh [hf download filters, e.g. --include 'HPA-train_v1.0/tars/HPA00/*']
# Run several in parallel with disjoint filters to download faster.
set -euo pipefail
if [[ ${1:-} != --slurm-run ]]; then
    repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
    printf '%s\n' 'Resources: CPU only; 16 CPUs, 32 GiB RAM, up to 2 days; disk = selected files (all: 689 GB) on /hai/scratch/mrvlim.'
    job=$(sbatch --hold --parsable --chdir="$repo_root" \
        --output="$repo_root/runs/%j/slurm.out" --error="$repo_root/runs/%j/slurm.err" \
        "$repo_root/slurm_jobs/download_data.sh" --slurm-run "$@")
    [[ $job =~ ^[0-9]+$ ]]
    mkdir -p "$repo_root/runs/$job"
    printf 'Download the CM4AI-DREAM training data from Hugging Face into data/raw/CM4AI-DREAM (filters: %s).\n' "${*:-none}" > "$repo_root/runs/$job/why.txt"
    scontrol release "$job"
    printf 'Submitted %s; logs: %s/runs/%s\n' "$job" "$repo_root" "$job"
    exit 0
fi
shift
: "${SLURM_JOB_ID:?Run through Slurm}"
cd "${SLURM_SUBMIT_DIR:?}"
# Keep the HF cache off AFS home: AFS tokens expire inside long Slurm jobs.
export HF_HOME="$PWD/.cache/huggingface"
exec conda run --no-capture-output -n jit hf download LundbergLab/CM4AI-DREAM --repo-type dataset \
    --revision b5b90b3131430a8458ff5f87b3dfbc859c245f76 \
    --local-dir data/raw/CM4AI-DREAM --max-workers 16 "$@"
