---
layout: post
title:  "TripleO IPSEC setup"
date:   2017-11-30 12:14:55 +0200
categories: tripleo openstack
---
For some time in June we looked into adding encryption in all networks to
TripleO. At the time, TLS everywhere wasn't available, so we looked into IPSEC
as an alternative. Recently, we've been looking into formalizing that work and
integrate it better to the way TripleO currently does things.

Why IPSEC?
==========

In the network, TLS goes above the transport (TCP or UDP) layer and is
transparent to the application. This means that the application deployer has to
explicitly enable TLS in order to take advantage of the benefits it provides.
One then has to configure the application to use the 'https' protocol when
accessing a certain URL of a server, which also has to match what's configured
in the certificate. Besides this, one has to make sure that the certificate is
trusted, so configuring the trusted CA (the one that issued the server's
certificate) is also part of the application's configuration. One can also
configure several other aspects of the communication, such as the cipher to be
used, and in case mutual authentication is required, one also has configure the
'client' certificate and key to be used.

IPSEC offers an alternative that's easier on the application configuration
point of view. It sits below the application layer. So, when enabled, the
applications have no notion that they're using secure communications. Which
means, one can keep the same old configurations for the applications, and still
have a secure setup. One still has to manage secrets (either Pre-Shared Keys or
PKI setups) and configure encryption setups, but this is now an IPSEC
configuration problem, instead of being something one has to do for each and
every application in the cloud. This made IPSEC a great candidate to provide
out-of-band security for the TripleO setup.

With TLS we have an application that's securely serving content on a specific
endpoint. With IPSEC we have a secure tunnel between two interfaces in the
network. Everything passing through this tunnel is encrypted.

Note that if one uses certificates and private keys for IPSEC's authentication
mechanism, one still has to maintain a PKI, similarly to the TLS case. So we
still need a CA, and we still need to provision certificates and keys for each
node.

TripleO considerations
======================

The IPSEC configuration is tightly integrated with the way the TripleO network
is set up. For a regular deployment, one expects there to be network-isolation.
This means that we will have several networks on which the nodes are connected.
The different networks handle different types of traffic, and not all nodes are
connected to all networks.

Using the default configuration, the controllers (which belong to the
Controller role), are connected to the following networks:

* External
* InternalApi
* Storage
* StorageMgmt
* Tenant
* Ctlplane

The computes on the other side, are connected to these instead:

* InternalApi
* Tenant
* Storage
* Ctlplane

Each role might have different networks available and these roles are also
configurable, so we could create a custom role with a very specific set of
networks, or even modify the networks that a certain role uses.

A network could be enabled or disabled entirely. There also could (or not) be a
Virtual IP address (VIP) being served on this network, which also needs to be
secured.

Finally, we could also create custom networks and use them in the roles.

This means that we can't make assumptions about the network setup of a
TripleO-deployed overcloud. And thus, everything has to be dynamic.

We also have to take into account that the VIPs are handled by pacemaker, which
can at any given moment move the VIP to another node depending on the node's
load or other heuristics. So this also needs to be taken into account.

IPSEC setup
===========

For our IPSEC configuration, we use *libreswan*, which supports several types
of schemes or [configurations][ipsec-configurations].

From these, we mainly use host-to-host and the "server for remote clients" (or
roadwarrior) configurations.

host-to-host
------------

For communications between regular IPs in the networks, we use the host-to-host
configuration. It's a very straight-forward configuration where we tell
libreswan to establish an IPSEC tunnel for communication between one IP and
another one.

For instance, lets say we have two nodes connected via the InternalApi network.
The controller-0 and controller-1 nodes have the IPs 172.16.2.13 and
172.16.2.14 respectively.

In this case, we would tell libreswan to explicitly set up a tunnel between the
172.16.2.13 and 172.16.2.14 IPs. And we could do so with the following
configuration:

{% highlight bash %}
conn my-cool-tunnel
        type=tunnel
        authby=secret
        leftid=172.16.2.13
        left=172.16.2.13
        rightid=172.16.2.14
        right=172.16.2.14
        failureshunt=drop
        ikev2=insist
        auto=start
        keyingtries=1
        retransmit-timeout=2s
        phase2alg=aes_gcm128-null
{% endhighlight %}

Here we create a connection with the identifier my-cool-tunnel (It can be
arbitrary but unique; in the real setup we try to give a meaningful value to
ease debugging). It authenticates using a pre-shared secret (authby=secret).
And if libreswan fails to establish a tunnel, it will drop all packets
(failureshunt=drop).

