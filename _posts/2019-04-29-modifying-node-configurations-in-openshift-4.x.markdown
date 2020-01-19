---
layout: post
title:  "Modifying node configurations in OpenShift 4.X"
date:   2019-04-29 12:56:52 +0300
categories: openshift
image: /images/cup.jpg
---

OpenShift 4.X relies heavily on operators in order to configure... just about
everything. This includes the configuration of the hosts that run the OpenShift
installation. In order to configure the aforementioned hosts, the installation
comes with a running instance of the "machine-config-operator", which is an
operator that applies host configurations and restarts the host whenever it
detects configuration changes.

So, to learn how to use this, lets change **/etc/chrony.conf** and set up some
specific servers.

First of all, lets look at the configuration we want to apply to chrony.conf:

{% highlight bash %}
server 0.fedora.pool.ntp.org
server 1.fedora.pool.ntp.org
server 2.fedora.pool.ntp.org
driftfile /var/lib/chrony/drift
makestep 1.0 3
rtcsync
keyfile /etc/chrony.keys
leapsectz right/UTC
logdir /var/log/chrony
{% endhighlight %}

This configuration is based on what's shipped by default in OpenShift, except
that we made the deployment get its time from the three specific fedora nodes
in ntp.org.

Prerequisites
=============

The machine-config-operator gives us a construct named ``MachineConfig``, which
allows us to apply configuration changes to specific files and to specific
roles.

What are these roles?

Well, the machine-config-operator works with so called ``MachineConfigPools``
which are sets of nodes that have a specific role in your system. Most likely
these nodes will run different services, and serve different purposes.

To view all of the roles in your system, do:


{% highlight bash %}
oc get machineconfigpools
{% endhighlight %}

In my basic deployment, I see the following:

{% highlight bash %}
NAME     CONFIG                                             UPDATED   UPDATING   DEGRADED
master   rendered-master-f0718d88f154089eae3b199e387696d4   True      False      False
worker   rendered-worker-3c907e9ae475284d33eadfa3bc6117a5   True      False      False
{% endhighlight %}

The main thing to note here are the names of  the roles, which we'll use in our
configuration.

Another thing to note is that currently, the configurations need URL encoding
in our ``MachineConfig`` definition.

For this, we can use the following snippet:

{% highlight bash %}
cat example-chrony.conf | python3 -c "import sys, urllib.parse; print(urllib.parse.quote(''.join(sys.stdin.readlines())))"
{% endhighlight %}

This will output the contents of the configuration file (in this case called
exmaple-chrony.conf), and read it in a python script which will encode the
contents, including newlines.

This will give us the following output:

{% highlight bash %}
server%200.fedora.pool.ntp.org%0Aserver%201.fedora.pool.ntp.org%0Aserver%202.fedora.pool.ntp.org%0Adriftfile%20/var/lib/chrony/drift%0Amakestep%201.0%203%0Artcsync%0Akeyfile%20/etc/chrony.keys%0Aleapsectz%20right/UTC%0Alogdir%20/var/log/chrony%0A
{% endhighlight %}

With this in mind, lets apply the aforementioned configuration!

Apply the configuration
=======================

{% highlight yaml %}
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  labels:
    machineconfiguration.openshift.io/role: worker
  name: 50-worker-chrony
spec:
  config:
    ignition:
      version: 2.2.0
    storage:
      files:
      - contents:
          source: data:,server%200.fedora.pool.ntp.org%0A%0Aserver%201.fedora.pool.ntp.org%0A%0Aserver%202.fedora.pool.ntp.org%0A%0Adriftfile%20/var/lib/chrony/drift%0A%0Amakestep%201.0%203%0A%0Artcsync%0A%0Akeyfile%20/etc/chrony.keys%0A%0Aleapsectz%20right/UTC%0A%0Alogdir%20/var/log/chrony%0A
        filesystem: root
        mode: 0644
        path: /etc/chrony.conf
{% endhighlight %}

We'll call this yaml file **chrony-enable-worker.yaml**.

Note that we specified the role via the
``machineconfiguration.openshift.io/role`` label in the ``MachineConfig``'s
metadata. We also gave it a name that reflects the application order (50 will
be applied in the middle), the role's name, and the configuration we're
applying.

Lets see all of the ``MachineConfig`` objects that are currently applied to our
system:

{% highlight bash %}
$ oc get machineconfigs                                                                                                                                                                              
NAME                                                        GENERATEDBYCONTROLLER               IGNITIONVERSION   CREATED
00-master                                                   4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             71m
00-worker                                                   4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             71m
01-master-container-runtime                                 4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             71m
01-master-kubelet                                           4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             71m
01-worker-container-runtime                                 4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             71m
01-worker-kubelet                                           4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             71m
99-master-1f70153f-6a5e-11e9-ae85-021543e42872-registries   4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             71m
99-master-ssh                                                                                   2.2.0             72m
99-worker-1f718afb-6a5e-11e9-ae85-021543e42872-registries   4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             71m
99-worker-ssh                                                                                   2.2.0             72m
rendered-master-f0718d88f154089eae3b199e387696d4            4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             71m
rendered-worker-591c18e125b4a536c8574ca84da362f6            4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             71m
{% endhighlight %}

