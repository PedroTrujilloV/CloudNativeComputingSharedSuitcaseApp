


# Software Engineering Team Rules

> **Our goal is to build reliable, scalable, secure, maintainable, and cost-effective software through discipline, automation, communication, documentation, testing, measurement, and continuous improvement.**

Successful software projects are built on **engineering discipline rather than heroism**. These rules establish the practices that our team agrees to follow throughout the entire software development lifecycle.

---

# 1. Project and Code Management

## 1.1 Everything Must Be Under Version Control

**Priority: Critical**

Every project artifact that affects the behavior, deployment, or operation of the system must be version controlled.

This includes:

* Source code.
* Infrastructure as Code (Terraform, CloudFormation, Pulumi, etc.).
* Configuration.
* Documentation.
* Database migrations.
* CI/CD pipelines.
* Relevant scripts and automation.

### Rule

> **If it affects the system, it should be reproducible from version-controlled artifacts.**

Never manually modify a production environment when the change can be automated and version controlled.

---

## 1.2 `main` Must Always Be Deployable

**Priority: Critical**

The `main` branch must remain stable and deployable.

### Rules

* Every commit should build successfully.
* Every commit should pass the required automated tests.
* Do not merge incomplete functionality unless it is safely controlled through feature flags.
* Changes must be merged through a Pull Request.
* Required CI checks must pass before merging.
* Do not commit directly to `main` except for explicitly authorized administrative or emergency changes.

### Workflow

```text
                    ┌───────────────┐
                    │ Feature Branch│
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ Pull Request  │
                    └───────┬───────┘
                            │
                    ┌───────▼───────┐
                    │ Code Review   │
                    └───────┬───────┘
                            │
                    ┌───────▼───────┐
                    │    CI/CD      │
                    └───────┬───────┘
                            │
                            ▼
                         main
```

### Emergency Rule

> **If `main` is broken, fixing `main` becomes the team's highest priority.**

Do not continue normal feature development while the main integration branch is broken.

---

# 2. Branching and Commit Strategy

## 2.1 Use a Clear and Consistent Branching Strategy

**Priority: Critical**

Use short-lived branches that represent a single logical objective.

Examples:

```text
feature/user-registration
feature/routes-api
fix/user-validation
refactor/auth-service
docs/api-documentation
test/user-service
```

### Rules

* Keep `main` stable and deployable.
* Create a dedicated branch for each feature, bug fix, task, or small unit of work.
* Keep branches short-lived.
* Avoid long-running branches that diverge significantly from `main`.
* Keep each branch focused on one logical objective.
* Regularly synchronize active branches with `main`.
* Delete branches after successful merging unless there is a reason to retain them.
* Do not commit directly to `main` except when explicitly authorized.

### Preferred Workflow

```text
main
 │
 ├── feature/user-registration
 │        │
 │        ├── commit
 │        ├── commit
 │        │
 │        └── Pull Request
 │                 │
 │                 ▼
 │              Review
 │                 │
 │                 ▼
 │                CI
 │                 │
 └─────────────────┴──────► Merge
```

A good branching strategy should **reduce integration conflicts**, not create additional complexity.

---

## 2.2 Make Commits Small, Focused, and Meaningful

**Priority: High**

Commits should make the project's history easy to understand, review, debug, and maintain.

### Promote

* One logical change per commit.
* Small, atomic commits.
* Clear commit messages explaining what changed and, when useful, why.
* Consistent commit-message conventions.
* Conventional Commits when appropriate.
* Separating formatting-only changes from functional changes whenever practical.
* Keeping commits buildable and testable whenever possible.
* Avoiding unrelated changes in the same commit.
* Avoiding unfinished or temporary code unless explicitly marked as work in progress.

Conventional Commit types commonly include:
```text
feat:       new functionality
fix:        bug fix
docs:       documentation changes
refactor:   code restructuring without behavior change
test:       adding or modifying tests
chore:      maintenance/tooling changes
ci:         CI/CD changes
build:      build system/dependency changes
```

### Example

Prefer:

```text
feat(users): add user registration endpoint
```

over:

