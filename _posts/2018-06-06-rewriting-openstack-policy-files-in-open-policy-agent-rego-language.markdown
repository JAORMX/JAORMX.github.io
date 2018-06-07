---
layout: post
title:  "Rewriting OpenStack policy files in Open Policy Agent's Rego language"
date:   2018-06-06 13:13:12 +0300
categories: openstack open-policy-agent opa
---

Rewriting OpenStack policy files in Open Policy Agent's Rego language
=====================================================================

I recently started experimenting with Open Policy Agent, and decided to test
out writing OpenStack policy files in [Rego][rego].

Background
----------

Policy in OpenStack has been a long-debated topic. Currently the way that works
is that most projects have the API's policies as part of the code-base. It is
also possible to overwrite, or add policy rules via a json or yaml file.
Furthermore, one can generate a yaml file with the default policy using the
'genpolicy' target which is available in most OpenStack projects' `tox.ini`
files. The library which is in charge of reading and enforcing policies is
[oslo.policy][oslo-policy], which provides an `Enforcer` class which we can
use to evaluate our policy against an API call to our service.

The advantage of this approach is that it enables each project to maintain
their own policies, instead of having a central group that should understand
every OpenStack project and has a central repository for the policies.

This approach, however, has several limitations. For instance, it's
non-trivial to update the policy file for a certain service. This is because
to do this, we would need to go to each node in the cluster, update the
policy.json file for every service and either reload it or restart it.
Restarting the service can be quite problematic as that means we'll have a
service disruption, and it'll interrupt any on-going tasks that the service is
doing. Unfortunately, as of now, not all services support live configuration
updates (this is a [community goal][mutable-config], and hopefully this won't
be a problem in the future). We also need to keep track of where every service
is running in the cluster, as we'll need to update the policy for a specific
OpenStack service. With this, we also need to keep track of the version that
the service is running with (in case we support rolling upgrades), and have
the possibility of rolling back any wrongly made policy changes.

Given the aforementioned limitations, it's clear that there are enhancements
needed to improve the policy situation in OpenStack. And while there have been
plenty of initiaties trying to address this, I hope that we don't come up with
yet another project, and try to converge in a more general solution, even if
it's not part of the OpenStack environment.

Open Policy Agent
-----------------

As I mentioned in a [previous blog post](/2018/kubeconcph2018/), I had the
fortune to attend Kubecon in Copenhagen, where I had more exposure to several
projects in the Cloud Native Foundation. One of these projects is
[Open Policy Agent][opa], which is general-purpose policy engine.

OPA can run in the form of an interactive shell, a server or middleware in a Go
service. It uses its own language, called Rego, to define policies. Eventually,
you can query the server for policy decisions with a simple REST API.

Given that OPA already has Kubernetes, Docker, Terraform and Kafka integration,
I thought it would be a good idea to try to take it into use in OpenStack, and
propose (yet another) solution to the community.

Rewritting Barbican's Policy File
---------------------------------

I decided to take barbican's [default policy][barbican-policy] file and rewrite
it in Rego as an exercise. The intention is to figure out how map between the
two policy formats, and hopefully come up with patterns to automate such a
task.

It turns out that it wasn't to hard to do, and I ended up [rewritting the whole
policy file][rego-rewrite].

oslo.policy Considerations
--------------------------

There are several things to know in order to start mapping between the two
formats:

* OpenStack services call `oslo.policy` to make policy decisions via the
  `enforce` function call of the `Enforcer` class.

  - The `enforce` call is called with three main arguments: `rule`, `target`
    and `creds`

  - The `rule` parameter can be either a string of a Check class. If it's a
    string, it's normally the API action name (e.g. secrets:get). The Check
    class is a class that contains the string representation of the policy
    check we'll do and the required function (the `__call__` function), to
    execute that check.

  - The `target` parameter is a dictionary containing any relevant information
    about the entity against which you're executing policy. If you're talking
    about Barbican's secret API, that'll be relevant information about the
    secret that the user is trying to access. Normally here you would put the
    object's project ID, but perhaps you could even a user ID, or any other
    relevant information you see fit. You'll normally see references to stuff
    you pass in the target in the policy files in the form of a python string
    formatting structure (e.g. '%(project_id)s' or '%(user_id)s').

  - The `creds` parameter contains a dictionary that contains information about
    the user trying to access the resource. Normally you'll have the roles,
    user ID and project ID. If you have a rule that says
    `project_id:%(project_id)s`, that means that it'll compare the project ID
    from the user (which comes from the `creds` parameter), to the entity's
    project ID (which comes from the target).

With these constructs in mind, we can start rewriting our policy files.

Rewritting OpenStack Policy Files
---------------------------------

We'll start off by setting up a common package for our Rego policy file.

{% highlight go %}
package openstack.policy
{% endhighlight %}

What this will do is that it'll set up a predictable path in OPA's server. So
when we want to do policy queries, we'll do requests to
`https://<OPA host>/v1/data/openstack/policy/` as a base.

