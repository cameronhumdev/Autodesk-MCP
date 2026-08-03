# `terraform/` — OpenTofu / Terraform

| Item | Value |
|------|--------|
| Role | Create cluster, storage, DNS; clone per `subscriber_id` |
| Engine | OpenTofu preferred (Terraform-compatible) |
| Swap | Change providers/modules; keep outputs (`kubeconfig`, `ingress_host`) stable |

## Layout

```text
terraform/
  README.md
  modules/subscriber/   # Skeleton module (inputs/outputs only for now)
```

## Later

Wire a real provider (e.g. local kind, or cloud AKS/EKS/GKE) and call `kubectl`/`helm` against `k8s/`.
