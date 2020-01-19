---
layout: post
title:  "Dissecting TripleO service templates (part 4)"
date:   2018-08-29 07:35:56 +0300
categories: tripleo openstack
image: /images/cup.jpg
---

In this series of blog posts, I've been covering all the different sections of
the service templates for TripleO.

To recap:

* On the [first part](
{% post_url 2018-08-27-dissecting-tripleo-service-templates-p1 %}) I covered
the bare-minimum sections you need for your template.

* On the [second part](
{% post_url 2018-08-27-dissecting-tripleo-service-templates-p2 %}) I covered
the sections that allow you to use Ansible to write and customize your service.

* On the [third part](
{% post_url 2018-08-28-dissecting-tripleo-service-templates-p3 %}) I covered the
sections that allow you to write a containerized service for TripleO.

Here I cover "the rest".

TripleO offers a lot of options to modify and configure your services, with all
this flexibility, we have needed to covered different common cases, and other
not so common cases. And it is also worth noting that TripleO is meant to
manage your day 2 operations for your OpenStack cloud, so this also needs to be
covered by TripleO.

Now that you know the basics, lets briefly cover the more advanced sections of
the service templates.

The overall view
================

While looking at other service templates is a good way to see what's being done
and how one can do things. If you want to know all the available options, there
is actually a file where this is gathered:
[common/services.yaml][common-services]

Here you'll find where the ResourceChain is called, so from this you can derive
the mandatory parameters from the templates. You'll also find what outputs are
gathered and how.

With this in mind, we can now continue and dive in the rest of the sections.
Given the diversity of the outputs that are left to cover; I'll try to divide
them in sections.

Extra hieradata options
=======================

These options, similarly to the ``config_settings`` section mentioned in [part
1]({% post_url 2018-08-27-dissecting-tripleo-service-templates-p1 %}), set up
appropriate hieradata, however, their usage and behavior varies.

``global_config_settings`` section
----------------------------------

While ``config_settings`` sets up hieradata for the role where the service is
deployed, ``global_config_settings`` allows you to output the needed hieradata
in all nodes of the cluster.

``service_config_settings`` section
-----------------------------------

Allows you to output hieradata to wherever a certain service is configured.
This is specially useful if your service can be a backend for another service.
Lets take Barbican as an example:

{% highlight yaml %}
service_config_settings:
  ...
  nova_compute:
    nova::compute::keymgr_backend: >
      castellan.key_manager.barbican_key_manager.BarbicanKeyManager
    nova::compute::barbican_endpoint:
      get_param: [EndpointMap, BarbicanInternal, uri]
    nova::compute::barbican_auth_endpoint:
      get_param: [EndpointMap, KeystoneInternal, uri_no_suffix]
  cinder_api:
    cinder::api::keymgr_backend: >
      castellan.key_manager.barbican_key_manager.BarbicanKeyManager
    cinder::api::keymgr_encryption_api_url:
      get_param: [EndpointMap, BarbicanInternal, uri]
    cinder::api::keymgr_encryption_auth_url:
      get_param: [EndpointMap, KeystoneInternal, uri_no_suffix]
{% endhighlight %}

In this case, the Barbican service template explicitly configures the
``nova_compute`` and ``cinder_api`` services by setting hieradata to wherever
they're at. This way, if someone enables barbican, we automatically enable the
volume encryption feature.

Update-related options
======================

These sections belong to the [update workflow][update-workflow], which is an
update within the same version (passing from one version to another is called
an upgrade).

``update_tasks`` section
------------------------

Similarly to the ``deploy_steps_tasks`` mentioned in [part 2](
{% post_url 2018-08-27-dissecting-tripleo-service-templates-p2 %}), these are
Ansible tasks that run on the node. However, these run as part of the updates
workflow at the beginning of the Ansible run. So, if you're acquainted with
this workflow, these run at the beginning of the ``openstack overcloud update
run`` command, which runs the Ansible playbook for updates. After this,
``host_prep_tasks`` and subsequently ``deploy_step_tasks`` run. Finalizing with
the ``post_update_tasks`` section.

To summarize, if your application needs to execute some actions when a minor
update is executed, which needs to happen before the TripleO steps, then you
need this section.

``post_update_tasks`` section
-----------------------------

As mentioned in the previous section, this runs at the end of the minor update
workflow. You might need this section for your service if you need to execute
some ansible tasks after the TripleO steps.

``external_update_tasks`` section
---------------------------------

While at the time of writing this no service is using this section, it might
prove to me useful at some point. This is fairly similar to the
``update_tasks`` section, except that this runs on the node that runs the
playbook (typically the undercloud). So, it also runs before the TripleO steps
as part of the updates workflow. This is meant for services that are deployed
with the ``external_deploy_tasks`` section, which was mentioned in [part 2](
{% post_url 2018-08-27-dissecting-tripleo-service-templates-p2 %}).

Upgrade-related options
=======================

These sections belong to the [upgrade workflow][upgrade-workflow]. Similarly to
the update workflow mentioned before, this is also powered via Ansible and has
a similar call path, with actions that run before and after the steps.

``upgrade_tasks`` section
-------------------------

Similarly to ``update_tasks``, this runs before the TripleO steps, but in the
upgrade workflow.

``post_upgrade_tasks`` section
------------------------------

