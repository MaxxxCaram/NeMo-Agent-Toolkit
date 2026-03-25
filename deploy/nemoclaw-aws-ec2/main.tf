provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile != "" ? var.aws_profile : null
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

locals {
  nemoclaw_env_lines = concat(
    var.telegram_bot_token != "" ? ["TELEGRAM_BOT_TOKEN=${var.telegram_bot_token}"] : [],
    var.nvidia_api_key != "" ? ["NVIDIA_API_KEY=${var.nvidia_api_key}"] : [],
  )
  nemoclaw_env_file_body = length(local.nemoclaw_env_lines) > 0 ? join("\n", local.nemoclaw_env_lines) : "# Set TELEGRAM_BOT_TOKEN and/or NVIDIA_API_KEY, then: sudo systemctl restart nemoclaw-aux"
}

resource "aws_security_group" "this" {
  name_prefix = "nemoclaw-ec2-"
  description = "SSH (+ default egress) for NemoClaw EC2 bootstrap"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ssm" {
  count              = var.enable_ssm ? 1 : 0
  name_prefix        = "nemoclaw-ssm-"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  count      = var.enable_ssm ? 1 : 0
  role       = aws_iam_role.ssm[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ssm" {
  count       = var.enable_ssm ? 1 : 0
  name_prefix = "nemoclaw-ec2-"
  role        = aws_iam_role.ssm[0].name
}

resource "aws_instance" "nemoclaw" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = sort(data.aws_subnets.default.ids)[0]
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.this.id]
  iam_instance_profile        = var.enable_ssm ? aws_iam_instance_profile.ssm[0].name : null
  key_name                    = var.key_name != "" ? var.key_name : null

  root_block_device {
    volume_size = var.volume_size_gb
    volume_type = "gp3"
  }

  user_data = sensitive(templatefile("${path.module}/user-data.sh.tftpl", {
    nemoclaw_sandbox_name  = var.nemoclaw_sandbox_name
    nemoclaw_env_file_body = local.nemoclaw_env_file_body
  }))
  user_data_replace_on_change = true

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  tags = {
    Name = "nemoclaw-ec2"
  }
}
