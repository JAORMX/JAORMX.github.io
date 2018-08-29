---
layout: post
title:  "TripleO service deployment steps"
date:   2018-08-27 14:28:08 +0300
categories: tripleo openstack
---

TripleO does a lot of things in the whole deployment process, from setting up
the appropriate networks, to provisioning the baremetal hosts. However, there
is a significant part of the deployment in which services are configured. This
part of the deployment is done in 5 steps. What happens in these steps has
traditionally been the following:

**1)** Load Balancer configuration

**2)** Core Services (Database/Rabbit/NTP/etc.)

**3)** Early Openstack Service setup (Ringbuilder, etc.)

**4)** General OpenStack Services

**5)** Service activation (Pacemaker) & Service post-configuration (e.g. nova
       host discovery)

This has tended to be done by Puppet, however, with the arrival of containers
to the deployment, and the need to provide more options to deploy the services,
there are now several things happening in between these steps. These would be
the overall steps nowadays:

* Host prep deployment (ansible tasks)

* Containers config files generated per hiera settings.

* Load Balancer configuration baremetal

    - external deploy step tasks (ansible tasks)

    - deploy step tasks (ansible tasks)

    - step 1 baremetal (puppet)

    - step 1 containers

* Core Services (Database/Rabbit/NTP/etc.)

    - external deploy step tasks (ansible tasks)

    - deploy step tasks (ansible tasks)

    - step 2 baremetal (puppet)

    - step 2 containers

* Early Openstack Service setup (Ringbuilder, etc.)

    - external deploy step tasks (ansible tasks)

    - deploy step tasks (ansible tasks)

    - step 3 baremetal (puppet)

    - step 3 containers

* General OpenStack Services

    - external deploy step tasks (ansible tasks)

    - deploy step tasks (ansible tasks)

    - step 4 baremetal (puppet)

    - step 4 containers

    - Keystone containers post initialization (tenant,service,endpoint creation)

* Service activation (Pacemaker)

    - external deploy step tasks (ansible tasks)

    - deploy step tasks (ansible tasks)

    - step 5 baremetal (puppet)

    - step 5 containers

It's useful to have the overall picture. Next, I'll try to explain the details
that are relevant to understanding what happens in each step and before them.

* **Host prep deployment**: This is seen as ``host_prep_tasks`` in the
  deployment service templates. These are ansible tasks that run before the
  configuration steps start. Typically because you want these steps to happen
  before the pacemaker configuration. Here you would put actions such as
  wiping out your disk, or migrating log files.

* **Container config files**: While traditionally, the configuration was done
  via puppet in each step. This changed when containers came around. Nowadays,
  the configuration files for containerized services are generated all in one
  go, before the steps happen. Subsequently, containers are started in the step
  that they would usually be started by puppet.

* **External deploy step tasks**: These are tasks that are ran from the node
  that's doing the deployment (typically the undercloud). These are powered by
  Ansible.

* **Deploy step tasks**: These are tasks that are ran on every overcloud node
  of a certain role. These are also powered by Ansible.

* **Baremetal step**: This will typically be the execution of the
  ``step_config`` statement in the service templates. Note that this will only
  happen for a service if it's configured to run on baremetal.

* **Container step**: This will initiate the containers that are configured to
  run on a certain step.

With these brief explanations, I hope you have a better notion of what's going
on in the deployment steps. If you want more in-depth knowledge about these
steps, I'm also writing a services of blog posts that describe the service
templates; which include way more detail. The series starts with a blog post
describing the [minimal things you need for your service template](
{% post_url 2018-08-27-dissecting-tripleo-service-templates-p1 %})