```text
changes
```

or:

```text
fixed stuff
```

A clean commit history makes:

* Code review easier.
* Debugging easier.
* `git bisect` more useful.
* Reverting changes safer.
* Project history easier to understand.

### Commit Principle

> **One commit should represent one understandable change.**

---

# 3. Pull Requests and Code Review

## 3.1 Keep Pull Requests Small and Frequent

**Priority: Critical**

Large Pull Requests are difficult to review, increase the probability of defects, and slow down development.

This is particularly important when working in a **monorepo**, where unrelated components may coexist in the same repository.

### Prefer

* Approximately **100–400 lines** when practical.
* One feature.
* One bug fix.
* One refactoring objective.
* One logical responsibility.

### Avoid

* 5,000-line Pull Requests.
* Multiple unrelated features.
* Large mixtures of refactoring and functionality.
* Formatting the entire repository together with a functional change.

### Rule

> **If a Pull Request is difficult to review, it is probably too large.**

When a feature is large, decompose it into multiple smaller Pull Requests.

---

## 3.2 Every Pull Request Requires Code Review

**Priority: Critical**

At least one experienced developer should review every Pull Request.

Reviews should evaluate:

* Correctness.
* Readability.
* Maintainability.
* Security.
* Performance.
* Cloud cost.
* Test coverage and quality.
* Architectural consistency.
* Potential operational impact.

### Code Review Principle

> **Review the code, not the person.**

The objective of a review is to improve the software and share knowledge—not to criticize the developer.

Review comments should be:

* Specific.
* Technical.
* Constructive.
* Actionable when possible.

---

## 3.3 Keep Pull Requests Focused

**Priority: High**

A Pull Request should clearly communicate:

```text
What changed?
Why was it changed?
How was it tested?
What should the reviewer verify?
```

The PR should not contain unrelated changes simply because they were convenient to make at the same time.

If unrelated work is discovered during implementation, create a separate task or Pull Request.

---

# 4. Software Quality and Testing

## 4.1 Automated Testing Is a Priority

**Priority: Critical**

Every implemented feature should include appropriate automated tests.

At minimum, the project should use:

* Unit tests.
* Integration tests.

Where appropriate, also use:

* Contract tests.
* End-to-end tests.
* Performance tests.
* Security tests.

### Rule

> **A feature is not complete merely because the code works manually. It must be verifiable.**

Whenever practical, write a regression test when fixing a bug so that the same problem cannot silently return.

---

## 4.2 Fail Fast

**Priority: Critical**

Detect problems as early as possible in the development lifecycle.

Use automated validation such as:

```text
Developer
   │
   ▼
Lint / Formatting
   │
   ▼
Static Analysis
   │
   ▼
Unit Tests
   │
   ▼
Integration Tests
   │
   ▼
Contract Tests
   │
   ▼
Build
   │
   ▼
Deployment Validation
   │
   ▼
Production
```

Examples include:

* Input validation.
* Linting.
* Static analysis.
* Unit tests.
* Integration tests.
* Contract tests.
* Build validation.
* Deployment validation.

Finding a problem before production is significantly cheaper than discovering it after release.

---

## 4.3 Define a Clear Definition of Done

**Priority: Critical**

A task is not considered complete merely because implementation has finished.

A task is complete when the applicable criteria have been satisfied.

### Definition of Done

* [ ] Code is implemented.
* [ ] Code has been reviewed.
* [ ] Code has been merged.
* [ ] Required tests pass.
* [ ] CI checks pass.
* [ ] Documentation is updated.
* [ ] Required security checks pass.
* [ ] Required monitoring is configured.
* [ ] Deployment succeeds.
* [ ] Acceptance criteria are satisfied.

Not every item is applicable to every task, but the team must explicitly determine what applies.

### Principle

> **"Done" must have the same meaning for everyone on the team.**

---

# 5. CI/CD and Automation

## 5.1 CI/CD Is Mandatory

**Priority: Critical**

Avoid manual deployment processes whenever they can be automated.

The CI/CD pipeline should automatically perform the applicable stages:

