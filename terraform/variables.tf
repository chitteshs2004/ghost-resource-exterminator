variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance size (t2.micro/t3.micro = AWS free-tier eligible)"
  type        = string
  default     = "t2.medium"
}
variable "instance_storage" {
  description = "EC2 instance storage size in GB (default: 8GB)"
  type        = number
  default     = 30
}

variable "key_pair_name" {
  description = "Name of an EXISTING EC2 key pair (create in AWS Console > EC2 > Key Pairs first)"
  type        = string
  default = "kavitha"
}

variable "my_ip" {
  description = "Your public IP in CIDR form, e.g. 103.21.45.10/32 (used to lock down SSH). Get it from https://checkip.amazonaws.com"
  type        = string
}

variable "project_name" {
  description = "Used to tag/name all resources"
  type        = string
  default     = "ghost-resource-exterminator"
}
 variable "ami_id" {
  description = "AMI ID to use for the EC2 instance (optional, overrides automatic Amazon Linux lookup)"
  type        = string
  default     = "ami-004f790b835b26145"
 }
 variable "subnet_id" {
  description = "Subnet ID to launch the EC2 instance in (optional, overrides automatic default subnet lookup)"
  type        = string
  default     = "subnet-094fd2e02848ed37f"
 }
 variable "security_group_id" {
  description = "Security Group ID to associate with the EC2 instance (optional, overrides automatic security group creation)"
  type        = list(string)
  default     = ["sg-03b9b5a3dcb9c28cf"]
 }

