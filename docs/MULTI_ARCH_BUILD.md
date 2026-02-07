# Multi-Architecture Build Guide

## Overview

OpenHQM supports building Docker images for **multiple CPU architectures**:
- **linux/amd64** (x86_64) - Intel/AMD processors
- **linux/arm64** (ARM64/aarch64) - ARM processors, Apple Silicon

This enables deployment on diverse hardware platforms including:
- Intel/AMD servers (AWS EC2, Azure VMs, GCP Compute)
- ARM-based instances (AWS Graviton, Azure Ampere, GCP Tau T2A)
- Apple Silicon (M1/M2/M3 Macs for development)
- ARM servers and edge devices

## Prerequisites

### Docker Buildx

Docker Buildx is required for multi-architecture builds:

```bash
# Check if buildx is available
docker buildx version

# List available builders
docker buildx ls
```

If not available, install:
- **Docker Desktop** (macOS/Windows): Includes buildx by default
- **Linux**: Install buildx plugin:
  ```bash
  apt-get install docker-buildx-plugin
  # or
  yum install docker-buildx-plugin
  ```

### QEMU (for cross-compilation)

To build for architectures different from your host:

```bash
# Install QEMU (Linux)
docker run --privileged --rm tonistiigi/binfmt --install all

# Verify platforms
docker buildx inspect --bootstrap
```

## Quick Start

### Using the Build Script

The easiest way to build multi-arch images:

```bash
# Build minimal variant for both architectures
./scripts/build-multiarch.sh --backend minimal

# Build redis variant for ARM64 only
./scripts/build-multiarch.sh --backend redis --platforms linux/arm64

# Build all variants
./scripts/build-multiarch.sh --build-all

# Build and push to registry
./scripts/build-multiarch.sh --backend sqs --push --tag v1.0.0
```

### Manual Docker Buildx Commands

For more control:

```bash
# Build for both architectures
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --build-arg QUEUE_BACKEND=redis \
  --tag openhqm:latest-redis \
  .

# Build for single architecture and load locally
docker buildx build \
  --platform linux/arm64 \
  --build-arg QUEUE_BACKEND=minimal \
  --tag openhqm:latest-minimal \
  --load \
  .

# Build and push to registry
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --build-arg QUEUE_BACKEND=all \
  --tag ghcr.io/yourusername/openhqm:latest \
  --push \
  .
```

## Build Script Options

```bash
./scripts/build-multiarch.sh [OPTIONS]

Options:
  -p, --platforms PLATFORMS    Target platforms (default: linux/amd64,linux/arm64)
  -b, --backend BACKEND        Queue backend (all|redis|kafka|sqs|azure|gcp|mqtt|minimal)
  -n, --name NAME              Image name (default: openhqm)
  -t, --tag TAG                Image tag (default: latest)
  --push                       Push to registry
  --build-all                  Build all 8 variants
  --test-only                  Test build without creating image
  -h, --help                   Show help
```

### Examples

```bash
# Development: Build minimal variant for local arch
./scripts/build-multiarch.sh --backend minimal --platforms linux/arm64

# Testing: Build SQS variant for both architectures
./scripts/build-multiarch.sh --backend sqs

# Production: Build and push all variants for release
./scripts/build-multiarch.sh --build-all --push --tag v1.2.0

# Custom registry: Build and push to private registry
IMAGE_NAME=myregistry.io/openhqm ./scripts/build-multiarch.sh \
  --backend redis --push --tag prod

# CI/CD: Build specific variant with cache
./scripts/build-multiarch.sh \
  --backend azure \
  --platforms linux/amd64,linux/arm64 \
  --tag $(git describe --tags)
```

## Architecture-Specific Builds

### Build for Current Architecture Only

Faster for local development:

```bash
# Automatically detects your architecture
docker build \
  --build-arg QUEUE_BACKEND=redis \
  --tag openhqm:redis-local \
  .

# Or specify explicitly
./scripts/build-multiarch.sh \
  --backend redis \
  --platforms linux/$(uname -m)
```

### Build for Different Architecture

