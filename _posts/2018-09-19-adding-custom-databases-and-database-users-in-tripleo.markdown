---
layout: post
title:  "Adding custom databases and database users in TripleO"
date:   2018-09-19 07:50:22 +0300
categories: tripleo openstack
image: /images/cup.jpg
---

For folks integrating with TripleO, it has been quite painful to always need to
modify puppet in order to integrate with the engine. This has been typically
the case for things like adding a HAProxy andpoint and adding a database and a
database user (and grants). As mentioned in a [previous post](
{% post_url 2018-09-04-adding-a-custom-haproxy-endpoint-in-tripleo %}), this is
no longer the case for HAProxy endpoints, and this ability has been in TripleO
for a a couple of releases now.

With the same logic in mind, I added this same functionality for mysql
databases and database users. And this relecently landed in Stein. So, all you
need to do is add something like this to your service template:

{% highlight yaml %}
    service_config_settings:
      mysql:
        ...
        tripleo::my_service_name::mysql_user:
          password: 'myPassword'
          dbname: 'mydatabase'
          user: 'myuser'
          host: {get_param: [EndpointMap, MysqlInternal, host_nobrackets]}
          allowed_hosts:
            - '%'
            - "%{hiera('mysql_bind_host')}"
{% endhighlight %}

This will create:

* A database called ``mydatabase``
* A user that can access that database, called ``myuser``
* The user ``myuser`` will have the password ``myPassword``
* And grants will be created so that user can connect from the hosts specificed
  in the ``host`` and ``allowed_hosts`` parameters.

Now you don't need to modify puppet to add a new service to TripleO!
