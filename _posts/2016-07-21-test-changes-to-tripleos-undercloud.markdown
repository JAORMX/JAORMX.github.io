---
layout: post
title:  "Test changes to TripleO's undercloud"
date:   2016-07-21 14:31:35 +0300
categories: tripleo openstack
---
In a [previous post][post] I covered how to make changes in puppet-tripleo and
test them in the undercloud. However, I now realized that making changes to the
undercloud itself is not as straight forward.

Thankfully, the [script][tripleo-sh] that I've been mentioning so much in my
previous post is a great help for this. Note that this assumes that you have
cloned the [tripleo-ci repository][tripleo-ci] in the home directory.

First off, if we need to set the delorean environment in order to build
packages:

{% highlight bash %}
./tripleo-ci/scripts/tripleo.sh --delorean-setup
{% endhighlight %}

This will leave us with a directory called _tripleo_ in the home directory.

Then, we need to run the following:

{% highlight bash %}
./tripleo-ci/scripts/tripleo.sh --delorean-build [some package]
{% endhighlight %}

So, if we want to make a change to the instack-undercloud code-base. We need to
do the following:

{% highlight bash %}
./tripleo-ci/scripts/tripleo.sh --delorean-build openstack/instack-undercloud
{% endhighlight %}

We will now have a directory called _instack-undercloud_ inside the _tripleo_
directory. Here we can make the changes that we need, or pull the changes that
we have already uploaded to gerrit.

Once we have the changes we need in that directory, it's a matter of running
_--delorean-build_ again to build the package we need.

I usually just search for the package:
{% highlight bash %}
find tripleo/ -name "*rpm"
{% endhighlight %}

And finally just overwrite the previous package I had installed:
{% highlight bash %}
rpm -i --force /path/to/the/package.rpm
{% endhighlight %}

Now, to run the undercloud installation again with the latest puppet manifests,
we do the following:
{% highlight bash %}
./tripleo-ci/scripts/tripleo.sh --undercloud
{% endhighlight %}

### Note:

Depending on the type of change you're doing, you might need to change the
undercloud's deployment configuration. You can do this by changing the
_undercloud.conf_ file in the home directory (at least as deployed by
tripleo-quickstart). So make sure that you make those changes to that file
before running the _--undercloud_ command from tripleo.sh.

[post]: http://jaormx.github.io/2016/testing-puppet-tripleo-changes-for-the-undercloud/ 
[tripleo-sh]: https://github.com/openstack-infra/tripleo-ci/blob/master/scripts/tripleo.sh
[tripleo-ci]: https://github.com/openstack-infra/tripleo-ci