```text
Commit
  │
  ▼
Build
  │
  ▼
Lint / Quality Checks
  │
  ▼
Automated Tests
  │
  ▼
Security Scanning
  │
  ▼
Package / Artifact
  │
  ▼
Deploy
  │
  ▼
Deployment Validation
  │
  ▼
Rollback if Necessary
```

The pipeline should provide a repeatable path from source code to deployment.

### Principle

> **If the team performs the same deployment operation repeatedly by hand, look for an opportunity to automate it.**

---

## 5.2 Infrastructure as Code

**Priority: Critical**

Infrastructure must be reproducible.

Use Infrastructure as Code when applicable, such as:

* Terraform.
* CloudFormation.
* Pulumi.
* Other appropriate IaC technologies.

Avoid manually configuring servers and infrastructure when the configuration can be represented as code.

### Principle

> **Infrastructure should be reproducible, reviewable, and version controlled.**

If a server fails, the preferred approach is:

```text
Failure
  │
  ▼
Replace / Recreate
  │
  ▼
Automated Provisioning
  │
  ▼
Known Configuration
  │
  ▼
Operational System
```

rather than manually repairing an unknown state.

---

# 6. Security

## 6.1 Never Commit Secrets to Git

**Priority: Critical**

Never commit sensitive credentials to the repository.

Never commit:

* Passwords.
* API keys.
* Certificates.
* Access tokens.
* Private keys.
* Other credentials or secrets.

Use an appropriate secure secret-management mechanism, such as:

* Secret Manager.
* Key Vault.
* AWS Parameter Store.
* Another approved secret-management system.

Secrets should also be rotated regularly according to the project's security requirements.

### Principle

> **If a credential is secret, it does not belong in Git.**

---

## 6.2 Security Is Everyone's Responsibility

**Priority: Critical**

Security must be considered throughout development rather than added at the end.

Every developer should consider:

* Least privilege.
* Encryption.
* Authentication.
* Authorization.
* Dependency vulnerabilities.
* Input validation.
* Secure defaults.
* Secure configuration.
* Protection of sensitive data.
* Appropriate logging and auditing.

### Principle

```text
Security
   │
   ├── Design
   ├── Development
   ├── Testing
   ├── CI/CD
   ├── Deployment
   └── Operations
```

Security is a continuous responsibility throughout the software lifecycle.

---

# 7. Architecture and Design

## 7.1 Design Before Implementation

**Priority: High**

Before implementing a significant feature or architectural change, define the relevant design.

Consider:

* Problem statement.
* Scope.
* Architecture.
* API contracts.
* Database changes.
* Dependencies.
* Risks.
* Rollback strategy.

### Principle

> **An hour of thoughtful design can save days of rework.**

Design does not mean creating unnecessary documentation or delaying implementation. It means understanding the problem and important consequences before making expensive decisions.

---

## 7.2 Prefer Simplicity

**Priority: High**

Choose the simplest solution that satisfies the requirements.

Avoid unnecessary:

* Microservices.
* Abstractions.
* Design patterns.
* Frameworks.
* Infrastructure.
* Dependencies.
* Premature optimizations.

Do not introduce complexity merely because a technology is popular or technically interesting.

### Principle

> **Complexity must be justified by a real requirement.**

Simple systems are generally easier to:

* Understand.
* Test.
* Deploy.
* Operate.
* Maintain.
* Debug.

---

# 8. Coding Standards

## 8.1 Establish Consistent Coding Standards

**Priority: High**

All developers should follow the same project conventions.

Standards should cover:

* Formatting.
* Naming.
* Project structure.
* Documentation.
* Logging.
* Error handling.
* Testing conventions.
* Configuration conventions.

Use automated tools whenever practical:

* Formatters.
* Linters.
* Static analyzers.
* Pre-commit hooks.
* CI quality checks.

### Principle

> **Automate style enforcement whenever possible instead of relying on reviewers to enforce formatting manually.**

---

## 8.2 Refactor Continuously

**Priority: Medium**

Leave the codebase slightly better than you found it.

Promote:

