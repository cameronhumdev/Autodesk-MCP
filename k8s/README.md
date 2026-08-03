# `k8s/` — Kubernetes manifests

| Item | Value |
|------|--------|
| Role | Pods, probes, services, Ingress |
| Provisioned by | Terraform / OpenTofu (`../terraform/`) |
| Swap | Replace manifests/Helm chart; keep Service name `test-ui` stable for Ingress |

## Layout

```text
k8s/
  README.md
  test-ui/          # Dev / smoke Deployment for test-ui
```

## Apply (after cluster exists)

```bash
kubectl apply -f k8s/test-ui/
```

## Notes

- Per-subscriber isolation later = Namespace + NetworkPolicy (`subscriber_id`).
- CAD workers stay off Linux nodes (Windows v2).
