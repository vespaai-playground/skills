# Production Deployments (Vespa Cloud)

Load this reference when promoting a Vespa Cloud application to production zones (as opposed to dev/perf deployments).

Production deployments in Vespa Cloud go through an automated pipeline rather than direct `vespa deploy`.

## Initialize Production Config

```bash
# Generate deployment.xml and production security setup
vespa prod init
```

This creates a `deployment.xml` with production zone declarations and prepares the required certificate configuration.

## Submit to Production Pipeline

```bash
# Submit the application package for production deployment
vespa prod deploy
```

## Deployment Pipeline Stages

1. **Build**: the application package is validated and compiled.
2. **System test**: automated tests run against an ephemeral test deployment.
3. **Staging test**: the upgrade path from the currently deployed version is tested.
4. **Production**: the application is rolled out to the declared production zones.

Each stage must pass before proceeding to the next. Failures block the pipeline and require investigation.
