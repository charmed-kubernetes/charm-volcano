# Contributing

To make contributions to this charm, you'll need a working [development setup](https://juju.is/docs/sdk/dev-setup).

You can use the environments created by `tox` for development:

```shell
tox --notest -e unit
source .tox/unit/bin/activate
```

## Testing

This project uses `tox` for managing test environments. There are some pre-configured environments
that can be used for linting and formatting code when you're preparing contributions to the charm:

```shell
tox -e format        # update your code according to linting rules
tox -e lint          # code style
tox -e unit          # unit tests
tox -e integration   # integration tests
tox                  # runs 'lint' and 'unit' environments
```

## Build the charm

Build the charm in this git repository using:

```shell
charmcraft pack -p charms/volcano-admission
charmcraft pack -p charms/volcano-controllers
charmcraft pack -p charms/volcano-scheduler
```

## Build the bundle

The bundle is created via the `.bundle_template` and the `bundle` executable within this repo.  

```shell
./bundle -n volcano -o /tmp/path -c 1.27/stable
charmcraft pack -p /tmp/path
```

The built bundle will be a zip file at `/tmp/path/volcano.zip`