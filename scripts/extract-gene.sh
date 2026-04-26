#!/bin/bash
# Gene Extraction Helper
# Creates a new gene from a learning entry or discovered methodology
# Usage: ./extract-gene.sh <gene-name> [options]

set -e

# Configuration
GENES_DIR="./ai-logs/.genes"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    cat << EOF
Usage: $(basename "$0") <gene-name> [options]

Create a new gene (reusable method/approach) with versioned variants.

Arguments:
  gene-name          Name of the gene (lowercase, hyphens for spaces)

Options:
  --dry-run                Show what would be created without creating files
  --output-dir DIR         Relative output directory (default: ./.genes)
  --source-learning ID     Associate with a source learning entry ID
  --source-type TYPE       Origin type: learning | article | observation (default: learning)
  -h, --help               Show this help message

Examples:
  $(basename "$0") tdd-red-green-refactor
  $(basename "$0") api-retry-backoff --dry-run
  $(basename "$0") error-boundary-pattern --source-learning LRN-20260304-001
  $(basename "$0") cache-invalidation --source-type article --output-dir ./.genes

The gene will be created in: \$GENES_DIR/<gene-name>/
EOF
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Parse arguments
GENE_NAME=""
DRY_RUN=false
SOURCE_LEARNING=""
SOURCE_TYPE="learning"

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --output-dir)
            if [ -z "${2:-}" ] || [[ "${2:-}" == -* ]]; then
                log_error "--output-dir requires a relative path argument"
                usage
                exit 1
            fi
            GENES_DIR="$2"
            shift 2
            ;;
        --source-learning)
            if [ -z "${2:-}" ] || [[ "${2:-}" == -* ]]; then
                log_error "--source-learning requires an ID argument (e.g., LRN-20260304-001)"
                usage
                exit 1
            fi
            SOURCE_LEARNING="$2"
            shift 2
            ;;
        --source-type)
            if [ -z "${2:-}" ] || [[ "${2:-}" == -* ]]; then
                log_error "--source-type requires a type argument (learning|article|observation)"
                usage
                exit 1
            fi
            SOURCE_TYPE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            if [ -z "$GENE_NAME" ]; then
                GENE_NAME="$1"
            else
                log_error "Unexpected argument: $1"
                usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Validate gene name
if [ -z "$GENE_NAME" ]; then
    log_error "Gene name is required"
    usage
    exit 1
fi

