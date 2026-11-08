#!/bin/bash
# Render every frame and build the film on the airavata compute node.
# Submit from this folder:  sbatch render_airavata.slurm
# Setup, once: see "Rendering on airavata" in plan.md.
#SBATCH --job-name=afms_film
#SBATCH --partition=part3
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=128
#SBATCH --mem=120G
#SBATCH --time=08:00:00
#SBATCH --output=render_%j.log

set -e
cd "$SLURM_SUBMIT_DIR"
ENV=${AFMS_ENV:-$HOME/.conda/envs/flexflow_env}
CASES=${AFMS_CASES:-/scratch/arunperiyal/afms_cases}
export PATH="$ENV/bin:$PATH"
unset LD_LIBRARY_PATH DISPLAY

# Memory sets the job counts: about 0.7 GB per bare job and 2.2 GB per helical job.
python make_film.py render --cases "$CASES" --bare-jobs 64 --helical-jobs 44 --frozen-jobs 32
python make_film.py film
