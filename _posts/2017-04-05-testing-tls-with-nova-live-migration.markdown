---
layout: post
title:  "Testing TLS with Nova live migration"
date:   2017-04-05 09:48:24 +0300
categories: tripleo openstack
---

As part of the TLS everywhere work, I've been working on getting Nova's live
migration to work with TLS as well. This requires to set up libvirt's remote
transport URL to use TLS. Thankfully, to better understand this, libvirt's
[documentation][libvirt-tls-doc] is actually pretty good.

## A little research

From the [configuration reference][libvirt-tls-reference] we can see that there
are several defaults that we can take into account to make life easier. For
instance, the default directory for both the client and server certificates are
stored in **/etc/pki/libvirt**. The client certificate file's default is
**clientcert.pem** and the server certificate file's default is
**servercert.pem**. Also, libvirt needs a specific CA file to verify the
certificates used, this defaults to using **/etc/pki/CA/cacert.pem**.

### Notes on GNUTLS

Libvirt uses GNUTLS as a backend library to handle TLS. This makes it a little
different from how OpenSSL-based programs work.

OpenSSL has a default file for the CA bundle that it uses, which one could get
with the following python code:

{% highlight python %}
import ssl
print(ssl.get_default_verify_paths().openssl_cafile)
{% endhighlight %}

However, this is not the same file GNUTLS would use if you would try to use the
default CA bundle or the "system trust", which one can do via the
``gnutls_certificate_set_x509_system_trust`` function call. For instance, for
Fedora, GNUTLS is compiled with the following flag:

{% highlight bash %}
...
--with-default-trust-store-pkcs11="pkcs11:model=p11-kit-trust;manufacturer=PKCS%2311%20Kit"
...
{% endhighlight %}

Which will use a pkcs11 URL instead of a file for the CA bundle. This is nice
and all, but can be a little tricky, since there are certain limitations that
are not apparent.

When I was trying to configure libvirt to use the same CA bundle as the one
provided by OpenSSL I got a failure due to the file size. Digging further, it
turns out that the function that GNUTLS uses to read CA files (which is
``gnutls_certificate_set_x509_trust_file``) if reading from a file can only
read files that have a maximum size of ~65.5K, being that it uses a ``size_t``
variable to get the read bytes from the file.

This is quite problematic, since the default OpenSSL CA bundle that comes from
Fedora is around 200K in size. Another limitation is that libvirt can only
read CA's from files, and has no means to use pkcs11 URLs.

So taking all this into account, I opted for being explicit in the CA file that
I set for **/etc/pki/CA/cacert.pem**; being it the one CA file that signs the
certificates for the overcloud services. And this being the default CA for
Tripleo, FreeIPA, which has it's CA pem file in **/etc/ipa/ca.crt**.

## Environment setup

First off, we will need a setup will FreeIPA available, since we'll be
deploying a TLS-everywhere environment. We'll need a very similar environment
as described in [this blog post]({{ site.baseurl }}{% post_url 2017-02-21-deploying-a-tls-everywhere-environment-with-oooq-and-an-existing-freeipa-server %})
with the main difference being that we need at least two computes to test the
live migration.

quickstart now takes different configuration files for the topology of the
nodes, so we'll create a configuration file such as the following:

{% highlight yaml %}
# Define a single controller node and a two compute nodes.
overcloud_nodes:
  - name: control_0
    flavor: control
    virtualbmc_port: 6230

  - name: compute_0
    flavor: compute
    virtualbmc_port: 6231

  - name: compute_1
    flavor: compute
    virtualbmc_port: 6232
{% endhighlight %}

You'll also need to tell the overcloud deployment that you want to deploy more
computes, so you need to specify it in your general configuration with
something like this:

{% highlight yaml %}
extra_args: >-
  --compute-scale 2
{% endhighlight %}

The rest of the configuration described in the blog post will remain the same.

So, run the quickstart.sh command, get a coffee, beer, go to the gym, or
whatever you would like to do, and wait until it's done.

## Testing out live migration

