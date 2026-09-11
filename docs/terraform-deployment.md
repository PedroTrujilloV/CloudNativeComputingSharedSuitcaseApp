# Terraform Cloud Infrastructure

## Overview

This project uses Terraform to provision cloud infrastructure on AWS (Amazon Web Services) in the `us-east-1` region. The infrastructure consists of three stacks deployed in a specific order: network, data, and compute. Each stack is responsible for a specific layer of the architecture.

The deployment pipeline (`ci_entrega2_deploy.yml`) orchestrates the following steps:

1. Terraform applies each stack in order (network -> data -> compute).
2. Docker images are built and pushed to Amazon ECR repositories.
3. Kubernetes manifests are applied to the EKS cluster.

## Infrastructure Architecture

```mermaid
graph TD
  subgraph GitHub["GitHub Repository + Actions"]
    GitCode[Git Push] --> Pipeline[ci_entrega2_deploy.yml]
    TFCode[terraform/\nstacks/* +\nenvironments/*] --> Pipeline
    AppCode[App Dockerfiles\n(users_app, posts_app,\noffers_app, etc.)] --> Pipeline
  end

  subgraph AWS["AWS us-east-1"]
    subgraph EKS["EKS Cluster (compute)"]
      K8sPods[Kubernetes Pods\norchestrators + apps]
    end
    RDS[RDS PostgreSQL\ndata layer]
    ECR[ECR Repositories\none per app]

    subgraph Network["VPC/Networking (network)"]
      VPC[VPC]
      IGW[Internet Gateway]
      NAT[NAT Gateway]
    end
  end

  Pipeline --> EKS
  Pipeline --> RDS
  Pipeline --> ECR
  Pipeline --> Network

  K8sPods --> RDS
  K8sPods -.-> |pull images from| ECR

  style TFCode fill:#f9f,stroke:#333
  style AppCode fill:#bbf,stroke:#333
  style EKS fill:#ff9,stroke:#333
  style RDS fill:#9f9,stroke:#333
  style ECR fill:#ff9,stroke:#333
  style Network fill:#cfc,stroke:#333
```

## Stack Decomposition

The project follows a three-stack decomposition model:

| Order | Stack | Components | Purpose |
|-------|-------|-----------|---------|
| 1 | **network** | VPC, public/private subnets (2 AZs), Internet Gateway, NAT Gateway, Route Tables, Security Groups (RDS, EKS nodes, ALB) | Provides the isolated networking foundation for all other stacks. |
| 2 | **data** | RDS PostgreSQL instance, Secrets Manager secrets (DB credentials + per-app schema isolation), SSM Parameter (schema creation script) | Provisions the shared database layer with per-app schema/role isolation. |
| 3 | **compute** | EKS Cluster (v1.31), managed node group, ECR repositories (8 total), IAM roles (cluster, nodes, pod identity), OIDC provider | Provides the container orchestration platform and image registry for application workloads. |

This separation of concerns allows each stack to be deployed and destroyed independently while maintaining clear dependency boundaries: **compute** depends on both **network** and **data**; **data** depends on **network**.

## Stack README Files

Each stack includes a detailed README describing its components, variables, outputs, and relationships. These READMEs are auto-copied during the GitHub Pages deployment process.

- [Network Stack README](./terraform/network-README.md)
- [Data Stack README](./terraform/data-README.md)
- [Compute Stack README](./terraform/compute-README.md)

## Local Deployment (Development Testing)

This section describes how to deploy the infrastructure locally for development and testing purposes. The local deployment uses a `local` Terraform backend with stub state files that simulate AWS resource outputs without creating real AWS resources.

### Prerequisites

- [Terraform >= 1.10.0](https://developer.hashicorp.com/terraform/install) installed
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) configured (for any AWS operations, such as kubectl configuration)
- A valid `aws` credential profile or environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)

### Step 1: Network Stack

```bash
# Navigate to the network stack directory
cd terraform/stacks/network

# Initialize Terraform with local backend
terraform init

# Review the plan (uses defaults from network-terraform.tfvars)
terraform plan -var-file=../../environments/student1/network/network-terraform.tfvars

# Apply the network stack
terraform apply -var-file=../../environments/student1/network/network-terraform.tfvars
```

The network stack creates: VPC with CIDR `10.0.0.0/16`, 2 public subnets, 2 private subnets, Internet Gateway, NAT Gateway, route tables, and security groups for RDS, EKS nodes, and ALB.

### Step 2: Data Stack

```bash
# Navigate to the data stack directory
cd ../data

# Initialize Terraform with local backend
terraform init

# Review the plan (uses defaults from data-terraform.tfvars)
# IMPORTANT: db_username and db_password are required variables. 
# Override them in data-terraform.tfvars or via command line:
terraform plan \
  -var-file=../../environments/student1/data/data-terraform.tfvars

# Apply the data stack
terraform apply \
  -var-file=../../environments/student1/data/data-terraform.tfvars
```

The data stack creates: a single RDS PostgreSQL instance (db.t3.micro, 20 GB gp3 storage), Secrets Manager secret for master DB credentials, per-app Secrets Manager secrets with generated passwords, and an SSM Parameter storing the schema creation SQL script.

### Step 3: Compute Stack

```bash
# Navigate to the compute stack directory
cd ../compute

# Initialize Terraform with local backend
terraform init

# Review the plan (uses defaults from terraform-compute.tfvars)
terraform plan -var-file=../../environments/student1/compute/terraform-compute.tfvars

# Apply the compute stack
terraform apply \
  -var-file=../../environments/student1/compute/terraform-compute.tfvars
```

