pipeline {
    agent any

    environment {
        // Docker Hub info
        DOCKER_IMAGE = 'latest'
        DOCKERHUB_USERNAME = 'oyinc'
        DOCKERHUB_REPO = 'waste_detection'

        // Raspberry Pi connection via ngrok
        // ⚠️ Update these when ngrok restarts unless you have a static tunnel
        PI_HOST = '6.tcp.eu.ngrok.io'
        PI_PORT = '12845'
        PI_USER = 'hshl'
    }

    stages {

        stage('Initialize Logs') {
            steps {
                script {
                    sh '''
                        mkdir -p ci_logs
                        echo "ci_timing log for Jenkins run $(date)" > ci_logs/ci_timing.log
                        echo "$(date +%s),initialize_logs_done" >> ci_logs/ci_timing.log
                    '''
                }
            }
        }

        stage('Login to Docker Hub') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'oyinc-docker',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh '''
                        echo "$(date +%s),docker_login_start" >> ci_logs/ci_timing.log
                        echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin
                        echo "$(date +%s),docker_login_done" >> ci_logs/ci_timing.log
                    '''
                }
            }
        }

        stage('Build and Push ARM64 Docker Image') {
            steps {
                script {
                    sh '''
                        echo "$(date +%s),docker_build_start" >> ci_logs/ci_timing.log

                        # Build directly for Raspberry Pi architecture
                        docker build \
                            --build-arg TARGETARCH=arm64 \
                            -t ${DOCKERHUB_USERNAME}/${DOCKERHUB_REPO}:${DOCKER_IMAGE} \
                            -f app/Dockerfile app/

                        echo "$(date +%s),docker_build_done" >> ci_logs/ci_timing.log
                        
                        echo "$(date +%s),docker_push_start" >> ci_logs/ci_timing.log
                        docker push ${DOCKERHUB_USERNAME}/${DOCKERHUB_REPO}:${DOCKER_IMAGE}
                        echo "$(date +%s),docker_push_done" >> ci_logs/ci_timing.log
                    '''
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

                                mkdir -p ci_logs
                                echo "$(date +%s),remote_deploy_start" >> ci_logs/ci_timing_deploy.log

                                echo "$(date +%s),docker_pull_start" >> ci_logs/ci_timing_deploy.log
                                docker compose pull
                                echo "$(date +%s),docker_pull_end" >> ci_logs/ci_timing_deploy.log

                                docker compose down || true
                                docker compose up -d app

                                echo "$(date +%s),docker_prune_start" >> ci_logs/ci_timing_deploy.log
                                docker image prune -af
                                echo "$(date +%s),docker_prune_end" >> ci_logs/ci_timing_deploy.log

                                echo "$(date +%s),remote_deploy_end" >> ci_logs/ci_timing_deploy.log
                            '

                            echo "$(date +%s),deploy_done" >> ci_logs/ci_timing.log
                        '''
                    }
                }
            }
        }
    }

    post {
        always {
            // Archive build & deploy logs
            archiveArtifacts artifacts: 'ci_logs/ci_timing.log', fingerprint: true
        }
    }
}
