---
layout: post
title:  "Dissecting TripleO service templates (part 2)"
date:   2018-08-27 15:18:43 +0300
categories: tripleo openstack
---
In the [previous blog post](
{% post_url 2018-08-27-dissecting-tripleo-services-templates-p1 %}) we covered
the bare-minimum pieces you need to create a service. It was also briefly
mentioned that you can use Ansible in order to configure your service.

In the blog post about the [steps in which TripleO deploys services](
{% post_url 2018-08-27-tripleo-service-deployment-steps %}) you can notice that
there are three main bits in the deployment where Ansible is ran:

* Host prep deployment (``host_prep_tasks`` in the templates)

* External deploy tasks (``external_deploy_tasks`` in the templates)

* Deploy steps tasks (``deploy_steps_tasks`` in the templates)

Lets describe these better:


Host prep deployment (or host prep tasks)
=========================================

This is seen as ``host_prep_tasks`` in the deployment service templates.
These are Ansible tasks that run before the configuration steps start, and
before any major services are configured (such as pacemaker). Here you would
put actions such as wiping out your disk, or migrating log files.

Lets look at the output section of the example from the previous blog post:

{% highlight yaml %}
outputs:
  role_data:
    description: Role data for the RHSM service.
    value:
      service_name: rhsm
      config_settings:
        tripleo::rhsm::firewall_rules: {}
      upgrade_tasks: []
      step_config: ''
      host_prep_tasks:
        - name: Red Hat Subscription Management configuration
          vars: {get_attr: [RoleParametersValue, value, vars]}
          block:
          - include_role:
              name: redhat-subscription
{% endhighlight %}

Here we see that an Ansible role is called directly from the
``host_prep_tasks`` section. In this case, we're setting up the Red Hat
subscription for the node where this is running. We would definitely want this
to happen in the very beginning of the deployment, so ``host_prep_tasks`` is an
appropriate place to put it.

External deploy tasks
=====================

These are Ansible tasks that take place in the node where you executed the
"overcloud deploy". You'll find these in the service templates in the
``external_deploy_tasks`` section. These actions are also ran as part of the
deployment steps, so you'll have the ``step`` fact available in order to limit
the ansible tasks to only run on a specific step. Note that this runs on each
step before the "deploy steps tasks", the puppet run, and the container
deployment.

Typically you'll see this used when, to configure a service, you need to
execute an Ansible role that has special requirements for the Ansible
inventory.

Such is the case for deploying OpenShift on baremetal via TripleO. The Ansible
role for deploying OpenShift requires several hosts and groups to exist in the
inventory, so we set those up in ``external_deploy_tasks``:

{% highlight yaml %}
...
{% raw %}
- name: generate openshift inventory for openshift_master service
  copy:
    dest: "{{playbook_dir}}/openshift/inventory/{{tripleo_role_name}}_openshift_master.yml"
    content: |
      {% if master_nodes | count > 0%}
      masters:
        hosts:
        {% for host in master_nodes %}
        {{host.hostname}}:
            {{host | combine(openshift_master_node_vars) | to_nice_yaml() | indent(6)}}
        {% endfor %}
      {% endif %}

      {% if new_masters | count > 0 %}
      new_masters:
        hosts:
        {% for host in new_masters %}
        {{host.hostname}}:
            {{host | combine(openshift_master_node_vars) | to_nice_yaml() | indent(6)}}
        {% endfor %}

      new_etcd:
        children:
          new_masters: {}
      {% endif %}

      etcd:
        children:
          masters: {}

      OSEv3:
        children:
          masters: {}
          nodes: {}
          new_masters: {}
          new_nodes: {}
          {% if groups['openshift_glusterfs'] | default([]) %}glusterfs: {}{% endif %}
{% endraw %}
{% endhighlight %}

In the case of OpenShift, Ansible itself is also called as a command from here,
using variables and the inventory that's generated in this section. This way we
don't need to mix the inventory that the overcloud deployment itself is using
with the inventory that the OpenShift deployment uses.

Deploy steps tasks
==================

These are Ansible tasks that take place in the overcloud nodes. Note that like
any other service, these tasks will only execute on the nodes whose role has
this service enabled. You'll find this as the ``deploy_steps_tasks`` section in
the service templates. These actions are also ran as part of the deployment
steps, so you'll have the ``step`` fact available in order to limit the
ansible tasks to only run on a specific step. Note that on each step, this runs
after the "external deploy tasks", but before the puppet run and the container
deployment.

Typically you'll run quite simple tasks in this section, such as setting the
boot parameters for the nodes. Although, you can also run more complex roles,
such as the IPSec service deployment for TripleO:

{% highlight yaml %}
...
- name: IPSEC configuration on step 1
  when: step == '1'
  block:
  - include_role:
      name: tripleo-ipsec
    vars:
      map_merge:
      - ipsec_configure_vips: false
        ipsec_skip_firewall_rules: false
      - {get_param: IpsecVars}
...
{% endhighlight %}

This type of deployment applies for services that are better tied to TripleO's
Ansible inventory or that don't require a specific inventory to run.

Conclusion
==========

With these three options you can already build quite powerful service
templates powered by Ansible. Please note that full support for "external
deploy tasks" and "deploy steps tasks" came on the Rocky release; so this is
not available for Queens.

Finally, in the next part of the series, I'll describe all the relevant parts
of the service template in order to deploy containerized services as
implemented in TripleO.
