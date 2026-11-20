#!/bin/bash
#
# Install FlowReel into a conda environment (flexflow_env by default) and add a
# `flowreel` alias to your shell, so it runs without activating the environment.
#
# Usage:
#   ./install.sh               install, or update an existing install
#   ./install.sh -y            the same, answering yes to every question
#   ./install.sh --no-alias    install, but leave your shell's start-up file alone
#   ./install.sh --uninstall   remove FlowReel and the alias (the environment stays)
#   ./install.sh --help
#
# Environment variables:
#   CONDA_ENV_NAME=NAME    the environment (default flexflow_env, shared with FlexFlow)
#   SHELLKIT_DIR=DIR       install shellkit from a local checkout (editable), for a
#                          machine that cannot reach GitHub
#
# What it does: finds conda; creates the environment from environment.yml, or, when it
# exists, installs only the packages it lacks (so other tools in it keep their
# versions); installs shellkit if missing; installs FlowReel editable (pip --no-deps
# -e), so `git pull` updates it; checks ffmpeg; adds the alias.

set -e

FLOWREEL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="${CONDA_ENV_NAME:-flexflow_env}"
PYTHON_VERSION="3.12"
MARK_BEGIN="# >>> FlowReel (added by install.sh) >>>"
MARK_END="# <<< FlowReel <<<"
YES=0
ALIAS=1
ACTION=install

if [ -t 1 ]; then
    BOLD=$'\033[1m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; RED=$'\033[0;31m'
    BLUE=$'\033[0;34m'; NC=$'\033[0m'
else
    BOLD=""; GREEN=""; YELLOW=""; RED=""; BLUE=""; NC=""
fi

step()  { echo; echo "${BOLD}${BLUE}==> $*${NC}"; }
info()  { echo "    $*"; }
ok()    { echo "    ${GREEN}✓${NC} $*"; }
warn()  { echo "    ${YELLOW}!${NC} $*"; }
fail()  { echo "    ${RED}✗ $*${NC}" >&2; exit 1; }

ask() {   # ask "question" -> 0 for yes
    [ "$YES" = 1 ] && return 0
    local reply
    read -r -p "    $1 [y/N] " reply
    [[ "$reply" =~ ^[Yy] ]]
}

usage() { sed -n '2,/^$/{s/^# \{0,1\}//;p}' "$0"; }

for arg in "$@"; do
    case "$arg" in
        -y|--yes) YES=1 ;;
        --no-alias) ALIAS=0 ;;
        -u|--uninstall) ACTION=uninstall ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown option: $arg (see ./install.sh --help)" >&2; exit 2 ;;
    esac
done

# -- conda -----------------------------------------------------------------------------

