---
layout: post
title:  "Testing TLS everywhere with tripleo-quickstart"
date:   2018-09-18 08:50:33 +0300
categories: tripleo openstack
---

I've gotten the request for help deploying TLS everywhere with TripleO several
times. Even though there's [documentation][tls-everywhere-docs], deploying from
scratch can be quite daunting, specially if all you want to do is test it out,
or merely integrate your service to it.

However, for development purposes, there is
[tripleo-quickstart][tripleo-quickstart], which makes deploying such a scenario
way simpler.

Here's the magical incantation to deploy TripleO with TLS everywhere enabled:

{% highlight bash %}
./quickstart.sh --no-clone --teardown all --clean -p quickstart-extras.yml \
    -N config/nodes/1ctlr_1comp_1supp.yml \
    -c config/general_config/ipa.yml \
    -R master-tripleo-ci \
    --tags all \
    $VIRTHOST
{% endhighlight %}

Note that this assumes that you're in the tripleo-quickstart repository.

Assuming ``$VIRTHOST`` is the host where you'll do the deployment, this will
leave you with a very minimal deployment: An undercloud, one controller, one
compute, and a supplemental node where we deploy FreeIPA.

Because we're using the ``master-tripleo-ci``, this setup also deploys the
latest promoted images. If you want to use the latest "stable" master
deployment, you can use ``master`` instead. If you want to deploy Queens,
you'll merely use ``queens`` instead. So, for reference, here's how to deploy a
Queens environment:

{% highlight bash %}
./quickstart.sh --no-clone --teardown all --clean -p quickstart-extras.yml \
    -N config/nodes/1ctlr_1comp_1supp.yml \
    -c config/general_config/ipa.yml \
    -R queens \
    --tags all \
    $VIRTHOST
{% endhighlight %}

Lets also note that ``--tags all`` deploys the "whole thing"; meaning, it'll
also do the overcloud deployment. If you remove this, the quickstart will leave
you with a deployed undercloud, and you can do the overcloud deployment
yourself.

[tls-everywhere-docs]: http://tripleo.org/install/advanced_deployment/ssl.html#tls-everywhere-for-the-overcloud
[tripleo-quickstart]: https://github.com/openstack/tripleo-quickstart
