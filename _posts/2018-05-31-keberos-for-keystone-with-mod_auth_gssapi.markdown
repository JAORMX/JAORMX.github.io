---
layout: post
title:  "Setting up Keberos for Keystone auth with mod_auth_gssapi"
date:   2018-05-31 16:13:08 +0300
categories: tripleo kerberos keystone openstack
---
Setting up Keberos for Keystone auth with mod_auth_gssapi
=========================================================

I've been following blog posts about setting up Keystone with kerberos
authentication, and recently tried to implement that manually in TripleO.
Here's how it went:

mod_auth_gssapi instead of mod_auth_kerb
----------------------------------------

Asking around, it turns out that mod_auth_kerb is not going to be supported
anymore, and using mod_auth_gssapi is the preferred alternative. Unfortunately
all the blogs I found were using mod_auth_kerb, so I needed to research how to
use mod_auth_gssapi.

Required packages
-----------------

We'll need to install the following packages in the host where keystone is
running:

* mod_auth_gssapi
* python-requests-kerberos

Given that we run keystone in a container in TripleO, I needed to add those
packages to the keystone container.

Deployment
----------

I deployed TripleO with [TLS everywhere][tls-everywhere] to have all the nodes enrolled to
FreeIPA and set up keystone to use LDAP-backed domains as I referenced in a
[previous blog post][previous-blog-post].

This would leave me with a deployment where I can authenticate to keystone
using users coming from FreeIPA's LDAP.

Given that we deployed using TLS everywhere, we already have quite a bunch of
service principals registered in FreeIPA, namely, we already have
`HTTP/overcloud-controller-<number>.<networks>.<domain>`. Unfortunately, this
is not a principal we can use, since the clients will authenticate to keystone
by first going through HAProxy, which is listening on the external network and
has the FQDN that references the 'cloud name'. Lets say that our domain is
example.com. In that case, we'll need to have a principal that looks as
follows: `HTTP/overcloud.example.com@EXAMPLE.COM` (assuming our kerberos
realm matches the domain).

So, lets add this principal to FreeIPA:


{% highlight bash %}
ipa service-add HTTP/overcloud.example.com --force
{% endhighlight %}

Subsequently, we'll need to tell FreeIPA that the service is being managed by
another host (given that there actually isn't a host for
overcloud.example.com). Assuming we only have one controller named
`overcloud-controller-0.example.com`, we can make it manage the service with
the following command:

{% highlight bash %}
ipa service-add-host HTTP/overcloud.example.com --hosts=overcloud-controller-0.example.com
{% endhighlight %}

Having done this in the FreeIPA server, we can now go to our controller(s) and
get the necessary kerberos keytab for that service:

{% highlight bash %}
# We get the host's credentials
kinit -kt /etc/krb5.keytab

# Using those credentials we request the keytab
ipa-getkeytab -p HTTP/overcloud.example.com -k /var/lib/config-data/puppet-generated/keystone/etc/keystone.keytab

# We change the permissions so httpd has access to the keytab
chown root:apache /var/lib/config-data/puppet-generated/keystone/etc/keystone.keytab
chmod 0660 /var/lib/config-data/puppet-generated/keystone/etc/keystone.keytab
{% endhighlight %}

We'll notice that I used `/var/lib/config-data/puppet-generated/keystone/` as
a path. This is because we're using a containerized deployment in TripleO, and
this is the directory that's bind-mounted to the keystone container.

I also changed the file permissions of the keytab, so the apache process can
access it.

Configuration
-------------

With all the previous steps done, we can start configuring keystone's apache
instance!

To avoid issues in the container, I manually copied `10-auth_gssapi.conf` to
the container's `conf.modules.d` directory. We can do this from the host by
getting that file as `10-auth_gssapi.load` into
`/var/lib/config-data/puppet-generated/keystone/etc/httpd/conf.modules.d`.

Subsequently, I added the following configuration to keystone's apache
configuration in the `conf.d` directory:

{% highlight apache %}
  ...
  WSGIScriptAlias /krb "/var/www/cgi-bin/keystone/keystone-public"
  WSGIScriptAlias / "/var/www/cgi-bin/keystone/keystone-public"
  WSGIPassAuthorization On

  <Location "/krb/v3/auth/tokens">
        LogLevel debug
        AuthType GSSAPI
        AuthName "GSSAPI Login"
        GssapiCredStore keytab:/etc/keystone.keytab
        GssapiCredStore ccache:FILE:/var/run/keystone-krb5ccache
        GssapiLocalName On
        Require valid-user
        SetEnv REMOTE_DOMAIN freeipadomain
  </Location>
{% endhighlight %}

We'll be able to modify this file from the host by editing
`/var/lib/config-data/puppet-generated/keystone/etc/httpd/conf.d/10-keystone_wsgi_main.conf`.
Something similar will need to be done for the admin endpoint, which is in the
same directory as `10-keystone_wsgi_admin.conf`.

We'll note that the `WSGIScriptAlias / ...` and `WSGIPassAuthorization On`
already existed in the configuration.

It is also very relevant that the `/krb` route is added before the `/` route;
else we'll get 404 errors in our deployment.

Finally, I changed the `methods` configuration option that's under the `auth`
group in `keystone.conf`:

{% highlight ini %}
[auth]
...
methods = external,password,token,kerberos,application_credential
{% endhighlight %}

With this, we can now restart the keystone container:

{% highlight bash %}
docker restart keystone
{% endhighlight %}

Authenticating
--------------

Note that we'll need the package `python-requests-kerberos` in the client side
as well.

To test this out, I created a user called 'demo' and a project called
'freeipa-project' in the LDAP-backed domain called 'freeoipadomain'.

We need to authenticate to kerberos using the desired principal:

{% highlight bash %}
kinit demo
{% endhighlight %}

We'll also need an rc file. For this example, it'll look as follows:

{% highlight bash %}
# Clear any old environment that may conflict.
for key in $( set | awk '{FS="="}  /^OS_/ {print $1}' ); do unset $key ; done
export OS_NO_CACHE=True
export COMPUTE_API_VERSION=1.1
export no_proxy=,overcloud.example.com,overcloud.ctlplane.example.com
export OS_VOLUME_API_VERSION=3
export OS_CLOUDNAME=overcloud
export OS_AUTH_URL=https://overcloud.example.com:13000/krb/v3
export NOVA_VERSION=1.1
export OS_IMAGE_API_VERSION=2
export OS_PROJECT_DOMAIN_NAME=freeipadomain
export OS_IDENTITY_API_VERSION=3
export OS_PROJECT_NAME=freeipa-project
export OS_AUTH_TYPE=v3kerberos
{% endhighlight %}

Lets try it out!

{% highlight bash %}
openstack token issue --max-width 100
+------------+-------------------------------------------------------------------------------------+
| Field      | Value                                                                               |
+------------+-------------------------------------------------------------------------------------+
| expires    | 2018-05-31T16:02:37+0000                                                            |
| id         | gAAAAABbEA6NijwIrXbNndVrUjgAuz0MQoBLjpeKJ_K-                                        |
|            | OmU_ofYTxUlFISnX70fyWY5h99fsb50l6X5gsSCPXMLmDikzjfN4FDY-                            |
|            | bJ0LgO9PUc1ysYIbhKBRTIkkK2fbzPsrkBRbM8i-wy9vT2NP1ZFdVtYlWkYAwHE5hNY4Nf3HgaMoxj4t_IM |
|            | Fcjk_K6RHAcMXrkxuAS3yhd_NfJd5FnxmqwObNX42jx0eHaIbb5G3GQBDOkLSu2g                    |
| project_id | 39e72472bc964ebfb2faeaca1f865c0e                                                    |
| user_id    | ce2f93c933ca64e3e1d313942c0f5cd2e2c31ce8ffcaf92c83a7e4fac8c5afad                    |
+------------+-------------------------------------------------------------------------------------+
{% endhighlight %}

Blogs I used as references
--------------------------

* [Objectif Libre blog](https://www.objectif-libre.com/en/blog/2018/02/26/kerberos-authentication-for-keystone/)
* [Jamie Lennox's blog](https://www.jamielennox.net/blog/2015/02/12/step-by-step-kerberized-keystone/)

[tls-everywhere]: http://tripleo.org/install/advanced_deployment/ssl.html#tls-everywhere-for-the-overcloud
[previous-blog-post]: /2017/freeipa-ldap/