We'll also add a way to map the inputs coming from the `enforce` call:

{% highlight go %}
import input.credentials as credentials
import input.action_name as action_name
import input.target as target
{% endhighlight %}

This stages the input coming from the user, on to the main namespace. The input
JSON will look as follows:

{% highlight json %}
{
    "input": {
        "credentials": ...
        "action_name": ...
        "target": ...
    }
}
{% endhighlight %}

In order to make policy decisions, we'll need to agree on an entry to query on
that'll contain the decision result. In our case, we'll use `allow`. We'll set
it to `false` by default, since, if no policy rule matches, that's the result
we want to get.

{% highlight go %}
default allow = false
{% endhighlight %}

So, with the current configuration, we can do a query as follows:

{% highlight bash %}
curl -X POST "http://<OPA URL>/v1/data/openstack/policy/allow" \
    --data '{"input": {"credentials": {}, "target": {}, "action_name": ""}}' \
    -H 'Content-Type: application/json'
{% endhighlight %}

We'll get the following result:

{% highlight bash %}
{"result":false}
{% endhighlight %}

There are several translations we can do when it comes to writing policy.json
files into rego language given the definitions and assumptions we made above.

policy.json files refer to keystone roles with the prefix `role:`, before the
name of the role. This is used to define a check that matches if the incoming
role (from the credentials) matches the role defined in the policy role.

Looking at the policy.json file from barbican, we can see such a rule
definition:

{% highlight json %}
{
"admin": "role:admin",
...
{% endhighlight %}

We can easily translate this to rego, which would look as follows:

{% highlight go %}
admin {
    credentials.roles[_] = "admin"
}
{% endhighlight %}

This means that out of the several roles in the roles array, which is in the
credentials object, the "admin" entry should exist. If this is true, the rule
"admin" will be true.

Another example which we can generalize is the usage of "or" statements. Lets
look at another example from the policy.json file:

{% highlight json %}
...
"admin_or_creator": "rule:admin or rule:creator",
...
{% endhighlight %}

This refers to two previously defined rules in the policy (the "admin and
"creator" rules), and, if those two rules are true, then the
"admin_or_creator" rule is true. In rego, it would look as follows:

{% highlight go %}
admin_or_creator {
    admin
}

admin_or_creator {
    creator
}
{% endhighlight %}

As you can see, two definitions came out of this. What this means in rego is
that, it'll evaluate both of them, and if the first one (which calls the admin
rule), isn't true, then it won't define "admin_or_creator", so it'll continue.
If the second one (which calls "creator") isn't true or defined either, it
again won't define the "admin_or_creator" rule, and any call that other rules
do to the "admin_or_creator" rule will not evaluate either. However, if any of
those two definitions ends up evaluating to true, "admin_or_creator" will be
true. This is how we implement "or" statements in rego.

In the following example of the policy.json file we can see the usage of the
"and" operator:

{% highlight json %}
...
"secret_non_private_read": "rule:all_users and rule:secret_project_match and not rule:secret_private_read",
...
{% endhighlight %}

It can be translated to rego as follows:

{% highlight go %}
secret_non_private_read {
    all_users
    secret_project_match
    not secret_private_read
}
{% endhighlight %}

Where "secret_non_private_read" will only evaluate to `true` if all the rules
evaluate to `true`. This also covers the negation case, which translates
directly to rego language by just using the 'not' keyword.

Lets look at the usage of the target and credential parameters:

{% highlight json %}
...
"secret_project_match": "project:%(target.secret.project_id)s",
...
{% endhighlight %}

We can detect the usage of `target` with the usage of string formatters. So the
fact that the reference to `target.secret.project_id` is surrounded with a
string formatter tells us that we should use `target`. On the other hand, the
prepended `project:` reference tells us that we should get that from the
credentials (given that it's not a constant nor a reserved word such as
'rule'). So we'll translate the rule as follows:

{% highlight go %}
secret_project_match {
    credentials.project = target.target.secret.project_id
}
{% endhighlight %}

The 'project' entry in the credentials is accessed directly, but you'll notice
that the target access looks like this: `target.target.secret.project_id`. This
is actually on purpose, and it's because the access was
`%(target.secret.project_id)s`. So, in the code, barbican actually calls
`enforce` call with the `access` parameter with the following value:

{% highlight json %}
{
    "target": {
        "secret": {
            "project_id": "<some project id>"
        }
    }
}
{% endhighlight %}

If the access had been just `%(project_id)s`, we would have translated that as
`target.project_id`.

We also need to detect whether we're comparing against constants:

{% highlight json %}
...
"secret_acl_read": "'read':%(target.secret.read)s",
...
{% endhighlight %}

This is fairly straight forward, as constants are surrounded by quotes. So it
would translate as follows:

{% highlight go %}
secret_acl_read {
    "read" = target.target.secret.read
}
{% endhighlight %}

Finally, we have the references to actions (which is what we ultimately want to
execute policy on). Here are some examples of actions in the barbican policy
file:

