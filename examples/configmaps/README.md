# OpenHQM ConfigMap Examples

Ready-to-use Kubernetes ConfigMap examples that can be imported directly into OpenHQM Router Manager.

## 📋 Available ConfigMaps

### 1. Starter Routes (`starter-routes.yaml`)
**Purpose:** Simple beginner-friendly configuration  
**Routes:** 4 routes  
**Use Case:** Getting started, development, learning

**Features:**
- Basic user registration with JQ transformation
- Simple order creation (passthrough)
- Notification routing with regex pattern
- Default fallback route

**Deploy:**
```bash
kubectl apply -f configmaps/starter-routes.yaml
```

**Import to Router Manager:**
1. Copy contents of `starter-routes.yaml`
2. Open Router Manager (http://localhost:5173)
3. Click "Import" button
4. Paste YAML content
5. Click "Import ConfigMap"

---

### 2. Production Routes (`production-routes.yaml`)
**Purpose:** Production-ready comprehensive configuration  
**Routes:** 10 routes  
**Use Case:** Production deployments, multi-environment setups

**Features:**
- Priority-based routing (high-priority orders)
- Multiple transformation types (JQ, Template, JSONPath)
- Header and query parameter mappings
- Retry configuration
- Timeout settings per route
- Payment processing with idempotency
- Analytics tracking with pattern matching
- Legacy system integration

**Deploy:**
```bash
kubectl apply -f configmaps/production-routes.yaml
```

**Import to Router Manager:**
1. Copy contents of `production-routes.yaml`
2. Open Router Manager
3. Import via UI
4. Edit and customize for your environment

---

### 3. Microservices Routes (`microservices-routes.yaml`)
**Purpose:** Service-based routing for microservices architecture  
**Routes:** 6 routes  
**Use Case:** Microservices, API gateway patterns

**Features:**
- Service-based routing (users, orders, products, inventory, shipping)
- Consistent transformation patterns
- API gateway fallback
- Clean separation of concerns

**Deploy:**
```bash
kubectl apply -f configmaps/microservices-routes.yaml
```

**Import to Router Manager:**
1. Copy contents of `microservices-routes.yaml`
2. Import to Router Manager
3. Customize service endpoints

---

## 🔧 Usage Workflow

### 1. Import ConfigMap to Router Manager

```bash
# Option A: Copy-paste in UI
cat configmaps/starter-routes.yaml | pbcopy  # macOS
# Then paste in Router Manager import dialog

# Option B: Use via file upload (if supported)
# Click "Import" > "Upload File" > Select yaml file
```

### 2. Edit Routes Visually

- Add new routes with drag-and-drop
- Test JQ transformations in playground
- Simulate routing with sample payloads
- Preview final ConfigMap before export

### 3. Export Modified ConfigMap

- Click "Export" button
- Choose YAML format
- Download updated ConfigMap
- Deploy to Kubernetes

### 4. Deploy to Kubernetes

```bash
# Deploy the exported ConfigMap
kubectl apply -f exported-routes.yaml

# Verify deployment
kubectl get configmap -n <namespace>
kubectl describe configmap openhqm-routes -n <namespace>

# Apply to OpenHQM StatefulSet
kubectl rollout restart statefulset openhqm-workers -n <namespace>
```

---

## 🧪 Testing ConfigMaps

### Validate Before Import

```bash
# Validate YAML syntax and structure
cd ../../  # back to examples/
python3 validate_routing_config.py configmaps/starter-routes.yaml
python3 validate_routing_config.py configmaps/production-routes.yaml
python3 validate_routing_config.py configmaps/microservices-routes.yaml
```

### Test in Router Manager

1. **Import ConfigMap:**
   ```bash
   # Start Router Manager
   cd ../../../openhqm-rm
   npm run dev
   ```

2. **Test Routes:**
   - Open JQ Playground
   - Test each route's transformation
   - Use Simulator to test routing logic

3. **Run E2E Tests:**
   ```bash
   npm run test:e2e -- configmap-import.spec.ts
   ```

---

## 📊 ConfigMap Comparison

| ConfigMap | Routes | Complexity | Transform Types | Best For |
|-----------|--------|------------|----------------|----------|
| **starter-routes** | 4 | Low | JQ, Passthrough | Learning, Development |
| **production-routes** | 10 | High | JQ, Template, JSONPath, Passthrough | Production, Complex workflows |
| **microservices-routes** | 6 | Medium | JQ, Passthrough | Microservices architecture |

---

## 🎯 Customization Guide

### Modify Endpoints

```yaml
# Change this:
endpoint: "user-service"

# To your actual service:
endpoint: "https://api.example.com/users"
```

### Add Authentication Headers

```yaml
header_mappings:
  Authorization: "metadata.authToken"
  X-API-Key: "metadata.apiKey"
```

### Adjust Timeouts

```yaml
timeout: 60  # seconds
max_retries: 3
```

### Add Custom Routes

1. Import ConfigMap to Router Manager
2. Click "Add Route" button
3. Fill in route details
4. Test with Simulator
5. Export updated ConfigMap

---

## 🚀 Production Deployment

### Pre-deployment Checklist

- [ ] Validate all ConfigMaps with `validate_routing_config.py`
- [ ] Test transformations in Router Manager JQ Playground
- [ ] Simulate routing with realistic payloads
- [ ] Update service endpoints to production URLs
- [ ] Add appropriate namespace and labels
- [ ] Configure timeouts based on SLAs
- [ ] Set retry policies for each route
- [ ] Add monitoring labels and annotations
- [ ] Review security: remove sensitive data from ConfigMaps
- [ ] Test in staging environment first

### Deployment Commands

```bash
# Deploy to staging
kubectl apply -f configmaps/production-routes.yaml -n staging

# Verify
kubectl get configmap -n staging
kubectl describe configmap openhqm-production-routes -n staging

# Monitor rollout
kubectl rollout status statefulset openhqm-workers -n staging

# Deploy to production (after validation)
kubectl apply -f configmaps/production-routes.yaml -n production
```

---

## 🔗 Related Documentation

- [OpenHQM Routing Documentation](../../docs/ROUTING_PARTITIONING.md)
- [Router Manager Guide](../../../../openhqm-rm/README.md)
- [Validation Tool](../validate_routing_config.py)
- [Integration Guide](../../docs/INTEGRATION.md)

---

## ✨ Tips

1. **Start Simple:** Begin with `starter-routes.yaml` and add complexity as needed
2. **Test Locally:** Always test transformations in Router Manager before deploying
3. **Version Control:** Keep ConfigMaps in git alongside your application code
4. **Namespace Isolation:** Use different ConfigMaps per namespace/environment
5. **Monitor Changes:** Track ConfigMap versions with annotations
6. **Backup Strategy:** Export ConfigMaps regularly from Router Manager

---

**Last Updated:** 2024-02-08  
**Version:** 1.0  
**Status:** ✅ Production Ready
