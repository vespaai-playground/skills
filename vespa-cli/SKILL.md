---
name: "vespa-cli"
description: "Vespa CLI for deploying, managing, and debugging Vespa.ai applications -- covers target configuration, authentication, deployment lifecycle, production pipelines, document operations, log inspection, testing, and CI/CD integration."
---

# Vespa CLI

## Overview

The Vespa CLI (`vespa`) is the official command-line tool for interacting with Vespa instances -- both self-hosted deployments and Vespa Cloud. It provides commands for deploying application packages, feeding documents, running queries, inspecting logs, running tests, and managing authentication.

### Installation

On macOS via Homebrew:

```bash
brew install vespa-cli
```

On Linux or other platforms, download the binary from the GitHub releases page:

```bash
# Example for Linux amd64
curl -fsSL https://github.com/vespa-engine/vespa/releases/latest/download/vespa-cli_linux_amd64.tar.gz | tar xz
sudo mv vespa /usr/local/bin/
```

Verify the installation:

```bash
vespa version
```

### Core Concepts

- **Target**: the Vespa endpoint the CLI talks to (local, cloud, or a custom URL).
- **Application**: a specific Vespa application identified as `tenant.application.instance`.
- **Cluster**: a named container or content cluster within an application. Required when an application has multiple clusters.

## Configuration & Targets

The CLI stores configuration in a `.vespa` directory. There is a global config at `~/.vespa` and an optional local config in the current working directory (`.vespa`).

### Setting the Target

```bash
# Target a local Vespa instance (default: http://localhost:8080)
vespa config set target local

# Target Vespa Cloud
vespa config set target cloud

# Target a custom endpoint URL
vespa config set target https://my-vespa-host:8080
```

### Setting the Application

```bash
# Format: tenant.application.instance
vespa config set application mytenant.myapp.default
```

### Viewing Current Configuration

```bash
vespa config get
```

This prints all effective configuration values including their source (flag, environment, local config, or global config).

### Config Hierarchy

Configuration values are resolved in the following order (highest priority first):

1. **Command-line flags** (`--target`, `--application`, etc.)
2. **Environment variables** (`VESPA_CLI_HOME`, etc.)
3. **Local `.vespa` config** in the current working directory
4. **Global `~/.vespa` config** in the user home directory

### Environment Variables

| Variable | Description |
|---|---|
| `VESPA_CLI_HOME` | Override the default config directory (`~/.vespa`). |
| `VESPA_CLI_CLOUD_URL` | Override the Vespa Cloud API URL. |
| `VESPA_CLI_DATA_PLANE_KEY_FILE` | Path to the private key file for mTLS data-plane authentication. |
| `VESPA_CLI_DATA_PLANE_CERT_FILE` | Path to the certificate file for mTLS data-plane authentication. |

## Authentication (Vespa Cloud)

Vespa Cloud requires authentication at two layers: the **control plane** (API calls for deployment, configuration) and the **data plane** (queries, feeding).

### Control Plane: Browser-Based Login

```bash
# Log in via browser-based OAuth flow
vespa auth login

# Log out and clear stored credentials
vespa auth logout
```

After logging in, the CLI stores a token that authenticates subsequent control-plane operations (deploy, status checks, log retrieval).

### Data Plane: mTLS Certificates

Vespa Cloud uses mutual TLS for data-plane access (queries, feeding). You need a certificate and private key.

```bash
# Generate a self-signed key pair and add the certificate to the application package
vespa cert

# Add an existing certificate to the application package (does not generate a new key)
vespa cert add path/to/cert.pem
```

The `vespa cert` command creates the key pair and places the certificate in `security/clients.pem` inside the application package. The private key is stored in `~/.vespa/` by default.

### API Key Authentication (CI/CD)

For headless environments where browser login is not possible, use an API key:

```bash
# Point the CLI to an API key file for control-plane auth
vespa config set api-key-file /path/to/api-key.pem
```

API keys are created in the Vespa Cloud console under your tenant settings.

## Deployment Lifecycle

### Deploy

```bash
# Deploy the application package in the current directory
vespa deploy

# Deploy from a specific path
vespa deploy myapp/

# Deploy and wait up to 300 seconds for convergence
vespa deploy --wait 300
```

The `vespa deploy` command uploads the application package, validates it, and activates it on the target. For Vespa Cloud dev/perf zones, this is a single-step operation.

### Prepare and Activate (Self-Hosted)

On self-hosted Vespa, you can split deployment into two stages:

