# Vespa CLI Tests and Utility Commands

Load this reference when running Vespa test suites, cloning sample applications, or using rarely-used utility commands.

## Running Tests

```bash
# Run a test suite from a JSON test file
vespa test tests/system-test.json

# Run tests against Vespa Cloud
vespa test -t cloud tests/system-test.json

# Run all test files in a directory
vespa test tests/
```

Test files are JSON documents that describe HTTP requests and expected responses. They support setup, test, and teardown steps.

## Clone a Sample Application

```bash
# Clone a Vespa sample application into a local directory
vespa clone album-recommendation my-app

# List available sample applications
vespa clone -l
```

## Version Information

```bash
vespa version
```

## Generate Man Pages

```bash
vespa man
```

This generates man pages for all CLI commands in the current directory.
