---
layout: post
title:  "Oslo Policy Deep Dive p3"
date:   2018-10-09 12:59:34 +0300
categories: tripleo openstack
author: Juan Antonio Osorio Robles & Adam Young
---

One of the biggest flaws in the OpenStack implemetnation of RBAC policy is the
longstanding bug 96869: https://bugs.launchpad.net/keystone/+bug/968696

To understand this bug, we have to look at how role assignments work in
Keystone.

The most common form of A Role Assignment links a user, a role, and a project.

For example, User: adam, Role: Member, project: Dynamo

Example
-------

Lets take our beloved Barbican service as an example.

We control access to the ability to decrypt secrets in Barbican using RBAC.
Only users with the role of creator and admin can do this.
If I want to decrypt a secret inside the Dynamo project, I should check that
the user presents a token scoped to the Dynamo project. If I have a role on
another project called Exotherm, I should not be able to use a token scoped to
Exotherm in order to do anything inside Dynamo. A simplified policy rule looks
something like this:

{% highlight yaml %}
"admin": "role:admin"
"secret_project_match": "project:%(target.secret.project_id)s"
"secret_creator_user": "user:%(target.secret.creator_id)s"
"secret_project_creator": "rule:creator and rule:secret_project_match and rule:secret_creator_user"
"secret_project_admin": "rule:admin and rule:secret_project_match"
"secret:decrypt": "rule:secret_project_creator or rule:secret_project_admin"
{% endhighlight %}

Here we have a two part rule connected by an "And" rule. This means that both
parts would need to be true.

The first rule enforces that the auth_data associated with the token presented
by the user has the role "Member" in it.

The second part enforces that the auth_data associated with the token
presented by the user is scoped to the same project as is the target of the
request. In this case, this would be the id of the project within which the
user is trying to create the network.

Lets assume (to make it more readable) that the projects named Dynamo and
Exotherm had the IDs of D555 and E777 respectively.

If I presented a token that had project ID: D555 but tried to create a Network
inside of project with id of E7777, this rule would reject it.

If I presented a token that only had the rule "Reader" in it when I tried to
create a network, even if the project IDs matched, this rule would reject it.

Going back to bug 968696, we find that many of the services in OpenStack have a
default admin test that looks like this:

{% highlight yaml %}
"context_is_admin": "role:admin",
"default": "role:admin",
{% endhighlight %}

That one is from glance.

What this means is that if a user has a token with the admin role on project
D555 and they present that when they are trying to create a network inside the
proejct with id E7777, they are allowed to do so.

Admin anywhere is Admin everywhere.

When you are writing policies for OpenStack services, you want to incorporate
this two part rule structure. Every rule should have both a Role and a Scope
associated with it.
