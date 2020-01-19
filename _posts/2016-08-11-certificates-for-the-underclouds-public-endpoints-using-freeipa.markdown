---
layout: post
title:  "Certificates for the undercloud's public endpoints using FreeIPA"
date:   2016-08-11 13:59:48 +0300
categories: tripleo freeipa
image: /images/cup.jpg
---
TripleO's undercloud has the option to auto-generate certificates for its
public endpoints (hopefully soon I'll add the same option for the admin and
internal ones). This is based on certmonger. Being certmonger able to get
certificates from FreeIPA, we'll do just that.

## FreeIPA setup

It is assumed that you have FreeIPA running somewhere. Else, you can follow
this [post by Adam Young][freeipa-install] to install it quickly, or you could
even [use Heat to install it][heat-freeipa-install].

First of all, we need to register the undercloud node as a host in FreeIPA. For
this, we need an account that's able to do this. So, making sure we have the
appropriate permissions and that we have a kerberos ticket that's valid. We add
the host to FreeIPA as the following:

{% highlight bash %}
ipa host-add undercloud.walrusdomain --password=MySecret --force
{% endhighlight %}

Remember to use your own domain here.

This will give you an output such as the following:

{% highlight bash %}
------------------------------------
Added host "undercloud.walrusdomain"
------------------------------------
  Host name: undercloud.walrusdomain
  Password: True
  Keytab: False
  Managed by: undercloud.walrusdomain
{% endhighlight %}

You might aso need an appropriate service for HAProxy in the undercloud. We can
add it with the following command:

{% highlight bash %}
ipa service-add haproxy/undercloud.walrusdomain@WALRUSDOMAIN --force
{% endhighlight %}

Make sure that the hostname, the domain and the kerberos realm are
appropriate to your deployment. Once the aforementioned command was ran, you'll
see output such as the following:

{% highlight bash %}
------------------------------------------------------------
Added service "haproxy/undercloud.walrusdomain@WALRUSDOMAIN"
------------------------------------------------------------
  Principal: haproxy/undercloud.walrusdomain@WALRUSDOMAIN
  Managed by: undercloud.walrusdomain
{% endhighlight %}

Once we have this ready, we need to log in the undercloud node and enroll it as
a FreeIPA client.

## Undercloud enrollment to FreeIPA

Please note that we need to make sure we have access to the FreeIPA server node
from the undercloud. Also, the undercloud's domain needs to match the kerberos
realm that FreeIPA manages. Finally, the undercloud's FQDN must match the host
that was created in FreeIPA. So, with this in mind, we can do the enrollment:

{% highlight bash %}
# Install needed FreeIPA client package
sudo yum install -y ipa-client
# Enroll host to FreeIPA
sudo ipa-client-install --server ipa.walrusdomain --password=MySecret \
    --domain=walrusdomain --unattended
{% endhighlight %}

Once this is done, in FreeIPA we can now see the following:

{% highlight bash %}
$ ipa host-show undercloud.walrusdomain
  Host name: undercloud.walrusdomain
  Principal name: host/undercloud.walrusdomain@WALRUSDOMAIN
  Password: False
  Keytab: True
  Managed by: undercloud.walrusdomain
  SSH public key fingerprint: 70:01:26:83:99:98:9C:60:07:FA:E7:48:AD:4B:13:1E (ssh-rsa),
                              C9:48:BC:55:CE:89:A8:14:A5:7C:B0:3F:85:86:E0:11 (ssh-ed25519),
                              CB:D4:09:3D:3B:1E:6B:FB:70:A4:0C:2C:1C:50:B3:C6 (ecdsa-sha2-nistp256)
{% endhighlight %}

Noting that the OTP is no longer usable (Password: False) and the Keytab is set
to True, which means we have a keytab in that host that we can use for
authenticating.

Now, in the undercloud node, we need to get the kerberos ticket in order to be
able to request our certificate:

{% highlight bash %}
sudo kinit -k -t /etc/krb5.keytab
{% endhighlight %}

We can verify that we indeed have a kerberos ticket with the following command:

{% highlight bash %}
sudo klist
{% endhighlight %}

Which should give the output that resembles this:

{% highlight bash %}
Ticket cache: FILE:/tmp/krb5cc_0
Default principal: host/undercloud.walrusdomain@WALRUSDOMAIN

Valid starting       Expires              Service principal
08/11/2016 11:48:08  08/12/2016 11:48:08  krbtgt/WALRUSDOMAIN@WALRUSDOMAIN
{% endhighlight %}

## Undercloud setup

Now we have everything we need. So for the undercloud to be able to request
certificates from FreeIPA, we need to add the following values to the
undercloud.conf file.

{% highlight bash %}
# With this we will make HAProxy bind to this hostname, so it will use the IP
# that hostname has. It will also get the keystone endpoints to use a hostname
# instead of an IP.
undercloud_public_vip = undercloud.walrusdomain
# This will tell the undercloud to use certmonger to autogenerate the
# certificate.
generate_service_certificate = true
# This will tell certmonger to use FreeIPA as the CA for those certificates.
certificate_generation_ca = IPA
# This is the service principal that we created for HAProxy
service_principal = haproxy/undercloud.walrusdomain@WALRUSDOMAIN
{% endhighlight %}

Having changed these values, we can run this to install or re-install the
undercloud:

{% highlight bash %}
openstack undercloud install
{% endhighlight %}

Once this is done, we can verify that the public keystone endpoints are
listening on https like this:

{% highlight bash %}
# Keystone v3
openstack endpoint list
# Keystone v2
openstack endpoint list --long
{% endhighlight %}

Furtherly, we can check that certmonger is tracking the service certificate:

{% highlight bash %}
sudo getcert list
{% endhighlight %}

Which should show something like this:

{% highlight bash %}
Request ID 'undercloud-haproxy-public-cert':
        status: MONITORING
        stuck: no
        key pair storage: type=FILE,location='/etc/pki/tls/private/undercloud-front.key'
        certificate: type=FILE,location='/etc/pki/tls/certs/undercloud-front.crt'
        CA: IPA
        issuer: CN=Certificate Authority,O=WALRUSDOMAIN
        subject: CN=undercloud.walrusdomain,O=WALRUSDOMAIN
        expires: 2018-08-12 12:12:09 UTC
        principal name: haproxy/undercloud.walrusdomain@WALRUSDOMAIN
        key usage: digitalSignature,nonRepudiation,keyEncipherment,dataEncipherment
        eku: id-kp-serverAuth,id-kp-clientAuth
        pre-save command: 
        post-save command: /usr/bin/instack-haproxy-cert-update '/etc/pki/tls/certs/undercloud-front.crt' '/etc/pki/tls/private/undercloud-front.key' /etc/pki/tls/certs/undercloud-undercloud.walrusdomain.pem
        track: yes
        auto-renew: yes
{% endhighlight %}

[freeipa-install]: http://adam.younglogic.com/2016/07/installing-freeipa-few-lines/
[heat-freeipa-install]: https://resurrexit.github.io/2016/07/29/using-heat-to-deploy-a-freeipa-server.html
