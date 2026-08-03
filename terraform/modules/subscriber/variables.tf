variable "subscriber_id" {
  type        = string
  description = "Unique subscriber identifier"
}

variable "public_ai" {
  type        = bool
  description = "Whether to expose a public AI route"
  default     = false
}
