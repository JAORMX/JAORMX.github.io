---
layout: post
title:  "Deploying a TLS everywhere environment with oooq and an existing FreeIPA server"
date:   2017-02-21 10:04:00 +0200
categories: tripleo openstack
---

As an attempt to make the "TLS everywhere" bits more usable and easier for
people to try out, I added the deployment steps to tripleo-quickstart.

This currently works if you have an existing FreeIPA server installed somewhere
accessible. Note that in this example, the IP is set to '192.168.24.250'. this
is because that's the value that we use in CI. So use what suits your
deployment.

The main things to be added to the configuration are the following:

{% highlight yaml %}

# Main switch to enable all the workflow
enable_tls_everywhere: true

# Undercloud FQDN
undercloud_undercloud_hostname: undercloud.example.com

# Hostnames and domain relevant for the overcloud
overcloud_cloud_name: overcloud.example.com
overcloud_cloud_name_internal: overcloud.internalapi.example.com
overcloud_cloud_name_storage: overcloud.storage.example.com
overcloud_cloud_name_storage_management: overcloud.storagemgmt.example.com
overcloud_cloud_name_ctlplane: overcloud.ctlplane.example.com
overcloud_cloud_domain: example.com

# Nameservers for both the undercloud and the overcloud
overcloud_dns_servers: ["192.168.24.250"]
undercloud_undercloud_nameservers: ["192.168.24.250"]

freeipa_admin_password: FreeIPA4All

freeipa_server_hostname: ipa.example.com

{% endhighlight %}

* `enable_tls_everywhere`: This is the main switch that will enable the whole
  workflow. It defaults to false.
* `undercloud_undercloud_hostname`: This will set the hostname for the
  undercloud node and will be used in this workflow to create the host
  principal for the undercloud.
* The following are the hostnames for the overcloud VIPs. They will be used as
  the keystone endpoints. Please note that these values are network dependant,
  and the names should reflect it. The values are these:

    * `overcloud_cloud_name`
    * `overcloud_cloud_name_internal`
    * `overcloud_cloud_name_storage`
    * `overcloud_cloud_name_storage_management`
    * `overcloud_cloud_name_ctlplane`

* `overcloud_cloud_domain`: This is the domain for the cloud deployment. It
  will be used for the overcloud nodes, and should match the FreeIPA kerberos
  realm.
* `overcloud_dns_servers`: This is a list of servers that will be used as the
  nameservers for the overcloud nodes. It gets persisted in the DnsServers
  parameter in heat.
* `undercloud_undercloud_nameservers`: This is a list of servers that will be
  used as the nameservers for the undercloud node.
* `freeipa_admin_password`: This is the password for the admin user of your
  FreeIPA server.
* `freeipa_server_hostname`: The FQDN of your FreeIPA server.

The main things that are added to the deployment workflow are the following:

* Before installing the undercloud, we install the novajoin package, and use
  the FreeIPA credentials to set up the necessary permissions/privileges in
  FreeIPA, as well as create the undercloud service principal.

* Before uploading the overcloud images to glance, we install a specific
  version of cloud-init for novajoin to work. This is because the version
  that's currently in CentOS has a bug; and the newest version available has
  dependency issues that doesn't let Heat software deployments work.

* It adds the relevant environment files to the overcloud deploy script created
  by quickstart. These will in turn deploy the overcloud with TLS-everywhere
  enabled.

In some instances, you might not want to give your FreeIPA credentials to
ansible. If this is the case, you'll need to run the preparation script for
novajoin yourself. If you want to do this, you will also need to set up the
following flag:

{% highlight yaml %}
prepare_novajoin: false
{% endhighlight %}
