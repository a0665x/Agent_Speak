#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
project_root=$(cd "$script_dir/../.." && pwd)
providers_dir="$project_root/AI_Avatar/.providers"
model_root="${AGENT_SPEAK_AVATAR_MODEL_PATH:-$project_root/models/avatar_interpolation}"

film_commit="69f8708f08e62c2edf46a27616a4bfcf083e2076"
rife_commit="5d8adbdd40e12c2c8f91930eff838aebe561c086"
film_repo="$providers_dir/film"
rife_repo="$providers_dir/rife"
film_model="$model_root/film/film_net/Style/saved_model"
rife_model="$model_root/rife/train_log"

clone_at_commit() {
  local url=$1
  local target=$2
  local commit=$3
  if [[ ! -d "$target/.git" ]]; then
    git clone "$url" "$target"
  fi
  git -C "$target" fetch --depth 1 origin "$commit"
  git -C "$target" checkout --detach "$commit"
}

mkdir -p "$providers_dir" "$model_root"
clone_at_commit \
  "https://github.com/google-research/frame-interpolation.git" \
  "$film_repo" \
  "$film_commit"
clone_at_commit \
  "https://github.com/hzwer/ECCV2022-RIFE.git" \
  "$rife_repo" \
  "$rife_commit"

missing=0
if [[ ! -f "$film_model/saved_model.pb" ]]; then
  echo "MISSING_FILM_MODEL expected=$film_model" >&2
  missing=1
fi
if ! compgen -G "$rife_model/*.pkl" >/dev/null; then
  echo "MISSING_RIFE_MODEL expected=$rife_model/*.pkl" >&2
  missing=1
fi
if (( missing )); then
  echo "Download the official FILM SavedModel and RIFE HD weights to the paths above." >&2
  exit 2
fi

ln -sfn "$rife_model" "$rife_repo/train_log"
echo "AVATAR_INTERPOLATION_READY film=$film_commit rife=$rife_commit models=$model_root"
