---
layout: post
title:  "Uploading container images to your openshift registry"
date:   2019-04-17 13:47:14 +0300
categories: openshift
image: /images/cup.jpg
---

I recently started exploring OpenShift, and while I did find the concept of
builds and imagestreams to be quite useful. I didn't find a straight forward
way to upload a docker image from my machine towards the cluster's image
registry.

So, for reference, I gathered this script from the CI scripts of the [openshift
logging project][openshift-logging].

{% highlight bash %}
#!/bin/bash

# Define constants
registry_namespace=openshift-image-registry
registry_svc=image-registry
LOCAL_PORT=5000

# Get port where the remote registry is on
registry_port=$(oc get svc $registry_svc -n $registry_namespace -o jsonpath='{.spec.ports[0].port}')

# Get object that we'll port forward to
port_fwd_obj=$(oc get pods -n $registry_namespace | awk '/^image-registry-/ {print $1}' )

# Do port forwarding on the needed pod
oc --loglevel=9 port-forward "$port_fwd_obj" -n "$registry_namespace" "$LOCAL_PORT:$registry_port" > pf.log 2>&1 &

port_foward_proc=$!
echo "The process spawned is $port_foward_proc"

# Get token for kubeadmin user
oc login -u kubeadmin -p "$(cat ~/openshift-dev-cluster/auth/kubeadmin-password)"

# Use token to log in with docker
docker login -u "kubeadmin" -p "$(oc whoami -t)" localhost:5000
{% endhighlight %}

This allows you to use localhost:5000 as an endpoint to upload your images
towards your clusters image registry. Note that you'll need to specify the
specific openshift "project" as part of the path when you're uploading images.

Lets say, for instance, that you want to upload the image ``my-image``, and you
have access to the project ``default``. You'll do:

{% highlight bash %}
docker push localhost:5000/default/my-image:latest
{% endhighlight %}

Note when you want to use your new image in an application, you must replace
``localhost:5000`` with ``image-registry.openshift-image-registry.svc:5000``,
since that's the URL that OpenShift makes available.

So, you'll have something as:

{% highlight yaml %}
...
    spec:
      containers:
        ...
        image: image-registry.openshift-image-registry.svc:5000/default/my-image:latest
        imagePullPolicy: Always
{% endhighlight %}

Note that I also tried to create a route towards the openshift-image-registry
service. However, that didn't work for me, as the registry wasn't getting my
requests.

Special thanks to Rich Megginson for guiding my through the CI scripts.

[openshift-logging]: https://github.com/openshift/origin-aggregated-logging
