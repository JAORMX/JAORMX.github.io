---
layout: post
title:  "TripleO Denver 2018 PTG notes"
date:   2018-09-14 15:04:21 -0600
categories: tripleo openstack
image: /images/cup.jpg
---

I recently had the opportunity to attend the OpenStack PTG at Denver. It's
always good to see folks face to face :D. Here are my notes on what I thought
was relevant.

Edge edge edge
==============

A big topic in the PTG has been Edge. On the Working Group perspective, the
discussion was more focused on identifying the Edge cases, and figuring out
appropriate architectures for them, while at the same time, trying to come up
with gaps in the projects that we could tackle.

On the TripleO side, the discussion is slightly more focused, as the main issue
is to figure out how to deploy a base architecture that will cover our most
sought for cases.

Currently, some "Edge" TripleO deployments have different entire TripleO
deployments per edge deployment (undercloud, overcloud and all).

To address this issue, and try to make the deployments more lightweight. There
are several ideas and approaches:

* One of the proposals is to move away from having each deployment be a heat
  stack, and instead leverage ansible to provide a base deployment, and fill in
  the gaps with variables. This has the advantage of making very lightweight
  deployments (heat stacks are expensive), and exposing very clear repeatable
  edge architectures.

* Another idea was to have our baremetal deployment driven by metalsmith
  instead of Heat/Nova. This would reduce the load on Heat/Nova, and instead
  rely on Ansible. This would allow us to have some failure tolerance, where
  folks can deploy large amounts of machines, and the deployment won't
  necessarily fail if one node fails.

* There is the approach for split deployments, where each set of machines is
  represented by a stack. You would deploy the control plane, and subsequently
  you would deploy sets of computes (on each edge cluster), with their
  respective storage. The leaf nodes would require information (passwords,
  IPs and such) from the central control plane nodes' stack. Ollie Walsh
  already has a POC working with this, and will continue working on ironing out
  this approach and making it more accessible. Ultimately, this approach seems
  like the most likely to come in the near future, since it relies on already
  existing things in TripleO, and only minimal changes are required.

To make TripleO be more "Edge-friendly" there are still a lot of things that we
need to add to the engine. One of them is making routed networks available to
TripleO's internal networks, and not just the control plane. This will allow to
have different network segments on the edge sites, while having our interfaces
such as the ServiceNetMap work as expected with the segments.

Python 3
========

With the on-going OpenStack wide goal of switching to python 3, there are
several implications and work items that we need to do in TripleO in order to
get this properly working and tested.

Alex Schultz has been looking into this, and it seems that at least on the
TripleO side we're quite well off into having our tooling run on python 3.
Being a deployment engine, however, we do depend on other projects supporting
python 3.

To test all this, we also need to run our deployment in an environment that has
python 3 by default. CentOS (what we currently use to test), doesn't have this.
So the proposal has been brought up to start building Fedora 28 container
images. This way, we can move forward in our python 3-based deployments
testing. This will require a lot of work though, since Kolla currently doesn't
build container images for Fedora. Alternatives will be investigated.

Standalone OpenStack with TripleO
=================================

Work has been done to get TripleO to deploy a standalone one-node OpenStack
instance, such as Packstack is able to do. There were a bunch of folks trying
it out and the results seem quite promising. Here is the relevant
[documentation][standalone-docs]. The big advantage in this is that it'll
enable developers to test out their features in a faster manner than the
regular full blown deployment, allowing for faster deployment times and faster
iterations. The reason being that it's no longer an undercloud and an
overcloud, but one node that contains the base OpenStack services.

We'll also switch several of our multinode scenario jobs to run standalone
deployments. This will enable us to have faster CI times and more lightweight
testing environments. However, this also means that the scenarios will have a
reduced set of services, given that the nodes we get from infra are quite
limited. This will result in us introducing more scenarios to make up for this.
However, we would still benefit from shorter CI runs.

tripleo-quickstart / -extras merging
=====================================

This used to be kept separate for historical reasons, but in the near future,
the plan is to merge these two repositories. This will make it easier for folks
to make changes and find the relevant places to make such changes.
Subsequently, if other projects (such as infrared), would like to use parts of
tripleo-quickstart, these will be divided in roles in separate repos, as
requests come.

Ansible
=======

With us moving more and more into ansible, our current repo structure is
getting more challenging to understand. Where does heat end and ansible begin?

To address this issue, efforts are being made to move the ansible bits into
[tripleo-specific ansible roles][ansible-roles-spec]. Right now, the plan is to
move each service to have it's own repository with the relevant role. However,
this plan is still open for discussion.

There is also the need to run tasks when deleting a host, or scaling down. This
used to work since Heat used to manage the deployment, so we would run
scripts based on heat triggering a DELETE action. With the move to Ansible,
this no longer works. So a [spec][ansible-scale-down] has been proposed in
order to address this. The plan is to introduce new sections to the service
deployment, and run specific ansible tasks on a specialized command that will
execute the scale down. This will be very useful, for instance, when scaling
down and needing to unregister the RHEL node.

Security
========

Password rotation
-----------------

Password rotation for some services was broken when we moved our services to
containers. Specifically there's the issue of changing the master MySQL
password, which, currently breaks as the new password is used, and we're not
able to set the new one. Steps are being taken to address this, and in order
to avoid regressions, we'll create a periodic job that will run this action.
Here is where the standalone job approach shines, since we can have a fairly
fast and lightweight job to only test this capability. Ultimately, we'll want
to notify folks that care about this job when it breaks, so the ability to
notify specific people in a Squad will be added to CI.

