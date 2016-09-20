---
layout: post
title:  "Adding packages to overcloud images"
date:   2016-09-20 12:11:15 +0300
categories: tripleo openstack
---

If you don't want to re-build your overcloud images and need an extra package,
adding it is actually simpler than one would expect. Since we have our
overcloud images in qcow2 format, it's just a matter of doing::

    virt-customize -a overcloud-full.qcow2 --install <package name>

Adding extra packages is then a matter of specifying them in a comma-separated
list

    virt-customize -a overcloud-full.qcow2 --install <package name #1>,<package name #2>

For instance, I need my overcloud nodes to have the ipa-client package already
installed, since I want them to enroll to FreeIPA, but I want to skip the
overhead time of installing the package in an ExtraConfig script. So the
command would simply be::

    virt-customize -a overcloud-full.qcow2 --install ipa-client

Now, having done this, we need to remember to upload our new images to the
overcloud's glance. This can be done without removing the old images too. So,
for this, we have to do the following:

    openstack overcloud image upload --update-existing

And we're done!
