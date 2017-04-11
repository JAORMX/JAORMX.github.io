---
layout: post
title:  "Using FreeIPA as an LDAP domain backend for keystone in TripleO"
date:   2017-04-11 10:16:09 +0300
categories: tripleo freeipa openstack
---

Configuring FreeIPA to be the backend of a keystone domain is pretty simple
nowadays with recent additions to TripleO.

I took the configuration and several aspects of the setup (such as the users)
from [RDO VM Factory][config] and used to to create the following environment
file which we'll use for TripleO:

{% highlight yaml %}
parameter_defaults:
  KeystoneLDAPDomainEnable: true
  KeystoneLDAPBackendConfigs:
    freeipadomain:
      url: ldaps://ipa.example.com
      user: uid=keystone,cn=users,cn=accounts,dc=example,dc=com
      password: MySecretPassword
      suffix: dc=example,dc=com
      user_tree_dn: cn=users,cn=accounts,dc=example,dc=com
      user_objectclass: person
      user_id_attribute: uid
      user_name_attribute: uid
      user_mail_attribute: mail
      user_allow_create: false
      user_allow_update: false
      user_allow_delete: false
      group_tree_dn: cn=groups,cn=accounts,dc=example,dc=com
      group_objectclass: groupOfNames
      group_id_attribute: cn
      group_name_attribute: cn
      group_member_attribute: member
      group_desc_attribute: description
      group_allow_create: false
      group_allow_update: false
      group_allow_delete: false
      user_enabled_attribute: nsAccountLock
      user_enabled_default: False
      user_enabled_invert: true
{% endhighlight %}

We'll call this **freeipa-ldap-config.yaml**.

Note that I set a user with uid called `keystone`. We'll need to create this on
the FreeIPA side. For convenience, we'll also create a demo user. So, with your
FreeIPA admin credentials loaded, do the following:

{% highlight bash %}
create_ipa_user() {
    echo "$2" | ipa user-add $1 --cn="$1 user" --first="$1" --last="user" --password
}
# Add a keystone user that Keystone will bind as
create_ipa_user keystone MySecretPassword

# Add a demo user
create_ipa_user demo MySecretPassword
{% endhighlight %}

Now, having this, we can do an overcloud install adding the configuration to
the environments:

{% highlight bash %}
./overcloud-deploy.sh -e freeipa-ldap-config.yaml
{% endhighlight %}

When the deployment finishes, for convenience, we'll assign the admin role for
our admin user. We already have credentials for this user in the generated
overcloudrc file from the deployment. So we'll source that file, and add the
role:

{% highlight bash %}
source overcloudrc.v3
openstack role add --domain $(openstack domain show freeipadomain -f value -c id)\
        --user $(openstack user show admin --domain default -f value -c id) \
        $(openstack role show admin -c id -f value)
{% endhighlight %}

Note that keystone v3 is needed for this, so we sourced **overcloudrc.v3**.

Now that we have a role in the FreeIPA-backed domain, we can list its users:

{% highlight bash %}
$ openstack user list --domain freeipadomain
+------------------------------------------------------------------+----------+
| ID                                                               | Name     |
+------------------------------------------------------------------+----------+
| 1bf11b164f896bbbaa94c7ca7de6d54fcd49f46e3e0fa452c7334bcd0586aeba | admin    |
| 61673b89cc0f0d50de0e649587c8ef2ecd28e3a029fde529a1db77ed0cf7c1d9 | keystone |
| b16f3fe6a5ffbca9e4fd45131f935dc516a21b597fc894dff4a1290d4ce8c6db | demo     |
+------------------------------------------------------------------+----------+
{% endhighlight %}

[config]: https://github.com/nkinder/rdo-vm-factory/blob/master/rdo-domain-setup/vm-post-cloud-init-rdo.sh#L76-L109
