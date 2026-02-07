# Python Style Guide

## Python General
- Follow **PEP 8** style guidelines for Python code.
- Use **Type Hints** for function arguments and return values.
- Use **Docstrings** (Google Style) for all functions, classes, and modules.
- Prefer `f-strings` for string formatting.
- Handle exceptions specifically; avoid bare `except:`.

## Docker & Deployment
- Keep the image size small. Use minimal base images (e.g., `public.ecr.aws/lambda/python:3.x`).
- Clean up caches (`pip cache purge`) in the Dockerfile to reduce image size.
