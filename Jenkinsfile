pipeline {
    agent any

    environment {
        DOCKER_IMAGE = 'latest'
        DOCKERHUB_USERNAME = 'oyinc'
        DOCKERHUB_REPO = 'waste_detection'
    }

    stages {

        stage('Initialize Logs') {
            steps {
                script {
                    // Create ci_logs folder and initialize log file
                    sh '''
                        mkdir -p ci_logs
                        echo "ci_timing log for Jenkins run $(date)" > ci_logs/ci_timing.log
                        echo "$(date +%s),initialize_logs_done" >> ci_logs/ci_timing.log
                    '''
                }
            }
        }

        stage('Enable Buildx') {
            steps {
                script {
                    sh '''
                        echo "$(date +%s),buildx_start" >> ci_logs/ci_timing.log
                        export DOCKER_CLI_EXPERIMENTAL=enabled
                        docker buildx create --use || true
                        docker buildx inspect --bootstrap || true
                        echo "$(date +%s),buildx_done" >> ci_logs/ci_timing.log
                    '''
                }
            }
        }

        stage('Login to Docker Hub') {
            steps {
                withCredentials([string(credentialsId: 'docker-hub-password', variable: 'DOCKER_PASSWORD')]) {
                    sh '''
                        echo "$(date +%s),docker_login_start" >> ci_logs/ci_timing.log
                        echo $DOCKER_PASSWORD | docker login -u ${DOCKERHUB_USERNAME} --password-stdin
                        echo "$(date +%s),docker_login_done" >> ci_logs/ci_timing.log
                    '''
                }
            }
        }

        stage('Build & Push Multi-Arch Image') {
            steps {
                script {
                    sh '''
                        echo "$(date +%s),docker_build_push_start" >> ci_logs/ci_timing.log
                        docker buildx build --platform linux/arm/v7,linux/arm64,linux/amd64 \
                            -t ${DOCKERHUB_USERNAME}/${DOCKERHUB_REPO}:${DOCKER_IMAGE} \
                            --push .
                        echo "$(date +%s),docker_build_push_done" >> ci_logs/ci_timing.log
                    '''
                }
            }
        }

    }

    post {
        always {
            // Archive the timing log for download
            archiveArtifacts artifacts: 'ci_logs/ci_timing.log', fingerprint: true
        }
    }
}
