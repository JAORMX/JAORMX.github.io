---
layout: post
title:  "Dissecting TripleO service templates (part 3)"
date:   2018-08-28 07:38:12 +0300
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

This covers the sections that allow you to write a containerized service for
TripleO.

Containerized services brought a big change to TripleO. From packaging puppet
manifests and relying on them for configuration, we now have to package
containers, make sure the configuration ends up in the container somehow, then
run the containers. Here I won't describe the whole workflow of how we
containerized OpenStack services, but instead I'll describe what you need to
know to deploy a containerized service with TripleO.

Lets take a look at an example. Here's the output section of the containerized
etcd template in t-h-t:

{% highlight yaml %}
outputs:
  role_data:
    description: Role data for the etcd role.
    value:
      service_name: {get_attr: [EtcdPuppetBase, role_data, service_name]}
      ...
      config_settings:
        map_merge:
          - {get_attr: [EtcdPuppetBase, role_data, config_settings]}
          - etcd::manage_service: false
      # BEGIN DOCKER SETTINGS
      puppet_config:
        config_volume: etcd
        config_image: &etcd_config_image {get_param: DockerEtcdConfigImage}
        step_config:
          list_join:
            - "\n"
            - - "['Etcd_key'].each |String $val| { noop_resource($val) }"
              - get_attr: [EtcdPuppetBase, role_data, step_config]
      kolla_config:
        /var/lib/kolla/config_files/etcd.json:
          command: /usr/bin/etcd --config-file /etc/etcd/etcd.yml
          config_files:
            - source: "/var/lib/kolla/config_files/src/*"
              dest: "/"
              merge: true
              preserve_properties: true
          permissions:
            - path: /var/lib/etcd
              owner: etcd:etcd
              recurse: true
      docker_config:
        step_2:
          etcd:
            image: {get_param: DockerEtcdImage}
            net: host
            privileged: false
            restart: always
            healthcheck:
              test: /openstack/healthcheck
            volumes:
              - /var/lib/etcd:/var/lib/etcd
              - /etc/localtime:/etc/localtime:ro
              - /var/lib/kolla/config_files/etcd.json:/var/lib/kolla/config_files/config.json:ro
              - /var/lib/config-data/puppet-generated/etcd/:/var/lib/kolla/config_files/src:ro
            environment:
              - KOLLA_CONFIG_STRATEGY=COPY_ALWAYS
      docker_puppet_tasks:
        # Etcd keys initialization occurs only on single node
        step_2:
          config_volume: 'etcd_init_tasks'
          puppet_tags: 'etcd_key'
          step_config:
            get_attr: [EtcdPuppetBase, role_data, step_config]
          config_image: *etcd_config_image
          volumes:
            - /var/lib/config-data/etcd/etc/etcd/:/etc/etcd:ro
            - /var/lib/etcd:/var/lib/etcd:ro
...
{% endhighlight %}

Here, we can already see some familiar sections:

* ``service_name``: Typically you want the service name to match the
  non-containerized service's name, so here we directly call the
  ``service_name`` output.

* ``config_settings``: Since we still use puppet to configure the service, we
  still take the hieradata into use, so we use the same hieradata as the
  non-containerized template, and add any extra hieradata we need.

After these, the rest are container-only sections. So lets describe them in
more detail

``puppet_config`` section
-------------------------

As I mentioned in a [previous blog post](
{% post_url 2018-08-27-tripleo-service-deployment-steps %}), before getting
into the steps where TripleO starts running services and containers, there is
a step where puppet is ran in containers and all the needed configurations are
created. The ``puppet_config`` section controls this step.

There are several options we can pass here:

* ``puppet_tags``: This describes the puppet resources that will be allowed to
  run in puppet when generating the configuration files. Note that deeper
  knowledge of your manifests and what runs in puppet is required for this.
  Else, it might be better to generate the configuration files with Ansible
  with the mechanisms described in a [previous blog post](
  {% post_url 2018-08-27-dissecting-tripleo-service-templates-p2 %}).
  Any service that specifies tags will have the default tags of
  ``'file,concat,file_line,augeas,cron'`` appended to the setting.
  To know what settings to set here, as mentioned, you need to know your puppet
  manifests. But, for instance, for keystone, an appropriate setting would be:
  ``keystone_config``. For our etcd example, no tags are needed, since the
  default tags we set here are enough.

* ``config_volume``: The name of the directory where configuration files
  will be generated for this service. You'll eventually use this to know what
  location to bind-mount into the container to get the configuration. So, the
  configuration will be persisted in:
  ``/var/lib/config-data/puppet-generated/<config_volume>``

* ``config_image``: The name of the container image that will be used for
  generating configuration files. This is often the same container
  that the runtime service uses. Some services share a common set of
  config files which are generated in a common base container. Typically
  you'll get this from a paremeter you pass to the template, e.g.
  ``<Service name>Image`` or ``<Service name>ConfigImage``. Dealing with these
  images requires dealing with the [``container image prepare``
  workflow][image-prepare-workflow]. The parameter should point to the specific
  image to be used, and it'll be pulled from the registry as part of the
  deployment.

* ``step_config``: Similarly to the ``step_config`` that I described in the
  [first blog post of this series](
  {% post_url 2018-08-27-dissecting-tripleo-service-templates-p1 %}) this
  setting controls the puppet manifest that is ran for this service.
  The aforementioned puppet tags are used along with this manifest to generate
  a config directory for this container.

