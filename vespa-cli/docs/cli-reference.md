# Vespa CLI Command Reference

Complete reference for the Vespa CLI. Install with `brew install vespa-cli` or download from
<https://github.com/vespa-engine/vespa/releases>.

Global flags available on all commands: `--target <url|local|cloud>`, `--application <tenant.app.instance>`,
`--zone <env.region>`, `--color <auto|never|always>`, `--quiet`.

---

## vespa deploy

Deploy an application package to Vespa.

```
vespa deploy [application-directory] [flags]
```

| Flag | Description |
|------|-------------|
| `[application-directory]` | Path to the application package directory. Defaults to the current working directory. |
| `--wait <seconds>` | Wait up to this many seconds for the deployment to converge on all nodes. A value of 0 returns immediately after the deploy request succeeds. |
| `--timeout <duration>` | Timeout for the HTTP request itself (e.g. `60s`, `5m`). |
| `--add-cert` | Automatically generate a self-signed certificate and add it to `security/clients.pem` in the application package before deploying. Useful for first-time Vespa Cloud deployments. |
| `--run-tests` | Run basic and system tests as part of the deployment pipeline. |

On Vespa Cloud this deploys to the dev zone by default. Use `--zone` to target a different zone.

## vespa prepare / vespa activate

Session-based two-phase deployment for self-hosted Vespa clusters.

```
vespa prepare [application-directory] [flags]
vespa activate [flags]
```

`vespa prepare` uploads and validates the application package, creating a session.
`vespa activate` applies the prepared session, making it the active deployment.
This two-step flow lets you inspect validation results before activating.

Both commands accept `--wait <seconds>` and `--timeout <duration>`.

## vespa status

Check readiness of Vespa containers or deployment convergence.

```
vespa status [flags]
vespa status deploy [flags]
```

| Subcommand | Description |
|------------|-------------|
| `vespa status` | Check whether the container is ready to serve traffic. Returns exit code 0 when healthy. |
| `vespa status deploy` | Check whether the last deployment has converged on all nodes. |

| Flag | Description |
|------|-------------|
| `--wait <seconds>` | Poll repeatedly until the status is ready or the timeout expires. |
| `--cluster <name>` | Target a specific container or content cluster by name. Required when the application has multiple clusters. |

## vespa config

View and modify CLI configuration.

```
vespa config set <key> <value>
vespa config get [key]
vespa config unset <key>
```

**Configuration keys:**

| Key | Description |
|-----|-------------|
| `target` | Vespa target: `local` (localhost:8080), `cloud`, or a custom URL. |
| `application` | Application identifier in the form `tenant.application.instance`. |
| `instance` | Instance name when not embedded in the application identifier. |
| `cluster` | Default cluster name. |
| `zone` | Default zone in `environment.region` format (e.g. `dev.aws-us-east-1c`). |
| `api-key` | Inline API key value (Vespa Cloud). |
| `api-key-file` | Path to a file containing the API key (Vespa Cloud). |
| `color` | Terminal color output: `auto`, `always`, or `never`. |
| `quiet` | Suppress informational output when set to `true`. |

**Scope:** Configuration set inside a directory with a `.vespa` folder applies only to that
directory tree (local scope). Configuration set outside such a directory applies globally
and is stored in `~/.vespa/config.yaml`.

## vespa auth

Authenticate with Vespa Cloud.

```
vespa auth login
vespa auth logout
vespa auth api-key
```

| Subcommand | Description |
|------------|-------------|
| `vespa auth login` | Start an OAuth device-code flow that opens a browser for authentication. The resulting credentials are stored in `~/.vespa`. |
| `vespa auth logout` | Remove stored credentials. |
| `vespa auth api-key` | Generate a new API key for use in CI/CD pipelines. The private key is written to `~/.vespa/<tenant>.api-key.pem`. Add the public key in the Vespa Cloud console. |

## vespa cert

Manage data-plane certificates for Vespa Cloud.

```
vespa cert [flags]
vespa cert add [flags]
```

| Subcommand | Description |
|------------|-------------|
| `vespa cert` | Generate a self-signed certificate and private key pair. The private key is written to `~/.vespa/<app>.data-plane.key.pem` and the certificate to `~/.vespa/<app>.data-plane.cert.pem`. The certificate is also added to the application package at `security/clients.pem`. |
| `vespa cert add` | Add an existing certificate from `~/.vespa` to the application package's `security/clients.pem` without generating a new one. |

Both commands accept `--application` and the optional `[application-directory]` positional argument.

## vespa feed

High-performance bulk document feeding using the Vespa HTTP document/v1 API.

```
vespa feed <file> [file...] [flags]
vespa feed -             # read from stdin
```

| Flag | Description |
|------|-------------|
| `<file>` | One or more feed files. Supports `.json` (array or single operation), `.jsonl` (one operation per line), and `.gz` (gzip-compressed json/jsonl). |
| `--connections <N>` | Number of HTTP/2 connections to establish. Default: `8`. |
| `--max-streams-per-connection <N>` | Maximum concurrent streams per connection. Default: `128`. Effective parallelism is connections x streams. |
| `--timeout <duration>` | Timeout per document operation (e.g. `30s`). |
| `--route <route>` | Vespa document route (e.g. `default`, `indexing`). |
| `--trace <level>` | Trace level (1-9) to include in each document operation for debugging. |
| `--verbose` | Print the result of every individual document operation, not just the summary. |
| `--stdin` / `-` | Read the document feed from standard input. |

