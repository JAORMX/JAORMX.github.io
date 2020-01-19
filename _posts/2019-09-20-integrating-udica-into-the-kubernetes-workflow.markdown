---
layout: post
title:  "Integrating Udica into the Kubernetes workflow"
date:   2019-09-20 14:34:47 +0300
categories: openshift udica kubernetes k8s selinux
image: /images/cup.jpg
---

In a [previous blog post]({% post_url 2019-09-20-selinux-and-kubernetes %}) I
explained about how to set up the SELinux labels for your workloads in
Kubernetes and how Udica could be used to generate SELinux policies for your
containers. In the end, I hinted at a way to integrate udica into your regular
kubernetes development workflow. Here I present work that I did recently on
this area.

Why?
====

As a developer creating SELinux policies in "cloud-native" workloads should be
as simple as possible. One should just annotate their pod manifest and get an
appropriate policy for it. The least manual steps that developers should do the
better. This is not to say that folks shouldn't know how to generate policies
themselves, or that they shouldn't know SELinux. They should, and hopefully
teams will have someone with security knowledge. However, if we can make the
barrier of entry and the development process smoother, this is a win on the
security side.

As a deployer I'd like to restrict the usage of privileged containers to be as
minimal as possible. So, the hope is that with an easier workflow, folks
will generate policies for their workloads instead of deploying them as
privileged.

What?
=====

I've created a POC that's automates the creation of policies for your
workloads. Here's the link:

[https://github.com/JAORMX/selinux-policy-helper-operator](https://github.com/JAORMX/selinux-policy-helper-operator)

selinux-policy-helper-operator listens to pods in the kubernetes cluster. If
the pod is annotated with the "generate-selinux-policy" label, it'll
generate a config for it and upload it to a config map.

So, your pod will need to have an annotation as the following:

{% highlight yaml %}
apiVersion: v1
kind: Pod
metadata:
  name: errorlogger
  annotations:
    generate-selinux-policy: ""
...
{% endhighlight %}

And here's the operator in action:

{% include selinux-policy-helper-operator-demo.html %}

This operator uses udica to genenerate the aforementioned policy. Currently,
the udica from the pod has a set of additions:

* A patch that adds support for CRI-O:
  [https://github.com/containers/udica/pull/40](https://github.com/containers/udica/pull/40)

* A patch that improves the log_container template from udica:
  [https://github.com/containers/udica/pull/44](https://github.com/containers/udica/pull/44)
  (Big thanks to Lukas Vrabec for the help on this one!)

The pod that's launched by the operator runs a script that calls the CRI to get
the information from the requested pod and pass that down to udica, finally,
this pod creates a configmap with the policy. That code is here:

[https://github.com/JAORMX/selinux-k8s](https://github.com/JAORMX/selinux-k8s)

This removes the need of having to run manual commands and makes it simpler for
udica to be part of the developer's CI workflow.

Not that this doesn't remove the need to review your policy for several
reasons:

* Your application might have extra needs or capabilities that need to be
  manually added to the policy

* You really want to review your policies because of **security reasons**.
  *Always* audit the permissions you give to your workloads.

Conclusion
----------

This covers the work of automating and making it easier to generate policies
for your workloads. There are still several features to add. PRs are welcome!

Further work
------------

We still need better and friendlier ways to manager policies in our clusters,
make sure we can install/uninstall these policies, and optionally restrict who
can use which policy. Work on this is coming.
