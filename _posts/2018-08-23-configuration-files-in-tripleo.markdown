---
layout: post
title:  "Configuration files in TripleO"
date:   2018-08-23 10:06:55 +0300
categories: tripleo openstack
---

There have been several ocasions where I've been asked where a file gets
generated, or where does it come from in a TripleO deployment. Ideally this
would be quite an easy thing to answer. However, more often than not, there is
quite a bit of stuff going on in the deployment steps that makes this task
non-trivial.

There are ways to go forward and look. The aim of this blog post is to try
to put in words a systematic way of doing this.

Where do I begin?
-----------------

It all begins in [tripleo-heat-templates][tripleo-heat-templates], which we
will refer from now on as t-h-t. Note that it's relevant to know how to write
Heat templates in order to understand how this all works.

In these templates we define a lot of things about the service's deployment.
The services themselves are defined in the ``*/services/`` folder.

There are three main folders currently in t-h-t:

* **puppet/services/** : These are the base service configurations. In the
  beginning, when TripleO deployed  the OpenStack services on bare-metal, these
  templates were used directly and puppet was invoked with the information from
  the templates. Nowadays, these templates are still used, but these templates
  are not used directly anymore, but instead wrapped in another set of
  templates that re-use this information. The main things these templates
  contain are the hieradata and the puppet manifest invocation.

* **docker/services/** : Since the Pike release, TripleO deploys OpenStack over
  containers. Containerized services are thus stored in this directory. Most of
  the time these templates inherit from the puppet templates, which means they
  re-use the information from them. Aside from this information re-use, these
  templates contain information relevant to starting the containers: what
  command is used for the container, what containers will be ran, etc. TripleO
  leverages Kolla in order to run and build the containers.

* **extraconfig/services/** : These are services that have been created quite
  recently, and do not use puppet nor the container mechanisms that other
  services use. Given that TripleO nowadays has quite extensive Ansible
  integration, these services leverage that for their deployment. Perhaps in
  the future this folder should be renamed **ansible/services/**, but time will
  tell :).

### Why was this relevant?

These are the places were you will look for information, these folders tell you
how the service was deployed, and the templates inside these folders contain
the information about how the service is being configured. Most of the
information is set as the **output** for these templates, which are actually
Heat stacks. The output itself is grouped in a common output called
``role_data``, which will contain several sections that are used in different
ways.

### Digging in the templates

There's a lot of information in the templates, but, relevant to our search are
the following:

* **hieradata**: These are key-value pairs that will be used to get dynamic
  data for our service's configuration. These are mostly used by puppet in
  order to fill in the configuration files. You can find this info in the
  following sections of the templates: ``config_settings``,
  ``service_config_settings``

* **puppet invocation**: At some point in the deployment, puppet is invoked in
  order to generate the configuration files for our service. In the case of a
  bare-metal deployment, puppet is invoked directly. But for containerized
  services, puppet also runs inside a container, and generates all the
  configuration for the services in one step. Either way, the manifest that's
  invoked for a specific service is defined in the ``step_config`` section.
  The ``::tripleo`` prefix in the include, means that we'll find the manifest
  in the [puppet-tripleo][puppet-tripleo] repository.

* **containers**: We also need to tell TripleO specifically which containers to
  keep track of and run. This is defined in the ``docker_config`` section,
  which contains the container definitions themselves. The running of
  containers is divided by steps. I won't talk about what happens in each step
  (maybe this is good material for another blog post :) )

* **kolla configuration**: as extra configuration for our containers, we
  leverage kolla to handle certain things for us. Namely we use it to tell the
  container what command to run, to copy files to the container's filesystem,
  and to set the appropriate permissions for these files. We can get all this
  information from the ``kolla_config`` section of the templates.

Note that not all of the aforementioned sections are mandatory, but it's
relevant to understand them to know what's going on in the deployment.

With all this information in hand, we can now know how the configuration was
made and figure out where to look. For most services, chances are that the
next step is to look at the puppet manifest that configures this service. So
lets do that.

Puppet
------

As mentioned before, most services are still configured by puppet. The way to
know what repository to look at is to check the value of ``step_config``, then
take the first word in the include statement, and prepend "_puppet-_" to it.

Most of the services, however, have a wrapper manifest in the
[puppet-tripleo][puppet-tripleo] repository. The way to get which puppet file
to look at also relies on the include invocation we saw on ``step_config``.
Lets figure this out with an example:

For keystone, we can see that the value of ``step_config`` is
``::tripleo::profile::base::keystone``. From this we can tell that it was
configured from a manifest in ``puppet-tripleo``, because of the "``tripleo``"
keyword in the beginning of the include. Inside ``puppet-tripleo``, we can take
the rest of the keywords in that invocation to figure out the manifest. All of
the manifests are inside the **manifests/** directory, and inside there, we
go deeper with each keyword. So for ``::tripleo::profile::base::keystone``
we'll find the manifest in **manifests/profile/base/keystone.pp**.

With this in mind, we can go as deep as needed to find where configurations are
done.

We can see that the **keystone.pp** manifest calls the "``keystone``" class:

{% highlight puppet %}
...
    class { '::keystone':
      sync_db                    => $sync_db,
      enable_bootstrap           => $sync_db,
...
{% endhighlight %}

So, to see what that class does, we need to follow the same logic as we did
before. We prepend the "``puppet-``" keyword in order to know what repository
contains what we need. In this case, we need to look in
[puppet-keystone][puppet-keystone].

If the ``class`` or the ``include`` statement doesn't contain a keyword after
the one we used to derive the repository, this means that the **init.pp**
manifest was used, which is also in the **manifests/** directory of the
repository.

It is here that we'll start seeing signs of where the actual configuration
parameters are set.

Lets look at the following statement in the **init.pp** file for
puppet-keystone:

{% highlight puppet %}
...
  keystone_config {
    'token/provider':              value => $token_provider;
    'DEFAULT/max_token_size':      value => $max_token_size;
    'DEFAULT/notification_format': value => $notification_format;
  }
...
{% endhighlight %}

Here we can explicitly see how token-related options are configured for
keystone. It's fairly simple to map these options to **keystone.conf**. Lets
take the first option here as an example: **token/provider**. Here, **token**
is the group for the configuration option, and **provider** is the actual
option. In keystone.conf this will look as:

{% highlight ini %}
[token]
...
provider = <some value>
...
{% endhighlight %}

But, how do we know that this ``keystone_config`` statement configures
**/etc/keystone/keystone.conf**?