* Small refactorings during normal development.
* Removal of unnecessary complexity.
* Elimination of duplicated code.
* Improvements to readability.
* Continuous reduction of technical debt.

Avoid allowing technical debt to accumulate indefinitely.

### Principle

> **Do not wait for the codebase to become unmaintainable before improving it.**

---

## 8.3 Manage Technical Debt Explicitly

**Priority: Medium**

Maintain a visible list of technical debt.

Examples include:

* Code cleanup.
* Dependency upgrades.
* Architectural improvements.
* Performance improvements.
* Deprecated APIs.
* Temporary workarounds.

Dedicate time regularly to addressing important technical debt.

### Principle

> **Technical debt should be visible, prioritized, and managed—not forgotten.**

---

# 9. Documentation and Knowledge Management

## 9.1 Maintain a Single Source of Truth

**Priority: High**

Avoid contradictory documentation.

Document the information developers and operators need, including:

* Architecture.
* APIs.
* Deployment procedures.
* Onboarding instructions.
* Operational runbooks.
* Important engineering decisions.

Keep documentation close to the code whenever practical.

### Principle

> **There should be one authoritative place to find each important piece of project information.**

---

## 9.2 Communicate Important Decisions

**Priority: High**

Important architectural and engineering decisions should be documented so that the team understands:

* What was decided.
* Why it was decided.
* What alternatives were considered when relevant.
* What consequences the decision has.

This reduces repeated discussions and prevents knowledge from existing only in someone's memory.

---

# 10. Observability and Operations

## 10.1 Build Observable Systems

**Priority: High**

A production system must provide enough information for the team to understand its behavior.

Where applicable, services should expose:

* Logs.
* Metrics.
* Distributed traces.
* Health checks.

### Principle

> **If you cannot observe a system, you cannot operate it effectively.**

Observability should help answer:

```text
Is the system working?
        │
        ▼
What is failing?
        │
        ▼
Who or what is affected?
        │
        ▼
Why is it failing?
        │
        ▼
What changed?
```

---

## 10.2 Assign Clear Ownership

**Priority: High**

Every important component should have a clearly identified owner or responsible team.

Ownership includes responsibility for:

* Deployments.
* Bugs.
* Documentation.
* Monitoring.
* Maintenance.
* Operational issues.

Avoid situations where "everyone" is responsible but nobody is accountable.

### Principle

> **Shared responsibility is valuable; unclear accountability is not.**

---

# 11. Cloud Cost Management

## 11.1 Keep Cloud Costs Visible

**Priority: High**

Cloud resources have operational costs. Engineering decisions must balance functionality, performance, reliability, and cost.

Monitor areas such as:

* Idle resources.
* Storage growth.
* Data transfer.
* Compute utilization.
* Autoscaling efficiency.

### Principle

> **Cloud architecture is also cost architecture.**

A technically correct solution that creates unnecessary operational costs should be reconsidered.

---

# 12. Communication and Team Collaboration

## 12.1 Communicate Problems Early

**Priority: Critical**

Raise problems as soon as they become visible.

Do not wait until a deadline to report:

* Blockers.
* Risks.
* Delays.
* Uncertainty.
* Technical difficulties.
* Dependency problems.

### Principle

> **Early communication gives the team time to adapt.**

A blocker reported today can be solved.

A blocker reported on the deadline may become a project failure.

---

## 12.2 Learn From Incidents

**Priority: High**

When something fails:

1. Analyze what happened.
2. Identify contributing factors.
3. Improve the system or process.
4. Prevent recurrence where possible.
5. Document important lessons.

Focus on learning rather than assigning blame.

### Principle

> **The objective of an incident review is to improve the system, not to find someone to blame.**

---

## 12.3 Encourage Continuous Learning

**Priority: Medium**

Promote:

* Knowledge sharing.
* Pair programming.
* Design reviews.
* Architecture discussions.
* Internal demonstrations.
* Post-incident reviews.
* Technical discussions.

A team that shares knowledge is more resilient and less dependent on individual experts.

---

# 13. Measurement and Continuous Improvement

## 13.1 Measure What Matters

**Priority: Medium**

Use objective metrics to identify bottlenecks and improve software delivery.