Now that you have an environment set, make sure you can contact the overcloud
via FQDNs (if not, you can run the overcloud-deploy-post.sh script in the
**stack** user's home directory and it'll add the relevant entries to
**/etc/hosts**.

Now, we need a VM that's running in our overcloud in order to try to migrate
it. For this, I merely used the overcloud-validate.sh script, which spawns a
VM and creates the networks. However, I modified it so it won't clean up after
it's done.

with the overcloud's credentials we should check what hypervisors we have
available.

{% highlight bash %}
(overcloud)$ openstack hypervisor list
+----+-------------------------------------+-----------------+--------------+-------+
| ID | Hypervisor Hostname                 | Hypervisor Type | Host IP      | State |
+----+-------------------------------------+-----------------+--------------+-------+
|  1 | overcloud-novacompute-1.example.com | QEMU            | 192.168.24.7 | up    |
|  2 | overcloud-novacompute-0.example.com | QEMU            | 192.168.24.9 | up    |
+----+-------------------------------------+-----------------+--------------+-------+
{% endhighlight %}

Having a VM running, we should inspect it to see what hypervisor it's running
on:

{% highlight bash %}
(overcloud)$ openstack server show Server1
+-------------------------------------+-------------------------------------------+
| Field                               | Value                                     |
+-------------------------------------+-------------------------------------------+
| OS-DCF:diskConfig                   | MANUAL                                    |
| OS-EXT-AZ:availability_zone         | nova                                      |
| OS-EXT-SRV-ATTR:host                | overcloud-novacompute-0.example.com       |
| OS-EXT-SRV-ATTR:hypervisor_hostname | overcloud-novacompute-0.example.com       |
| OS-EXT-SRV-ATTR:instance_name       | instance-00000001                         |
| OS-EXT-STS:power_state              | Running                                   |
| OS-EXT-STS:task_state               | None                                      |
| OS-EXT-STS:vm_state                 | active                                    |
| OS-SRV-USG:launched_at              | 2017-04-19T07:06:29.000000                |
| OS-SRV-USG:terminated_at            | None                                      |
| accessIPv4                          |                                           |
| accessIPv6                          |                                           |
| addresses                           | default-net=192.168.2.103, 192.168.24.104 |
| config_drive                        |                                           |
| created                             | 2017-04-19T07:06:16Z                      |
| flavor                              | pingtest_stack-test_flavor-lgz6q2t5zq4l...|
| hostId                              | 4a961344ed67fb4ec77676f6fa719d805ae1162...|
| id                                  | 67e21344-c78e-42b7-b1b9-fabc08beb9fc      |
| image                               |                                           |
| key_name                            | pingtest_key                              |
| name                                | Server1                                   |
| progress                            | 0                                         |
| project_id                          | e6f9e9c9df0a4c5a933fc479fabba6fc          |
| properties                          |                                           |
| security_groups                     | name='pingtest-security-group'            |
| status                              | ACTIVE                                    |
| updated                             | 2017-04-19T07:06:29Z                      |
| user_id                             | e30fd0f4b59b4e309e483b391803139b          |
| volumes_attached                    | id='b5f799ac-a09e-4670-839c-5cd71a15c467' |
+-------------------------------------+-------------------------------------------+
{% endhighlight %}

It's running on **overcloud-novacompute-0.example.com** as pointed out by the
``OS-EXT-SRV-ATTR:hypervisor_hostname`` entry.

{% highlight bash %}
openstack server migrate --wait --live overcloud-novacompute-1.example.com Server1
{% endhighlight %}

After the migration is complete, you should see the changes reflected:

{% highlight bash %}
$ openstack server show Server1
+-------------------------------------+-------------------------------------------+
| Field                               | Value                                     |
+-------------------------------------+-------------------------------------------+
| OS-DCF:diskConfig                   | MANUAL                                    |
| OS-EXT-AZ:availability_zone         | nova                                      |
| OS-EXT-SRV-ATTR:host                | overcloud-novacompute-1.example.com       |
| OS-EXT-SRV-ATTR:hypervisor_hostname | overcloud-novacompute-1.example.com       |
| OS-EXT-SRV-ATTR:instance_name       | instance-00000002                         |
| OS-EXT-STS:power_state              | Running                                   |
| OS-EXT-STS:task_state               | None                                      |
| OS-EXT-STS:vm_state                 | active                                    |
| OS-SRV-USG:launched_at              | 2017-04-19T08:20:58.000000                |
| OS-SRV-USG:terminated_at            | None                                      |
| accessIPv4                          |                                           |
| accessIPv6                          |                                           |
| addresses                           | default-net=192.168.2.103, 192.168.24.108 |
| config_drive                        |                                           |
| created                             | 2017-04-19T08:20:46Z                      |
| flavor                              | pingtest_stack-test_flavor-ihsr2xk3hr6c...|
| hostId                              | dde8b1db86db6c7ce9f11af7284d6b865525490...|
| id                                  | da5dc53f-5989-4873-a55d-1e4418fa4b04      |
| image                               |                                           |
| key_name                            | pingtest_key                              |
| name                                | Server1                                   |
| progress                            | 0                                         |
| project_id                          | e6f9e9c9df0a4c5a933fc479fabba6fc          |
| properties                          |                                           |
| security_groups                     | name='pingtest-security-group'            |
| status                              | ACTIVE                                    |
| updated                             | 2017-04-19T08:22:47Z                      |
| user_id                             | e30fd0f4b59b4e309e483b391803139b          |
| volumes_attached                    | id='658114dd-6b56-44ce-8a32-bebf18cf4bb5' |
+-------------------------------------+-------------------------------------------+
{% endhighlight %}

You can try doing this while having an active ssh connection to the server,
pinging the IP address, and even deploying an application and poking it. Stuff
should still work :D.

[libvirt-tls-doc]: http://wiki.libvirt.org/page/TLSSetup
[libvirt-tls-reference]: http://libvirt.org/remote.html#Remote_libvirtd_configuration
