---
layout: post
title:  "Kubernetes operator day 2 development workflow"
date:   2019-09-30 08:13:10 +0300
categories: openshift kubernetes
---

There are plenty of blog posts about how to create a Kubernetes operator or
controller from scratch. However, for those of us who are fairly new to
Kubernetes, there are no guides on what do you do if you need to fix an already
existing operator, or if you want to propose a new feature. What do you do
then?

This small guide aims at explaining that.

Note that I'm assuming that you already have a cluster running.

Case
====

In this scenario, I'll attempt to change the openshift-cluster-logging-operator.
This operator is in charge of setting up a logging stack in
OpenShift. Specifically it'll set up an EFK stack in your cluster:
Elasticsearch, Fluentd & Kibana (amongst other implementation details).

Normally, operators will have controllers that deploy and manage other
workloads. In this case, the operator will manage fluentd daemonsets, kibana
deployments, and will ensure that certain configurations exist in the
elasticsearch-operator (which is in charge of managing an elasticsearch
cluster).

In this case, I want to add a configuration file to the fluentd image that the
operator deploys, and subsequently enable its usage in the operator.

Note that this specific operator is fairly specific to OpenShift, but the same
workflow will apply to other more general operators.

Set up
======

In the same fashion as with every other open source project, lets clone the
repos:

{% highlight bash %}
# The operator source code
git clone git@github.com:openshift/cluster-logging-operator.git

# The repo where the images are defined
git clone git@github.com:openshift/origin-aggregated-logging.git
{% endhighlight %}

Make sure that the operator repo is available in your gopath, as it's a Go
project and we'll need to build it.

Workload changes/fixes
======================

First, we'll start with the changes to the workloads itself. In this case, the
workload is the fluentd instances that the operator spawns.

In the origin-aggregated-logging repo, you'll the see `fluentd` directory. Here
are all the scripts to build the image and configurations that are injected
into the image. In our case, we'll add some extra configurations here.

Build the image
---------------

We'll now need to build the image, so lets do that! You'll notice there's some
dockerfiles in the `fluentd` directory. So, lets build it from there:

{% highlight bash %}
# Move to the directory
cd fluentd

# Build the image
podman build -t logging-fluentd:pipes -f Dockerfile.centos7 .
{% endhighlight %}

If all goes well, we should see the following:

{% highlight bash %}
$ podman images                                                                                                                                                  audit-log  
REPOSITORY                         TAG      IMAGE ID       CREATED          SIZE
localhost/logging-fluentd          pipes    7e292ad5b9a5   40 seconds ago   726 MB
docker.io/centos/ruby-25-centos7   latest   4de276882055   11 days ago      591 MB
{% endhighlight %}

Push the image to a remove registry
-----------------------------------

In [another previous post]({% post_url 2019-04-17-uploading-container-images-to-your-openshift-registry %})
I explained how to upload images to your OpenShift registry; so you might want
to follow that. Assuming that you followed the instructions from that post, you
should be able to push your image to the registry.

**NOTE**: Operators normally operate on a specific namespace, you want to
figure what that namespace is in order to push the image to it. This way, the
workload will be able to pull the image.

For this case, we need the `openshift-logging` namespace to exist in order for
our workload to run. So lets create it. In the case of OpenShift, you'll need
to do:

{% highlight bash %}
oc adm new-project openshift-logging
{% endhighlight %}

In other distributions (or vanilla Kubernetes), you would do:

{% highlight bash %}
$ cat logging-namespace.json
{
  "kind": "Namespace",
  "apiVersion": "v1",
  "metadata": {
    "name": "openshift-logging"
  }
}
$ kubectl create -f logging-namespace.json
{% endhighlight %}

With this in place, we can now push the image:

{% highlight bash %}
podman push --tls-verify=false localhost/logging-fluentd:pipes localhost:5000/openshift-logging/logging-fluentd:pipes
{% endhighlight %}

