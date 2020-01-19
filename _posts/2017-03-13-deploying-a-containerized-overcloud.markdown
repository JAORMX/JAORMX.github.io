---
layout: post
title:  "Deploying a containerized overcloud"
date:   2017-03-13 17:55:32 +0200
categories: tripleo openstack
image: /images/cup.jpg
---

Deploying a containerized overcloud is a matter of adding the
_environments/docker.yaml_ environment to the overcloud deployment.

Now, for developing, one is likely to want to use local images instead of the
ones from dockerhub. So we'll set heat parameters in an environment file. This,
fortunately, is already done for us by quickstart. So we'll see the file
`containers-default-parameters.yaml` with something like the following:

{% highlight yaml %}

parameter_defaults:
  DockerNamespace: 192.168.24.1:8787/tripleoupstream
  DockerNamespaceIsRegistry: true

{% endhighlight %}

Of course, the IP address depends on your undercloud deployment.

Now, this requires one to upload the images to the local registry. So, if we
created our deployment using a recent version of tripleo-quickstart, there is
already a utility script that we can use for this purpose:
`upload_images_to_local_registry.py`

Note that to run the aforementioned script, one needs to either do it with root
privileges (via sudo) or add a docker group and subsequently a user to it; for
instance, the stack user. So choose depending on your security requirements.

## TLDR;

Do your regular openstack deploy but add the following environments:

* tripleo-heat-templates/environments/docker.yaml
* $HOME/containers-default-parameters.yaml

## Note

Currently (now that I'm writing this post) HA deployments are not available. So
don't try to use the pacemaker environment cause that will fail.
