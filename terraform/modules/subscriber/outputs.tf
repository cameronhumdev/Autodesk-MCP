output "namespace" {
  value       = "sub-${var.subscriber_id}"
  description = "Intended Kubernetes namespace"
}

output "ingress_host" {
  value       = "${var.subscriber_id}.ai.example.local"
  description = "Placeholder hostname — wire real DNS later"
}

output "public_ai" {
  value = var.public_ai
}