The compute stack creates: an EKS cluster (Kubernetes v1.31) with a managed node group (2 t3.medium nodes), 8 ECR repositories (one per app in config.yaml), IAM roles for the cluster, nodes, and pod identity, and an OIDC provider for IRSA.

### Verification Steps

After all three stacks are deployed:

```bash
# Verify VPC resources
aws ec2 describe-vpcs --region us-east-1 \
  --filters "Name=tag:Name,Values=shared-suitcase-vpc"

# Verify RDS instance
aws rds describe-db-instances --db-instance-identifier \
  shared-suitcase-postgres --region us-east-1

# List ECR repositories
aws ecr describe-repositories --region us-east-1

# Configure kubectl for the EKS cluster
aws eks update-kubeconfig --name shared-suitcase-cluster --region us-east-1

# Verify EKS cluster connectivity
kubectl get nodes
```

## Stack Deployment Order

The stacks must be deployed in the following order:

1. **network**: foundational infrastructure (no dependencies)
2. **data**: depends on network stack outputs via remote state
3. **compute**: depends on both network and data stack outputs via remote state

## Destroy Order

Destroy the stacks in reverse order to avoid dependency conflicts:

```bash
# 1. Destroy compute (EKS cluster, ECR repos)
cd terraform/stacks/compute && terraform destroy \
  -var-file=../../environments/student1/compute/terraform-compute.tfvars

# 2. Destroy data (RDS instance, Secrets Manager secrets)
cd ../data && terraform destroy \
  -var-file=../../environments/student1/data/data-terraform.tfvars

# 3. Destroy network (VPC, subnets, gateways, security groups)
cd ../network && terraform destroy \
  -var-file=../../environments/student1/network/network-terraform.tfvars
```

## Post-Deployment: Kubernetes Workloads

After Terraform creates the EKS cluster and ECR repositories, deploy application workloads using kubectl:

### Push Application Images to ECR

For each application in `config.yaml`:

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 | docker login \
  --username AWS <ecr-repository-uri>

# Build and push the image
cd users_app
docker build -t users-app:v0.0.0 .
docker tag users-app:v0.0.0 <ecr-repository-uri>/users-app:v0.0.0
docker push <ecr-repository-uri>/users-app:v0.0.0
cd ..
```

### Deploy Kubernetes Manifests

After all images are pushed to ECR, update the k8s manifests with the ECR image URIs and RDS endpoint, then apply:

```bash
kubectl apply -f k8s/

# Verify pods are running
kubectl get pods
kubectl get services
kubectl get ingress
```

### Per-App Schema Initialization

The data stack stores a schema creation SQL script in SSM Parameter `/shared-suitcase/rds/schema-create`. Execute this script on the RDS instance to create per-app schemas and roles:

```bash
# Get the schema script from SSM Parameter Store
SCHEMA_SCRIPT=$(aws ssm get-parameter \
  --name "/shared-suitcase/rds/schema-create" \
  --region us-east-1 \
  --query 'Parameter.Value' --output text)

# Execute the script on the RDS instance (requires psql CLI and access to the DB subnet)
echo "$SCHEMA_SCRIPT" | psql "host=<RDS_ENDPOINT> port=5432 dbname=shared_db user=admin"
```

## Terraform State Backend Configuration

### Local Testing

For local development testing, each stack uses a `local` backend by default. The state file path is specified in the `backend.tfvars` files under:

```
terraform/environments/<environment>/network/backend.tfvars
terraform/environments/<environment>/data/backend.tfvars
terraform/environments/<environment>/compute/backend.tfvars
```

Example for the compute stack:

```hcl
path = terraform.tfstate
```

### CI/CD Deployment to AWS Academy Accounts

For CI/CD deployments to AWS Academy accounts, replace the `local` backend with an S3 remote backend with DynamoDB state locking. Configure the backend in the corresponding `backend.tfvars` file:

```hcl
bucket         = "my-terraform-state-bucket"
key            = "<stack>/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "terraform-locks"
```

The stack name should replace `<stack>` (for example, `network/terraform.tfstate`, `data/terraform.tfstate`, or `compute/terraform.tfstate`).

## Remote State Configuration

Each downstream stack reads outputs from upstream stacks via Terraform remote state. The state file paths are configured as variables:

| Stack | Reads From | Variable | Default Path |
|-------|-----------|----------|-------------|
| data | network | `network_state_path` | `../../environments/student1/network/terraform.tfstate` |
| compute | network | `network_state_path` | `../../environments/student1/network/terraform.tfstate` |
| compute | data | `data_state_path` | `../../environments/student1/data/terraform.tfstate` |

These paths are relative to the stack directory and are resolved at runtime. For multi-environment support, each environment (for example, `student1`, `tutor`) has its own set of backend and tfvars files under `terraform/environments/<environment>/`.

## Security Considerations

- **No credentials in source code**: AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, DB_USERNAME, DB_PASSWORD) are stored exclusively as GitHub Environment secrets or in local `.tfvars` files excluded from version control.
- **Least privilege IAM roles**: Each stack defines only the minimum IAM policies required for its resources. The compute stack includes Pod Identity (IRSA) so that k8s workloads can access Secrets Manager without long-lived credentials.
- **Per-app credential isolation**: Each application has its own Secrets Manager secret with a unique generated password, preventing cross-app credential sharing.
- **RDS deletion protection is disabled**: This simplifies local testing and stack destroy workflows, but should be enabled in production environments.
