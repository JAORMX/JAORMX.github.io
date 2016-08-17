---
layout: post
title:  "FreeIPA TripleO integration notes"
date:   2016-08-12 13:53:22 +0300
categories: tripleo openstack
---

So I'm trying to get the overcloud nodes from TripleO to enroll to FreeIPA. And
before having nice middleware that will do this through config-drive or
something of the sort. I decided to setup a simple heat template that will do
this. So I have a [temporary repository][temp-repo] where I'm doing the work.

Basically what's going on there is that I made a stack that will be used on the
[node type]ExtraConfigPre hook in tripleo. This stack will in turn run a
script that gets an OTP, the domain managed by FreeIPA and the address or
hostname of the FreeIPA server. With this, we first install the ipa-client
package, do the enrollment, and finally get the kerberos ticket. Also, since
we need to be aware of the domain when running the ipa-client installation, we
check if the domain was set already, and if it isn't we set it up. By default
we do this only for controllers, but the script can also add a hook for the
computes if a flag is set.

To use it we need to run a little script first which will generate a heat
environment file that we can then use to add that stack to the hook. So, on
the base directory of the repo, we can run:

    ./create_freeipa_enroll_envfile.py -h

Which will give all the available options. What matters to us is the OTP, the
FreeIPA server (or just server), and the domain. You might need to include the
DnsServer (or several, depending on your setup).

Be aware that if you're using tripleo-quickstart, network-environment.yaml will
already contain a nameserver corresponding to the host's IP address. You might
want to change that if FreeIPA is in another address and you want to specify
it. The parameter in tripleo-heat-templates is called _DnsServers_. In my case,
I'm using the standard ha setup that quickstart provides, so I *don't* need to
set DNS servers in my environment, the defaults work fine.

## What do I want this stuff for?

So basically what I want to do is to have every overcloud controller node
enrolled as a FreeIPA host, but also I want to have certificates for the
HAProxy public VIP.

In order to get these, we need to first create the hosts and services in
FreeIPA. As a bonus I'll also create the undercloud node, since, as I mentioned
in a past blog post, we can now get the HAProxy public IP for the undercloud
via FreeIPA.

## FreeIPA setup

I define the following environment variables for convenience:

    export SECRET=MySecret
    export DOMAIN=walrusdomain
    export IPA_SERVER="ipa.$DOMAIN"

And here's the setup I've been doing:

{% highlight bash %}
# Add undercloud host
ipa host-add undercloud.$DOMAIN --password=$SECRET --force

# Add overcloud Public VIP host
ipa host-add overcloud.$DOMAIN --force

# Add overcloud hosts
for i in {0..2}; do ipa host-add overcloud-controller-$i.$DOMAIN --password=$SECRET --force; done

# Make overcloud VIP host be managed by overcloud nodes
ipa host-add-managedby overcloud.$DOMAIN --hosts=overcloud-controller-{0..2}.$DOMAIN

# Add HAProxy service for the undercloud
ipa service-add haproxy/undercloud.$DOMAIN --force

# Add HAProxy service for the overcloud Public VIP
ipa service-add haproxy/overcloud.$DOMAIN --force

# Get overcloud nodes to manage haproxy service for the overcloud VIP host
ipa service-add-host haproxy/overcloud.$DOMAIN --hosts=overcloud-controller-{0..2}.$DOMAIN
{% endhighlight %}

Note that the compute nodes might need to be enrolled too, depending on your
usecase. In our use-case, the compute nodes need to trust FreeIPA as a CA. So
we might as well enroll them too:

{% highlight bash %}
ipa host-add overcloud-novacompute-0.$DOMAIN --password=$SECRET --force
{% endhighlight %}

With all this set up, I ran these commands on the overcloud nodes... but this
is pretty much what the heat stack already does:

install freeipa client on each node

    sudo yum install -y ipa-client

enroll each controller

{% highlight bash %}
sudo ipa-client-install --server $IPA_SERVER \
    --password=$SECRET --domain=$DOMAIN --unattended
{% endhighlight %}

Get ticket

    sudo kinit -k -t /etc/krb5.keytab

And to test that we can do what we want, here we try to get haproxy overcloud
cert:

{% highlight bash %}
getcert request -I overcloud-public-cert -c IPA -N overcloud.$DOMAIN \
    -K haproxy/overcloud.$DOMAIN -k /etc/pki/tls/private/overcloud-key.pem \
    -f /etc/pki/tls/certs/overcloud-cert.pem
{% endhighlight %}

SUCCESS! We can do this for every overcloud node.

With the stack we can already do the enrollment on the overcloud nodes, what I
need now is to get the certificate request to happen in the service profiles.

[temp-repo]: https://github.com/JAORMX/freeipa-tripleo-incubator
