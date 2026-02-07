#!/usr/bin/env bash
# Build OpenHQM Docker images for multiple architectures
# Supports: linux/amd64, linux/arm64

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
QUEUE_BACKEND="${QUEUE_BACKEND:-all}"
IMAGE_NAME="${IMAGE_NAME:-openhqm}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
PUSH="${PUSH:-false}"
BUILDER_NAME="${BUILDER_NAME:-openhqm-builder}"

# Available queue backends
AVAILABLE_BACKENDS=("all" "redis" "kafka" "sqs" "azure" "gcp" "mqtt" "minimal")

# Print usage
usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Build OpenHQM Docker images for multiple architectures.

Options:
    -p, --platforms PLATFORMS    Target platforms (default: linux/amd64,linux/arm64)
    -b, --backend BACKEND        Queue backend variant (default: all)
                                Available: ${AVAILABLE_BACKENDS[*]}
    -n, --name NAME             Image name (default: openhqm)
    -t, --tag TAG               Image tag (default: latest)
    --push                      Push to registry (requires login)
    --build-all                 Build all backend variants
    --test-only                 Only test build, don't create image
    -h, --help                  Show this help message

Examples:
    # Build minimal variant for current architecture
    $0 --backend minimal --platforms linux/arm64

    # Build redis variant for both architectures
    $0 --backend redis

    # Build and push all variants
    $0 --build-all --push --tag v1.0.0

    # Test build without creating image
    $0 --backend sqs --test-only

Environment Variables:
    PLATFORMS       Target platforms (comma-separated)
    QUEUE_BACKEND   Queue backend variant
    IMAGE_NAME      Docker image name
    IMAGE_TAG       Docker image tag
    PUSH            Push to registry (true/false)

EOF
    exit 0
}

# Log functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if docker buildx is available
check_buildx() {
    if ! docker buildx version &>/dev/null; then
        log_error "Docker Buildx is not available. Please install Docker Desktop or Docker Buildx plugin."
        exit 1
    fi
    log_success "Docker Buildx is available"
}

# Create or use existing builder
setup_builder() {
    if docker buildx inspect "$BUILDER_NAME" &>/dev/null; then
        log_info "Using existing builder: $BUILDER_NAME"
        docker buildx use "$BUILDER_NAME"
    else
        log_info "Creating new builder: $BUILDER_NAME"
        docker buildx create --name "$BUILDER_NAME" --driver docker-container --use
        docker buildx inspect --bootstrap
    fi
}

# Build single variant
build_variant() {
    local backend=$1
    local full_tag="${IMAGE_NAME}:${IMAGE_TAG}"
    
    # Add backend suffix if not "all"
    if [ "$backend" != "all" ]; then
        full_tag="${IMAGE_NAME}:${IMAGE_TAG}-${backend}"
    fi
    
    log_info "Building: $full_tag"
    log_info "Platforms: $PLATFORMS"
    log_info "Backend: $backend"
    
    # Build arguments
    local build_args=(
        --platform "$PLATFORMS"
        --build-arg "QUEUE_BACKEND=$backend"
        --tag "$full_tag"
        --progress plain
    )
    
    # Add push flag if requested
    if [ "$PUSH" = "true" ]; then
        build_args+=(--push)
        log_info "Will push to registry"
    else
        build_args+=(--load)
        log_warning "Local build only (not pushing). Note: --load works only with single platform."
    fi
    
    # Add cache settings for faster builds
    build_args+=(
        --cache-from "type=registry,ref=${IMAGE_NAME}:buildcache-${backend}"
        --cache-to "type=inline"
    )
    
    # Build
    log_info "Starting build..."
    if docker buildx build "${build_args[@]}" .; then
        log_success "Built: $full_tag"
        
        # Show image size if local
        if [ "$PUSH" != "true" ]; then
            log_info "Image size:"
            docker images "$full_tag" | head -2
        fi
        
        return 0
    else
        log_error "Failed to build: $full_tag"
        return 1
    fi
}

# Validate backend
validate_backend() {
    local backend=$1
    for valid in "${AVAILABLE_BACKENDS[@]}"; do
        if [ "$backend" = "$valid" ]; then
            return 0
        fi
    done
    log_error "Invalid backend: $backend"
    log_error "Available backends: ${AVAILABLE_BACKENDS[*]}"
    exit 1
}

# Main function
main() {
    local build_all=false
    local test_only=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -p|--platforms)
                PLATFORMS="$2"
                shift 2
                ;;
            -b|--backend)
                QUEUE_BACKEND="$2"
                shift 2
                ;;
            -n|--name)
                IMAGE_NAME="$2"
                shift 2
                ;;
            -t|--tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            --push)
                PUSH="true"
                shift
                ;;
            --build-all)
                build_all=true
                shift
                ;;
            --test-only)
                test_only=true
                shift
                ;;
            -h|--help)
                usage
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                ;;
        esac
    done
    
    # Header
    echo ""
    log_info "╔════════════════════════════════════════╗"
    log_info "║   OpenHQM Multi-Arch Build Script     ║"
    log_info "╚════════════════════════════════════════╝"
    echo ""
    
    # Check prerequisites
    check_buildx
    
    # Setup builder (unless test-only)
    if [ "$test_only" = "false" ] && [ "$PUSH" = "false" ] && [[ "$PLATFORMS" == *","* ]]; then
        log_warning "Multi-platform builds cannot be loaded locally"
        log_warning "Either specify single platform or use --push"
        log_info "Continuing with build only (no load)..."
        PUSH="load-disabled"
    fi
    
    # Change to script directory
    cd "$(dirname "$0")/.." || exit 1
    
    # Build variants
    local failed=0
    
    if [ "$build_all" = "true" ]; then
        log_info "Building all variants..."
        for backend in "${AVAILABLE_BACKENDS[@]}"; do
            echo ""
            if ! build_variant "$backend"; then
                ((failed++))
            fi
        done
    else
        validate_backend "$QUEUE_BACKEND"
        if ! build_variant "$QUEUE_BACKEND"; then
            ((failed++))
        fi
    fi
    
    # Summary
    echo ""
    log_info "════════════════════════════════════════"
    if [ $failed -eq 0 ]; then
        log_success "All builds completed successfully!"
    else
        log_error "$failed build(s) failed"
        exit 1
    fi
    
    # Show next steps
    echo ""
    log_info "Next steps:"
    if [ "$PUSH" = "true" ]; then
        log_info "  Images pushed to registry"
        log_info "  Pull with: docker pull ${IMAGE_NAME}:${IMAGE_TAG}"
    else
        log_info "  Test locally: docker run --rm ${IMAGE_NAME}:${IMAGE_TAG}"
        log_info "  Push: $0 --push --backend $QUEUE_BACKEND"
    fi
    echo ""
}

# Run main
main "$@"
