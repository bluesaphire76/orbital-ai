# OrbitalAI MVP Distribution Requirements

## Installation

OrbitalAI must be installable by third parties without cloning the
source repository or manually installing application dependencies.

The supported installation mechanism must use versioned release
packages and pre-built container images.

## Containerisation

All runtime application components must run in containers.

Users must not be required to install Python, Node.js, PostgreSQL,
Prometheus, Grafana, or application dependencies manually.

## Distribution

Application images will be published as versioned OCI images.

Release artifacts will contain the deployment configuration,
installer, upgrade tooling, checksums, and documentation.

## Configuration

Environment-specific values such as domain names, credentials,
Cloudflare configuration, database passwords, and signing keys
must never be hardcoded.

Secrets must never be stored in the public repository.

## Security

Production GUI access must use HTTPS.

Public deployments must support Cloudflare Tunnel and Cloudflare
Access without requiring inbound Internet ports on the host.

Internal service communication must be isolated using Docker
networks and encrypted where appropriate.

## Operations

The distribution must provide supported mechanisms for:

- install
- start
- stop
- status
- update
- backup
- restore
- diagnostics
- uninstall

## Observability

Prometheus, Grafana, Loki and Alertmanager are part of the platform
distribution and must not require separate manual installation.

## Upgradeability

Database migrations and configuration migrations must be automated.

Versioned installations must support controlled upgrade and rollback.