{% highlight json %}
...
"secret:get": "rule:secret_non_private_read or rule:secret_project_creator or rule:secret_project_admin or rule:secret_acl_read",
"secret:put": "rule:admin_or_creator and rule:secret_project_match",
"secret:delete": "rule:secret_project_admin or rule:secret_project_creator",
"secrets:post": "rule:admin_or_creator",
"secrets:get": "rule:all_but_audit",
...
{% endhighlight %}

Action names have the format `<entity>:<action>`. And, since that's where we
want to make our policy decisions, that's where we'll set the `allow` value.
Lets take the simple example of the "secrets:get" action. This is how we
translate it:

{% highlight go %}
allow {
    action_name = "secrets:get"
    all_but_audit
}
{% endhighlight %}

There we match the action name and we make sure that the rule evaluates.

Following the aforementioned rules, we can then start translating every rule in
the policy file.

Testing it out
--------------

Currently I'm testing it out by doing calls directly to OPA.

Assuming the barbican rego file is called `barbican.rego`, here's how I run OPA
to begin with:

{% highlight bash %}
./opa_linux_amd64 run -s --addr "http://localhost:8181" ~/barbican.rego
{% endhighlight %}

This makes OPA run as a server which listens on localhost on port `8181`, and
uses the `barbican.rego` for policy which is in my home directory.

Lets execute a query now. We'll test if we can list secrets from barbican.
We can do this with the "secrets:get" action. We know that the rule says every
user with a relevant role except the audit role can list secrets. Which means,
a user with the roles admin, creator or observer can do this, but not users
with just the audit role.

So, for a successful listing of secrets, lets define the following input:

{% highlight json %}
{
    "input": {
        "action_name": "secrets:get",
        "credentials": {
            "roles": ["creator"]
        },
        "target": {}
    }
}
{% endhighlight %}

This is a user that had the `creator` role, and is querying the `secrets:get`
action.

To get a policy result, we call it as follows:

{% highlight bash %}
$ curl -X POST "http://localhost:8181/v1/data/openstack/policy/allow" --data @barbican-creator-list.json  -H 'Content-Type: application/json'
{"result":true}
{% endhighlight %}

As you can see, it passed the check!

If you want to see all the checks that evaluated with that call, you can remove
the `allow` section from the path:

{% highlight bash %}
$ curl -X POST "http://localhost:8181/v1/data/openstack/policy" --data @barbican-creator-list.json  -H 'Content-Type: application/json'
{"result":{"admin_or_creator":true,"all_but_audit":true,"all_users":true,"allow":true,"creator":true}}
{% endhighlight %}

Now lets try with the `audit` role. The input would look as follows:

{% highlight json %}
{
    "input": {
        "action_name": "secrets:get",
        "credentials": {
            "roles": ["audit"]
        },
        "target": {}
    }
}
{% endhighlight %}

And lets do our queries:

{% highlight bash %}
$ curl -X POST "http://localhost:8181/v1/data/openstack/policy" --data @barbican-audit-list.json  -H 'Content-Type: application/json'
{"result":{"all_users":true,"allow":false,"audit":true}}

$ curl -X POST "http://localhost:8181/v1/data/openstack/policy/allow" --data @barbican-audit-list.json  -H 'Content-Type: application/json'
{"result":false}
{% endhighlight %}

As we can see, the policy check failed, so this would translate to the `audit`
role not having the ability to list secrets in barbican.

Next Steps
----------

### Test the policy with the actual service

I need to hack up barbican in order to make calls to OPA instead of doing the
regular oslo.policy calls. If we decide to go through with getting OPA
integrated with OpenStack, this code would be the base for an alternative
`Enforcer` class. This new class would communicate with OPA either via HTTP or
via a UNIX domain socket. OPA could be running as a side-car container with the
service itself, expose a UNIX domain socket, and execute policy that way.

### Automate!!

The steps to translate the policies should be automated in the form of a
parser. This will allow us to test this approach with other OpenStack services,
and not have folks have to do this translation manually.

### Evaluate

We need to check how this performs when compared to the oslo.policy library. It
wouldn't make sense to take this approach into use if we have performance
degradation.

... The Future?
---------------

If all goes well with the previous steps I mentioned, the ideal thing would be
to look into building a control plane for OPA that can configure and distribute
policies for all our OpenStack services. It would also be able to keep track of
the policy version the services are using, and be able to deploy and roll-back
policy changes.

There is a lot of work to do it seems!


[rego]: https://www.openpolicyagent.org/docs/how-do-i-write-policies.html
[oslo-policy]: https://docs.openstack.org/oslo.policy/latest/
[mutable-config]: https://governance.openstack.org/tc/goals/rocky/enable-mutable-configuration.html
[opa]: https://www.openpolicyagent.org/
[barbican-policy]: https://gist.github.com/JAORMX/19399f507e3c0243bd007ff96398116a
[rego-rewrite]: https://gist.github.com/JAORMX/23679c582f3a20c89d192027b8d17050
