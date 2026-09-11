
# Terraform Stacks


This directory contains the README files for each Terraform stack used to provision cloud infrastructure on AWS.


- [Network Stack](./network-README.md) VPC, subnets, IGW, NAT, security groups
- [Data Stack](./data-README.md) RDS PostgreSQL, Secrets Manager, schema isolation
- [Compute Stack](./compute-README.md) EKS cluster, node group, ECR repositories, IAM




## The mental model, in plain language

In order to understand how the pieces fit together, it's worth stepping back and looking at the *big picture* of what this project is doing. 

### Overview Diagram

![Infrastructure Architecture](./diagrams/infra-overview.png "Terraform Infrastructure Architecture")


There are actually **three separate systems** working together, and the confusion usually comes from not seeing where one ends and the next begins:

1. **Terraform** creates *infrastructure that isn't Kubernetes itself*: the EKS cluster (the "empty" Kubernetes control plane + worker nodes), the RDS database, the ECR repositories (empty image shelves). Terraform does **not** know what a Pod or a Deployment is in the app sense it only creates the *platform* those things will later run on.
2. **kubectl / K8s manifests** once EKS exists, a *separate* step (`kubectl apply -f k8s/`) talks to that cluster and creates the actual application objects: Deployments, Services, Ingress. This is a completely different tool talking to a completely different API (the K8s API, not the AWS API).
3. **GitHub Actions** the glue. It's a *runner* that, on the command, executes Terraform first (to build the platform), then builds+pushes Docker images to ECR (so K8s has something to pull), then runs kubectl (to deploy onto the now-existing cluster).

The reason people find this confusing is that Terraform and kubectl **feel similar** ("apply some config, get infrastructure") but they're talking to two entirely different APIs (AWS API vs. Kubernetes API), and nothing forces them to run in the same tool they just happen to run back-to-back in the same pipeline.

## What goes into Git vs. what doesn't

- **In Git:** all `.tf` files (Terraform *code* the definitions of "make me an EKS cluster," "make me an RDS instance"), all `.tfvars` files *without secrets* (non-secret config like instance sizes, region), all K8s `.yml` manifests, all app source code + Dockerfiles.
- **Not in Git, ever:** AWS credentials, DB passwords these live only in **GitHub Environment secrets**, injected as environment variables at pipeline runtime.
- **A subtlety:** Terraform itself needs to remember what it already built (its "state") so a second run knows to *update* instead of *duplicate*. That state file also isn't committed to Git it lives in an S3 bucket (that's what `backend.tfvars` configures: *where* that remote state lives, not secrets themselves).

Now the diagram:A quick note: **this diagram is explanatory only** it's to understand the mechanics, not something to drop into the graded `/docs` folder as is (it mixes GitHub Actions internals and dev workflow, which isn't what the rubric's "deployment view" is asking for that one should stay focused on the *AWS/K8s runtime topology*, which is what `deployment.puml` already covers).

Walking through the four pipeline jobs, since that's the part that was probably fuzziest:

- **Job 1 (config):** just reads `config.yaml` and checks the required secrets exist before doing anything expensive this is why missing `AWS_SESSION_TOKEN` fails immediately instead of halfway through a 10-minute Terraform apply.
- **Job 2 (terraform apply):** for each name in `tf_stacks` (in the case, just `apps`), runs `terraform apply` using that stack's `.tf` files plus the matching environment's `.tfvars`. This is what actually calls the AWS API to create EKS/RDS/ECR. Terraform tracks what it already made using its state file (stored in S3, not git) that's the entire reason `backend.tfvars` exists: to tell Terraform *where* that bookkeeping file lives.
- **Job 3 (build & push images):** ordinary `docker build` + `docker push`, once per app listed in `config.yaml`, landing in the ECR repos Job 2 just created (which start out empty Terraform makes the shelf, not the contents).
- **Job 4 (kubectl apply):** a completely separate tool now talks to the *Kubernetes API* of the cluster Job 2 built, applying the `k8s/*.yml` files. EKS then schedules the pods and pulls the images Job 3 just pushed. This is the step that finally creates the Ingress/Services/Deployments we have been diagramming this whole conversation.

The one thing worth internalizing: **Terraform's job ends the moment EKS/RDS/ECR exist.** It never touches Pods, Deployments, or the Ingress resource those are 100% `kubectl`'s domain, running against a totally different API, even though both happen inside the same GitHub Actions run back-to-back.