Similarly to ``post_update_tasks``, this runs after the TripleO steps, but in
the upgrade workflow.

``external_upgrade_tasks`` section
----------------------------------

Similarly to ``external_update_tasks``, this runs before the TripleO steps, but
in the host that's calling the ansible playbook and on the upgrade workflow.

``pre_upgrade_rolling_tasks`` section
-------------------------------------

This runs before ``upgrade_tasks`` (which already runs before the TripleO
steps) and is be executed in a node-by-node rolling fashion at the beginning of
the major upgrade workflow.

This is quite a special case, where you need to take special care and do so in
a node-by-node fashion, such as was the case when upgrading the neutron
services on to containerized services. This made sure that instance
connectivity wasn't lost.

Fast Forward upgrades options
=============================

The following sections belong to the [Fast forward upgrades
workflow][ffu-workflow], which updates from one release up to 3 releases
forward (``N -> N+3``).

``fast_forward_upgrade_tasks`` section
--------------------------------------

These are carried in steps, but are also carried by release. So moving from
release to release, you'll need to specify which tasks are executed for what
release, and in what step of the deployment they're executed.

There is a maximum of 9 steps, of which the loops are divided into two
categories.

From steps 0 to 3, these are considered prep tasks, so they're ran on all nodes
containing that service.

After this, from steps 4 to 9, these are bootstrap tasks, so they're ran only
on one node that contains the service.

For more information on this, the [developer documentation is
quite][ffu-dev-docs] relevant, and the [commit that introduced
this][ffu-commit] has a great explanation.

``fast_forward_post_upgrade_tasks`` section
-------------------------------------------

Similarly to the updates and upgrades ``_post_*_tasks`` sections, this runs
after the TripleO steps on the FFU ugprades and does certain ansible tasks.

Other options
=============

``external_post_deploy_tasks`` section
--------------------------------------

In synergy with the ``external_deploy_tasks`` section described in [part 2](
{% post_url 2018-08-27-dissecting-tripleo-service-templates-p2 %}), and
similarly to other ``*_post_*`` sections, ``external_post_deploy_tasks``
executes ansible tasks on the node that runs the Ansible playbook, and this
happens after the TripleO steps.

``monitoring_subscription`` section
-----------------------------------

This is used for [sensu][sensu] integration. For all of the services, the
subscription names will be gathered and set up for the sensu client
susbcriptions.

``service_metadata_settings`` section
-------------------------------------

This belongs to the [TLS everywhere][tls-everywhere] workflow and is better
described in the [developer documentation][tls-everywhere-dev-docs]. But, in a
nutshell, this controls how the service principals are created in FreeIPA via
[novajoin][novajoin]. Eventually this information gets passed from the
templates via nova-metadata to the novajoin vendordata plugin, which
subsequently calls FreeIPA and generates the necessary service principals.

``docker_config_scripts`` section
---------------------------------

This section is meant to create scripts that will be persisted in the
``/var/lib/docker-config-scripts`` directory. It takes the following options:

* **mode**: The mode number that defines the file permissions.

* **content** the actual content of the script.

``workflow_tasks`` section
--------------------------

Allows you to execute Mistral actions or workflows for a specific service. It
was primarily used by Ceph when it was introduced, but it changed to use
Ansible directly instead.

An example would be the following:

{% highlight yaml %}
  workflow_tasks:
    step2:
      - name: echo
        action: std.echo output=Hello
    step3:
      - name: external
        workflow: my-pre-existing-workflow-name
        input:
          workflow_param1: value
          workflow_param2: value
{% endhighlight %}

``cellv2_discovery`` section
----------------------------

This is meant to be a boolean flag that indicates if a node should be
considered for cellv2 discovery. Mostly, the nova-compute and ironic services
set this flag in order for t-h-t to consider add them to the list of nodes.
Chances are, you don't need to set this flag at all, unless you do a service
that overwrites the nova-compute service.

Deprecated or unused parameters
===============================

Finally, the following parameters are deprecated, set or set for deprecation.
I'm adding them here in case you have Queens or newer templates, and with hopes
they don't confuse you.

The following commands used to be for fluentd integration:

* ``logging_sources``

* ``logging_groups``

These are no longer used, and instead, this integration is now done via
hieradata directly.

[common-services]: https://github.com/openstack/tripleo-heat-templates/blob/stable/rocky/common/services.yaml
[update-workflow]: http://tripleo.org/install/post_deployment/package_update.html
[upgrade-workflow]: https://docs.openstack.org/tripleo-docs/latest/install/post_deployment/upgrade.html
[ffu-workflow]: http://tripleo.org/install/post_deployment/fast_forward_upgrade.html
[ffu-dev-docs]: http://tripleo.org/install/developer/upgrades/fast_fw_upgrade.html
[ffu-commit]: https://review.openstack.org/#/c/499221/
[sensu]: https://github.com/sensu/sensu
[tls-everywhere]: http://tripleo.org/install/advanced_deployment/ssl.html#tls-everywhere-for-the-overcloud
[tls-everywhere-dev-docs]: http://tripleo.org/install/developer/tht_walkthrough/tls_for_services.html#internal-tls-for-services-that-don-t-run-over-httpd
[novajoin]: https://github.com/openstack/novajoin
