---
layout: post
title:  "SELinux, kubernetes & Udica"
date:   2019-09-20 09:59:39 +0300
categories: openshift selinux kubernetes k8s
---

So, you have your service written and everything seems to be working. You did a
lot of work to get it working in the first place, learned what was the best
deployment strategy, and your Kubernetes manifests are ready to deploy... There
is something that's off here though... Your service has a section called
"securityContext", and the flag "privileged" is marked as "true"... Oops!

You try to remove that flag. After all, you don't want workloads to run as
privileged in production. You try to depoy it but now Kubernetes shows there's
errors. You decide to check the node since you have a hunch... SELinux denials!
What do you do now?

Lets first try to understand the available options before trying to solve this.

Note
----

Some time ago, I wrote [another blog post]({% 2018-02-13-selinux-and-docker-notes %})
about how SELinux applies to containers. Even if in this case, I'm using
OpenShift with CRI-O instead of docker, the same concepts still apply.

securityContext
---------------

Kubernetes has a construct that you can add to your pods and containers called
"securityContext", as mentioned above.

These options are general security options that will either lock down or free
up your containers and pods. The "securityContext" can be set up in two levels:
The pod level and the container level.

Lets look at an example:

{% highlight yaml %}
apiVersion: v1
kind: Pod
metadata:
  name: security-context-demo-2
spec:
  securityContext:
    runAsUser: 1000
  containers:
  - name: sec-ctx-demo-2-a
    image: gcr.io/google-samples/node-hello:1.0
    securityContext:
      runAsUser: 2000
      allowPrivilegeEscalation: false
  - name: sec-ctx-demo-2-b
    image: gcr.io/google-samples/node-hello:1.0
{% endhighlight %}

As you might guess, the container "sec-ctx-demo-2-a" will use the options that
were defined in the "securityContext" in its own scope. While
"sec-ctx-demo-2-b" will use the one coming from the pod itself. It is important
to know that each group can take a different set of options, and have different
definitions in the Kubernetes API spec. One of them being
[PodSecurityContext][podsecuritycontext] and the other one being simply named
[SecurityContext][securitycontext].

Here are the different options available:

**PodSecurityContext**:

* fsGroup
* runAsGroup
* runAsNonRoot
* runAsUser
* seLinuxOptions
* supplementalGroups
* sysctls
* windowsOptions

**SecurityContext**:

* allowPrivilegeEscalation
* capabilities
* privileged
* procMount
* readOnlyRootFilesystem
* runAsGroup
* runAsNonRoot
* runAsUser
* seLinuxOptions
* windowsOptions

Most of these options are self-explanatory. If you want to read more about
this, the [Kubernetes documentation is a good guide][k8ssecuritycontextdocs].

seLinuxOptions
--------------

Our main concern for today is the "seLinuxOptions" parameter from the
"securityOptions". Lets look a little deeper into it.

Here are all the options you can set from it:

* level
* role
* type
* user

If you're acquainted with SELinux, these options will look familiar to you. And
they do map directly to the labels for the process.

As a quick recap, lets say your container is running with the following label:

{% highlight bash %}
system_u:system_r:container_t:s0:c829,c861
{% endhighlight %}

The observed "seLinuxOptions" would be as follows:

{% highlight yaml %}
seLinuxOptions:
  user: system_u
  role: system_r
  type: container_t
  level: s0:c829,c861
{% endhighlight %}

[podsecuritycontext]: https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.16/#podsecuritycontext-v1-core
[securitycontext]: https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.16/#securitycontext-v1-core
[k8ssecuritycontextdocs]: https://kubernetes.io/docs/tasks/configure-pod-container/security-context/
