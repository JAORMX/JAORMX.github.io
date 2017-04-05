---
layout: post
title:  "Testing containerized OpenStack services with kolla"
date:   2017-03-20 15:15:47 +0200
categories: kolla openstack
---

Note that the following instructions are for Fedora 25 as that's what I'm
currently running.

## Setup

First, make sure that you have docker installed in your system.

    sudo dnf install -y docker

This might not be the most secure thing; but for development purposes I added
my user to the docker group, so I can run docker commands without sudo.

    groupadd docker
    usermod -a -G docker <my user>

After this, you might want to open a new session, and make sure that in that
session your user is in the docker group.

Having done this, make sure you enable docker on your system:

    sudo systemctl enable docker

or restart it if it was running already:

    sudo systemctl restart docker

Now, having done this, we need to get the kolla repository, where the image
definitions are declared:

    git clone git://git.openstack.org/openstack/kolla
    # We should also move to the directory
    cd kolla

next, we need to generate a base/sample configuration. We can easily do this
thanks to oslo-config-generator:

    tox -e genconfig

This will generate a sample configuration in _./etc/kolla/kolla-build.conf_

Now, since I don't want to install kolla in my system, I'll just rely on the
virtualenv that tox creates:

    tox -e py27
    source .tox/py27/bin/activate

## Building images with kolla

One can just build all the images with:

    kolla-build

or:

    ./kolla/cmd/build.py

However, in my case, at the moment I only want to test out the keystone image.
So I do:

    ./kolla/cmd/build.py keystone

This will build the keystone-related images, and some that I didn't really want
to build (such as barbican and barbican-keystone-listener). This will give a
very verbose output and take a while. So go fetch a coffee/beer or your
beverage of choice.

We can check which images were built using the usual docker CLI:

    $ docker images
    kolla/centos-binary-keystone-ssh                 4.0.0               42b10416796b        8 minutes ago       718.9 MB
    kolla/centos-binary-keystone-fernet              4.0.0               77ca80589ec6        8 minutes ago       699.5 MB
    kolla/centos-binary-barbican-keystone-listener   4.0.0               9d5b536d599a        9 minutes ago       640.8 MB
    kolla/centos-binary-keystone                     4.0.0               5b9e0c7085f0        9 minutes ago       677.4 MB
    kolla/centos-binary-keystone-base                4.0.0               689e1df70317        9 minutes ago       677.4 MB
    kolla/centos-binary-barbican-base                4.0.0               af286e15b9e7        10 minutes ago      619.5 MB
    kolla/centos-binary-openstack-base               4.0.0               a2eae63c41f1        11 minutes ago      588.6 MB
    kolla/centos-binary-base                         4.0.0               cbdeca2ecfab        15 minutes ago      397.8 MB
    docker.io/centos                                 7                   98d35105a391        4 days ago          192.5 MB

The images are based by default on the centos image. Which is fine for me.
However, if you would like to use another base (such as ubuntu) you can specify
that with the -b parameter.

    kolla-build -b ubuntu

## Testing it out with kolla-ansible

To test it out, for now, I decided to try out kolla-ansible. So, we need to
install some relevant packages, clone the repo, and run tox so it can build a
virtual environment for us with all the dependencies installed:

    dnf install python-docker-py ansible
    git clone git://git.openstack.org/openstack/kolla-ansible
    cd kolla-ansible
    tox -e py27
    source .tox/py27/bin/activate
    # For some reason, it seems that kolla is missing from here, so I install
    # it inside the virtual environment.
    pip install kolla

Now, to try out the keystone container, I need the rsyslog and mariadb
containers as well. so lets build them

    kolla-build mariadb rsyslog