Useful metrics may include:

* Deployment frequency.
* Lead time for changes.
* Change failure rate.
* Mean Time to Recovery (MTTR).
* Test coverage as a supporting metric.
* Service availability.
* Customer-impacting defects.

Metrics should be used to improve the system and team—not to create unhealthy competition or punish individuals.

### Principle

> **Measure the system to improve the system.**

---

# 14. Project Planning and Requirements

## 14.1 Make Requirements and Decisions Explicit

**Priority: High**

Before implementing significant functionality, ensure that the team understands:

* What problem is being solved.
* What is in scope.
* What is out of scope.
* What the acceptance criteria are.
* What dependencies exist.
* What risks exist.
* What decisions still need to be made.

If information is unknown, explicitly identify it instead of silently making assumptions.

Use clear markers such as:

```text
NEEDS MORE INFORMATION
NOT SURE
NEEDS DECISION
RECOMMENDATION
```

This prevents assumptions from becoming accidental requirements.

---

# 15. Team Language and Project Communication

## 15.1 Use English for Project Artifacts

**Priority: High**

The project itself should be written in English.

This includes:

* Code.
* GitHub issues.
* Kanban tasks.
* Pull Requests.
* Commit messages.
* Code comments.
* README files.
* Documentation.
* Technical specifications.
* Other project artifacts.

Team members may communicate in Spanish through informal communication channels such as conversations and meetings.

### Principle

> **Project artifacts should use one consistent technical language so that they remain accessible and maintainable by the entire team.**

---

## 15.2 Use Official Team Communication Channels

**Priority: High**

Use the team's official communication channels for project-related communication.

Official channels include:

* **Slack**—primary team communication.
* **Zoom**—meetings and video calls.
* **Uniandes email**—formal institutional communication.
* **GitHub**—code, Pull Requests, issues, documentation, and project collaboration.

Personal communication tools such as WhatsApp should remain primarily for personal communication rather than becoming an unofficial project-management system.

### Principle

```text
                    Project Communication
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
      Slack               GitHub              Zoom
   Team Chat          Code / PRs / Issues     Meetings
        │
        └───────────────────┬───────────────────┘
                            ▼
                     Uniandes Email
                    Formal Communication
```

Keeping project communication in official channels makes information easier to find, share, and preserve.

---

# 16. Project Success Priorities

When multiple concerns compete for attention, use the following priority order:

```text
1. Security and Critical Incidents
           ↓
2. Keep main stable
           ↓
3. Correctness and Data Integrity
           ↓
4. Blocking Issues
           ↓
5. Required Features
           ↓
6. Testing and Quality
           ↓
7. Reliability and Observability
           ↓
8. Performance and Cost Optimization
           ↓
9. Refactoring and Technical Debt
           ↓
10. Nice-to-Have Improvements
```

This does not mean that every situation follows this exact order. Critical incidents, security vulnerabilities, or data-integrity problems should always receive appropriate priority over normal feature development.

---

# 17. The Team's Engineering Philosophy

The rules above can be summarized by the following principles:

> **Automate what can be automated.**

> **Version what must be reproduced.**

> **Keep `main` stable.**

> **Keep Pull Requests small.**

> **Review code constructively.**

> **Test continuously.**

> **Fail fast.**

> **Never commit secrets.**

> **Design before making expensive decisions.**

> **Prefer simplicity.**

> **Make infrastructure reproducible.**

> **Make systems observable.**

> **Make costs visible.**

> **Communicate problems early.**

> **Learn from failures.**

> **Manage technical debt.**

> **Share knowledge.**

> **Continuously improve.**

---

# 18. Definition of Team Success

A successful team is not the team that works the most hours or depends on individual heroes.

A successful team is one that consistently delivers software that is:

* **Correct**
* **Secure**
* **Tested**
* **Observable**
* **Deployable**
* **Maintainable**
* **Reproducible**
* **Cost-conscious**
* **Well documented**
* **Continuously improved**

The ultimate objective is to build a development process where **good engineering practices are the default**, rather than something that depends on individual effort or heroism.