```bash
# Prepare: upload and validate the package without activating
vespa prepare

# Activate: activate the most recently prepared session
vespa activate
```

This two-step workflow is useful when you want to validate configuration before making it live.

### Check Status

```bash
# Check if container and content nodes are up and ready
vespa status

# Check deployment convergence (are all nodes running the latest config?)
vespa status deploy
```

### Tear Down (Vespa Cloud)

```bash
# Destroy the dev deployment (requires interactive confirmation)
vespa destroy
```

This removes the application from the Vespa Cloud dev zone. It does not affect production deployments.

## Production Deployments (Vespa Cloud)

Production deployments in Vespa Cloud go through an automated pipeline rather than direct `vespa deploy`.

### Initialize Production Config

```bash
# Generate deployment.xml and production security setup
vespa prod init
```

This creates a `deployment.xml` with production zone declarations and prepares the required certificate configuration.

### Submit to Production Pipeline

```bash
# Submit the application package for production deployment
vespa prod deploy
```

### Deployment Pipeline

The production pipeline runs through these stages:

1. **Build**: the application package is validated and compiled.
2. **System test**: automated tests run against an ephemeral test deployment.
3. **Staging test**: the upgrade path from the currently deployed version is tested.
4. **Production**: the application is rolled out to the declared production zones.

Each stage must pass before proceeding to the next. Failures block the pipeline and require investigation.

## Document Operations

The CLI provides commands for individual document CRUD and bulk feeding. For detailed JSON wire format, partial update syntax, and advanced feeding patterns, load the `feed-operations` skill.

### Single-Document Operations

```bash
# Put a document from a JSON file
vespa document put doc.json

# Put with an explicit document ID
vespa document put id:mynamespace:music::doc-1 doc.json

# Get a document by ID
vespa document get id:mynamespace:music::doc-1

# Remove a document by ID
vespa document remove id:mynamespace:music::doc-1
```

### Bulk Feeding

```bash
# Feed a JSONL file (one operation per line)
vespa feed docs.jsonl

# Feed from stdin
cat docs.jsonl | vespa feed -

# Feed with tuned concurrency
vespa feed --connections 4 --max-streams-per-connection 128 docs.jsonl
```

### Querying

```bash
# Run a YQL query
vespa query 'select * from music where artist contains "Radiohead"'

# Pass additional parameters
vespa query 'select * from music where true' hits=5 ranking=my_profile
```

### Visiting / Exporting Documents

```bash
# Visit all documents
vespa visit

# Visit with a selection expression
vespa visit --selection "music.year > 2000"

# Limit the number of visited documents
vespa visit --count 100
```

## Debugging & Troubleshooting

### Log Inspection

```bash
# Show recent logs from the Vespa instance
vespa log

# Follow logs in real time (like tail -f)
vespa log --follow

# Filter by log level
vespa log --level warning,error

# Show only logs from the last 2 hours
vespa log --from 2h
```

On Vespa Cloud, `vespa log` retrieves logs from the cloud logging infrastructure. On self-hosted, it reads from the config server log endpoint.

### Authenticated HTTP Requests

`vespa curl` sends HTTP requests to the Vespa endpoint with the correct authentication headers and certificates already configured:

```bash
# Check application status
vespa curl /ApplicationStatus

# Fetch metrics
vespa curl /metrics/v2/values

# Custom container endpoint
vespa curl /search/?yql=select+*+from+music+where+true

# Target a specific API path on the config server
vespa curl --service config /application/v2/tenant/
```

This is particularly useful for Vespa Cloud, where requests require mTLS certificates that `vespa curl` attaches automatically.

### Query Tracing

Add `tracelevel` to a query to get detailed execution traces:

```bash
# Trace at level 3 (shows query rewriting, dispatch, and backend timing)
vespa query 'select * from music where title contains "computer"' tracelevel=3

# Higher levels produce more detail (up to 9)
vespa query 'select * from music where true' tracelevel=5
```

Trace output is included in the JSON response under the `trace` object. It reveals query parsing, ranking, matching, and network timing information.

### Running Tests

```bash
# Run a test suite from a JSON test file
vespa test tests/system-test.json

# Run tests against Vespa Cloud
vespa test -t cloud tests/system-test.json

# Run all test files in a directory
vespa test tests/
```

Test files are JSON documents that describe HTTP requests and expected responses. They support setup, test, and teardown steps.

## Utility Commands

### Clone a Sample Application

```bash
# Clone a Vespa sample application into a local directory
vespa clone album-recommendation my-app

# List available sample applications
vespa clone -l
```

