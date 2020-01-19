---
layout: post
title:  "Oslo Policy Deep Dive (part 2)"
date:   2018-09-26 17:01:27 +0300
categories: tripleo openstack
image: /images/cup.jpg
---

In the [previous blog post](
{% post_url 2018-09-24-oslo-policy-deep-dive-p1 %}) I covered all you need to
know to write your own policies and understand where they come from.

Here, We'll go through some examples of how you would change the policy for a
service, and how to take that new policy into use.

For this, I've created a [repository][test-repo] to try things out and
hopefully get you practicing this kind of thing. Of course, things will be
slightly different in your environment, depending on how you're running
OpenStack. But you should get the basic idea.

We'll use Barbican as a test service to do basic policy changes. The
configuration that I'm providing is not meant for production, but it makes it
easier to make changes and test things out. It's a very minimal and simple
barbican configuration that has the "unauthenticated" context enabled. This
means that it doesn't rely on keystone, and it will use whatever roles and
project you provide in the REST API.

The default policy & how to change it
=====================================

As mentioned in the previous blog post, nowadays, the default policy in
"shipped" as part of the codebase. For some services, folks might still package
the **policy.json** file. However, for our test service (Barbican), this is not
the case.

You can easily overwrite the default policy by providing a **policy.json** file
yourself. By default, _oslo.policy_ will read the project's base directory,
and try to get the **policy.json** file from there. For barbican, this will be
**/etc/barbican/policy.json**. For keystone, **/etc/keystone/policy.json**.

It is worth noting that this file is configurable by setting the
``policy_file`` setting in your service's configuration, which is under the
``oslo_policy`` group of the configuration file.

If you have a running service, and you add or modify the **policy.json** file,
the changes will immediately take effect. No need to restart nor reload your
service.

The way this works is that olso.policy will attempt to read the file's
modification time (using ``os.path.getmtime(filename)``), and cache that. If
on a subsequent read, the modification time has changed, it'll re-read the
policy file and load the new rules.

It is also worth noting that when using **policy.json**, you don't need to
provide the whole policy, only the rules and aliases you're planning to change.

If you need to get the policy of a specific service, it's fairly
straightforward given the tools that oslo.policy provides. All you need to do
is the following:

{% highlight bash %}
oslopolicy-policy-generator --namespace $SERVICE_NAME
{% endhighlight %}

It is important to note that this will get you the effective policy that's
being executed. So, any changes that you make to the policy will be reflected
in the output of this command.

If you want to get a sample file for the default policy with all the
documentation for each option, you'll do the following:

{% highlight bash %}
oslopolicy-sample-generator --namespace $SERVICE_NAME
{% endhighlight %}

So, in order to output Barbican's effective policy, we'll do the following:

{% highlight bash %}
oslopolicy-policy-generator --namespace barbican
{% endhighlight %}

Note that this outputs the policy in yaml format, and oslo.policy reads
policy.json by default, so you'll have to tranform such file into json to take
it into use.

Setting up the testing environment
==================================

**NOTE:** If you just plan to read through this and not actually do the
exercises,  you may skip this section.

Lets clone the repository first:

{% highlight bash %}
git clone https://github.com/JAORMX/barbican-policy-tests.git
cd barbican-policy-tests
{% endhighlight %}

Now that we're in the repo, you'll notice several scripts there. To provide you
with a consistent environemnt, I decided to rely on **containeeeers!!!** So, in
order to continue, you'll need to have Docker installed in your system.

