# OpenHQM Documentation

Complete documentation for OpenHQM - HTTP Queue Message Handler.

## 📚 Core Documentation

### Getting Started
- **[Quickstart Guide](QUICKSTART.md)** - Get up and running in 5 minutes
- **[Quick Reference](QUICK_REFERENCE.md)** - Command cheat sheet

### Architecture & Design
- **[Software Design Document (SDD)](../SDD.md)** - Complete system design
- **[Architecture Overview](ARCHITECTURE.md)** - High-level architecture diagrams
- **[Composable Patterns](COMPOSABLE_PATTERNS.md)** - HTTP→Queue, Queue→HTTP patterns

## 🎯 Deployment Patterns

### Kubernetes & Containers
- **[Kubernetes Sidecar Pattern](KUBERNETES_SIDECAR.md)** - Deploy as K8s sidecar
- **[Sidecar Revolution](SIDECAR_REVOLUTION.md)** - Modernize legacy apps
- **[Deployment Patterns](DEPLOYMENT_PATTERNS.md)** - Various deployment strategies

### Docker & Multi-Architecture
- **[Docker Images](DOCKER_IMAGES.md)** - Image variants and usage
- **[Multi-Arch Build Guide](MULTI_ARCH_BUILD.md)** - Build for AMD64 & ARM64
- **[Build Test Results](BUILD_TEST_RESULTS.md)** - Multi-arch test validation
- **[Multi-Arch Summary](MULTI_ARCH_SUMMARY.md)** - Implementation overview

## 🔌 Queue Backends

- **[Queue Backends Guide](QUEUE_BACKENDS.md)** - Complete guide for all 7 backends
- **[Queue Infrastructure Summary](QUEUE_INFRASTRUCTURE_SUMMARY.md)** - Quick reference

**Supported Backends:**
- Redis Streams (low latency)
- Apache Kafka (high throughput)
- AWS SQS (cloud-managed)
- Azure Event Hubs (cloud-managed, Kafka-compatible)
- GCP Pub/Sub (cloud-managed, global scale)
- MQTT (IoT/edge computing)
- Custom (bring your own handler)

## 🔄 Proxy Mode

- **[Proxy Mode Guide](PROXY_MODE.md)** - Complete reverse proxy documentation
- **[Proxy Summary](PROXY_SUMMARY.md)** - Quick overview
- **[Testing Proxy Mode](TESTING_PROXY.md)** - Test scenarios

## 🎨 Feature Summaries

- **[Feature Summary](FEATURE_SUMMARY.md)** - All features at a glance

## 📖 Navigation by Topic

### I want to...

**Get Started Quickly**
→ [Quickstart Guide](QUICKSTART.md) → [Quick Reference](QUICK_REFERENCE.md)

**Understand the Architecture**
→ [SDD](../SDD.md) → [Architecture Overview](ARCHITECTURE.md) → [Composable Patterns](COMPOSABLE_PATTERNS.md)

**Deploy on Kubernetes**
→ [Kubernetes Sidecar](KUBERNETES_SIDECAR.md) → [Sidecar Revolution](SIDECAR_REVOLUTION.md) → [Deployment Patterns](DEPLOYMENT_PATTERNS.md)

**Build Docker Images**
→ [Docker Images](DOCKER_IMAGES.md) → [Multi-Arch Build](MULTI_ARCH_BUILD.md) → [Quick Reference](QUICK_REFERENCE.md)

**Configure Queue Backend**
→ [Queue Backends Guide](QUEUE_BACKENDS.md) → [Queue Infrastructure Summary](QUEUE_INFRASTRUCTURE_SUMMARY.md)

**Use as Reverse Proxy**
→ [Proxy Mode Guide](PROXY_MODE.md) → [Proxy Summary](PROXY_SUMMARY.md) → [Testing Proxy](TESTING_PROXY.md)

**Modernize Legacy Apps**
→ [Sidecar Revolution](SIDECAR_REVOLUTION.md) → [Kubernetes Sidecar](KUBERNETES_SIDECAR.md) → [Composable Patterns](COMPOSABLE_PATTERNS.md)

**Build Multi-Architecture Images**
→ [Multi-Arch Build](MULTI_ARCH_BUILD.md) → [Build Test Results](BUILD_TEST_RESULTS.md) → [Docker Images](DOCKER_IMAGES.md)

## 🛠️ Additional Resources

- **[Contributing Guidelines](../CONTRIBUTING.md)** - How to contribute
- **[Changelog](../CHANGELOG.md)** - Version history
- **[License](../LICENSE)** - MIT License

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/openhqm/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/openhqm/discussions)
- **Documentation**: This folder and main [README](../README.md)