Well, for this, you need to know some puppet. But the main thing is that puppet
allows you to define "providers", which are pieces of code that allow you to
extend puppet's functionality to do a certain task. There are providers to
create the keystone endpoints, to modify configuration files, and all sorts of
things. To find them, we'll need to look in the following directory:
**lib/puppet/provider/**. Here we can see the different providers that the
specific pupet module enables.

Going back to the keystone example, as we can see, the aforementioned
``keystone_config`` definition is here. The full path to it would be
``lib/puppet/provider/keystone_config/ini_setting.rb``. Here, we can explicitly
see that this module configures the configuration file:

{% highlight ruby %}
Puppet::Type.type(:keystone_config).provide(
  :ini_setting,
  :parent => Puppet::Type.type(:openstack_config).provider(:ini_setting)
) do

  def self.file_path
    '/etc/keystone/keystone.conf'
  end

end
{% endhighlight %}

So... What does this mean in the actual deployment?
---------------------------------------------------

When looking in the configuration files, if a service was deployed on
bare-metal, the configuration files will be exactly where you expect. However,
when dealing with containerized services, TripleO executes puppet inside a
container and persists the configurations in the following directory:
**/var/lib/config-data/puppet-generated/<service name>**. Inside the
aforementioned directory you'll find only the files that puppet manages and
modifies, with the file structure you would expect in the system. So, if you're
looking for **/etc/keystone/keystone.conf** you'll find it in
**/var/lib/config-data/puppet-generated/keystone/etc/keystone/keystone.conf**

But... The file I was looking for wasn't managed by puppet
----------------------------------------------------------

It could be the case that the service is managed by puppet, however, the
specific file you were looking for isn't managed by puppet. While this might be
a bit confusing, don't worry, there is no black magic here :) (or is it?).

Chances are the specific file you were looking for was already part of the
container. Which means, it comes from a package.

Packages themselves are maintained by a group of awesome folks, the [RDO
community][rdo].

They have their own [Gerrit instance][rdo-gerrit], on which they host the rpm
spec definitions. You'll normally be able to find the spec definition, and
other relevant files in a special repository with the **-distgit** suffix. So,
to find the packaging for Keystone, we need to look at the
[keystone-distgit][keystone-distgit] repository.

The _.spec_ file will show us all the files that are included for that package,
and some extra files will be also part of the distgit repository, such as the
logrotate configuration.

How do I know what packages are included in the container?
----------------------------------------------------------

TripleO uses Kolla to build containers. So, the place to look at is the [kolla
repository][kolla]. In this repository, and under the **docker/** directory, we
can find the list of projects they support. Here we have the Dockerfile
definitions used to build the containers, which are set as jinja templates in
order to allow folks to extend them. The hierarchy will usually be
**docker/<project>/<container>**, although some projects consist of only one
container, in which case, you'll find the Dockerflie definition under
**docker/<project>**.

Looking at the dockerfile, you'll find the packages installed are defined by
the following keyword: ``<container name>_packages``. For instance, for
barbican, we'll find the following in the barbican-api definition:

{% highlight jinja2 %}
...
{% raw %}
       {% set barbican_api_packages = [
                'httpd',
                'mod_ssl',
                'mod_wsgi',
                'openstack-barbican-api',
                'uwsgi-plugin-python'
       ] %}
{% endraw %}
...
{% endhighlight %}

For TripleO, we might have some extra needs for the container though. So, for
things that we are not useful for the Kolla community and are TripleO-specific,
we'll need to look at the [tripleo-common][tripleo-common] directory. Any
overrides we do to the kolla container images, we'll find under
``container-images/tripleo_kolla_template_overrides.j2``. Package additions can
be found to be set with the ``<container name>_packages_append`` variable.


[tripleo-heat-templates]: https://github.com/openstack/tripleo-heat-templates/
[puppet-tripleo]: https://github.com/openstack/puppet-tripleo
[puppet-keystone]: https://github.com/openstack/puppet-keystone
[rdo]: https://www.rdoproject.org/
[rdo-gerrit]: https://review.rdoproject.org/r/
[keystone-distgit]: https://review.rdoproject.org/r/#/admin/projects/openstack/keystone-distgit
[kolla]: https://github.com/openstack/kolla
[tripleo-common]: https://github.com/openstack/tripleo-common/