Lets now apply our configuration 

{% highlight bash %}
oc create -f chrony-enable-worker.yaml
{% endhighlight %}

Having applied our changes, we'll see that the new configuration applies fairly
in the middle:

{% highlight bash %}
NAME                                                        GENERATEDBYCONTROLLER               IGNITIONVERSION   CREATED
00-master                                                   4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             72m
00-worker                                                   4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             72m
01-master-container-runtime                                 4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             72m
01-master-kubelet                                           4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             72m
01-worker-container-runtime                                 4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             72m
01-worker-kubelet                                           4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             72m
50-worker-chrony                                                                                2.2.0             13s
99-master-1f70153f-6a5e-11e9-ae85-021543e42872-registries   4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             73m
99-master-ssh                                                                                   2.2.0             73m
99-worker-1f718afb-6a5e-11e9-ae85-021543e42872-registries   4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             73m
99-worker-ssh                                                                                   2.2.0             73m
rendered-master-f0718d88f154089eae3b199e387696d4            4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             72m
rendered-worker-591c18e125b4a536c8574ca84da362f6            4.0.0-alpha.0-269-g0ae25d4c-dirty   2.2.0             72m
{% endhighlight %}

Going back to our ``MachineConfig`` declaration, lets also note that the
configuration was applied to the ``source`` key, and had the ``data:,`` prefix
in it. This details are important things to remember if you want your
configuration to be applied correctly, as they're things that the
machine-config-operator expects.

If we want to apply the configuration to other hosts, we'll need a
``MachineConfig`` object per-role (This might be [fixed in the
future][gh-role-issue]).

Verifying our configuration changes
===================================

Lets log into our node to check that the changes were successfully applied
(Note that it might take some time for the changes to apply, since they need to
be picked up by the operator first).

Lets first choose one node to view.

To check the nodes in your system, do:

{% highlight bash %}
$ oc get nodes
NAME                                         STATUS   ROLES    AGE   VERSION
ip-10-0-135-81.eu-west-1.compute.internal    Ready    master   96m   v1.13.4+4fd195e58
ip-10-0-138-158.eu-west-1.compute.internal   Ready    worker   89m   v1.13.4+4fd195e58
ip-10-0-154-149.eu-west-1.compute.internal   Ready    worker   89m   v1.13.4+4fd195e58
ip-10-0-157-220.eu-west-1.compute.internal   Ready    master   95m   v1.13.4+4fd195e58
ip-10-0-169-234.eu-west-1.compute.internal   Ready    worker   89m   v1.13.4+4fd195e58
ip-10-0-173-147.eu-west-1.compute.internal   Ready    master   96m   v1.13.4+4fd195e58
{% endhighlight %}

Notice that the roles of the host are specified in their own column.

So, given that it's a worker node, lets choose
**ip-10-0-138-158.eu-west-1.compute.internal**.

To log into the node, we do:

{% highlight bash %}
$ oc debug node/ip-10-0-138-158.eu-west-1.compute.internal
$ chroot /host
{% endhighlight %}

Once in the node, you can do the following command:

{% highlight bash %}
chronyc -4 -n sources
{% endhighlight %}

This should show that there are 3 sources that chronyd is using, and the IP
addresses to all of them.

The ultimate source of truth
============================

Another feature of the machine-config-operator, is that it allows you to query
an aggregated structure with all of the configurations that have been rendered
into the host.

Remember the output of getting the ``MachineConfigPools``? Lets get it
again:

{% highlight bash %}
oc get machineconfigpools                                                                                                                                                                          
NAME     CONFIG                                             UPDATED   UPDATING   DEGRADED
master   rendered-master-f8b48d03fe36cf056b547e294deafb44   True      False      False
worker   rendered-worker-3c907e9ae475284d33eadfa3bc6117a5   True      False      False
{% endhighlight %}

You will note two things:

* The items under the ``CONFIG`` column, are ``MachineConfig`` objects that you
  can query from the system.

* The keys under ``CONFIG`` changed from last time we checked! This was because
  there is a new rendering, since we applied the new chronyd configuration.

To look at the render, we can do the following:

{% highlight bash %}
oc get machineconfig/rendered-worker-3c907e9ae475284d33eadfa3bc6117a5 -o yaml
{% endhighlight %}

This will show us a yaml representation of all of the configurations that have
been applied to that role.

[gh-role-issue]: https://github.com/openshift/machine-config-operator/issues/269
