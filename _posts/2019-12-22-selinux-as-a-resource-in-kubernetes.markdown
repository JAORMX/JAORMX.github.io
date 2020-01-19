---
layout: post
title:  "SELinux as a resource in Kubernetes"
date:   2019-12-22 18:45:44 +0000
categories: openshift kubernetes udica selinux
image: /images/cup.jpg
---

It's not a new thing that you can (since a while ago) configure the SELinux
labels for your containers in kubernetes. And while that has been really good,
I haven't seen it in use very often.

On the other hand, what I have seen in use is the usage of privileged
containers... All over the place.

While the promise of containers was to get some isolation and in some cases,
even extra security for your workloads. That doesn't seem to trickle down to
certain types of components. For instance, anything that has to do with
infrastructure, e.g. log forwarding components such as fluentd. Tends to run as
a privileged container, just so the pod can bind-mount the /var/log directory
to read the logs from it.

So, basically the pod would have permission to do anything with whatever is
bind-mounted into it... Which is not great for security!

selinux-policy-helper-operator
==============================

One reason why people keep using privileged pods as opposed to creating SELinux
policies for their workloads is because it's easier to do so, and SELinux has
always been viewed as hard. Let alone writing your own policies!

There is one project which aims to help folks out in this! I've talked about
this before in [another blog post]({% post_url 2019-09-20-selinux-and-kubernetes %}).
And to recap, the name of the project is [Udica][udica-gh].

I liked that project so much, that I even tried to integrate it better with
Kubernetes. A solution which I described in
[yet another blog post]({% post_url 2019-09-20-integrating-udica-into-the-kubernetes-workflow %}).

As mentioned in that blog post, for the sake of trying to automate and make it
easier for folks to start generating their policies, I started experimenting
with what I called the `selinux-policy-helper-operator`. This operator had the
small task of detecting if a pod was scheduled with a certain annotation,
detect the node where it's scheduled, and generate an appropriate policy for
it. That policy would the be pushed as a ConfigMap for the deployer to check
out and apply.

This was a nice Proof-Of-Concept, and it was really fun to code! However, this
didn't fully solve all the issues.

The issues
==========

Generating a policy is one step of the whole process. And while it's very
useful and addresses a big gap in getting people to use SELinux to better
contain their workloads. There are other gaps that still need to be filled.

How do I install my module?
---------------------------

OK! So Udica helped us out to generate a policy for our containers... How do we
install it in the cluster?

My initial approach was to simply call a pod on a specific node that would run
`semodule -i`, which basically installs the module. Since the module was
generated on a ConfigMap, it was fairly simple to just mount it on the pod and
it would get intalled.

{% highlight yaml %}
apiVersion: v1
kind: Pod
metadata:
  name: policy-installer
  namespace: selinux-policy-helper-operator
spec:
  containers:
  - name: policy-installer
    image: quay.io/jaosorior/selinux-k8s:latest
    command: ["/bin/sh"]
    args: ["-c", "semodule -vi /tmp/policy/*.cil /usr/share/udica/templates/*cil"] 
    securityContext:
      privileged: true
    volumeMounts:
    - name: fsselinux
      mountPath: /sys/fs/selinux
    - name: etcselinux
      mountPath: /etc/selinux
    - name: varlibselinux
      mountPath: /var/lib/selinux
    - name: policy-volume
      mountPath: /tmp/policy
  restartPolicy: Never
  nodeName: NODE_NAME
  volumes:
  - name: fsselinux
    hostPath:
      path: /sys/fs/selinux
      type: Directory
  - name: etcselinux
    hostPath:
      path: /etc/selinux
      type: Directory
  - name: varlibselinux
    hostPath:
      path: /var/lib/selinux
      type: Directory
  - name: policy-volume
    configMap:
      name: policy-for-errorlogger-errorlogger
  serviceAccount: selinux-policy-helper-operator
{% endhighlight %}

This was easy enough... But it's tedious and not a great developer experience.
It also has several other shortcomings.

What modules have I installed?
------------------------------

While normally you would keep track of some set of modules via packages in your
distribution (e.g. there is an rpm for the OpenStack SELinux modules), with
this approach you can easily loose track of the modules you installed... And
there is nothing accounting or keeping track of them.

Of course, you can still do `semodule -l` on each node in your cluster to list
the installed modules, and subsequently run `semodule -r` to uninstall the
module if no longer needed. But in a world where we want to automate
everything, and in a world where we want to see the cluster as one big entity,
as opposed to working on a host-level, this approach is also not ideal. It also
doesn't tie in very well with the Kubernetes way to do things.

Who can use the module?
-----------------------

Another being issue is security...

Imagine that you create a SELinux module that allows you to read and write to
*/var/log*. You can happily take it into use as follows:

{% highlight yaml %}
apiVersion: v1
kind: Pod
metadata:
  name: my-log-reading-pod
  name: log-reader-ns
spec:
  containers:
  - name: logread
    image: ...
    securityContext:
      seLinuxOptions:
        type: readvarlog.process
