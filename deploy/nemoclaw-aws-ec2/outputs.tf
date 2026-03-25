output "instance_id" {
  value       = aws_instance.nemoclaw.id
  description = "EC2 instance ID."
}

output "private_ip" {
  value       = aws_instance.nemoclaw.private_ip
  description = "Private IPv4 address."
}

output "public_ip" {
  value       = aws_instance.nemoclaw.public_ip
  description = "Public IPv4 (empty if no public IP assigned)."
}

output "ssh_hint" {
  value       = var.key_name != "" ? "ssh -i <your-key.pem> ubuntu@${aws_instance.nemoclaw.public_ip}" : "SSH disabled unless key_name is set; use SSM (ssm_session_hint)."
  description = "Example SSH command when a key pair is configured."
}

output "ssm_session_hint" {
  value       = var.enable_ssm ? "aws ssm start-session --target ${aws_instance.nemoclaw.id} --region ${var.aws_region}" : "enable_ssm is false; enable it or use SSH with key_name."
  description = "AWS CLI command for Session Manager."
}

output "post_apply_steps" {
  value       = <<-EOT
    1) Wait for cloud-init: sudo tail -f /var/log/cloud-init-output.log
    2) On the host (not inside sandbox): nemoclaw list
    3) If Telegram: nemoclaw ${var.nemoclaw_sandbox_name} policy-add  (pick telegram), then sudo systemctl restart nemoclaw-aux
    4) If NVIDIA key missing: edit /etc/nemoclaw/nemoclaw.env (chmod 600) or run nemoclaw onboard once as ubuntu
  EOT
  description = "Manual follow-ups after first boot."
}
