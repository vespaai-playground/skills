# CI/CD Patterns for Vespa CLI

Load this reference when setting up automated deployment pipelines (GitHub Actions, GitLab CI, Jenkins, etc.), configuring headless authentication, or running Vespa in environments where browser login is not possible.

## API Key Authentication for CI

In CI environments, use an API key instead of browser-based login:

```bash
# Set the API key file path
vespa config set api-key-file /path/to/api-key.pem

# Or use environment variables for the data-plane credentials
export VESPA_CLI_DATA_PLANE_KEY_FILE=/path/to/data-plane-private-key.pem
export VESPA_CLI_DATA_PLANE_CERT_FILE=/path/to/data-plane-cert.pem
```

## GitHub Actions Example

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

## Environment Variable Configuration for CI

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

## Production Deployment in CI

For production pipelines, use `vespa prod deploy` instead of `vespa deploy`:

```bash
# Submit to the production deployment pipeline
vespa prod deploy
```

This submits the application package to the Vespa Cloud build system, which runs system and staging tests before rolling out to production zones. The command returns immediately after submission — use the Vespa Cloud console to monitor pipeline progress.
