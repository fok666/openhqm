# Quick Reference: Multi-Architecture Builds

## TL;DR

```bash
# Build for your architecture (fastest)
./scripts/build-multiarch.sh --backend redis --platforms linux/$(uname -m)

# Build for both AMD64 and ARM64
./scripts/build-multiarch.sh --backend redis

# Build all variants
./scripts/build-multiarch.sh --build-all
```

## Common Commands

### Development
```bash
# Quick local build (single arch)
docker build --build-arg QUEUE_BACKEND=redis -t openhqm:redis .

# Or use script for better output
./scripts/build-multiarch.sh --backend redis --platforms linux/arm64
```

### Testing
```bash
# Build minimal variant for testing
./scripts/build-multiarch.sh --backend minimal

# Test all backends (takes ~30-40 minutes)
./scripts/build-multiarch.sh --build-all
```

### Production
```bash
# Build and push specific variant
./scripts/build-multiarch.sh --backend sqs --push --tag v1.0.0

# Build and push all variants for release
./scripts/build-multiarch.sh --build-all --push --tag v1.0.0
```

## Build Script Options

| Option | Description | Example |
|--------|-------------|---------|
| `-b, --backend` | Queue backend variant | `--backend redis` |
| `-p, --platforms` | Target platforms | `--platforms linux/amd64,linux/arm64` |
| `-t, --tag` | Image tag | `--tag v1.0.0` |
| `-n, --name` | Image name | `--name myregistry.io/openhqm` |
| `--push` | Push to registry | `--push` |
| `--build-all` | Build all 8 variants | `--build-all` |
| `--test-only` | Test without creating image | `--test-only` |
| `-h, --help` | Show help | `--help` |

## Backend Variants

| Variant | Size | Use Case |
|---------|------|----------|
| `all` | ~500MB | Multi-cloud, development |
| `redis` | ~200MB | Low latency, simple |
| `kafka` | ~250MB | High throughput, streaming |
| `sqs` | ~230MB | AWS serverless |
| `azure` | ~280MB | Azure-native |
| `gcp` | ~270MB | GCP-native |
| `mqtt` | ~210MB | IoT, edge |
| `minimal` | ~180MB | Custom handlers |

## Platform Shortcuts

```bash
# Current architecture
--platforms linux/$(uname -m)

# Both major architectures
--platforms linux/amd64,linux/arm64

# AMD64 only
--platforms linux/amd64

# ARM64 only
--platforms linux/arm64
```

## Docker Buildx Commands

### Basic Multi-Arch Build
```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --build-arg QUEUE_BACKEND=redis \
  --tag openhqm:redis \
  .
```

### With Push
```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --build-arg QUEUE_BACKEND=sqs \
  --tag ghcr.io/user/openhqm:latest-sqs \
  --push \
  .
```

### With Cache
```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --build-arg QUEUE_BACKEND=kafka \
  --tag openhqm:kafka \
  --cache-from type=registry,ref=openhqm:buildcache \
  --cache-to type=inline \
  .
```

## Testing Images

### Run Specific Architecture
```bash
# Run ARM64 version
docker run --rm --platform linux/arm64 openhqm:redis

# Run AMD64 version
docker run --rm --platform linux/amd64 openhqm:redis
```

### Verify Architecture
```bash
# Check image architecture
docker inspect openhqm:redis --format='{{.Architecture}}'

# Test runtime
docker run --rm openhqm:redis python -c "import platform; print(platform.machine())"
```

### Verify Dependencies
```bash
# Check Redis variant has redis package
docker run --rm openhqm:redis pip list | grep redis

# Check SQS variant has boto3
docker run --rm openhqm:sqs pip list | grep boto3
```

## Troubleshooting

### Build Too Slow?
```bash
# Build for current architecture only
./scripts/build-multiarch.sh --backend redis --platforms linux/$(uname -m)
```

### Can't Load Multi-Arch Image?
```bash
# Multi-platform builds can't be loaded locally
# Solution: Build single platform or push to registry
./scripts/build-multiarch.sh --backend redis --platforms linux/arm64
```

### Builder Not Found?
```bash
# Create builder
docker buildx create --name openhqm-builder --use
docker buildx inspect --bootstrap
```

## CI/CD Integration

### GitHub Actions
```yaml
- uses: docker/setup-buildx-action@v3
- uses: docker/build-push-action@v5
  with:
    platforms: linux/amd64,linux/arm64
    build-args: QUEUE_BACKEND=redis
    push: true
```

### Environment Variables
```bash
export PLATFORMS="linux/amd64,linux/arm64"
export QUEUE_BACKEND="redis"
export IMAGE_NAME="openhqm"
export IMAGE_TAG="v1.0.0"
export PUSH="true"

./scripts/build-multiarch.sh
```

## Image Size Comparison

| Variant | AMD64 | ARM64 | Savings vs Full |
|---------|-------|-------|-----------------|
| **all** | 500MB | 490MB | 0% |
| **minimal** | 180MB | 175MB | 64% |
| **redis** | 200MB | 195MB | 60% |
| **kafka** | 250MB | 245MB | 50% |
| **sqs** | 230MB | 225MB | 54% |

## Pull Commands

```bash
# Specific variant (auto-selects architecture)
docker pull ghcr.io/user/openhqm:latest-redis

# Specific architecture
docker pull --platform linux/arm64 ghcr.io/user/openhqm:latest-redis
docker pull --platform linux/amd64 ghcr.io/user/openhqm:latest-redis

# Full image with all backends
docker pull ghcr.io/user/openhqm:latest
```

## Best Practices

1. **Development**: Use current architecture only
   ```bash
   ./scripts/build-multiarch.sh --backend redis --platforms linux/$(uname -m)
   ```

2. **Testing**: Build both architectures
   ```bash
   ./scripts/build-multiarch.sh --backend redis
   ```

3. **Production**: Use queue-specific images
   ```bash
   ./scripts/build-multiarch.sh --backend sqs --push --tag v1.0.0
   ```

4. **CI/CD**: Build all variants
   ```bash
   ./scripts/build-multiarch.sh --build-all --push --tag ${VERSION}
   ```

## Documentation

- 📘 **Complete Guide**: [MULTI_ARCH_BUILD.md](MULTI_ARCH_BUILD.md)
- 🧪 **Test Results**: [BUILD_TEST_RESULTS.md](BUILD_TEST_RESULTS.md)
- 📦 **Image Variants**: [DOCKER_IMAGES.md](DOCKER_IMAGES.md)
- 📋 **Summary**: [MULTI_ARCH_SUMMARY.md](MULTI_ARCH_SUMMARY.md)

## Need Help?

```bash
# Show script help
./scripts/build-multiarch.sh --help

# Check buildx version
docker buildx version

# List available builders
docker buildx ls

# Inspect builder platforms
docker buildx inspect --bootstrap
```
