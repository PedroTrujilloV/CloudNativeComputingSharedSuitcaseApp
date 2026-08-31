
# Project Delivery 1 - Shared Suitcase Package Delivery Platform (P2P Broker)

This project implements the first delivery of a brokerage platform (broker) for collaborative package delivery. The system consists of four independent applications (users, routes, posts, and offers), each with its own PostgreSQL database, deployed in containers and locally orchestrated using Kubernetes (Minikube).

## Page

- [Shared Suitcase App](https://ubiquitous-journey-4zq6j6o.pages.github.io/)

By using this project, you will find:

* Four independent REST microservices, each exclusively responsible for its own data.
* Network isolation between each application and its database through Kubernetes Network Policies.
* Authentication based on random tokens (not JWT) for user management.
* Technical documentation as code, with architecture views modeled in PlantUML and published through GitHub Pages.
* GitHub Actions pipelines to validate deployment, network policies, API contracts, and unit test coverage.

## Table of Contents

- [Project Delivery 1 - Shared Suitcase Package Delivery Platform (P2P Broker)](#project-delivery-1---shared-suitcase-package-delivery-platform-p2p-broker)
  - [Page](#page)
  - [Table of Contents](#table-of-contents)
  - [Team](#team)
  - [Architectural Views](#architectural-views)
  - [Development and Deployment Technologies](#development-and-deployment-technologies)
    - [Postman](#postman)
    - [Git](#git)
    - [Python 3.11](#python-311)
    - [Poetry](#poetry)
    - [Pyenv](#pyenv)
    - [IDE](#ide)
    - [Docker](#docker)
    - [Minikube](#minikube)
    - [Kubectl](#kubectl)
  - [Application Execution](#application-execution)
    - [1. Install Dependencies](#1-install-dependencies)
    - [2. Run Each Application Locally](#2-run-each-application-locally)
  - [Run with Docker](#run-with-docker)
  - [Run with Minikube](#run-with-minikube)
  - [Runing plantuml-generator](#runing-plantuml-generator)
  - [Technical Documentation](#technical-documentation)
  - [Contributing](#contributing)
  - [Team Rules](#team-rules)
  - [License](#license)
  - [Authors](#authors)

## Team

- Agustín Serrano: a.serranor@uniandes.edu.co
- Pedro Trujillo:  pe.trujillo@uniandes.edu.co
- Camilo Daza:     ca.dazab1@uniandes.edu.co
- Juan Roncancio:  j.roncancioc@uniandes.edu.co


## Architectural Views

System architecture documentation can be found at:

- [Information View](./information-view.md)
- [Functional View](./functional-view.md)
- [Deployment View](./deployment-view.md)

* Requirements
  * Requirement RF-003
    * [Solution pattern](./solution-patterns.md#rf-003). 
    * [Sequence View](./rf003-sequence-view.md). 
  * Requirement RF-004
    * [Solution pattern](./solution-patterns.md#rf-004). 
    * [Sequence View](./rf004-sequence-view.md). 
  * Requirement RF-005
    * [Solution pattern](./solution-patterns.md#rf-005). 
    * [Sequence View](./rf005-sequence-view.md). 

## Development and Deployment Technologies

This section describes the main technologies and tools used for development, testing, dependency management, containerization, and local deployment.

### Postman

**Postman** is an API development and testing platform used to send HTTP requests to the application's REST endpoints.

In this project, Postman is used to:

* Test REST API endpoints.
* Validate request and response behavior.
* Execute API integration test collections.
* Verify the deployed applications running on Minikube.

### Git

**Git** is a distributed version control system used to track changes to the source code and collaborate as a development team.

In this project, Git is used for:

* Version control.
* Branch and merge management.
* Collaboration between team members.
* Tracking project history.
* Integrating changes through Pull Requests.

Before making commits, configure your Git identity:

```bash
git config --global user.name "Your Name"
git config --global user.email "your-email@example.com"
```

Verify the configuration with:

```bash
git config --global --list
```

Configuring the Git user ensures that commits and project submissions are correctly associated with the corresponding team member.

### Python 3.11

**Python 3.11** is a general-purpose programming language used to develop the applications in this project when Python is selected as the application language.

Python is used for:

* Application development.
* Implementing REST APIs.
* Writing automated tests.
* Running development and execution scripts.

Verify the installed version with:

```bash
python3 --version
```

The expected version is:

```text
Python 3.11.x
```

### Poetry

**Poetry** is a dependency management and packaging tool for Python projects. It also manages isolated virtual environments for project dependencies.

In this project, Poetry is used to:

* Install project dependencies.
* Manage dependency versions.
* Create and manage virtual environments.
* Execute Python applications and tests within the project environment.

Common commands include:

```bash
poetry install
poetry run <command>
poetry shell
```

The project's dependencies and configuration are defined in:

```text
pyproject.toml
```

### Pyenv

**Pyenv** is a Python version management tool that allows developers to install and switch between multiple Python versions on the same machine.

It is useful when different projects require different Python versions.

For example:

```bash
pyenv install 3.11.9
pyenv local 3.11.9
```

Verify the active version with:

```bash
python --version
```

Pyenv and Poetry can be used together to ensure that the project runs with the required Python version.

### IDE

The team selected the IDE that best fits its workflow. The IDE is not required for deployment, but it facilitates development, debugging, code navigation, and integration with Git.

### Docker

**Docker** is a containerization platform used to package applications together with their dependencies and runtime environment.

In this project, each application has its own Docker image.

Docker is used to:

* Build application images.
* Provide consistent execution environments.
* Isolate applications and their dependencies.
* Prepare applications for deployment to Kubernetes.

Common commands include:

```bash
docker build -t <image_name>:<image_tag> .
docker images
docker run <image_name>:<image_tag>
```

### Minikube

**Minikube** is a tool that runs a local Kubernetes cluster, allowing Kubernetes applications to be developed and tested locally.

In this project, Minikube is used to deploy and validate the complete system locally, including:

* Four applications.
* Four PostgreSQL databases.
* Kubernetes Services.
* Network Policies.
* Application-to-database communication.

Start the cluster with:

```bash
minikube start
```

Check its status with:

```bash
minikube status
```

### Kubectl

**kubectl** is the command-line client used to interact with Kubernetes clusters.

In this project, `kubectl` is used to:

* Deploy Kubernetes manifests.
* Inspect Pods and Services.
* Check Network Policies.
* View application logs.
* Debug Kubernetes workloads.

For example:

```bash
kubectl apply -f k8s/
kubectl get pods
kubectl get services
kubectl get networkpolicies
kubectl logs <pod-name>
```

`kubectl` communicates with the Kubernetes cluster running through Minikube and provides the primary command-line interface for managing the deployment.



## Application Execution

### 1. Install Dependencies

Navigate to the folder of the application you want to run (for example, `users_app`) and follow the instructions in its local `README.md` to install the dependencies.

```bash
cd users_app
poetry install
```

### 2. Run Each Application Locally

Each application runs independently. Refer to the `README.md` in each folder for the exact execution command and required environment variables, including the connection to its PostgreSQL database on port `5432`:

- [Users App](apps/users_app.md)
- [Routes App](apps/routes_app.md)
- [Posts App](apps/posts_app.md)
- [Offers App](apps/offers_app.md)


## Run with Docker

Each application has its own `Dockerfile`. Build and run each application independently:

```bash
cd <app_folder>
docker build -t <image_name>:<image_tag> .
docker run -p <port>:<port> <image_name>:<image_tag>
```

The values of `image_name` and `image_tag` must exactly match those defined in `config.yaml` and in the manifests under `k8s/`.

## Run with Minikube

```bash
minikube start --cpus=2 --memory=4g

# Build and load each image into Minikube
minikube image load <image_name>:<image_tag>

# Deploy all components
kubectl apply -f k8s/

# Check the status of pods, services, and network policies
kubectl get pods
kubectl get services
kubectl get networkpolicies
```

Minikube will assign a NodePort to each application. You can retrieve it using:

```bash
minikube service <service-name> --url
```

This URL can then be used to access the application from your browser or Postman.

## Runing plantuml-generator

run from the repo root dir:
```
cd plantuml-generator && docker build -t plantuml/plantuml:latest .
cd ../
docker run --rm -e PLANTUML_LIMIT_SIZE=8192 -v "$(pwd)/docs/diagrams:/workspace" -w /workspace plantuml/plantuml:latest "**.puml"
```

## Technical Documentation

Development documentation can be found at:

- [Development View](./development-view.md)

## Contributing

Work is managed through the team's repository [Kanban board](https://github.com/orgs/MISW-4301-Desarrollo-Apps-en-la-Nube/projects/330/views/2).

Each team member is responsible for an application, including its code, tests, `Dockerfile`, `k8s/` manifests, and associated documentation.

Changes must be integrated through small, focused Pull Requests targeting the `main` branch.

## Team Rules

The project development team rules can be found in the following link:

- [Team Rules](./TeamRules.md)

## License

This project is for academic use in the context of the Cloud Application Development course.

## Authors

Refer to the `config.yaml` file for the list of team members and their participation percentage.