Another issue that was brought up, is that password rotation requires service
restarts. So there is no clean way in OpenStack in general to rotate passwords
without service interruptions. Not a lot we can do in TripleO, but I'll bring
this up to the OpenStack TC to see if we can make this a community goal;
similarly to the work that was done to make the "debug" option tunable on
runtime.

SELinux support for containers
------------------------------

With the move to supporting podman as a container deployment tool, we are also
looking into getting our containers to play nicely with SELinux. This work is
being lead by Cédric Jeanneret and is a great improvement on TripleO security.

Unfortunately this is not so simple to test upstream, as we get our SELinux
rules from RHEL, down to OpenStack.

The proposal to get better visibility on our support for SELinux is to enable
better logging in our jobs. We'll still run with SELinux in permissive mode,
however, we can enable more logs and even notifications to the security squad
whenever new breakages in the policy happen.

Secret management in TripleO
----------------------------

My team has been working in getting oslo.config to have the ability to fetch
the values from different drivers. Castellan will be one of these drivers,
which could subsequently use Vault to fetch data in a more secure manner.

This work is moving forward, however, time is soon coming to see how we'll hook
this up to TripleO.

This is not as straight-forward as it seems. If we want to keep the
sensitive data to be as safe as possible (which is the whole point), we want to
avoid duplicating this in other places (like heat or ansible) where it could
end up unencrypted. One of the ideas was to bring up a temporary instance of
Vault where we would store all the sensitive data, and eventually copy the
encrypted database to the overcloud.

This is still quite raw, and we hope to solidify a sane approach in the coming
months.

UX / UI
=======

In a nutshell, there will be on-going work to make the CLI and the UI converge
better, so they'll use the same mistral interfaces and have similar workflows
for doing things. This might result in breaking some old CLI commands in favor
of workflows similar to what we do in the UI, however, this will reduce the
testing matrix and hopefully the code-base as well.

Our validations framework will also be re-vamped, to uniformly depend on
Mistral for running. This way, it can be leveraged from both the UI and the CI.
The hope is to standardize and make validations part of the service
definitions, this will make validations more visible to other developers and
improve the experience.

Finally, work is coming for a framework for folks to be able to generate roles
safely. The issue is that when building custom roles, it's not apparent what
services are needed, and what services can be deployed together, or even which
services conflict (such as is the case for ODL). So having a tool to generate
roles, and that contains enough information to resolve such metadata about the
services, would be a great usability improvement for deployers.

Getting rid of Nova in the undercloud
=====================================

It was brought up that there is on-going work to remove Nova and expose more
explicit options for folks to deploy their baremetal nodes. This is quite
beneficial to TripleO as it will make the undercloud a lot lighter than before,
while also giving deployers more flexibility and features for their baremetal
deployments. It also opens TripleO to the possibility of becoming a more
general case baremetal provisioning framework. We already are able to deploy
OpenShift on baremetal, hopefully the more this is used, the more use-cases and
feature requests we get in order to make TripleO more usable for folks outside
of OpenStack.

The baremetal deployment would be driven by a tool called
[metalsmith][metalsmith] which leverages ironic, glance and neutron. Good
progress has been already made, and there's even a [patch][metalsmith-patch] to
enable this workflow.

While this work might land on Stein, it won't be enabled by default, since
there are still many things to figure out; such as how to upgrade from a heat
stack that uses Nova resources, to the nova-less approach. Another thing to
figure out is how to make the TLS everywhere workflow work without nova, since
currently we rely on nova-metadata and a vendor-data plugin to make this work.
Given the community seemed to have positive feelings about the metalsmith
approach, it seems relevant that we come up with an alternative approach for
TLS everywhere that we'll introduce in the T release. Since we now have
config-download as a default, using Ansible to make TLS everywhere work is
probably the way to go.

Major OS upgrades
=================

In an effort to make TripleO handle more and more scenarios, and to make
operator's lives easier, it's only a natural step that TripleO also manages
major OS upgrades. Currently our major upgrade workflow only handles major
OpenStack version upgrades, but we haven't taken into account major version
upgrades for the Operating System. This type of workflow is quite complex.

In a nutshell, the proposed solution, while destructive in some ways, is
probably the only sane way to go.

In a nutshell, the current plan is:

* Tear down and unprovision the first controller baremetal node. (if the node
  would be enrolled to FreeIPA, here we could delete it).

* Get ironic to provision the node again with the new OS installed.

* Update the OpenStack RPMs.

* Pull the new containers.

* Stop pacemaker services on the other controllers.

* Backup the database from the one of the other controllers on to the first
  controller which has been updated already.

* Run per-service upgrade steps.

* Upgrade the database (mariaDB).

* Restart pacemaker on the first controller.

* Force galera restart.

* Run the regular deployment steps.

* Shut down vrouters on the rest of the controllers.

* Delete and unprovision the rest of the controllers

* Add them to the pacemaker cluster.

* ???

* profit.

This was a rough sketch of the rough plan that was thought of in a long
discussion about this. Several other options where discussed (such as a
big-bang approach that unprovisions all the nodes and puts them up at the same
time). However, this seemed to address most of the concerns that people came up
with.

A blueprint will be written with a more structured workflow and hopefully we'll
have a working solution in the future.

[standalone-docs]: http://tripleo.org/install/containers_deployment/standalone.html
[ansible-roles-spec]: https://blueprints.launchpad.net/tripleo/+spec/ansible-tasks-to-role
[ansible-scale-down]: https://blueprints.launchpad.net/tripleo/+spec/scale-down-tasks
[metalsmith]: https://github.com/openstack/metalsmith
[metalsmith-patch]: https://review.openstack.org/#/c/576856/
