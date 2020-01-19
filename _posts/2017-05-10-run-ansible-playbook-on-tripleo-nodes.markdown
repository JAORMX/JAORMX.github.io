---
layout: post
title:  "Run ansible playbook on TripleO nodes"
date:   2017-05-10 09:22:13 +0300
categories: tripleo openstack
image: /images/cup.jpg
---

Running an ansible playbook on TripleO nodes is fairly simple thanks to the
work done by the folks working on tripleo-validations. There's no need to
manually maintain an inventory file with all the nodes as there is already a
dynamic inventory script set up for us.

So, using an ansible playbook would look as the following:

{% highlight bash %}
$ source ~/stackrc
$ ansible-playbook -i /usr/bin/tripleo-ansible-inventory path/to/playbook.yaml
{% endhighlight %}

This will use localhost for the undercloud node and fetch the nodes from nova
to get the overcloud nodes. There are also roles already available such as
controllers and computes, which can be accessed in your playbooks with the keys
"controller" and "compute" respectively. And support is coming for dynamic
roles as well.

So, for a simple example, lets say we want to install the Libreswan package in
all the overcloud nodes. It would be done with a playbook that looks as the
following:

{% highlight bash %}
---
- hosts: overcloud
  become: true
  tasks:
  - name: Install libreswan
    yum:
      name: libreswan
      state: latest
{% endhighlight %}
