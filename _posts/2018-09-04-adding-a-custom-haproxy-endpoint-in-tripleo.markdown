---
layout: post
title:  "Adding a custom HAProxy endpoint in TripleO"
date:   2018-09-04 16:07:19 +0300
categories: tripleo openstack
image: /images/cup.jpg
---

Typically, when you want to add a new service to TripleO, there's a bunch of
files you need to touch, both in tripleo-heat-templates and some puppet code
too.

Unfortunately this has made it quite tedious to add new services to TripleO, as
you need to modify puppet-tripleo's [haproxy manifest][haproxy-manifest] to add
your service.

A while ago, I thought to add a clever nice trick, so you could do this
[dynamically via hieradata][dynamic-endpoints-commit]. This code stayed there
for a while without a lot of people putting attention to it. And wrongly, I
also didn't document it. But what this gives you is that you now don't need to
touch puppet at all to enable a new endpoint in HAProxy.

So, in your service template's ``service_config_settings`` section, you'll need
to add the following:

{% highlight yaml %}
    service_config_settings:
      haproxy:
        ...
        tripleo::my_service_name::haproxy_endpoints:
            my_service_name:
                public_virtual_ip: "%{hiera('public_virtual_ip')}"
                internal_ip: "%{hiera('my_service_name_vip')}"
                service_port: {get_param: MyServicePublicPort}
                public_ssl_port: {get_param: MyServicePublicSSLPort}
                member_options: [ 'check', 'inter 2000', 'rise 2', 'fall 5' ]
                haproxy_listen_bind_param: ['transparent']
{% endhighlight %}

Here, ``service_config_settings`` is used because we specifically want to add
this hieradata to nodes that deploy haproxy.

In this example, ``my_service_name`` is the ``service_name`` from the service
template. It has to match in order for the resource to properly fill the
``ip_addresses`` and ``service_names`` parameters. Else, you'll have to
manually set up the needed values to fill those parameters.

Also, it is important to know that, if you added your service to the
``ServiceNetMap`` (which you can add by passing your service via that parameter
in heat), there will be some hiera keys enabled for you. For instance, lets say
that you added a service entry as follows:

{% highlight yaml %}
parameter_defaults:
    ServiceNetMap:
        my_service_name: internal_api
{% endhighlight %}

This would mean that you added your service to run on the internal API network
in TripleO. Thus, you'll get a hiera key called ``my_service_name_vip``, which
will have the value of the Virtual IP associated to the internal API network.

To know and take better use of all the available options, I recommend reading
the [puppet resource's code][endpoint-resource] that actually creates the
HAProxy endpoint.

It is also important to note that TripleO already fills up some defaults for
your application:

{% highlight puppet %}
  Tripleo::Haproxy::Endpoint {
    haproxy_listen_bind_param   => $haproxy_listen_bind_param,
    member_options              => $haproxy_member_options,
    public_certificate          => $service_certificate,
    use_internal_certificates   => $use_internal_certificates,
    internal_certificates_specs => $internal_certificates_specs,
    listen_options              => $default_listen_options,
    manage_firewall             => $manage_firewall,
}
{% endhighlight %}

From these, it is important to know that the certificates will be filled up for
you, so you don't need to add them.

Stein update
============

There are some services that need two or more endpoints, for these, it's not
possible to make the endpoints' names match the ``service_name`` parameter. For
these cases, I added the ``base_service_name`` parameter.

By setting ``base_service_name`` to match the ``service_name`` of the service
you want to load balance, the ``ip_addresses`` and the ``server_names``
parameters will be filled out auto-magically. This makes it easier to add
customized endpoints to load balance your service.

Lets take an example from the following [patch][openshift-patch], which adds
HAProxy endpoints to load balance OpenShift's infra endpoints. This adds two
endpoints in HAProxy, which will listen on specific ports, and forward the
traffic towards the nodes that contain the ``openshift_infra`` service.

{% highlight yaml %}
      service_config_settings:
        haproxy:
          tripleo::openshift_infra::haproxy_endpoints:
            openshift-router-http:
              base_service_name: openshift_infra
              public_virtual_ip: "%{hiera('public_virtual_ip')}"
              internal_ip: "%{hiera('openshift_infra_vip')}"
              service_port: 80
              listen_options:
                balance: 'roundrobin'
              member_options: [ 'check', 'inter 2000', 'rise 2', 'fall 5' ]
              haproxy_listen_bind_param: ['transparent']
            openshift-router-https:
              base_service_name: openshift_infra
              public_virtual_ip: "%{hiera('public_virtual_ip')}"
              internal_ip: "%{hiera('openshift_infra_vip')}"
              service_port: 443
              listen_options:
                balance: 'roundrobin'
              member_options: [ 'check', 'inter 2000', 'rise 2', 'fall 5' ]
              haproxy_listen_bind_param: ['transparent']
{% endhighlight %}

[haproxy-manifest]: https://github.com/openstack/puppet-tripleo/blob/master/manifests/haproxy.pp
[dynamic-endpoints-commit]: https://review.openstack.org/#/c/474109/
[endpoint-resource]: https://github.com/openstack/puppet-tripleo/blob/stable/rocky/manifests/haproxy/endpoint.pp
[openshift-patch]: https://review.openstack.org/#/c/601241/11
