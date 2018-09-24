---
layout: post
title:  "Oslo Policy Deep Dive (part 1)"
date:   2018-09-24 13:29:30 +0300
categories: openstack policy
---

In the upcoming [OpenStack Summit in Berlin][summit-berlin] we have submitted a
talk to teach folks about oslo.policy. The name is of the talk is [OpenStack
Policy 101][policy-talk], and its purpose is:

* To teach folks how policy works in OpenStack (from both a developer and an
  operator point of view) and what can you do with the oslo.policy library.

* To show folks they can write their own policies, change them and subsequently
  take them into use in OpenStack.

* [Hopefully][oslo-driver-spec] to teach folks how to write policy drivers
  that they can use to evaluate their OpenStack policies.

The purpose of this post is to write a comprehensive set of notes to deliver
for the talk, as well as have me review all the material :D. But I hope this is
useful for other folks that are interested in this topic as well.

What is oslo.policy - overview
==============================

It's a python library that OpenStack services use in order to enable RBAC (Role
Based Access Control) policy. This policy determines which user can access
which objects or resources, in which way. The library contains its own
implementation of a policy language that the service creator will use in order
to create appropriate defaults on what is allowed by each endpoint of the
service. Operators can then overwrite these defaults in order to customize the
policy for the specific service.

The policy language is based on either yaml or json, however given that these
implementations are quite similar, here we'll focus on only one of these. We
assume it's fairly trivial to use both, since a json-writen policy will also
be correctly parsed as yaml.

Where are the policies defined?
===============================

Given that each services has different purposes, endpoints, and different
needs, each service has its own policy, and the responsibility of defining it.

In the past, it used to be the case that you would find the policy for a given
service as a yaml or json file itself. This had the advantage that you would
then see the whole policy in a single file.

Recently though, OpenStack [moved the default policy to be
in-code][policy-in-code] rather than in a yaml file shipped with the projects.
This change was mostly targeted at giving a better experience to operators,
with the following reasons:

* If the operator doesn't change the default policies, they don't need to
  do or change anything. (no longer needing to package the policy.yaml, and
  everything will work as-is)

* If the operator does change the default policies, they now only need to add
  the rules they're modifying, which has several advantages:

  - Easier auditing of what's changing

  - Easier maintenance (only maintain the changes and not a whole policy.yaml
    file).

This doesn't mean that the usage of a full-fledged policy.yaml is no longer
available as folks can still generate these files from the OpenStack project's
codebase with the tooling that was created as part of this work (I'll tell you
how to do this later). So you also don't need to dig into the project's code
base to get the default policy, just use the tooling and it'll all be fine :).

How do I write policies?
========================

Whether you're a service creator or an operator, it is quite useful to know how
to write policies if you want proper RBAC to work with your service, or if you
want to modify it. So lets give it a go!

Each policy rule is defined as follows:

{% highlight yaml %}
"< target >": "< rule >"
{% endhighlight %}

Simple as that!

The targets could be either aliases or actions. Lets leave aliases for later.
Actions, represent API calls or operations. For Keystone, for instance, it
could be something like "create user" or "list users". For Barbican it could
be "create secret" or "list secrets". It is whatever operation your service is
capable of doing.

The target (as an action) will typically typically look as follows:
``secrets:get``. In the aforementioned case, that target refers to the "list
secrets for a specific project" action. Typically, the service creators define
these names, and the only way to know what action name refers to what operation
is to either refer to the project's documentation, or to dig into the project's
code-base.

The "rule" section defines what needs to be fulfilled in order to allow the
operation.

Here's what rules can be:

* Always true.
* Always false.
* A special check (for a role, another rule, or an external target).
* A comparison of two values.
* Boolean expressions based on simpler rules.