# Validate gene name format (lowercase, hyphens, no spaces)
if ! [[ "$GENE_NAME" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
    log_error "Invalid gene name format. Use lowercase letters, numbers, and hyphens only."
    log_error "Examples: 'tdd-red-green', 'api-retry-backoff', 'error-boundary'"
    exit 1
fi

# Validate output path to avoid writes outside current workspace.
if [[ "$GENES_DIR" = /* ]]; then
    log_error "Output directory must be a relative path under the current directory."
    exit 1
fi

if [[ "$GENES_DIR" =~ (^|/)\.\.(/|$) ]]; then
    log_error "Output directory cannot include '..' path segments."
    exit 1
fi

GENES_DIR="${GENES_DIR#./}"
GENES_DIR="./$GENES_DIR"

GENE_PATH="$GENES_DIR/$GENE_NAME"

# Check if gene already exists
if [ -d "$GENE_PATH" ] && [ "$DRY_RUN" = false ]; then
    log_error "Gene already exists: $GENE_PATH"
    log_error "Use a different name or remove the existing gene first."
    exit 1
fi

# Generate Gene ID: GEN-YYYYMMDD-XXX (random 3 hex chars)
DATE_PART=$(date +%Y%m%d)
RANDOM_PART=$(head -c 2 /dev/urandom | od -An -tx1 | tr -d ' ' | head -c 3 | tr '[:lower:]' '[:upper:]')
# Ensure we have exactly 3 chars
if [ ${#RANDOM_PART} -lt 3 ]; then
    RANDOM_PART="${RANDOM_PART}A"
fi
RANDOM_PART="${RANDOM_PART:0:3}"
GENE_ID="GEN-${DATE_PART}-${RANDOM_PART}"

CREATED_TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Registry path
REGISTRY_PATH="$GENES_DIR/registry.json"

# Dry run output
if [ "$DRY_RUN" = true ]; then
    log_info "Dry run - would create:"
    echo "  $GENE_PATH/"
    echo "  $GENE_PATH/gene.yaml"
    echo "  $GENE_PATH/variants/"
    echo "  $GENE_PATH/variants/v1.yaml"
    echo "  $REGISTRY_PATH (append entry)"
    echo ""
    echo "Gene ID: $GENE_ID"
    echo ""
    echo "--- gene.yaml ---"
    cat << TEMPLATE
# Gene: $GENE_NAME
gene_id: $GENE_ID
name: $GENE_NAME
description: "[TODO: What reusable method/approach this gene encodes]"
parent_gene: ""
forked_from: ""
current_version: v1
variant_count: 1
effectiveness_score: 0.5
usage_count: 0
last_used: ""
created: $CREATED_TS
freshness_score: 1.0
decay_status: active
decay_window_days: 90
source_type: $SOURCE_TYPE
source_learning_ids: "$SOURCE_LEARNING"
context_tags: ""
applicable_areas: ""
TEMPLATE
    echo ""
    echo "--- variants/v1.yaml ---"
    cat << TEMPLATE
version: v1
created: $CREATED_TS
author: initial
supersedes: ""
summary: "[TODO: One-line description of this variant's approach]"
approach: |
  [TODO: Step-by-step methodology]
trigger: "[TODO: When to apply this variant]"
source_learning_id: "$SOURCE_LEARNING"
notes: ""
TEMPLATE
    exit 0
fi

# Create gene directory structure
log_info "Creating gene: $GENE_NAME (ID: $GENE_ID)"

mkdir -p "$GENE_PATH/variants"

# Create gene.yaml
cat > "$GENE_PATH/gene.yaml" << TEMPLATE
# Gene: $GENE_NAME
gene_id: $GENE_ID
name: $GENE_NAME
description: "[TODO: What reusable method/approach this gene encodes]"
parent_gene: ""
forked_from: ""
current_version: v1
variant_count: 1
effectiveness_score: 0.5
usage_count: 0
last_used: ""
created: $CREATED_TS
freshness_score: 1.0
decay_status: active
decay_window_days: 90
source_type: $SOURCE_TYPE
source_learning_ids: "$SOURCE_LEARNING"
context_tags: ""
applicable_areas: ""
TEMPLATE

log_info "Created: $GENE_PATH/gene.yaml"

# Create initial variant
cat > "$GENE_PATH/variants/v1.yaml" << TEMPLATE
version: v1
created: $CREATED_TS
author: initial
supersedes: ""
summary: "[TODO: One-line description of this variant's approach]"
approach: |
  [TODO: Step-by-step methodology]
  1. First step
  2. Second step
  3. Third step
trigger: "[TODO: When to apply this variant]"
source_learning_id: "$SOURCE_LEARNING"
notes: ""
TEMPLATE

log_info "Created: $GENE_PATH/variants/v1.yaml"

# Update registry.json
if [ ! -f "$REGISTRY_PATH" ]; then
    mkdir -p "$(dirname "$REGISTRY_PATH")"
    echo '{"genes":[]}' > "$REGISTRY_PATH"
    log_info "Created: $REGISTRY_PATH"
fi

# Use python3 to safely append to JSON
python3 -c "
import json, sys
registry_path = '$REGISTRY_PATH'
try:
    with open(registry_path, 'r') as f:
        registry = json.load(f)
except (json.JSONDecodeError, FileNotFoundError):
    registry = {'genes': []}

if 'genes' not in registry:
    registry['genes'] = []

registry['genes'].append({
    'gene_id': '$GENE_ID',
    'name': '$GENE_NAME',
    'path': '$GENE_NAME',
    'created': '$CREATED_TS',
    'decay_status': 'active',
    'freshness_score': 1.0
})

with open(registry_path, 'w') as f:
    json.dump(registry, f, indent=2)
    f.write('\n')
"

log_info "Updated: $REGISTRY_PATH"

# Suggest next steps
echo ""
log_info "Gene scaffold created successfully!"
echo ""
echo "Next steps:"
echo "  1. Edit $GENE_PATH/gene.yaml"
echo "     - Add a meaningful description"
echo "     - Set context_tags and applicable_areas"
echo "  2. Edit $GENE_PATH/variants/v1.yaml"
echo "     - Fill in the approach steps"
echo "     - Add trigger conditions"
echo "     - Optionally add example code"
echo "  3. If this came from a learning entry, update it with:"
echo "     **Status**: promoted_to_gene"
echo "     **Gene-ID**: $GENE_ID"
echo "     **Gene-Path**: .genes/$GENE_NAME"