Now, I have a config file such as the following:

    kolla_base_distro: "centos"
    kolla_install_type: "binary"

    # This is the interface with an ip address you want to bind mariadb and keystone too
    network_interface: "enp0s25"
    # Set this to an ip address that currently exists on interface "network_interface"
    kolla_internal_address: "192.168.X.X"

    # Easy way to change debug to True, though not required
    openstack_logging_debug: "True"

    # For your information, but these default to "yes" and can technically be removed
    enable_keystone: "yes"
    enable_mariadb: "yes"

    # Builtins that are normally yes, but we set to no
    enable_glance: "no"
    enable_haproxy: "no"
    enable_heat: "no"
    enable_memcached: "no"
    enable_neutron: "no"
    enable_nova: "no"
    enable_rabbitmq: "no"
    enable_horizon: "no"

I placed this file in the home directory in a directory I named kolla:
~/kolla/globals.yml

Remember to change the internal IP address to the relevant one in your system.

We also need a passwords file, so, lets get the base for it and generate
the relevant passwords:

    # Copy the default empty passwords file in the kolla-ansible repository
    cp etc/kolla/passwords.yml ~/kolla/
    # Generate passwords
    kolla-genpwd -p ~/kolla/passwords.yml

Even if we don't run kolla-ansible as root, we still need the /etc/kolla
directory. So one has to create it and give your user permissions to it.

    sudo mkdir /etc/kolla
    sudo chown -R $USER:$USER /etc/kolla

This is becaue there are binds from this directory to the containers taking
place. And also, we'll be able to get the admin credentials for the openstack
services in a file that'll subsequently be created in this directory.

Finally, we can issue the deploy:

    ./tools/kolla-ansible --configdir ~/kolla/ \
        --passwords ~/kolla/passwords.yml deploy

After this finishes we can now see several containers running:


    $ docker ps
    CONTAINER ID        IMAGE                                     COMMAND             CREATED             STATUS              PORTS               NAMES
    5e9e41b0b404        kolla/centos-binary-keystone:4.0.0        "kolla_start"       8 minutes ago       Up 8 minutes                            keystone
    a84ab9997e3a        kolla/centos-binary-mariadb:4.0.0         "kolla_start"       9 minutes ago       Up 9 minutes                            mariadb
    1687512f6984        kolla/centos-binary-cron:4.0.0            "kolla_start"       9 minutes ago       Up 9 minutes                            cron
    bb3235e0a880        kolla/centos-binary-kolla-toolbox:4.0.0   "kolla_start"       9 minutes ago       Up 9 minutes                            kolla_toolbox
    b23c48b04c53        kolla/centos-binary-fluentd:4.0.0         "kolla_start"       9 minutes ago       Up 9 minutes                            fluentd

Now, we can get the admin credentials:

    ./tools/kolla-ansible --configdir ~/kolla/ \
        --passwords ~/kolla/passwords.yml post-deploy

This will create _admin-openrc.sh_ in the /etc/kolla directory. So we can do a
simple test to see that keystone is running by doing the following.

    source /etc/kolla/admin-openrc.sh
    openstack user list

And this should print an admin user.

To log into the keystone container. I can do the following:

    docker exec -ti keystone /bin/bash

### Note about docker's storage

At some point after writing this blog post I ran into the issue where I
destroyed the kolla-ansible deployment and attempted to create it again, with
it finally failing. This apparently was because of the kolla-toolbox container
not finding the storage file it needed to.

Talking to the kolla community I was pointed to [this blog recommending not to
use the devicemapper driver][docker-blog]. And after following the
recommendations there, using OverlayFS instead for my case, destroying the
deployment and the images, and rebooting my system; I was able to deploy
again successfully.


## References

Special thanks to Adam Young. His blog has always been really useful!

The kolla-ansible bits are mostly based [this blog post of his][adam-blog].

The rest has been based on the [kolla][kolla] and
[kolla-ansible][kolla-ansible] documentation.

[adam-blog]: http://adam.younglogic.com/2016/02/holla-kolla/
[kolla]: https://docs.openstack.org/developer/kolla/image-building.html
[kolla-ansible]: https://docs.openstack.org/developer/kolla-ansible/quickstart.html
[docker-blog]: http://www.projectatomic.io/blog/2015/06/notes-on-fedora-centos-and-docker-storage-drivers/
