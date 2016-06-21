---
layout: post
title:  "Deploying latest TripleO using TripleO-quickstart"
date:   2016-06-21 10:13:03 +0300
categories: tripleo openstack
---

### Preface (you may skip this)

I've been working with [TripleO][tripleo] and somehow setting my development
environment is usually quite painful. Mostly because I hadn't been taking notes
and always have to research again how to do it.

So in honor of the title of this blog; finally I will note it down.

For a long time I was using a great tool developed by Jiri Stransky, called
[Inlunch][inlunch]. This tool is great! But the desire from the community is to
have a more supported tool which is easier to use.

## Enter quickstart

[tripleo-quickstart][quickstart-repo] in the same manner as inlunch is an
ansible-based tool to aid people getting a TripleO development up and running.
And it's great! Does a lot of the dirty work for you, and leaves you with a
nice virtual setup coming from a stable branch.

So, lets clone and get into the tripleo-quickstart directory:

{% highlight bash %}
git clone https://github.com/openstack/tripleo-quickstart.git
cd tripleo-quickstart
{% endhighlight %}

And so, getting a basic environment is as easy as:

{% highlight bash %}
./quickstart.sh --no-clone $HOST
{% endhighlight %}

Where _$HOST_ is the hostname of the node you want to deploy to and
_--no-clone_ tells the script not to clone quickstart again.
This will leave you with a working undercloud and with ready-made scripts to
deploy an overcloud to virtual nodes that have already been made for you.

*NOTE:* that the host needs to be accessible without a password, so you'll need
to copy your key there beforehand.

Now, there are several configurations you can deploy TripleO with. Being HA a
very common one, it's just a matter of adding the _--config_ parameter and a
configuration file.

{% highlight bash %}

./quickstart.sh --config config/general_config/ha.yml --no-clone $HOST

{% endhighlight %}

There are several configurations already made which you can use in the
[config/general_config][config-dir] directory .

### Working in master

All this is quite nice already. Problem is, for a dev-environment, I want to
use master.

Now, I can see there are several options for the releases, so there exists
master and master-tripleo.

I didn't get master-tripleo to work. So I guess 'master' it is.

{% highlight bash %}
./quickstart.sh --config config/general_config/ha.yml --no-clone $HOST master
{% endhighlight %}

This will leave you with a fairly new and working undercloud.

### Even newer master

If we want to work with an even newer version, in the way that it's done in the
TripleO CI, we can use [tripleo.sh][tripleo-sh].

So, logged in the undercloud machine:

{% highlight bash %}
# Clone the tripleo-ci repo
git clone https://git.openstack.org/openstack-infra/tripleo-ci
# Install the repo with the latest package versions in the present system.
./tripleo-ci/scripts/tripleo.sh --repo-setup
# Update your system
yum update -y
# Update your undercloud
./tripleo-ci/scripts/tripleo.sh --undercloud
{% endhighlight %}

At this point I encountered a weird error. With the keystone puppet manifest
failing. By looking at the logs, I figured that the database wasn't being
updated; which means that for some reason the resource keystone::db::sync was
not receiving a refresh. So after running *keystone-manage db_sync* manually, I
was able to get the undercloud deployment command to work.

Besides a newer undercloud, I want my overcloud images to be updated:

{% highlight bash %}
# Remove old overcloud image from home directory
rm -f overcloud-full.qcow2
# Rebuild and re-deploy overcloud images
./tripleo-ci/scripts/tripleo.sh --overcloud-images
{% endhighlight %}

And that's that! The new images should be registered in the undercloud's
Glance, and you should be ready to go!

[tripleo]: http://tripleo.org/index.html
[inlunch]: https://github.com/jistr/inlunch
[quickstart-repo]: https://github.com/openstack/tripleo-quickstart
[config-dir]: https://github.com/openstack/tripleo-quickstart/tree/master/config/general_config
[tripleo-sh]: https://github.com/openstack-infra/tripleo-ci/blob/master/scripts/tripleo.sh