It is also possible to use operators on these rules. The available operators
are the following (in order of precedence:

* grouping: Defined with parentheses: ``( ... )``
* negation: Defined with the ``not`` operation: ``not <rule>``
* and: e.g. ``<rule 1> and <rule 2>``
* or: e.g. ``<rule 1> or <rule 2>``


Lets dig in through each case:

Always true
-----------

So, lets say that you want to write a policy where anyone can list the compose
instances. Here's what you can do:

* An empty string

{% highlight yaml %}
"compute:get_all": ""
{% endhighlight %}

* An empty list

{% highlight yaml %}
"compute:get_all": []
{% endhighlight %}

* The "@" value

{% highlight yaml %}
"compute:get_all": "@"
{% endhighlight %}

Any of the three aforementioned values will get you the same result, which is
to allow anybody to list the compute instances.

Always false
------------

If you want to be very restrictive, and not allow anybody to do such an
operation. You use the following:

* The "!" value

{% highlight yaml %}
"compute:get_all": "!"
{% endhighlight %}

This will deny the operation for everyone.

Special checks
--------------

### Role checks

Lets say that you only want to allow users with the role "lister" to list
instances. You can do so with the following rule:

{% highlight yaml %}
"compute:get_all": "role:lister"
{% endhighlight %}

These roles tie in directly with Keystone roles, so when using such a policy,
you need to make sure that the relevant users have the appropriate roles in
Keystone. For some services, this tends to cause confusion. Such as is the case
for Barbican. In Barbican, the default policy makes reference to several rules
that are non-standard in OpenStack:

* creator
* observer
* audit

So, it is necessary to get your users access to these rules if you want them to
have access to Barbican without being admin.

### Rule aliases

Remember in the beginning where I mentioned that rule definitions could be
either aliases or actions? Well, here are the alises!

In order to re-use rules, it is possible to create rule aliases and
subsequently use these aliases in other rules. This comes in handy when your
rules start to get longer and you take operators into use. For this example,
lets use the "or" operator, and create a rule that allows users with the
"admin" role or the "creator" role to list compute instances:

{% highlight yaml %}
"admin_or_creator": "role:admin or role:creator"
"compute:get_all": "rule:admin_or_creator"
{% endhighlight %}

As you can see, the ``compute:get_all`` rule is a reference to the
``admin_or_creator`` rule that we defined in the line above it. We can
even take that rule into use for another target. For instance, to create
servers:

{% highlight yaml %}
"compute:create": "rule:admin_or_creator"
{% endhighlight %}

### External check

It is also possible to use an external engine in order to evaluate individual
policies. The syntax is fairly simple, as one only needs to use the URL of the
external decision endpoint.

So, lets say that we have written a service that does this, and we'll use it to
evaluate if a certain user can list the compute instances. We would write the
rule as follows:

{% highlight yaml %}
"compute:create": "http://my-external-service.example.com/path/to/resource"
{% endhighlight %}

Or better yet:

{% highlight yaml %}
"compute:create": "https://my-external-service.example.com/path/to/resource"
{% endhighlight %}

The external resource then needs to answer exactly "True". Any other response
is considered negative.

The external resource is passed the same enforcement data as oslo.policy gets:
Rule, target and credentials (I'll talk about these later).

There are also several ways that one can configure the interaction with this
external engine, and this is done through oslo.config. In the service
configuration and under the ``oslo_policy`` section, one can set the following:

* ``remote_content_type``: This defines how to pass the data to the external
  enforcer (either URL encoded or as JSON). The available options are:
  ``application/x-www-form-urlencoded`` or ``application/json``

* ``remote_ssl_verify_server_crt``: Whether to enable or disable the external
  server certificate validation (it defaults to False).

* ``remote_ssl_ca_crt_file``: The CA path to use to validate the external
  server certificate.

* ``remote_ssl_client_crt_file``: The client certificate to use in order to
  authenticate (through TLS) to the external server.

* ``remote_ssl_client_key_file``: The client key to use in order to
  authenticate (through TLS) to the external server.

Note that it is possible to create custom checks, but we'll cover this topic in
a subsequent blog post.

Comparisons
-----------

In certain cases where checking the user's role isn't enough, we can also do
comparisons between several things. Here's the available objects we can use:

* Constants: Strings, numbers, true, false
* API attributes
* Target object attributes

### Constants

If you would like to base your policy decision by comparing a certain attribute
to a constant, it's possible to do so as follows:

{% highlight yaml %}
"compute:get_all": "<variable>:'xpto2035abc'"
"compute:create": "'myproject':<variable>"
{% endhighlight %}

### API attributes

We typically derive these from the request's context. These would normally be:

* Project ID: as ``project_id``

* User ID: as ``user_id``

* Domain ID: as ``domain_id``

While most projects have tried to keep these attributes constant, it is
important to note that not all of the projects use the exact names. This is
because the way these are passed is dependent on how the oslo.policy library is
called. There are, however, efforts to standardize this. Hopefully in the near
future (as this gets standardized), the available API attributes will be the
same ones as what's available from oslo.context.

### Target object attributes

This refers to the objects that the policies are working on.

Lets take barbican as an example. We want to make sure that the incoming user's
project ID matches the secret's project ID. So, for this, we created the
following rule:

{% highlight yaml %}
"secret_project_match": "project:%(target.secret.project_id)s",
{% endhighlight %}

Here ``project`` refers to the user's project ID, while
``target.secret.project_id`` refers to the secret that is target of this
operation.

It is important to note that how these "targets" are passed is highly project
specific, and you would typically need to dig into the project's code to figure
out how these attributes are passed.

Checks recap
------------

The olso.policy code documentation contains a very nice table that sums the
aforementioned cases quite nicely:

|            TYPE                |                SYNTAX                    |
|--------------------------------|------------------------------------------|
|User's Role                     |            ``role:admin``                |
|                                |                                          |
|Rules already defined on policy |        ``rule:admin_required``           |
|                                |                                          |
|Against URLs                    |       ``http://my-url.org/check``        |
|                                |                                          |
|User attributes                 |  ``project_id:%(target.project.id)s``    |
|                                |                                          |
|Strings                         |      - ``<variable>:'xpto2035abc'``      |
|                                |      - ``'myproject':<variable>``        |
|                                |                                          |
|                                |       - ``project_id:xpto2035abc``       |
|Literals                        |       - ``domain_id:20``                 |
|                                |       - ``True:%(user.enabled)s``        |


Where do API attributes and target objects come from?
=====================================================

As I mentioned in previous sections, these parameters are dependant on how the
library is called, and it varies from project to project. Lets see how this
works.

oslo.policy enforces policy using an object called ``Enforcer``. You'll
typically create it like this:

{% highlight python %}
from oslo_config import cfg
CONF = cfg.CONF
enforcer = policy.Enforcer(CONF, policy_file=_POLICY_PATH)
{% endhighlight %}

Once you have this ``Enforcer`` object created, every time you need policy to
be evaluated, you need to call the [enforce][enforce-method] or [authorize][
authorize-method] methods for that object:

{% highlight python %}
enforce(rule, target, creds, do_raise=False, exc=None, *args, **kwargs)
{% endhighlight %}

``enforce`` and ``authorize`` take the same arguments.

Lets look at the relevant parameters:

* ``rule``: This is the name of the rule. So if you want to enforce policy on
  ``secrets:get``, you'll pass that as a string.

* ``target``: This is the target object. It is a dictionary that should receive
  information about the object you're applying the operation on to. If it's an
  secret, you can add here what project the secret belongs to.

* ``creds``: This is the information about the user, and will be the "API
  attributes". You can either pass in a map containing the information, or you
  can pass [an oslo.context object][policy-context-rev].

Unfortunately, if you ever need to change the policy and decipher what
information is passed as the API attributes and the target, you'll need to dig
into the project's codebase and look for where the ``enforce`` or ``authorize``
calls are made for the relevant policy rule you're looking for.

Conclusion
==========

Here we learned what oslo.policy is, how to write policies with it, and how to
get the relevant information on how the policy is called for specific projects.

In the next blog post, we'll learn how to do modifications to policies and how
to reflect them on a running service.

[summit-berlin]: https://www.openstack.org/summit/berlin-2018
[policy-talk]: https://www.openstack.org/summit/berlin-2018/summit-schedule/events/21977/openstack-policy-101
[oslo-driver-spec]: https://review.openstack.org/#/c/578719/
[policy-in-code]: https://governance.openstack.org/tc/goals/queens/policy-in-code.html
[enforce-method]: https://docs.openstack.org/oslo.policy/latest/reference/api/oslo_policy.policy.html#oslo_policy.policy.Enforcer.enforce
[authorize-method]: https://docs.openstack.org/oslo.policy/latest/reference/api/oslo_policy.policy.html#oslo_policy.policy.Enforcer.authorize
[policy-context-rev]: https://review.openstack.org/#/c/534440/
