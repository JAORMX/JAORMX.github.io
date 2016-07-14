---
layout: post
title:  "Testing puppet-tripleo changes for the undercloud"
date:   2016-07-14 10:59:34 +0300
categories: tripleo openstack
---
I've been trying to test some puppet-tripleo changes that apply for the
undercloud only. And it seems that the process is not the same as in the
overcloud. There, you have several options:

* Build the images giving the reference to DIB.
* Modify the images, upload them again and use them like that.

But it seems that this is not the case for the undercloud, as it doesn't take
into account the changes I've been trying to introduce.

One thing to note is that I'm using [tripleo.sh][tripleo-sh] to do things like
we do in CI and to be able to work with the lastest code for tripleo.

So while bumping my head against the wall figuring out why the package I was
building through _tripleo.sh --delorean-build openstack/puppet-tripleo_ wasn't
being used. I noticed that if I tried replacing the manifest in
_/opt/stack/puppet-modules_ the undercloud installation was failing due to an
"unmatching ref".

I then discovered that for CI, we are using DIB for the openstack puppet
modules, as seen [here][dib-usage].

So in the end, to have it work, I ended up following similar steps as with the
image building:

{% highlight bash %}
export DIB_INSTALLTYPE_puppet_tripleo=source
export DIB_REPOLOCATION_puppet_tripleo=https://review.openstack.org/openstack/puppet-tripleo
export DIB_REPOREF_puppet_tripleo=refs/changes/05/341405/2
{% endhighlight %}

And that did the trick! Now I was able to test my changes.

[tripleo-sh]: https://github.com/openstack-infra/tripleo-ci/blob/master/scripts/tripleo.sh
[dib-usage]: https://github.com/openstack-infra/tripleo-ci/blob/master/scripts/tripleo.sh#L390