The feed command prints a progress summary including throughput (docs/sec, MB/sec), latency
percentiles, and error counts.

## vespa document

Single-document CRUD operations.

```
vespa document put [id] <file.json>
vespa document get <id>
vespa document remove <id>
```

| Subcommand | Description |
|------------|-------------|
| `put` | Write a document. If `id` is omitted it is read from the JSON file. The JSON must contain a `put`, `update`, or `remove` field with the document ID. |
| `get` | Retrieve a document by its full document ID (e.g. `id:ns:doctype::1`). |
| `remove` | Remove a document by its full document ID. |

| Flag | Description |
|------|-------------|
| `--timeout <duration>` | Request timeout. |
| `--cluster <name>` | Target a specific content cluster. |
| `--verbose` | Print the full HTTP response. |

## vespa query

Issue a query against the Vespa search API.

```
vespa query '<yql>' [param=value...] [flags]
```

Pass the YQL statement as the first argument and any additional query API parameters as
`key=value` pairs:

```
vespa query 'select * from music where artist contains "metallica"' hits=10 ranking=my_profile
```

| Flag | Description |
|------|-------------|
| `--timeout <duration>` | Query timeout sent to the server. |
| `--cluster <name>` | Target a specific container cluster. |
| `--format <json\|plain>` | Output format. Default: `json`. |
| `--header <key:value>` | Add a custom HTTP header. Can be repeated. |

## vespa visit

Export documents from a Vespa content cluster.

```
vespa visit [flags]
```

| Flag | Description |
|------|-------------|
| `--selection <expression>` | Document selection expression to filter which documents to visit (e.g. `music.year > 2000`). |
| `--field-set <set>` | Comma-separated list of fields to return, or a named field set such as `[document]` (all document fields) or `[id]` (document IDs only). |
| `--cluster <name>` | Content cluster to visit. Required when the application has more than one content cluster. |
| `--chunk-count <N>` | Maximum number of documents per response chunk. |
| `--slice-id <id>` | The slice this visitor handles (0-based). Use together with `--slices` for parallel visiting across multiple processes. |
| `--slices <N>` | Total number of slices for parallel visiting. |

## vespa log

View or stream Vespa log messages.

```
vespa log [flags]
```

| Flag | Description |
|------|-------------|
| `--follow` / `-f` | Stream log messages continuously as they arrive. |
| `--level <levels>` | Comma-separated list of log levels to include. Available levels: `error`, `warning`, `info`, `debug`, `spam`. Default: `error,warning,info`. |
| `--from <timestamp>` | Only show log messages from this point in time (ISO-8601 or relative like `-1h`). |
| `--to <timestamp>` | Only show log messages up to this point in time. |

## vespa curl

Execute curl commands with automatic Vespa authentication and endpoint resolution.

```
vespa curl <path> [curl-flags...] [flags]
```

The command constructs a full URL from the configured target and the given path, then invokes
`curl` with the appropriate TLS certificates (cloud) or endpoint URL (self-hosted). Any
additional flags are passed through to curl.

Examples:

```
vespa curl /ApplicationStatus
vespa curl /state/v1/health
vespa curl /metrics/v2/values
vespa curl /document/v1/namespace/doctype/docid/1
```

## vespa test

Run Vespa system and staging tests.

```
vespa test <test-file-or-directory> [flags]
```

Test files are JSON documents containing an array of `steps`. Each step specifies a `request`
(method, URI, body) and expected `response` (status code, body assertions).

| Flag | Description |
|------|-------------|
| `--zone <env.region>` | Target zone for running the tests. Defaults to the configured zone. |

Place tests in `tests/system-test/` and `tests/staging-test/` within the application package.

## vespa clone

Clone a Vespa sample application.

```
vespa clone <sample-app> [directory] [flags]
```

| Flag | Description |
|------|-------------|
| `<sample-app>` | Name of the sample application (e.g. `album-recommendation`, `text-search`). |
| `[directory]` | Target directory. Defaults to a directory named after the sample app. |
| `--list` | List all available sample applications instead of cloning. |

## vespa prod

Commands for Vespa Cloud production deployments.

```
vespa prod init [flags]
vespa prod deploy [flags]
```

| Subcommand | Description |
|------------|-------------|
| `vespa prod init` | Initialize production deployment files. Generates `deployment.xml` with default production regions and creates the `security/` directory for certificates. |
| `vespa prod deploy` | Submit the application package to the Vespa Cloud production deployment pipeline. This triggers automated staging tests followed by a progressive rollout. |

## vespa destroy

Remove a deployment from Vespa Cloud.

```
vespa destroy [flags]
```

Permanently removes the application deployment in the configured zone. This command requires
interactive confirmation and does not have a `--force` flag. All data in the deployment is
deleted.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VESPA_CLI_HOME` | Directory for CLI configuration and credentials. Default: `~/.vespa`. |
| `VESPA_CLI_CLOUD_URL` | Override the Vespa Cloud API endpoint URL. |
| `VESPA_CLI_DATA_PLANE_KEY_FILE` | Path to the data-plane private key file, overriding the default location. |
| `VESPA_CLI_DATA_PLANE_CERT_FILE` | Path to the data-plane certificate file, overriding the default location. |
| `VESPA_CLI_API_KEY_FILE` | Path to the Vespa Cloud API key file, overriding the default location. |