...
{% endhighlight %}

Imagining that our policy is named `readvarlog`, you happily install your
module in the cluster, you deploy your workload, and done! You're ready to go
and happy! Right...?

Well! Unfortunately there is no guarantee that the SELinux context will only be
used by that one worload, or that one namespace. Anybody can take it into use!
Which is not exactly what you want... So, you could just use it in another
namespace like this:

{% highlight yaml %}
apiVersion: v1
kind: Pod
metadata:
  name: evil-log-tamperer
  name: another-namespace
spec:
  containers:
  - name: logtamper
    image: ...
    securityContext:
      seLinuxOptions:
        type: readvarlog.process
...
{% endhighlight %}

So now you have a pod that has permission to tamper with the logs.

Wouldn't it be nice to be able to limit who's able to use a specific module? Or
at least limit the usage of the module to a specific namespace?

selinux-operator
================

So, with the purpose of trying to solve all the aforementioned problems, I
started coding what I called the [selinux-operator][selinux-operator-gh].

The goal was to try to integrate SELinux as much as possible to Kubernetes. And
what a better way to do that than making the policies be objects tracked
directly by Kubernetes!

SELinux modules can be represented by the `SelinuxPolicy` Custom Resource,
which would look as follows:

{% highlight yaml %}
apiVersion: selinux.openshift.io/v1alpha1
kind: SelinuxPolicy
metadata:
  name: readwrite-varlog
  namespace: default
spec:
  apply: true
  policy: |
    (blockinherit container)
    (blockinherit net_container)
    (allow process var_log_t ( dir ( open read getattr lock search ioctl add_name remove_name write ))) 
    (allow process var_log_t ( file ( getattr read write append ioctl lock map open create  ))) 
    (allow process var_log_t ( sock_file ( getattr read write append open  ))) 
{% endhighlight %}

When running the operator, if it detects that a `SelinuxPolicy` CR is created,
it'll spawn a pod per node in the cluster and install the policy in them. The
pods will stay running (though inactive), and will remove the policy from the
nodes if the CR is deleted.

Note that only policies with the flag `apply` set to `true` will be created.
This ensures that folks have a chance to audit and review their policies
before deploying them. By default (without the `apply` flag) policies and not
installed.

The CR is also namespaced, so the policy will only be visible and usable by
folks operating in the same namespace where the policy exists. Giving a little
more limitation and isolation.

You would be able to see what modules are available in your namespace, simply
by doing

{% highlight bash %}
kubectl get selinuxpolicies
{% endhighlight %}

Given that the policies are namespaced, to avoid name collisions, I did enforce
the namespace to be embedded in the resulting policy name. So, to take the
above policy into use in your workload, you would need to call it as follows:

{% highlight yaml %}
apiVersion: v1
kind: Pod
metadata:
  name: my-log-reading-pod
  name: log-reader-ns
spec:
  containers:
  - name: logread
    image: ...
    securityContext:
      seLinuxOptions:
        type: readwrite-varlog_default.process
...
{% endhighlight %}

The format being `<name of the selinux policy object>_<namespace>.process`

There is also a small validating webhook running in the operator which you can
deploy, and it'll validate that the policy that you're trying to use exists,
and that it's available and usable in the namespace that the pod belongs to.
So, it'll check the name format of the policy, and that the the namesace of the
policy itself and the namespace of the pod match.


Back to the selinux-policy-helper-operator
==========================================

Having this in mind, I decided to go back to the policy helper operator and
rewrite it to generate the `SelinuxPolicy` Custom Resource instead of
ConfigMaps. 

I also took the opportunity to rewrite the operator using operator-sdk (of
which I'm a big fan of) instead of kubebuilder, which I used originally.

And the work is there now!

The same annotations work as before, and the operator will aide you in
generating policies!

Next steps
==========

More fine-grained RBAC
----------------------

While we can already limit who's allowed to do CRUD operations on the policies
in the cluster. The operator and webhook still don't have the ability to tell who's
able to use the policy. It would be great to be able to limit the usage of
the policy to just a certain specific service account, instead of the whole
namespace.

Who installs the installer?
---------------------------

While these operators allow you to generate your own policies and use them on
your workloads... These pods are privileged containers too! I still don't like
that.

One option would be to include the policy as part of the cluster installation
(thus allowing us to run the operator using that policy). But... That would
allow any other pod to use that policy.

What if we could use this same concept to bootstrap the operator itself?

One idea would be to spawn a "bootstrap" privileged pod that installs the
policy that the operator needs, and subsequently the operator would spawn pods
using that specific policy.

Make it easily available!
-------------------------

Right now you have to download the repos and manually deploy the manifests for
the operators. The idea would be to include the operators in the marketplace in
order to make them widely available for folks! Of course if there's enough
interest :)



[udica-gh]: https://github.com/containers/udica
[selinux-operator-gh]: https://github.com/JAORMX/selinux-operator
