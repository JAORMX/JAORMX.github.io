---
layout: post
title:  "Testing out the TLS everywhere patches for TripleO"
date:   2016-10-05 13:14:51 +0300
categories: tripleo openstack
---

With the TLS-everywhere (powered by certmonger) patches accumulating in gerrit.
It's probably a good idea to write how I set up my development environment so
others can do the same and try it out.

# Physical setup

For all my development, I use only one node, where I run the virtual machines
that comprise the TripleO deployment.

Since the setup needs a CA that's trusted on all the nodes, I install FreeIPA
on that same host, which will serve as our CA.

I don't install it in one of the virtual machines for simplicity, since in this
setup, the undercloud node and the overcloud nodes point to the hypervisor
(that runs FreeIPA) as a DNS server, so we get that for free.

# FreeIPA

To install FreeIPA with a very minimal configuraton (only for testing
purposes), you can do the following command:

{% highlight bash %}

export DOMAIN=walrusdomain
export SECRET=SomePassword
ipa-server-install --realm=$(echo $DOMAIN | awk '{print toupper($0)}') \
    --admin-password=$SECRET --ds-password=$SECRET \
    --hostname=$(hostname -f) -U

{% endhighlight %}

Once this finishes you need to authenticate using the password you have
(hopefully you're using a different password than the one I put there). So we
do:

{% highlight bash %}

# Get a kerberos ticket for the admin user
kinit admin
# verify we have a ticket
klist

{% endhighlight %}

Now, with FreeIPA installed and the kerberos ticket loaded, you need to set up
the necessary hosts and services in FreeIPA for the overcloud deployment.
You'll also need to set up a hostname for the undercloud, since we need to
enroll this too so it's both tracked and it trusts FeeIPA as a CA.

For this, lets define two environment variables that we'll use for this:

{% highlight bash %}

export SECRET=MySecret
export DOMAIN=walrusdomain

{% endhighlight %}

Where SECRET will be the OTP that we'll use for the nodes to authenticate in
the enrollment phase, and DOMAIN is the domain that we already set for FreeIPA
(or the kerberos realm).

To add the undercloud node we can do the following:

{% highlight bash %}

ipa host-add undercloud.$DOMAIN --password=$SECRET --force

{% endhighlight %}

Now, for the overcloud nodes, the number of hosts and services can vary
depending on the deployment size. So to simplify this, I have a script that
will do this for you. So, assuming that you'll do an HA setup, lets do this:

{% highlight bash %}

git clone https://github.com/JAORMX/freeipa-tripleo-incubator.git
cd freeipa-tripleo-incubator
python create_ipa_tripleo_host_setup.py -w $SECRET -d $DOMAIN \
    --controller-count 3 --compute-count 1

{% endhighlight %}

This will create a node for each of the VIPs, 3 controller hosts and a relevant
host for each node in each network (external, internalapi, storage,
storagemgmt and ctlplane), and finally one compute host. On the other hand, it
will create a haproxy service for the VIP hosts, and an HTTPD service for the
controllers. Also, the controllers will manage the haproxy services. All of
this is needed to request the appropriate certificates for the services from
the overcloud nodes.

Hopefully everything went well, so now we can set up TripleO!

# TripleO

## Undercloud setup

Now, we need to position ourselves in the undercloud host. For this, I assume
you already have a running undercloud host, and the overcloud nodes are ready
to deploy. Now, one thing is that the FreeIPA host needs to be accessible from
both the undercloud and the overcloud nodes, so make sure this is the case by
attempting to ping that host using its FQDN.

For simplicity, lets say that the FreeIPA node's FQDN is "ipa" + the kerberos
realm:

    export DOMAIN=walrusdomain
    export IPA_SERVER="ipa.$DOMAIN"

On the other hand, we need to make sure that the undercloud node has the FQDN
we specified to FreeIPA (including the domain.

    sudo hostnamectl set-hostname undercloud.$DOMAIN

You can alternatively edit your _/etc/hosts_ file

Now, we need to get the undercloud to trust FreeIPA as a CA. To do this, we'll
enroll the undercloud node with the following steps:

{% highlight bash %}

export SECRET=MySecret

sudo yum install -y ipa-client
sudo ipa-client-install --server $IPA_SERVER \
    --password=$SECRET --domain=$DOMAIN --unattended

{% endhighlight %}

And we're set! Now we can authenticate byu using the keytab to get a kerberos
ticket:

{% highlight bash %}

# Get kerberos ticket
sudo kinit -k -t /etc/krb5.keytab
# Verify we got a ticket
sudo klist

{% endhighlight %}

Now that we have the undercloud enrolled, lets prepare everything for the
overcloud deploy.

## Overcloud setup

### Preparing the images

Now, before doing the deployment, we'll need a couple of packages in the
overcloud images so everything goes smoothly. We'll need the ipa-client
package (just like in the undercloud) and we'll need mod_ssl (in case you're
also securing apache). So lets install those into the images:

    # Install packages in the imge
    virt-customize -a overcloud-full.qcow2 --install ipa-client,mod_ssl
    # Upload images to undercloud's glance
    openstack overcloud image upload --update-existing

Note that to get the virt-customize utility, you need to install
``libguestfs-tools`` (in CentOS).

### Heat environment files

Our overcloud will need several things for the FreeIPA enrollment:

* The domain needs to match the kerberos realm
* The VIP hosts need to have the kerberos realm as a domain
* The nodes need to get the appropriate data (IPA server name, OTP and
  kerberos realm or domain)
* We need to tell the nodes to enroll somehow

freeipa-tripleo-incubator has another script for this, thankfully:

{% highlight bash %}

# Clone the repo
git clone https://github.com/JAORMX/freeipa-tripleo-incubator.git
# Move to that directory
cd freeipa-tripleo-incubator
# Run script to generate environment file
./create_freeipa_enroll_envfile.py -w $SECRET -d $DOMAIN -s $IPA_SERVER \
    --add-computes

{% endhighlight %}

This will output two environment files:

* cloud-names.yaml : This files contain the overrides for the VIP host names
  which we'll use.
* freeipa-enroll.yaml : This contains the necessary info we need for the
  enrollment, as well as an override of the controller and compute
  ExtraConfigPre hook. This hook will execute the enrollment the same way we
  did it for the undercloud.

Now, as for the environment files needed that should be available in
tripleo-heat-templates. These are the ones introduced by the TLS-everywhere
commits:

This tells certmonger to request the certificate for the public endpoint of
HAProxy:

    tripleo-heat-templates/environments/services/haproxy-public-tls-certmonger.yaml

Now, you could use a certificate and key and inject those since this is what we
already do for the overcloud... but, just so you know, there will be support
for using FreeIPA there too.

This tells certmonger to request certificates for the rest of the internal
endpoints (which correspond to the VIPs for the different networks):

    tripleo-heat-templates/environments/services/haproxy-internal-tls-certmonger.yaml

It will also set the necessary configuration in HAProxy to serve the
certificate/key for the endpoints.

This tells TripleO to set the endpoints to use TLS everywhere (it will be
reflected in the keystone catalog):

    tripleo-heat-templates/environments/tls-everywhere-endpoints-dns.yaml

And if we want to enable TLS in the internal network too, we can include this:

    tripleo-heat-templates/environments/enable-internal-tls.yaml
