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

...

[libvirt-tls-doc]: http://wiki.libvirt.org/page/TLSSetup
[libvirt-tls-reference]: http://libvirt.org/remote.html#Remote_libvirtd_configuration
