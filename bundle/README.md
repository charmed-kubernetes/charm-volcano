# charms for Volcano

## Description

Volcano is a batch system built on Kubernetes. 

It provides a suite of mechanisms that are commonly required by many 
classes of batch & elastic workload including: machine learning/deep learning,
bioinformatics/genomics and other "big data" applications. 
These types of applications typically run on generalized domain frameworks 
like TensorFlow, Spark, Ray, PyTorch, MPI, etc, which Volcano integrates with.

More information: 
* https://charmhub.io/volcano
* https://charmhub.io/volcano-admission
* https://charmhub.io/volcano-controllers
* https://charmhub.io/volcano-scheduler

## Deployment

### Quickstart
The suite of Volcano charms can be deployed within any kubernetes cluster so long as one has a valid admin token in a kubeconfig.

If deploying to an existing machine based juju controller, you'll first need to add a kubernetes-cloud with [`add-k8s`](https://juju.is/docs/olm/juju-add-k8s)

```bash
KUBECONFIG=path/to/my/kubeconfig juju add-k8s k8s-cloud
```

Next, create a kubernetes namespace for volcano with a juju model

```bash
juju add-model volcano-system
```

Then deploy the bundle from charmhub
```bash
juju deploy volcano --trust
```

## Other resources

- [Read more](https://volcano.sh)

- [Contributing](CONTRIBUTING.md) <!-- or link to other contribution documentation -->

- See the [Juju SDK documentation](https://juju.is/docs/sdk) for more information about developing and improving charms.