(Maybe in the future I'll update this to run with Podman and Buildah)

To build the minimal barbican container, execute the following:

{% highlight bash %}
./build-barbican-container-image.sh
{% endhighlight %}

You can verify that you have the ``barbican-minimal`` image with the ``latest``
tag by running ``docker images``.

To test that the image was built correctly and you can run barbican, execute
the following:

{% highlight bash %}
./0-run-barbican-simple.sh
{% endhighlight %}

You will notice barbican is running, and can see the name of its container with
``docker ps``. You'll notice its listening on the port 9311 on ``localhost``.

Exercises
=========

Preface
-------

In the following exercises, we'll do some changes to the Barbican policy. To do
this, it's worth understanding some things about the service and the policy
itself.

Barbican is Secret Storage as a service. To simplify things, we'll focus on the
secret storage side of things.

There are the operations you can do on a secret:

* ``secrets:get``: List all secrets for the specific project.

* ``secrets:post``: Create a new secret.

* ``secret:decrypt``: Decrypt the specified secret.

* ``secret:get``: Get the metadata for the specified secret.

* ``secret:put``: Modify the specified secret.

* ``secret:delete``: Delete the specified secret.

Barbican also assumes 5 keystone roles, and bases its policy on the usage of
these roles:

* ``admin``: Can do all operations on secrets (List, create, read, update,
  delete and decrypt)

* ``creator``: Can do all operations on secrets; This role is limited on
  other resources (such as secret containers), but we'll ignore other resources
  in this exercises.

* ``observer``: In the context of secrets, observers can only list secrets and
  view a specific secret's metadata.

* ``audit``: In the context of secrets, auditors can only view a specific
  secret's metadata (but cannot do anything else).

* ``service_admin``: can't do anything related to secrets. This role is meant
  for admin operations that change the Barbican service itself (such as
  quotas).

The Barbican default policy also comes with some useful aliases as defaults:

{% highlight json %}
{
"admin": "role:admin",
"observer": "role:observer",
"creator": "role:creator",
"audit": "role:audit",
"service_admin": "role:key-manager:service-admin",
...
}
{% endhighlight %}

So this makes overwriting specific roles fairly straight forward.

Scenario #1
-----------

The [Keystone default roles proposal][default-roles] proposes the usage of
three roles, which should also work with all OpenStack services. These roles
are: ``reader``, ``member`` and ``admin``.

Lets take this into use in Barbican, and replace our already existing
``observer`` role, for ``reader``.

In this case, we can take the alias into use, by doing very minimal changes, we
can replace the usage of ``observer`` entirely.

I have already [defined this role][policy-reader] in the aforementioned repo,
lets take a look:

{% highlight json %}
{
"observer": "role:reader"
}
{% endhighlight %}

And that's it!

Now in the barbican policy, every instance of the "rule:observer" assertion
will actually reference the "reader" role.

### Testing scenario #1

There is already a script that runs barbican and takes this policy into use.
Lets run it, and verify that we can effectively use the ``reader`` role instead
of the ``observer`` role:

{% highlight bash %}
# Run the container
./1-run-barbican-with-reader-role.sh

# Create a sample secret
./create-secret.sh

# Attempt to list the available secrets with the reader role. This
# operation should succeed.
./list-secrets.sh reader

# Attempt to list the available secrets with the observer role. This
# operation should fail.
./list-secrets.sh observer

# Once you're done, you can stop the container
{% endhighlight %}

Scenario #2
-----------

Barbican's audit role is meant to only read a very minimal set of things from
the barbican's entities. For some, this role might not be very useful, and it
also doesn't fit with Keystone's set of default roles, so lets delete it!

As before, I have already [defined a policy][policy-no-audit] for this purpose:

{% highlight json %}
{
"audit": "!"
}
{% endhighlight %}

As you can see, this replace the ``audit`` alias, and any attempt to use it
will be rejected in the policy, effectively dissallowing the ``audit`` role
use.

### Testing scenario #2

There is already a script that runs barbican and takes this policy into use.
Lets run it, and verify that we can effectively no longer use the ``audit``
role:

{% highlight bash %}
# run the container
./2-run-barbican-without-audit-policy.sh

# create a secret
./create-secret.sh

# Attempt to view the secret metadata with the creator role. This
# operation should succeed.
curl -H 'X-Project-Id: 1234' -H 'X-Roles: creator' \
    http://localhost:9311/v1/secrets/<some ID> | python -m json.tool

# Attempt to view the secret metadata with the audit role. This
# operation should fail.
curl -H 'X-Project-Id: 1234' -H 'X-Roles: audit' \
    http://localhost:9311/v1/secrets/<some ID> | python -m json.tool

# Once you're done, you can stop the container
{% endhighlight %}

Scenario #3
-----------

Now that we have tried a couple of things and it has gone fine. Lets put it all
together and replicate the Keystone default role recommendation.

Here's what we'll do: As before, we'll replace the ``observer`` role with
``reader``. We'll also replace the ``creator`` role with ``member``, and
finally, we'll remove the ``audit`` role.

Here's the policy file:

{% highlight json %}
{
"observer": "role:reader",
"creator": "role:member",
"audit": "!"
}
{% endhighlight %}

This time, we'll change the policy file in-place, as this is something you
might need to do or automate in your own deployment.

### Testing scenario #3

Here, we'll run a minimal container that doesn't take any specific policy into
use. We'll log into it, modify the policy.json file, and test out the results.

{% highlight bash %}
# Run the container
./0-run-barbican-simple.sh

# Open a bash session in the container
docker exec -ti (docker ps | grep barbican-minimal | awk '{print $1}') bash

# (In the container) Create the new policy file
cat <<EOF > /etc/barbican/policy.json
{
"observer": "role:reader",
"creator": "role:member",
"audit": "!"
}
EOF

# (In the container) Exit the container
exit

# Attempt to create a sample secret with the creator role. This operation
# should fail
./create-secret.sh creator

# Attempt to create a sample secret with the member role. This operation
# should succeed
./create-secret.sh member

# Attempt to list the available secrets with the observer role. This
# operation should fail.
./list-secrets.sh observer

# Attempt to list the available secrets with the reader role. This
# operation should succeed.
./list-secrets.sh reader

# Attempt to view the secret metadata with the audit role. This
# operation should fail.
curl -H 'X-Project-Id: 1234' -H 'X-Roles: audit' \
    http://localhost:9311/v1/secrets/<some ID> | python -m json.tool

# Attempt to view the secret metadata with the creator role. This
# operation should fail.
curl -H 'X-Project-Id: 1234' -H 'X-Roles: creator' \
    http://localhost:9311/v1/secrets/<some ID> | python -m json.tool

# Attempt to view the secret metadata with the member role. This
# operation should succeed.
curl -H 'X-Project-Id: 1234' -H 'X-Roles: member' \
    http://localhost:9311/v1/secrets/<some ID> | python -m json.tool

# Once you're done, you can stop the container
{% endhighlight %}

Scenario #4
-----------

For our last case, lets assume that for some reason you need a "super-admin"
role that is able to read everybody's secret metadata. There is no equivalent
of this role in Barbican, so we'll have to modify more things in order to get
this to work.

To simplify things, we'll only modify the GET operation for secret metadata.

Please note that this is only done for learning purposes, do not try this in
production.

First thing we'll need is to retrieve the policy line that actually gets
executed for secret metadata. In Barbican, it's the ``secret:get`` policy.

From whithin the container, or if you have the barbican package installed
somewhere, you can do the following in order to get this exact policy:

{% highlight bash %}
oslopolicy-policy-generator --namespace barbican | grep "secret:get"
{% endhighlight %}

This will get us the following line:
{% highlight yaml %}
"secret:get": "rule:secret_non_private_read or rule:secret_project_creator or rule:secret_project_admin or rule:secret_acl_read"
{% endhighlight %}

Note that in the barbican policy, we explicitly check for most users that the
user is in the same project as the project that the secret belongs to. In this
case, we'll omit this in order to enable the "super-admin" to retrieve any
secret's metadata.

Here is the final policy.json file we'll use:

{% highlight json %}
{
"super_admin": "role:super-admin",
"secret:get": "rule:secret_non_private_read or rule:secret_project_creator or rule:secret_project_admin or rule:secret_acl_read or rule:super_admin"
}
{% endhighlight %}

### Testing scenario #4

Here, we'll run a minimal container that doesn't take any specific policy into
use. We'll log into it, modify the policy.json file, and test out the results.

{% highlight bash %}
# Run the container
./0-run-barbican-simple.sh

# Open a bash session in the container
docker exec -ti (docker ps | grep barbican-minimal | awk '{print $1}') bash

# (In the container) Lets verify what the current policy is for "secret:get".
# This should output the default rule.
oslopolicy-policy-generator --namespace barbican | grep "secret:get"

# (In the container) Create the new policy file
cat <<EOF > /etc/barbican/policy.json
{
"super_admin": "role:super-admin",
"secret:get": "rule:secret_non_private_read or rule:secret_project_creator or rule:secret_project_admin or rule:secret_acl_read or rule:super_admin"
}
EOF

# (In the container) Lets verify what the current policy is for "secret:get".
# This should output the updated policy.
oslopolicy-policy-generator --namespace barbican | grep "secret:get"

# (In the container) Exit the container
exit

# Lets now create a couple of secrets with the creator role in the default
# project (1234).

# This will be secret #1
./create-secret.sh creator
# This will be secret #2
./create-secret.sh creator

# Lets now create a couple of secrets with the creator role in another project
# (1111).

# This will be secret #3
./create-secret.sh creator 1111
{% endhighlight %}

Using the creator role and project '1234', you should only be able to
retrieve secrets #1 and #2, but should get an error with secret #3.

{% highlight bash %}
# So... this should work
curl -H 'X-Project-Id: 1234' -H 'X-Roles: creator' \
    http://localhost:9311/v1/secrets/<secret #1> | python -m json.tool

# this should work
curl -H 'X-Project-Id: 1234' -H 'X-Roles: creator' \
    http://localhost:9311/v1/secrets/<secret #2> | python -m json.tool

# ...And this should fail
curl -H 'X-Project-Id: 1234' -H 'X-Roles: creator' \
    http://localhost:9311/v1/secrets/<secret #3> | python -m json.tool
{% endhighlight %}

Using the creator role and project '1111', you should only be able to
retrieve secret #3, but should get an error with secrets #1 and #2

{% highlight bash %}
# So... this should fail
curl -H 'X-Project-Id: 1111' -H 'X-Roles: creator' \
    http://localhost:9311/v1/secrets/<secret #1> | python -m json.tool

# this should fail
curl -H 'X-Project-Id: 1111' -H 'X-Roles: creator' \
    http://localhost:9311/v1/secrets/<secret #2> | python -m json.tool

# ...And this should work
curl -H 'X-Project-Id: 1111' -H 'X-Roles: creator' \
    http://localhost:9311/v1/secrets/<secret #3> | python -m json.tool
{% endhighlight %}

Finally, lets try our new ``super-admin`` role. As you will notice, you don't
even need to be part of the projects to get the metadata:

{% highlight bash %}
# So... this should work
curl -H 'X-Project-Id: POLICY' -H 'X-Roles: super-admin' \
    http://localhost:9311/v1/secrets/<secret #1> | python -m json.tool

# this should work
curl -H 'X-Project-Id: IS' -H 'X-Roles: super-admin' \
    http://localhost:9311/v1/secrets/<secret #2> | python -m json.tool

# ...And this should work too
curl -H 'X-Project-Id: COOL' -H 'X-Roles: super-admin' \
    http://localhost:9311/v1/secrets/<secret #3> | python -m json.tool
{% endhighlight %}

Conclusion
==========

You have now learned how to do simple modifications to your service's policy!

With great power comes great responsibility... And all those things... But
seriously, be careful! You might end up with unintended results.

In the next blog post, we'll cover implied roles and how you can use them in
your policies!

[test-repo]: https://github.com/JAORMX/barbican-policy-tests
[default-roles]: https://specs.openstack.org/openstack/keystone-specs/specs/keystone/rocky/define-default-roles.html
[policy-reader]: https://github.com/JAORMX/barbican-policy-tests/blob/master/policy-reader.json
[policy-no-audit]: https://github.com/JAORMX/barbican-policy-tests/blob/master/policy-remove-audit.json
