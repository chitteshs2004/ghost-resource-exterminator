terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ── Find the latest Amazon Linux 2023 AMI automatically ──────────────────────
# So you never have to hardcode an AMI ID, which changes per region/date.

# ── IAM Role: what the EC2 instance is allowed to do in AWS ───────────────────
# This is the "IAM-based security" piece — instead of putting AWS access
# keys inside the .env file on the server, the EC2 instance itself carries
# temporary, auto-rotating credentials via this role. boto3 picks these up
# automatically with zero config (config.py's get_boto3_kwargs() already
# falls back to the default credential chain when no keys are supplied).
resource "aws_iam_role" "ghost_role" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

# Least-privilege custom policy: only what the scanner + cleanup workflow
# actually needs, instead of broad managed policies like AmazonEC2FullAccess.
resource "aws_iam_role_policy" "ghost_policy" {
  name = "${var.project_name}-policy"
  role = aws_iam_role.ghost_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadOnlyDiscovery"
        Effect = "Allow"
        Action = [
          "ec2:Describe*",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics"
        ]
        Resource = "*"
      },
      {
        Sid    = "ControlledCleanup"
        Effect = "Allow"
        Action = [
          "ec2:TerminateInstances",
          "ec2:DeleteVolume",
          "ec2:DeleteSnapshot"
        ]
        Resource = "*"
        # Optional hardening: add a Condition block here to restrict
        # this to resources tagged e.g. "zombie-candidate=true"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ghost_profile" {
  name = "${var.project_name}-profile"
  role = aws_iam_role.ghost_role.name
}

# ── EC2 Instance ───────────────────────────────────────────────────────────────
resource "aws_instance" "ghost_server" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_pair_name
  subnet_id              = var.subnet_id
  vpc_security_group_ids =var.security_group_id 
  iam_instance_profile   = aws_iam_instance_profile.ghost_profile.name

  user_data = file("${path.module}/user_data.sh")

  tags = {
    Name = var.project_name
  }
}

