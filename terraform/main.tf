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

# ── EC2 Instance ───────────────────────────────────────────────────────────────
resource "aws_instance" "ghost_server" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_pair_name
  subnet_id              = var.subnet_id
  vpc_security_group_ids =var.security_group_id 


root_block_device {
  volume_size = var.instance_storage
  volume_type = "gp3"
}
  user_data = file("${path.module}/user_data.sh")

  tags = {
    Name = var.project_name
  }
}