One important thing to note is that, if you're creating a containerized
service, you don't need to output a ``step_config`` section from the
``roles_data`` output. TripleO figured out if you're creating a containerized
service by checking for the existence of the ``docker_config`` section in the
``roles_data`` output.

``kolla_config`` section
------------------------

As you might know, TripleO uses kolla to build the container images. Kolla,
however, not only provides the container definitions, but provides a rich
framework to extend and configure your containers. Part of this is the fact
that it provides an entry point that receives a configuration file, with which
you can modify several things from the container on start-up. We take advantage
of this in TripleO, and it's exactly what the ``kolla_config`` represents.

For each container we create, we have a relevant ``kolla_config`` entry, with a
mapping key that has the following format:

    /var/lib/kolla/config_files/<container name>.json

This, contains YAML that represents how to map config files into the container.
In the container, this typically ends up mapped as
``/var/lib/kolla/config_files/config.json`` which kolla will end up reading.

The typical configuration settings we use with this setting are the following:

* ``command``: This defines the command we'll be running on the container.
  Typically it'll be the command that runs the "server". So, in the example you
  see ``/usr/bin/etcd ...``, which will be the main process running.

* ``config_files``: This tells kolla where to read the configuration files
  from, and where to persist them to. Typically what this is used for is that
  the configuration generated by puppet is read from the host as "read-only",
  and mounted on ``/var/lib/kolla/config_files/src``. Subsequently, it is
  copied on to the right location by the kolla mechanisms. This way we make
  sure that the container has the right permissions for the right user, given
  we'll typically be in another user namespace in the container.

* ``permissions``: As you would expect, this sets up the appropriate
  permissions for a file or set of files in the container.

``docker_config`` section
-------------------------

This is the section where we tell TripleO what containers to start. Here, we
explicitly write on which step to start which container. Steps are set as keys
with the ``step_<step number>`` format. Inside these, we should set up keys
with the specific container names. In our example, we're running only the etcd
container, so we use a key called ``etcd`` to give it such a name. A tool
called [paunch][paunch] will read these parameters, and start the containers
with those settings.

In our example, this is the container definition:

{% highlight yaml %}
step_2:
  etcd:
    image: {get_param: DockerEtcdImage}
    net: host
    privileged: false
    restart: always
    healthcheck:
      test: /openstack/healthcheck
    volumes:
      - /var/lib/etcd:/var/lib/etcd
      - /etc/localtime:/etc/localtime:ro
      - /var/lib/kolla/config_files/etcd.json:/var/lib/kolla/config_files/config.json:ro
      - /var/lib/config-data/puppet-generated/etcd/:/var/lib/kolla/config_files/src:ro
    environment:
      - KOLLA_CONFIG_STRATEGY=COPY_ALWAYS
{% endhighlight %}

This is what we're telling TripleO to do:

* Start the container on step 2

* Use the container image coming from the ``DockerEtcdImage`` heat parameter.

* For the container, use the host's network.

* The container is not [privileged][privileged-containers].

* Docker will use the ``/openstack/healthcheck`` endpoint for healthchecking

* We tell it what volumes to mount

    - Aside from the necessary mounts, note that we're bind-mounting the
      file ``/var/lib/kolla/config_files/etcd.json`` on to
      ``/var/lib/kolla/config_files/config.json``. This will be read by kolla
      in order for the container to execute the actions we configured in the
      ``kolla_config`` section.

    - We also bind-mount ``/var/lib/config-data/puppet-generated/etcd/``, which
      is where the puppet ran (which was ran inside a container) persisted the
      needed configuration files. We bind-mounted this to
      ``/var/lib/kolla/config_files/src`` since we told kolla to copy this to
      the correct location inside the container on the ``config_files`` section
      that's part of ``kolla_config``.

* Environment tells the container engine which environment variables to set

    - We set ``KOLLA_CONFIG_STRATEGY=COPY_ALWAYS`` in the example, since this
      tells kolla to always execute the ``config_files`` and ``permissions``
      directives as part of the kolla entry point. If we don't set this, it
      will only be executed the first time we run the container.

``docker_puppet_tasks`` section
-------------------------------

These are containerized puppet executions that are meant as bootstrapping
tasks. They typically run on a "bootstrap node", meaning, they only run on one
relevant node in the cluster. And are meant for actions that you should only
execute once. Examples of this are: creating keystone endpoints, creating
keystone domains, creating the database users, etc.

The format for this is quite similar to the one described in ``puppet_config``
section, except for the fact that you can set several of these, and they also
run as part of the steps (you can specify several of these, divided by the
``step_<step number>`` keys).

Conclusion
----------

With these sections you can create service templates for your containerized
services. If you plan to develop a containerized service, I suggest you also
read the guide on the containerized deployment from the [TripleO
documentation][containerized-deployment-guide].

With this, we have covered all the need-to-know sections for you to be
effective with TripleO templates. There are still several other sections which
you can take use of. I'll cover the rest in a subsequent blog post.

[image-prepare-workflow]: https://docs.openstack.org/tripleo-docs/latest/install/containers_deployment/overcloud.html#preparing-overcloud-images
[paunch]: https://github.com/openstack/paunch
[privileged-containers]: https://www.linux.com/blog/learn/sysadmin/2017/5/lazy-privileged-docker-containers
[containerized-deployment-guide]: http://tripleo.org/install/containers_deployment/index.html
