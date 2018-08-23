---
layout: post
title:  "Spawning your first OpenStack instance with Ansible"
date:   2018-02-05 12:50:57 +0200
categories: openstack
---

Great, so you got access to an OpenStack cloud, got your credentials ready, and
even spawned a test instance through Horizon. Life is great! You're proud that
you're finally getting the hang out of this OpenStack thingy.

But... doing this through horizon is slow...

Then you figure out that doing it through the CLI is actually kinda slow as
well.

Do I have to do all those clicks, or all those commands every time? Maybe I'll
just hook everything up in a bash script and hope I never have to extend it.

or... maybe I can just use Ansible!

The OpenStack Ansible modules are cool
--------------------------------------

Staying true to their statement of aiming to automate thing in a simple manner,
the OpenStack ansible modules are already quite simple and usable.

In case you're wondering where they are, here's the
[list of OpenStack modules][modules].

But before you dive into writing your playbooks just yet, lets do one thing
first.

Writing your clouds.yaml
------------------------

Remember when you where using the OpenStack CLI? You needed to source a file
(maybe called openrc or overcloudrc) that contains your user credentials, as
well as the authentication URL and some other values that you might or might
not be very acquainted with.

While you could still use these environment variables to run your
ansible playbooks, you could also specify them in a file called *clouds.yaml*.

[clouds.yaml][clouds-yaml] allows you to specify several parameters to access
your cloud provider, such as the authentication credentials, the region to use,
as well as logging configurations and some other OpenStack client-specific
configurations.

It can be very useful if you have access to several OpenStack providers, since
all you'll need to do is specify the name of the provider, and it'll
immediately use the credentials you set on its respective section.

A very simple *clouds.yaml* will look as follows:

{% highlight yaml %}
clouds:
  mariachicloud:
    auth:
      auth_url: https://:5000/
      project_name: pedro-infante
      username: pedro-infante
      project_domain_name: Default
      user_domain_name: Default
      password: This is an ultra-super-secure password and nobody can guess it.
    region_name: regionOne
    interface: public
    identity_api_version: 3
{% endhighlight %}

This defines a cloud called mariachicloud that you can reference from both ansible
and your OpenStack CLI. So, if you want to take it into use from the OpenStack
CLI, you could do the following:

{% highlight bash %}
openstack --os-cloud rdocloud server list
{% endhighlight %}

This will list the instances spawned in your project on your mariachicloud
account. Note that the important thing is to specify your cloud with the
``--os-cloud`` parameter. When doing openstack commands, there are three places
that the client will look for the *clouds.yaml* file:

* The current working directory
* The ``~/.config/openstack`` directory
* The ``/etc/openstack`` directory

A sample playbook
-----------------

Here's a simple playbook that shows how to spawn an instance in the
"mariachicloud" cloud provider
{% highlight yaml %}
---
- name: Create a test environment
  hosts: localhost
  tasks:
    - name: create network
      os_network:
        cloud: mariachicloud
        state: present
        name: test-network
        external: false
        wait: yes

    - name: create subnet
      os_subnet:
        cloud: mariachicloud
        state: present
        network_name: test-network
        name: test-subnet
        cidr: 192.168.1.0/24
        dns_nameservers:
          - 8.8.8.8
        wait: yes

    - name: create a router
      os_router:
        cloud: mariachicloud
        state: present
        name: test-router
        network: test-external-network
        interfaces:
          - test-subnet

    - name: create security group
      os_security_group:
        cloud: mariachicloud
        state: present
        name: test-security-group
        description: Security group for our test instances

    - name: create security group rule for ping
      os_security_group_rule:
        cloud: mariachicloud
        security_group: test-security-group
        protocol: icmp
        remote_ip_prefix: 0.0.0.0/0

    - name: create security group rule for SSH
      os_security_group_rule:
        cloud: mariachicloud
        security_group: test-security-group
        protocol: tcp
        port_range_min: 22
        port_range_max: 22
        remote_ip_prefix: 0.0.0.0/0

    - name: create instance
      os_server:
        state: present
        cloud: mariachicloud
        name: test-instance
        image: CentOS-7-x86_64-GenericCloud
        key_name: mariachi-pub-key
        timeout: 200
        flavor: m1.small
        network: test-network
        auto_ip: yes
        security_groups:
          - test-security-group
      register:
        my_instance

    - name: Get floating IPv4
      debug:
        msg: "{{ my_instance.server.public_v4 }}"

    - name: Get floating IPv6
      debug:
        msg: "{{ my_instance.server.public_v6 }}"
{% endhighlight %}

This playbook makes the following assumptions:

* We already have an external network for our project, in our case it's called
  **test-external-network**.

* We have already created a keypair with which we can access the instance. In
  our case it's called **mariachi-pub-key**.

* there is an image uploaded already that's called
  **CentOS-7-x86_64-GenericCloud**.

* There is a flavor created already that's called **m1.small**.

With this in mind, the playbook itself will create:

* A network called **test-network**.
* A subnet in that network, called **test-subnet**.
* A router that's connected to the subnet and the external network. The
  router's name is **test-router**.
* A security group called **test-security-group**.
* Two rules for the aforementioned security group.
  - One rules allows all ping traffic to come into the instance (the default
    direction for the rule is ingress).
  - Another rule that allows SSH traffic into the instance.
* One instance called **test-instance**. This instance is using the
  aforementioned security group, and is also connected to our test-network.
  Besides this, we set the ``auto_ip`` parameter, which automatically assigns a
  floating IP to the instance, which we can use to access the instance.

The last two tasks in our playbook will give us the floating IP address that we
can use to access our instance.

[modules]: http://docs.ansible.com/ansible/latest/list_of_cloud_modules.html#openstack
[clouds-yaml]: https://docs.openstack.org/python-openstackclient/latest/configuration/index.html