To recap from the aforementioned blog post, the target URL means the following:

* `localhost:5000`: Means that we're port-forwarding on the port 5000 in our
  local machine, towards the remote registry.

* `openshift-logging`: Is the namespace where the image is available

* `logging-fluentd:pipes`: Is the image and the relevant tag.

In the remote registry, the image will be available as follows:

`image-registry.openshift-image-registry.svc:5000/openshift-logging/logging-fluentd:pipes`

Operator changes/fixes
======================

Having now the workload patched and available in the cluster, we can now work
on the operator itself.

Making changes to the code-base should be fairly simple, as all operators work
with a similar pattern. **Hint**: Look for the `Reconciler` function, that
should contain all the logic of the operator.

Before testing your changes
---------------------------

Make sure that you have all the dependencies the operator needs available.

This could be namespaces, other kubernetes objects or even other operators.

In our case, we already created the `openshift-logging` namespace, since that's
where we pushed the image. We do need to install the elastricsearch operator,
since the cluster-logging-operator requires that to run. For OpenShift, this is
easily available through the OperatorHub.

You'll also need to create or update the CRDs (Custom Resource Definitions).

Operators often listen on Custom Resources, these resources will be either
objects that it'll act upon, or that will configure certain things.

In the case of the cluster-logging-operator, the CR is a representation of the
logging stack. It'll tell us how many replicas do we need for each service, how
much storage should we allocate for it amongst other things.

So lets create that!

In our case, the CRD is in `/manifests/4.2`. So, lets create the resource:

{% highlight bash %}
# For OpenShift
oc create -f manifests/4.2/cluster-loggings.crd.yaml

# For Kubernetes
kubectl create -f manifests/4.2/cluster-loggings.crd.yaml
{% endhighlight %}

If you're not sure where the CRD is, you can grep for it:

{% highlight bash %}
grep -R "kind: CustomResourceDefinition"
{% endhighlight %}

Run the operator
================

Now you have everything you need for the operator to function; However, there
are still some things to consider.

Workload image
--------------

Make sure that it's possible to overwrite the image of the workload the
operator will run on. Normally, operators have such options available; for
instance, the cluster-logging-operator enables you to use environment variables
to overwrite the default images for the different workloads it manages. In our
case, you can set the `FLUENTD_IMAGE` environment variable.

Credentials
-----------

In a usual case, the operator will itself be a pod in the cluster, and it'll
get its credentials from the ones that Kubernetes injects into the pod.
However, in this case, we'll be running the operator locally. This is usually
not a problem, as normally operator have a flag where you can pass in the
credentials; or it'll accept an environment variable as well. Usually, the
environment variable is `KUBECONFIG`.

Running the operator
--------------------

Lets now run the operator!

Normally, there will be a Makefile that'll allow you build and maybe even run
the operator. In our case, we do have the `run` target available. So lets use
it:

{% highlight bash %}
make run FLUENTD_IMAGE=image-registry.openshift-image-registry.svc:5000/openshift-logging/logging-fluentd:pipes
{% endhighlight %}

If you don't have a run target available, you can run `make`, and subsequently
run the generated binary directly.

At this point, you'll see the logs of the operator. Depending on what the
operator does, it might already start doing its job, or not. Normally it'll
just wait until you create the Custom Resource. So lets do that and look at our
operator logs.

{% highlight bash %}
# Remember we need to create the CR in the namespace the operator is watching
oc project openshift-logging

# Lets create the CR
oc create -f cr.yaml
{% endhighlight %}

If all went well, you should see the operator doing its thing! Or some error if
you made a mistake in your code (it happens!).

Conclusion
==========

Working with operators is fairly simple, but it can be a little confusing if
you're new to it. Just keep all the pieces:

* The workloads that the operator runs (and their container images)

* The dependencies of the operator (CRDs, CRs, k8s resources or other
  operators).

* Make sure your operator is configurable (overwrite the image locations).

Happy hacking!
