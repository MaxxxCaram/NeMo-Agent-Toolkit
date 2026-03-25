variable "aws_region" {
  type        = string
  description = "AWS region for the EC2 instance."
  default     = "us-east-1"
}

variable "aws_profile" {
  type        = string
  description = "AWS CLI profile (empty = default chain: env vars, then ~/.aws/credentials default)."
  default     = ""
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type (CPU is enough for local Ollama-style sandboxes; use GPU types if you add NIM later)."
  default     = "t3.xlarge"
}

variable "key_name" {
  type        = string
  description = "Optional EC2 key pair name for SSH. Leave empty to use SSM Session Manager only (requires enable_ssm = true)."
  default     = ""
}

variable "allowed_ssh_cidr" {
  type        = string
  description = "CIDR allowed to reach TCP 22 (your public IP/32 recommended)."
  default     = "0.0.0.0/0"
}

variable "enable_ssm" {
  type        = bool
  description = "Attach IAM instance profile for AWS Systems Manager Session Manager."
  default     = true
}

variable "nemoclaw_sandbox_name" {
  type        = string
  description = "Sandbox name passed to nemoclaw systemd unit (RFC1123-style)."
  default     = "my-assistant"
}

variable "telegram_bot_token" {
  type        = string
  description = "Telegram bot token (sensitive). Leave empty to configure later on the instance."
  default     = ""
  sensitive   = true
}

variable "nvidia_api_key" {
  type        = string
  description = "NVIDIA API key nvapi-... (sensitive). Leave empty if only using local inference and you handle prompts separately."
  default     = ""
  sensitive   = true
}

variable "volume_size_gb" {
  type        = number
  description = "Root EBS volume size (GiB)."
  default     = 80
}
