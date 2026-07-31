pipeline {
    agent any

    // Jenkins > Manage Jenkins > Credentials — create these two BEFORE running:
    //   dockerhub-creds : "Username with password" (your Docker Hub login)
    //   ec2-ssh-key      : "SSH Username with private key" (username: ec2-user,
    //                       private key: paste contents of your .pem file)
    environment {
        DOCKERHUB_CREDS   = credentials('docker_cred')
        IMAGE_NAME        = "chitteshs2004/ghost-resource-exterminator"
        IMAGE_TAG         = "${env.BUILD_NUMBER}"
        EC2_HOST          = "ubuntu@44.193.210.133"
    }

    stages {

        stage('Checkout') {
            steps {
                // Pulls the latest code from GitHub whenever this pipeline runs
                git branch: 'main', url: 'https://github.com/chitteshs2004/ghost-resource-exterminator.git'
            }
        }

        stage('Build Docker Image') {
            steps {
                sh "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} -t ${IMAGE_NAME}:latest ."
            }
        }

        stage('Push to Docker Hub') {
            steps {
                sh """
                    echo "${DOCKERHUB_CREDS_PSW}" | docker login -u "${DOCKERHUB_CREDS_USR}" --password-stdin
                    docker push ${IMAGE_NAME}:${IMAGE_TAG}
                    docker push ${IMAGE_NAME}:latest
                """
            }
        }

        stage('Deploy to EC2') {
            steps {
                sshagent(credentials: ['ec2-ssh-key']) {
                    sh """
                        ssh -o StrictHostKeyChecking=no ${EC2_HOST} '
                            sudo docker pull ${IMAGE_NAME}:latest &&
                            sudo docker stop ghost-dashboard || true &&
                            sudo docker rm ghost-dashboard || true &&
                            sudo docker run -d --name ghost-dashboard \
                                -p 8501:8501 \
                                --restart unless-stopped \
                                -v ghost-data:/app/data \
                                ${IMAGE_NAME}:latest
                        '
                    """
                }
            }
        }
    }

    post {
        success {
            echo "Deployed! Visit http://YOUR_EC2_PUBLIC_IP:8501"
        }
        failure {
            echo "Build or deploy failed — check the stage logs above."
        }
        always {
            sh "docker logout"
        }
    }
}