Each of the hosts can have this exact configuration applied to them, or have
the left and right values interchanged (libreswan will take care of figuring
out which is which).

The caveat here is that we need to set up a tunnel for every IP address in the
network that the node can communicate with. On the other hand, we also need to
establish similar tunnels for every other network. Thus, in a fairly big and
realistic environment, the number of tunnels can be quite big.

Virtual IPs
-----------

For VIPs we would have a very similar problem. Since we would need to specify
every node that's gonna connect to the VIP before hand, which can be very
tedious. Using the roadwarrior setup avoids this issue.

Assuming the same example as above and having a VIP in the network with the
172.16.2.4 address. The configuration on the node that holds the VIP looks as
follows:

{% highlight bash %}
conn my-cool-roadwarrior-tunnel
    left=172.16.2.4
    leftid=@internal_apivip
    right=%any
    rightid=@overcloudinternal_apicluster
    authby=secret
    auto=add
    dpdaction=hold
    dpddelay=5
    dpdtimeout=15
    phase2alg=aes_gcm128-null
    failureshunt=drop
{% endhighlight %}

As we noted in the host-to-host configuration, the connection's name can be
arbitrary but unique. Here we tell libreswan to establish tunnels from the VIP
(172.16.2.4) to any host that can authenticate correctly (as noted by the %any
value in the configuration key 'right'). The 'leftid' and 'rightid'
configuration values are used, in this case, to identify the specific PSK to
use for this tunnel. We also establish Dead Peer Detection parameters (dpd),
which are useful for when there's a failover for the VIP, and libreswan has to
re-establish the tunnel.

Failover handling
-----------------

Besides the aforementioned Dead Peer Detection that libreswan does. We have a
pacemaker [resource agent][resource-agent] that takes ownership of the VIP's
IPSEC tunnel and puts it up or down depending on the location of the VIP itself
(which is also managed by pacemaker). We do this by using a pacemaker
[colocation constraint][pacemaker-colocation] with the VIP.

Setting it all up (Enter Ansible)
=================================

The setup was made by creating an ansible role that would set up the
appropriate IPSEC tunnels.

Initially the networks and VIPs and even the roles this would apply to were
hardcoded. But, thanks to additions to the
[dynamic inventory from TripleO][dynamic-inventory] we can now get all the
information we need to have a dynamic setup that takes into account custom
roles, custom networks and the VIPs they might contain.

HOWTO
-----

To use it, you need to generate a playbook that looks like the following:

{% highlight bash %}
- hosts: overcloud
  become: true
  vars:
    ipsec_psk: "<a very secure pre-shared key>"
  roles:
  - tripleo-ipsec
{% endhighlight %}

Once you have that, you can call ansible as follows:

{% highlight bash %}
ansible-playbook -i /usr/bin/tripleo-ansible-inventory /path/to/playbook
{% endhighlight %}

And that's it! It will run and set up tunnels for your overcloud.

Note that the overcloud needs to be set up already.

Where is this magical thing?
----------------------------

All the work is currently in [github][repo], but we're looking into making it
officially part of TripleO, under the OpenStack umbrella.

**UPDATE**: It's now [officially][openstack-repo] part of OpenStack

Future work
===========

TripleO Integration
-------------------

Currently this is a role that one runs after a TripleO deployment. Hopefully in
the near future this will become yet another TripleO service that one can
enable using a heat environment file.

Pluggable authentication
------------------------

Currently the role sets up tunnels using a Pre-Shared Key for authentication.
While this is not ideal, it's better than nothing. In-coming work is to add
certificates into the mix, and even use certificates provided by FreeIPA.

[ipsec-configurations]: https://libreswan.org/wiki/Configuration_examples
[resource-agent]: https://github.com/ClusterLabs/resource-agents/blob/master/heartbeat/ipsec
[pacemaker-colocation]: https://clusterlabs.org/doc/en-US/Pacemaker/1.1/html/Pacemaker_Explained/s-resource-colocation.html
[dynamic-inventory]: http://jaormx.github.io/2017/run-ansible-playbook-on-tripleo-nodes/
[repo]: https://github.com/JAORMX/tripleo-ipsec
[openstack-repo]: https://review.openstack.org/#/admin/projects/openstack/tripleo-ipsec
