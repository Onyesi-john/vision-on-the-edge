pipeline {
    agent any

    environment {
        // Docker Hub info
        DOCKER_IMAGE = 'latest'
        DOCKERHUB_USERNAME = 'oyinc'
        DOCKERHUB_REPO = 'edge_deployment'

        // Raspberry Pi connection 
        PI_HOST = '5.tcp.eu.ngrok.io'
        PI_PORT = '19221'
        PI_USER = 'hshl'
    }

    stages {

        stage('Checkout') {
            steps {
                script {
                    sh '''
                        mkdir -p ci_logs
                        echo "ci_timing log for Jenkins run $(date)" > ci_logs/ci_timing.log
                        echo "$(date +%s),checkout_start" >> ci_logs/ci_timing.log
                    '''
                }
                checkout scm
                script {
                    sh 'echo "$(date +%s),checkout_end" >> ci_logs/ci_timing.log'
                }
            }
        }

        stage('Login, Build & Push Docker Image') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'oyinc-docker',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    script {
                        sh '''
                            echo "$(date +%s),build_start" >> ci_logs/ci_timing.log
                            
                            echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin

                            docker build \
                                --build-arg TARGETARCH=arm64 \
                                -t ${DOCKERHUB_USERNAME}/${DOCKERHUB_REPO}:${DOCKER_IMAGE} \
                                -f app/Dockerfile app/

                            docker push ${DOCKERHUB_USERNAME}/${DOCKERHUB_REPO}:${DOCKER_IMAGE}

                            echo "$(date +%s),build_end" >> ci_logs/ci_timing.log
                        '''
                    }
                }
            }
        }

        stage('Deploy to Raspberry Pi via ngrok') {
            steps {
                withCredentials([sshUserPrivateKey(
                    credentialsId: 'pi-ssh-key',
                    keyFileVariable: 'SSH_KEY_FILE'
                )]) {
                    script {
                        sh '''
                            echo "$(date +%s),deploy_start" >> ci_logs/ci_timing.log

                            ssh -i $SSH_KEY_FILE -p $PI_PORT -o StrictHostKeyChecking=no $PI_USER@$PI_HOST '
                                set -e
                                cd /home/hshl/VisionOnEdge || exit 1

                                docker compose pull
                                docker compose down || true
                                docker compose up -d app
                            '

                            echo "$(date +%s),deploy_end" >> ci_logs/ci_timing.log
                        '''
                    }
                }
            }
        }
    }

    post {
        always {
            echo "Archiving timing log..."
            archiveArtifacts artifacts: 'ci_logs/ci_timing.log', fingerprint: true
        }
    }
}
