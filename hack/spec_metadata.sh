#!/bin/bash
# hack/spec_metadata.sh - Gather git and researcher metadata for research documents
#
# Usage:
#   ./hack/spec_metadata.sh              # Output all metadata
#   ./hack/spec_metadata.sh --yaml       # Output as YAML frontmatter
#   ./hack/spec_metadata.sh --json       # Output as JSON
#
# Environment Variables:
#   RESEARCHER_NAME - Override the researcher name (defaults to git user.name or $USER)

set -euo pipefail

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to project root to ensure git commands work
cd "$PROJECT_ROOT"

# Gather metadata
get_date_iso() {
    date -Iseconds 2>/dev/null || date "+%Y-%m-%dT%H:%M:%S%z"
}

get_date_short() {
    date "+%Y-%m-%d"
}

get_timestamp_filename() {
    date "+%Y-%m-%d_%H-%M-%S"
}

get_git_commit() {
    git rev-parse --short HEAD 2>/dev/null || echo "unknown"
}

get_git_commit_full() {
    git rev-parse HEAD 2>/dev/null || echo "unknown"
}

get_git_branch() {
    git branch --show-current 2>/dev/null || git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown"
}

get_repository() {
    basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || basename "$PROJECT_ROOT"
}

get_researcher() {
    if [[ -n "${RESEARCHER_NAME:-}" ]]; then
        echo "$RESEARCHER_NAME"
    elif git config user.name &>/dev/null; then
        git config user.name
    else
        echo "${USER:-${USERNAME:-unknown}}"
    fi
}

# Output formats
output_plain() {
    echo "date=$(get_date_iso)"
    echo "date_short=$(get_date_short)"
    echo "timestamp=$(get_timestamp_filename)"
    echo "git_commit=$(get_git_commit)"
    echo "git_commit_full=$(get_git_commit_full)"
    echo "branch=$(get_git_branch)"
    echo "repository=$(get_repository)"
    echo "researcher=$(get_researcher)"
}

output_yaml() {
    cat <<EOF
---
date: $(get_date_iso)
researcher: $(get_researcher)
git_commit: $(get_git_commit)
branch: $(get_git_branch)
repository: $(get_repository)
status: in_progress
last_updated: $(get_date_short)
last_updated_by: $(get_researcher)
---
EOF
}

output_json() {
    cat <<EOF
{
  "date": "$(get_date_iso)",
  "date_short": "$(get_date_short)",
  "timestamp": "$(get_timestamp_filename)",
  "git_commit": "$(get_git_commit)",
  "git_commit_full": "$(get_git_commit_full)",
  "branch": "$(get_git_branch)",
  "repository": "$(get_repository)",
  "researcher": "$(get_researcher)"
}
EOF
}

# Main
case "${1:-}" in
    --yaml|-y)
        output_yaml
        ;;
    --json|-j)
        output_json
        ;;
    --help|-h)
        echo "Usage: $0 [--yaml|--json|--help]"
        echo ""
        echo "Gather git and researcher metadata for research documents."
        echo ""
        echo "Options:"
        echo "  --yaml, -y    Output as YAML frontmatter"
        echo "  --json, -j    Output as JSON"
        echo "  --help, -h    Show this help message"
        echo ""
        echo "Environment Variables:"
        echo "  RESEARCHER_NAME    Override the researcher name"
        ;;
    *)
        output_plain
        ;;
esac