### Version Information

```bash
vespa version
```

### Generate Man Pages

```bash
vespa man
```

This generates man pages for all CLI commands in the current directory.

## Global Flags

These flags are available on all commands and override configuration values:

| Flag | Description |
|---|---|
| `--target` | Override the target (e.g., `local`, `cloud`, or a URL). |
| `--application` | Override the application (`tenant.app.instance`). |
| `--cluster` | Specify the cluster to use when multiple clusters exist. |
| `--zone` | Specify the Vespa Cloud zone (e.g., `dev.aws-us-east-1c`). |
| `--color` | Control colored output (`auto`, `always`, `never`). |
| `--quiet` | Suppress non-essential output. |

## Common Errors & Fixes

| Error Message | Cause | Fix |
|---|---|---|
| `Deployment not converged` | Nodes have not finished applying the new configuration. | Wait longer or run `vespa status deploy` to monitor progress. Use `--wait` to increase the timeout. |
| `Unauthorized` | Missing or invalid control-plane credentials. | Run `vespa auth login` to re-authenticate, or verify your API key file path. |
| `Connection refused` | The CLI cannot reach the Vespa endpoint. | Verify the target with `vespa config get target`. Confirm Vespa is running and the port is correct. |
| `Certificate error` / `TLS handshake failure` | Data-plane mTLS certificate mismatch or missing key. | Re-run `vespa cert` to generate a fresh certificate. Check that `VESPA_CLI_DATA_PLANE_KEY_FILE` and `VESPA_CLI_DATA_PLANE_CERT_FILE` point to the correct files. Redeploy after updating the certificate. |
| `Application not found` | The configured `tenant.app.instance` does not exist. | Run `vespa config get application` and verify the value. Check the Vespa Cloud console for the correct tenant, application, and instance names. |
| `Cluster not found` | The CLI cannot determine which cluster to target. | Specify the cluster explicitly with `--cluster <name>`. Run `vespa status` to list available clusters. |
| `Invalid application package` | The application package has schema or configuration errors. | Read the error details in the CLI output. Fix the reported issues in `services.xml`, schemas, or `deployment.xml` and redeploy. |

## CI/CD Patterns

### API Key Authentication for CI

In CI environments, use an API key instead of browser-based login:

```bash
# Set the API key file path
vespa config set api-key-file /path/to/api-key.pem

# Or use environment variables for the data-plane credentials
export VESPA_CLI_DATA_PLANE_KEY_FILE=/path/to/data-plane-private-key.pem
export VESPA_CLI_DATA_PLANE_CERT_FILE=/path/to/data-plane-cert.pem
```

### GitHub Actions Example

```yaml
name: Deploy to Vespa Cloud

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Vespa CLI
        run: |
          curl -fsSL https://github.com/vespa-engine/vespa/releases/latest/download/vespa-cli_linux_amd64.tar.gz | tar xz
          sudo mv vespa /usr/local/bin/

      - name: Configure Vespa CLI
        run: |
          vespa config set target cloud
          vespa config set application mytenant.myapp.default

      - name: Write API key
        run: echo "${{ secrets.VESPA_API_KEY }}" > /tmp/api-key.pem

      - name: Set API key
        run: vespa config set api-key-file /tmp/api-key.pem

      - name: Deploy
        run: vespa deploy --wait 600

      - name: Run system tests
        run: vespa test tests/system-test.json

      - name: Clean up
        if: always()
        run: rm -f /tmp/api-key.pem
```

### Environment Variable Configuration for CI

For CI systems where file-based configuration is inconvenient, use environment variables:

```bash
export VESPA_CLI_HOME=/tmp/vespa-cli-config
export VESPA_CLI_DATA_PLANE_KEY_FILE=/tmp/data-plane-key.pem
export VESPA_CLI_DATA_PLANE_CERT_FILE=/tmp/data-plane-cert.pem

vespa config set target cloud
vespa config set application mytenant.myapp.default
vespa config set api-key-file /tmp/api-key.pem

vespa deploy --wait 600
```

### Production Deployment in CI

For production pipelines, use `vespa prod deploy` instead of `vespa deploy`:

```bash
# Submit to the production deployment pipeline
vespa prod deploy
```

This submits the application package to the Vespa Cloud build system, which runs system and staging tests before rolling out to production zones. The command returns immediately after submission -- use the Vespa Cloud console to monitor pipeline progress.

## Further Reading

For the complete list of every CLI command, subcommand, and flag, load:
- `docs/cli-reference.md` -- full command reference with all options and examples.
