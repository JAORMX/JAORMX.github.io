---
layout: post
title:  "Modifying Your Overcloud Images"
date:   2016-06-21 14:43:03 +0300
categories: tripleo openstack
---

It has been the case several times where I have done a change in a puppet
module, but I don't want to completely rebuild the images. Well
libguestfs-tools is your friend.

In this case, I'm testing some changes in puppet-tripleo that attempt to
request certificates for keystone. So I have a local copy of the puppet-tripleo
repository in my home directory. Note that I also have a local copy of the
overcloud-full image in my home directory.

Copying files to the image is fairly simple with the help of virt-copy-in.
But before this, one thing to note, is that opposed to what one would think,
the puppet manifests for the overcloud (and the undercloud) are not in the
directory you would expect. Usually you have your installed puppet modules
in _/etc/puppet/modules_, but in our case, that directory only contains
symlinks. So, since they are symlinks, using virt-copy-in will not work in this
case. So we must know that for RDO there is the convention to put the
OpenStack-related puppet modules in _/opt/stack/puppet-modules_.  So knowing
this we can finally copy our modules:

{% highlight bash %}
virt-copy-in -a overcloud-full.qcow2 \   # your local overcloud image
    puppet-tripleo/manifests/ \          # your local puppet manifests
    /opt/stack/puppet-modules/tripleo/   # the destination directory
{% endhighlight %}

To verify that this worked, we can use guestfish:

{% highlight bash %}
$ guestfish -a  overcloud-full.qcow2

Welcome to guestfish, the guest filesystem shell for
editing virtual machine filesystems and disk images.

Type: 'help' for help on commands
      'man' to read the manual
      'quit' to quit the shell

><fs> run
><fs> mount /dev/sda /
><fs> ls /etc/puppet/modules/tripleo/manifests/
cluster
fencing.pp
firewall
firewall.pp
haproxy
haproxy.pp
init.pp
internal_tls.pp
keepalived.pp
network
noop.pp
pacemaker
packages.pp
profile
redis_notification.pp
selinux.pp
><fs> exit
{% endhighlight %}

This modified our local copy of the image. So now what's left is to update the
undercloud to host our modified image. We can achieve this with the following
command:

{% highlight bash %}
openstack overcloud image upload --update-existing
{% endhighlight %}

This will check our local copies of the overcloud images in case there are
changes to them, and upload them to the undercloud's Glance instance if there
are differences. With this done, we now are ready to deploy our changes.
