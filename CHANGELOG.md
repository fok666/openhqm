# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Two sidecar modes in one image: `http-to-queue` and `queue-to-http`
- Queue adapters: Redis Streams, Kafka, SQS, Azure Event Hubs, GCP Pub/Sub, MQTT, custom
- Minimal 4-method queue contract (`connect/close/publish/consume`)
- Per-backend installs via pyproject extras, mirrored by Docker `QUEUE_BACKEND` builds
- Redis result store with TTL'd request state (`PENDING → PROCESSING → COMPLETED/FAILED`)
- Retry with backoff + dead letter queue
- Prometheus metrics, structured logging, K8s liveness/readiness probes

### Changed
- Requirements files replaced by pyproject extras
- Routing/partitioning engines removed — the Gateway does the routing
