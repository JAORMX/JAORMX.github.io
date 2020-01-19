---
layout: post
title:  "SELinux, kubernetes & Udica"
date:   2019-09-20 09:59:39 +0300
categories: openshift selinux kubernetes k8s udica
image: /images/cup.jpg
---

So, you have your service written and everything seems to be working. You did a
lot of work to get it working in the first place, learned what was the best
deployment strategy, and your Kubernetes manifests are ready to deploy... There
is something that's off here though... Your service has a section called
"securityContext", and the flag "privileged" is marked as "true"... Oops!

You try to remove that flag. After all, you don't want workloads to run as
privileged in production. You try to deploy it but now Kubernetes shows there's
errors. You decide to check the node since you have a hunch... SELinux denials!
What do you do now?

Lets first try to understand the available options before trying to solve this.

Note
----

Some time ago, I wrote [another blog post]({% post_url 2018-02-13-selinux-and-docker-notes %})
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

The two main options that we want to note are:

* *privileged*: This is the option that we had initially set for our workload.
  This means that we were spawning a privileged container.

* *seLinuxOptions*: This is the option that allows us to give parameters to the
  CRI to set appropriate SELinux labeling for our container.

Lets dig in!

Privileged Containers
---------------------

When you spawn a privileged container, there are several things that the CRI
enables for the container. Mainly, we are concerned with two things that
happen:

* It gives the process extra capabilities (CAP_SYS_ADMIN included).
* It spawns the process with the SELinux label "spc_t"

Lets focus on the SELinux bit.

Dan Walsh has a [blog post explaining this way better than I can][spcblog].
However, I'll try to summarize it here.

When you run a privileged container, the way we make SELinux not to contain the
container is to start it with the "spc_t" type. This type is very similar to
starting a process as "unconfined_t" with a few exceptions:

* Container runtimes are allowed to transition to spc_t (and not unconfined_t).
* Confined processes can communicate with sockets created by spc_t.

Other than these differences, an spc_t process (or container) is pretty much
unconfined, and can do pretty much anything on the system; SELinux won't
contain it. This is not ideal for security and we want to avoid deploying our
services with this type as much as possible.

seLinuxOptions
--------------

Our main concern for today is the "seLinuxOptions" parameter from the
"securityContext". Lets look a little deeper into it.

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

So... That's nice! Lets just generate a policy for our container using
audit2allow, and that's it! ...Unfortunately it's not that easy... We need to
make sure that we still inherit all the things from "container_t", which means
that we still can interact with files labeled with "container_file_t", amongst
other things. If only there was a tool that could help us write such a
policy... There is!

Enter Udica
-----------

[Udica][udica-gh] is a project with the purpose of helping folks generate
SELinux policies for their containers! It's already packaged for fedora too!

It works by reading the output of podman/docker inspect, and from that, it'll
read the ports and volumes that the container is using in order to determine
what to add to the policy.

Normally you would run it as follows:

{% highlight yaml %}
$ podman inspect $CONTAINER_ID > container.json
$ udica -j container.json  my_container
Policy my_container with container id 37a3635afb8f created!

Please load these modules using:
# semodule -i my_container.cil /usr/share/udica/templates/{base_container.cil,net_container.cil,home_container.cil}

Restart the container with: "--security-opt label=type:my_container.process" parameter
{% endhighlight %}

What happened here?

Uidca generated a file called *my_container.cil* which contains the policy that
we can use for our container. This policy is in [Common Intermediate Language
(CIL)][cil-gh] which allows you to define policies and inherit from others too.

To keep the policies minimal and reusable, udica comes with ready-made
templates that you can just reuse and inherit from when writing policies. These
are stored in */usr/share/udica/templates/*.

Using it with your Kubernetes application
-----------------------------------------

With this in mind, when you're developing a containerized application, these
would be the steps you should take to generates policies:

* Run your application locally with either podman or docker.
* Generate a policy with Udica
* Inspect your policy (you want to remove unneeded things, or add extra
  capabilities if needed).
* Install your policy in your kubernetes nodes (semodule -i ...)
* Update your application's manifest to include the appropriate labeling.
* Test in a test-cluster/namespace
* ...?
* Deploy

An updated manifest would look at follows:

{% highlight yaml %}
apiVersion: v1
kind: Pod
...
spec:
  containers:
  - name: my_container
    image: ...
    securityContext:
      seLinuxOptions:
        type: my_container.process
...
{% endhighlight %}

And that's it! Your container will use the type you defined and there won't be
the need for that scary "spc_t".

Further work
------------

The SELinux/Udica team has made an awesome job of the tool and it is quite
functional already. However, if you want a more automated flow (Automate
everything!), e.g. to use Udica directly on your Kubernetes deployment as part
of your CI. The current state of things makes it hard for such a use-case. This
is something I'll talk about in another
[blog post]({% post_url 2019-09-20-integrating-udica-into-the-kubernetes-workflow %}),
as well as a potential
solution for this.

[podsecuritycontext]: https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.16/#podsecuritycontext-v1-core
[securitycontext]: https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.16/#securitycontext-v1-core
[k8ssecuritycontextdocs]: https://kubernetes.io/docs/tasks/configure-pod-container/security-context/
[spcblog]: https://danwalsh.livejournal.com/74754.html
[udica-gh]: https://github.com/containers/udica
[cil-gh]: https://github.com/SELinuxProject/cil