Cross-compilation (requires QEMU):

```bash
# Build ARM64 image on AMD64 host
./scripts/build-multiarch.sh \
  --backend sqs \
  --platforms linux/arm64

# Build AMD64 image on ARM64 host
./scripts/build-multiarch.sh \
  --backend kafka \
  --platforms linux/amd64
```

## Verifying Multi-Arch Images

### Check Image Architecture

```bash
# Check loaded image (shows current architecture)
docker inspect openhqm:latest --format='{{.Architecture}}'

# For pushed multi-arch manifest
docker buildx imagetools inspect ghcr.io/yourusername/openhqm:latest
```

### Test Both Architectures

```bash
# Test ARM64 image
docker run --rm --platform linux/arm64 openhqm:latest \
  python -c "import platform; print(f'Arch: {platform.machine()}')"

# Test AMD64 image
docker run --rm --platform linux/amd64 openhqm:latest \
  python -c "import platform; print(f'Arch: {platform.machine()}')"
```

## Performance Considerations

### Build Times

| Scenario | Time (approx) |
|----------|---------------|
| Single arch (native) | 2-5 minutes |
| Single arch (emulated) | 10-15 minutes |
| Multi-arch (amd64+arm64) | 12-20 minutes |

**Tips:**
- Use `--cache-from` and `--cache-to` for faster rebuilds
- Build natively when possible (e.g., ARM64 on Apple Silicon)
- CI/CD: Use GitHub Actions matrix for parallel builds

### Native vs Cross-Compilation

**Native build** (same architecture):
```bash
# Fast - on Apple Silicon
./scripts/build-multiarch.sh --backend redis --platforms linux/arm64
```

**Cross-compilation** (different architecture):
```bash
# Slower - requires QEMU emulation
./scripts/build-multiarch.sh --backend redis --platforms linux/amd64
```

## CI/CD Integration

### GitHub Actions

Already configured in `.github/workflows/ci.yml` and `.github/workflows/release.yml`:

```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3

- name: Build multi-arch image
  uses: docker/build-push-action@v5
  with:
    platforms: linux/amd64,linux/arm64
    build-args: |
      QUEUE_BACKEND=${{ matrix.queue_backend.name }}
    push: true
    tags: ${{ steps.meta.outputs.tags }}
    cache-from: type=gha,scope=build-${{ matrix.queue_backend.name }}
    cache-to: type=gha,mode=max,scope=build-${{ matrix.queue_backend.name }}
```

### GitLab CI

```yaml
build-multiarch:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  before_script:
    - docker run --privileged --rm tonistiigi/binfmt --install all
    - docker buildx create --use
  script:
    - docker buildx build
        --platform linux/amd64,linux/arm64
        --build-arg QUEUE_BACKEND=all
        --tag $CI_REGISTRY_IMAGE:$CI_COMMIT_TAG
        --push
        .
```

### Jenkins

```groovy
pipeline {
    agent any
    stages {
        stage('Build Multi-Arch') {
            steps {
                sh '''
                    docker buildx create --use
                    ./scripts/build-multiarch.sh \
                        --backend all \
                        --push \
                        --tag ${BUILD_NUMBER}
                '''
            }
        }
    }
}
```

## Registry Support

### Pushing Multi-Arch Manifests

```bash
# Login to registry
docker login ghcr.io

# Build and push
./scripts/build-multiarch.sh \
  --backend redis \
  --push \
  --tag v1.0.0

# Verify manifest
docker buildx imagetools inspect ghcr.io/yourusername/openhqm:v1.0.0-redis
```

### Multiple Registries

```bash
# Push to multiple registries
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --build-arg QUEUE_BACKEND=sqs \
  --tag ghcr.io/yourusername/openhqm:latest-sqs \
  --tag docker.io/yourusername/openhqm:latest-sqs \
  --tag myregistry.io/openhqm:latest-sqs \
  --push \
  .
```

## Size Comparison by Architecture

Typical image sizes:

