# Install and scheduling

Python 3.10 or newer is required. The package has no third-party runtime dependency and does not silently configure a Hermes installation.

## Install

From a checkout or source archive, install the package with the normal Python packaging path:

```bash
python3 -m pip install .
```

This installs the `hermes-health-loops` command. The health command reads a caller-selected home, and the improvement command reads only explicitly supplied source files. See the README for short examples.

## Dry-run boundary

The installer accepts explicit values for selected modules, schedules, provider, model, delivery, Hermes context, runtime directory, and review acknowledgement. Those are operator-supplied review inputs; the package does not choose them. The default action renders an `install-manifest.v2` document and review-only command proposals without changing files or creating Hermes jobs.

## Apply

An apply request writes only `install-manifest.json` beneath the caller-selected external runtime directory. It still does not create or edit Hermes jobs, configuration, scheduler state, provider settings, model settings, routes, hosts, or delivery targets.

## Uninstall and rollback

Uninstall and rollback accept a caller-selected package runtime directory and validate package ownership before changing anything. Only package-owned manifests are targeted. A live Hermes home or other runtime surface is never a valid target.

## Scheduling note

Scheduling is non-operational in this package. A person may review emitted material and decide how to handle scheduling outside this repository. No schedule, transport, provider, model, route, host, or delivery value is recommended or selected here.