find_conda() {
    step "Finding conda"
    local base=""
    if [ -n "$CONDA_EXE" ] && [ -x "$CONDA_EXE" ]; then
        base="$(dirname "$(dirname "$CONDA_EXE")")"
    elif command -v conda >/dev/null 2>&1 && [ -x "$(command -v conda)" ]; then
        base="$(dirname "$(dirname "$(command -v conda)")")"
    else
        for d in "$HOME/miniforge3" "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/mambaforge" \
                 /opt/conda /opt/miniforge3 /home/apps/miniforge3; do
            [ -f "$d/etc/profile.d/conda.sh" ] && { base="$d"; break; }
        done
    fi
    [ -n "$base" ] && [ -f "$base/etc/profile.d/conda.sh" ] || fail "conda not found.
      Install Miniforge (https://github.com/conda-forge/miniforge), or load your
      cluster's conda module, then run ./install.sh again."
    # shellcheck disable=SC1091
    source "$base/etc/profile.d/conda.sh"
    ok "conda $(conda --version | awk '{print $2}') at $base"
}

env_path() {   # the environment's folder, or nothing
    conda env list | awk -v n="$ENV_NAME" '$1 == n {print $NF}'
}

# Python module -> conda-forge package, for everything FlowReel imports.
MODULES=(numpy:numpy pandas:"pandas>=2" scipy:scipy pyvista:"pyvista>=0.44" vtk:"vtk>=9.3"
         matplotlib:"matplotlib>=3.8" PIL:"pillow>=10" yaml:"pyyaml>=6" pytest:"pytest>=7")

setup_env() {
    step "Setting up the conda environment $ENV_NAME"
    ENV_DIR="$(env_path)"
    if [ -z "$ENV_DIR" ]; then
        info "Creating $ENV_NAME from environment.yml (Python $PYTHON_VERSION, conda-forge)"
        local spec
        spec="$(mktemp --suffix=.yml)"
        # shellkit is installed below, so the environment does not need GitHub access
        sed -e "s/^name: .*/name: $ENV_NAME/" -e '/^  - pip:/,$d' \
            "$FLOWREEL_DIR/environment.yml" > "$spec"
        echo "  - pip" >> "$spec"
        conda env create -q -f "$spec"
        rm -f "$spec"
        ENV_DIR="$(env_path)"
        [ -n "$ENV_DIR" ] || fail "could not create $ENV_NAME"
        ok "created $ENV_DIR"
    else
        ok "found $ENV_DIR"
        local py="$ENV_DIR/bin/python" missing=()
        [ -x "$py" ] || fail "$ENV_NAME has no Python; recreate it or set CONDA_ENV_NAME"
        local version
        version="$("$py" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
        [ "$version" = "$PYTHON_VERSION" ] || warn "Python $version in $ENV_NAME; FlowReel is tested on $PYTHON_VERSION"
        for pair in "${MODULES[@]}"; do
            "$py" -c "import ${pair%%:*}" >/dev/null 2>&1 || missing+=("${pair#*:}")
        done
        [ -x "$ENV_DIR/bin/ffmpeg" ] || missing+=("ffmpeg>=5.1")
        if [ ${#missing[@]} -eq 0 ]; then
            ok "every package FlowReel needs is there"
        else
            info "Missing: ${missing[*]}"
            if ask "Install them into $ENV_NAME from conda-forge?"; then
                conda install -y -q -n "$ENV_NAME" -c conda-forge "${missing[@]}"
                ok "installed ${missing[*]}"
            else
                fail "FlowReel needs ${missing[*]}"
            fi
        fi
    fi
    PY="$ENV_DIR/bin/python"
    PIP=("$PY" -m pip)
}

install_shellkit() {
    step "shellkit (the command layer)"
    if [ -n "$SHELLKIT_DIR" ]; then
        [ -f "$SHELLKIT_DIR/pyproject.toml" ] || fail "SHELLKIT_DIR is not a shellkit checkout: $SHELLKIT_DIR"
        "${PIP[@]}" install -q -e "$SHELLKIT_DIR"
        ok "installed from $SHELLKIT_DIR (editable)"
    elif "$PY" -c "import shellkit" >/dev/null 2>&1; then
        ok "already installed ($("$PY" -c 'import shellkit, os; print(os.path.dirname(shellkit.__file__))'))"
    else
        info "Installing from GitHub"
        "${PIP[@]}" install -q "git+https://github.com/arunperiyal/shellkit.git" || fail "could not
      install shellkit from GitHub. Clone it on a machine that can, copy it here, and
      run: SHELLKIT_DIR=/path/to/shellkit ./install.sh"
        ok "installed from GitHub"
    fi
}

install_flowreel() {
    step "FlowReel"
    "${PIP[@]}" install -q --no-deps -e "$FLOWREEL_DIR"
    ok "installed (editable) from $FLOWREEL_DIR: git pull updates it"
    "$ENV_DIR/bin/flowreel" --version >/dev/null || fail "flowreel does not start"
    ok "$("$ENV_DIR/bin/flowreel" --version)"
    if found="$("$PY" -c 'from flowreel.film import ffmpeg as f; x = f.find(); print(x.ffmpeg, ".".join(map(str, x.version)))' 2>&1)"; then
        ok "ffmpeg $found"
    else
        warn "ffmpeg: ${found##*$'\n'}"
        warn "films cannot be built until it is fixed (conda install -n $ENV_NAME -c conda-forge ffmpeg)"
    fi
}

# -- the alias ---------------------------------------------------------------------------

rc_file() {
    case "$(basename "${SHELL:-bash}")" in
        zsh) echo "${ZDOTDIR:-$HOME}/.zshrc" ;;
        *) echo "$HOME/.bashrc" ;;
    esac
}

remove_block() {   # remove_block FILE
    [ -f "$1" ] && grep -qF "$MARK_BEGIN" "$1" || return 0
    sed -i "\|$MARK_BEGIN|,\|$MARK_END|d" "$1"
}

add_alias() {
    step "The flowreel alias"
    local rc
    rc="$(rc_file)"
    touch "$rc"
    remove_block "$rc"
    {
        echo "$MARK_BEGIN"
        echo "# Runs FlowReel from $ENV_NAME without activating it (ffmpeg is found beside it)."
        echo "alias flowreel='$ENV_DIR/bin/flowreel'"
        echo "$MARK_END"
    } >> "$rc"
    ok "added to $rc"
    info "Open a new terminal, or run:  source $rc"
}

# -- main --------------------------------------------------------------------------------

install() {
    echo "${BOLD}FlowReel installer${NC}  ($FLOWREEL_DIR -> conda environment $ENV_NAME)"
    find_conda
    setup_env
    install_shellkit
    install_flowreel
    if [ "$ALIAS" = 1 ]; then add_alias; else info "Alias skipped (--no-alias)"; fi
    step "Done"
    info "flowreel --help                     the commands"
    info "flowreel                            the interactive shell"
    info "$PY -m pytest -q $FLOWREEL_DIR/tests   the tests (a few minutes)"
}

uninstall() {
    echo "${BOLD}FlowReel uninstaller${NC}  (conda environment $ENV_NAME)"
    find_conda
    ENV_DIR="$(env_path)"
    if [ -n "$ENV_DIR" ] && "$ENV_DIR/bin/python" -m pip show flowreel >/dev/null 2>&1; then
        step "Removing FlowReel from $ENV_NAME"
        "$ENV_DIR/bin/python" -m pip uninstall -y -q flowreel
        ok "removed; the environment and its other packages stay"
    else
        info "FlowReel is not installed in $ENV_NAME"
    fi
    step "Removing the alias"
    for rc in "$HOME/.bashrc" "${ZDOTDIR:-$HOME}/.zshrc"; do
        if [ -f "$rc" ] && grep -qF "$MARK_BEGIN" "$rc"; then
            remove_block "$rc"
            ok "removed from $rc"
        fi
    done
}

"$ACTION"
