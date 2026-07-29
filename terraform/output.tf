output "instance_public_ip" {
  description = "Public IP of the EC2 instance — use this to SSH in and to open the dashboard"
  value       = aws_instance.ghost_server.public_ip
}

output "dashboard_url" {
  description = "Open this in your browser once Jenkins has deployed the container"
  value       = "http://${aws_instance.ghost_server.public_ip}:8501"
}

output "ssh_command" {
  description = "Command to SSH into the instance"
  value       = "ssh -i <your-key.pem> ec2-user@${aws_instance.ghost_server.public_ip}"
}

