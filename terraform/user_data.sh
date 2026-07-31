#!/bin/bash
# Runs once, automatically, the first time the EC2 instance boots.
# Installs Docker so Jenkins can later `ssh` in and run containers.

set -e
dnf update -y
dnf install -y docker git
systemctl enable docker
systemctl start docker

# Let the default ec2-user run docker without sudo
usermod -aG docker ec2-user

# Install docker-compose plugin
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose



#!/bin/bash
set -e

apt-get update -y
apt-get install -y docker.io git curl

systemctl enable docker
systemctl start docker

# Let the default Ubuntu user run Docker without sudo
usermod -aG docker ubuntu

# Install Docker Compose plugin
mkdir -p /usr/local/lib/docker/cli-plugins

curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose

chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