| Variant | AMD64 Size | ARM64 Size |
|---------|------------|------------|
| **minimal** | ~180MB | ~175MB |
| **redis** | ~200MB | ~195MB |
| **kafka** | ~250MB | ~245MB |
| **sqs** | ~230MB | ~225MB |
| **azure** | ~280MB | ~275MB |
| **gcp** | ~270MB | ~265MB |
| **mqtt** | ~210MB | ~205MB |
| **all** | ~500MB | ~490MB |

**Note:** ARM64 images are often slightly smaller due to more efficient ARM instruction set.

## Troubleshooting

### Build Fails on Cross-Compilation

**Error:**
```
exec user process caused: exec format error
```

**Solution:** Install QEMU:
```bash
docker run --privileged --rm tonistiigi/binfmt --install all
```

### Cannot Load Multi-Arch Image Locally

**Error:**
```
ERROR: multi-platform images cannot be loaded with docker load
```

**Explanation:** Docker can only load images for the current architecture.

**Solution:**
```bash
# Option 1: Build for current architecture only
./scripts/build-multiarch.sh --backend redis --platforms linux/$(uname -m)

# Option 2: Push to registry instead
./scripts/build-multiarch.sh --backend redis --push
```

### Slow Build Times

**Problem:** Cross-compilation takes 5-10x longer than native builds.

**Solutions:**
1. **Use native builders:**
   - Build ARM64 on Apple Silicon or ARM servers
   - Build AMD64 on Intel/AMD servers

2. **Parallel builds in CI:**
   ```yaml
   strategy:
     matrix:
       platform: [linux/amd64, linux/arm64]
   ```

3. **Enable BuildKit cache:**
   ```bash
   export DOCKER_BUILDKIT=1
   docker buildx build --cache-from=... --cache-to=...
   ```

### Builder Not Found

**Error:**
```
ERROR: no builder instance found
```

**Solution:**
```bash
# Create builder
docker buildx create --name openhqm-builder --use
docker buildx inspect --bootstrap
```

## Best Practices

### 1. Test Both Architectures

Always test images on both AMD64 and ARM64 before release:

```bash
# Test AMD64
docker run --rm --platform linux/amd64 openhqm:test python -m pytest

# Test ARM64
docker run --rm --platform linux/arm64 openhqm:test python -m pytest
```

### 2. Use Architecture-Specific Images in Production

Pull images that match your platform for best performance:

```yaml
# Kubernetes on ARM nodes
containers:
  - name: openhqm
    image: openhqm:latest-redis
    # Kubernetes automatically pulls ARM64 if available
```

### 3. Tag Images with Architecture

For manual architecture selection:

```bash
# Build and tag with architecture suffix
docker buildx build \
  --platform linux/amd64 \
  --tag openhqm:latest-redis-amd64 \
  .

docker buildx build \
  --platform linux/arm64 \
  --tag openhqm:latest-redis-arm64 \
  .
```

### 4. Optimize for Target Architecture

Consider architecture-specific optimizations:

```dockerfile
# Example: Use architecture-specific base images
ARG TARGETARCH
FROM python:3.11-slim-${TARGETARCH}
```

### 5. Monitor Build Times

Track build times by architecture to identify bottlenecks:

```bash
time docker buildx build --platform linux/amd64 ...
time docker buildx build --platform linux/arm64 ...
```

## Resources

- [Docker Buildx Documentation](https://docs.docker.com/buildx/working-with-buildx/)
- [Multi-platform Images](https://docs.docker.com/build/building/multi-platform/)
- [GitHub Actions Build Push Action](https://github.com/docker/build-push-action)
- [QEMU User Emulation](https://www.qemu.org/docs/master/user/main.html)

## Summary

OpenHQM's multi-architecture support enables:
- ✅ Deployment on AMD64 and ARM64 platforms
- ✅ Cost savings with ARM-based cloud instances (AWS Graviton, etc.)
- ✅ Native performance on Apple Silicon for development
- ✅ Flexibility to choose optimal hardware for workloads
- ✅ Future-proof for emerging ARM server adoption

Use the provided build script for easy multi-arch builds, or integrate with your existing CI/CD pipelines.
