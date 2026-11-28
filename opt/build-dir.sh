#!/usr/bin/env bash
# build-dir.sh — stale build dir detection for the opt/*-tools compile scripts
# (sourced, not run; shared like opt/azero-os.sh).
#
# A build dir remembers the tools it was made with: CMake projects in their
# CMakeCache.txt, the make projects in a <build>/.toolchain record written
# here. When a run is about to use other tools (BIG_MODULAR_TOOLCHAINS os vs
# home, a moved SDK / toolchain, a moved checkout), reusing the dir fails or
# mixes them: CMake keeps the cached compiler and stops at the new SDK path,
# idf.py asks for `fullclean`, make keeps the objects of the other compiler and
# links them with the new one's libraries. The scripts then print one line with
# the reason and remove that build dir, so the build starts fresh. A build dir
# made with the same tools is kept and builds incrementally.

# Path with every symlink resolved (portable: no readlink -f on older macOS).
# A path that does not exist is returned as given.
build_dir_real_path() {
  local p="$1" dir link n=0
  [[ "$p" == /* ]] || p="$PWD/$p"
  while dir="$(cd -P "$(dirname "$p")" 2>/dev/null && pwd)"; do
    p="${dir%/}/$(basename "$p")"
    [[ -L "$p" && $n -lt 40 ]] || break
    link="$(readlink "$p")"
    [[ "$link" == /* ]] || link="$dir/$link"
    p="$link"
    n=$((n + 1))
  done
  echo "$p"
}

# Value of KEY in a CMakeCache.txt (KEY:TYPE=VALUE); status 1 when absent.
cmake_cache_value() { # cache key
  local line
  line="$(grep -m1 -E "^$2(:[A-Za-z]+)?=" "$1" 2>/dev/null)" || return 1
  echo "${line#*=}"
}

# BUILD_DIR_STALE holds the first difference found by cmake_cache_expect.
BUILD_DIR_STALE=""

# Note when cache entry KEY is set and differs from VALUE (paths compared with
# symlinks resolved). Entries the cache does not have are not compared.
cmake_cache_expect() { # cache key value [path]
  local had
  [[ -z "$BUILD_DIR_STALE" ]] || return 0
  had="$(cmake_cache_value "$1" "$2")" || return 0
  [[ -n "$had" && "$had" != "$3" ]] || return 0
  if [[ "${4:-}" == path && \
        "$(build_dir_real_path "$had")" == "$(build_dir_real_path "$3")" ]]; then
    return 0
  fi
  BUILD_DIR_STALE="$2 is $had, this build uses $3"
}

# Remove build dir DIR (one line with REASON on stdout). Refuses a dir that is
# or contains the project dir, / or $HOME.
remove_stale_build_dir() { # build_dir project_dir reason
  local dir proj
  dir="$(build_dir_real_path "$1")"
  proj="$(build_dir_real_path "$2")"
  if [[ ! -d "$dir" || "$dir" == / || "$dir" == "$(build_dir_real_path "$HOME")" || \
        "$proj/" == "$dir/"* ]]; then
    echo "Error: build dir $1 is stale ($3), but it is not a separate build dir: remove its build files by hand" >&2
    exit 1
  fi
  echo "==> Stale build dir $1: $3; removing it for a clean build"
  rm -rf -- "$1" || {
    echo "Error: could not remove $1 (files of another user? run as the checkout owner)" >&2
    exit 1
  }
}

# CMake build dir: remove it when cmake_cache_expect found a difference.
remove_build_dir_if_stale() { # build_dir project_dir
  [[ -z "$BUILD_DIR_STALE" ]] || remove_stale_build_dir "$1" "$2" "$BUILD_DIR_STALE"
  BUILD_DIR_STALE=""
}

# make build dir: compare the record of the tools it was built with (one
# NAME=VALUE argument each) with <build>/.toolchain; remove the dir when they
# differ, or when it has objects but no record (built before records were
# written, tools unknown). Then write the record for this build.
check_make_build_dir() { # build_dir project_dir NAME=VALUE...
  local dir="$1" proj="$2" record="$1/.toolchain" entry had reason=""
  shift 2
  if [[ -f "$record" ]]; then
    for entry in "$@"; do
      had="$(grep -m1 "^${entry%%=*}=" "$record" 2>/dev/null || true)"
      if [[ "$had" != "$entry" ]]; then
        reason="${entry%%=*} is ${had#*=}, this build uses ${entry#*=}"
        [[ -n "$had" ]] || reason="no ${entry%%=*} in its record, this build uses ${entry#*=}"
        break
      fi
    done
  elif [[ -d "$dir" && -n "$(find "$dir" \( -name '*.o' -o -name '*.elf' \) -print -quit 2>/dev/null)" ]]; then
    reason="no record of the toolchain it was built with"
  fi
  [[ -z "$reason" ]] || remove_stale_build_dir "$dir" "$proj" "$reason"
  mkdir -p "$dir"
  printf '%s\n' "$@" > "$record"
}
