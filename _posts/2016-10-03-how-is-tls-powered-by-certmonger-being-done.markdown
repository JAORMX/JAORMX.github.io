---
layout: post
title:  "How is TLS powered by certmonger being done"
date:   2016-10-03 08:36:04 +0300
categories: tripleo openstack
---

I've been working on trying to get TLS everywhere for TripleO. And, while not
everything has merged yet to the project, this is an overview of how things are
being done, which I hope helps reviewers have an easier time checking it out.
And me sanity-checking the approach.

# So what's this about?

The point is to try to get all the endpoints to listen for TLS connections
everywhere that's possible to do so. So this will include the OpenStack
services (which means their HAProxy endpoints and the actual service which is
in the internal network), RabbitMQ, MySQL (Database traffic and repplication
traffic) and MongoDB; to begin with.

Now, as we know, to set up TLS for a service, we need the service to have a TLS
certificate, and a key-pair. However, this certificate needs to be issued by a
certificate authority (CA) which entities communicating with that service
trust. Also, the installation (provisioning of the certificate and keys) needs
to happen on a secure manner. On the other hand, this certificate does expire,
so it needs to be renewed when this happens, and this also needs to happen in a
secure manner.

While we could just attempt to inject the certificates/keys to the overcloud
nodes (as we are able to do for the public-facing certificate of HAProxy), we
have to consider that for TLS-everywhere, we also attempt to secure the
services on the internal network, which are listening on an interface dedicated
to that specific node. So we need certificates for the virtual interfaces which
we listen on and also on the actual interfaces of the services, which require a
certificate/key per-node. On the other hand, we have to consider that our
deployments can have several networks (with most services listening on the
internal-api network, but some services actually listening on the control-plane
network, and others in the storage network), and there are even plans to make
these networks more flexible. So given this, we even need a certificate
per-network in each of the nodes. So, lets say that we have 3 controllers, and
services are listening on three networks (internal-api, ctlplane and storage);
this means that we'll 9 certificates that are node-specific, and given that we
have HAProxy listening on the VIPs, we need more 3 for HAProxy (and the public
certificate too).

Now, we could use wildcard certificate to address this, so it would be way
easier to deploy. However, this comes with several concerns. To begin with, on
the security-side, the compromise of just one node or sub-domain would end up
compromising all nodes. On the other hand, when revoking a wildcard
certificate, all nodes will need a new certificate, and given the amount of
nodes and endpoints we have, this can mean a lot of work.

So, instead, we will actually go for the single-domain certificates. However,
we'll rely on certmonger to handle this automatically for us. Since it will do
the certificate request for us, handle renewals, and even do pre-save and
post-save commands which we will need (such as getting an appropriate format
for the HAProxy certificates or change file ownerships). It needs, however, to
communicate to a real CA. So, to get a real CA for certmonger to communicate
to, we can go with FreeIPA, which can offer a lot more functionality that we
can use in TripleO besides just certificate issuance. However, certmonger can
work with other CAs, so we're not limited on that side.

### Note on FreeIPA

For FreeIPA to be able to issue certificates for a node or service. The node
and the service need to have a principal on FreeIPA, and to get this, we need
to enroll the node. This enrollment allows us to trust FreeIPA as a CA (all
nodes registered would trust it, which is what we want anyway) and enables the
node a kerberos keytab, which it can use to authenticate and subsequently do
requests to FreeIPA.

Enrollment can be a big problem by itself, because we want to also do this in a
secure manner. And for this, my colleagues are working on an
OpenStack-friendly approach which involved adding hooks to nova. However, since
this approach is not available yet, I'm using ExtraConfigPre hooks to pass the
necessary data for nodes to do the enrollment. This data is pretty much just
the FreeIPA DNS name, an OTP which the node uses to authenticate in the
enrollment phase and the kerberos realm.

FreeIPA does not issue certificates for IP addresses, so for the overcloud we
will need to use FQDNs for each of the endpoints, and these will be used in
both the CNs and the SubjectAltNames of the certificates.

# Approach

## HAProxy

The undercloud's HAProxy already can use certmonger for getting the public
certificate. Setting this in practice is a matter of setting the
``generate_service_certificates`` flag on hiera to ``true``, specifying the
specs for the certificate to generate using the ``certificates_specs``
parameter for the haproxy profile (which one can set via hiera with the
``tripleo::profile::base::haproxy::certificates_specs`` key, telling
certmonger which CA to talk to with the ``certonger_ca`` hiera key, and
finally, telling HAProxy where the relevant PEM file is located via the
``service_certificate`` parameter of the haproxy manifest (which is
_manifests/haproxy.pp_ and not the service profile).

Since the profile already takes a hash for auto-generating the certificate, we
can use this to generate the other certificates we need for the internal/admin
endpoints (it's more than an extra certificate since not all services listen on
the internal-api network). The format of the ``certificates_specs`` hash for
HAProxy is as follows:

    haproxy-<NETWORK name>:
      service_pem: '/etc/pki/tls/certs/overcloud-haproxy-<NETWORK name>.pem'
      service_certificate: '/etc/pki/tls/certs/overcloud-haproxy-<NETWORK name>.crt'
      service_key: '/etc/pki/tls/private/overcloud-haproxy-<NETWORK name>.key'
      hostname: "%{hiera('cloud_name_<NETWORK name>')}"
      postsave_cmd: "" # TODO
      principal: "haproxy/%{hiera('cloud_name_<NETWORK name>')}"

Where network name is defined in tripleo-heat-templates. With this in mind, the
certificate for the internal-api network, it would look like this:

    haproxy-internal_api:
      service_pem: '/etc/pki/tls/certs/overcloud-haproxy-internal_api.pem'
      service_certificate: '/etc/pki/tls/certs/overcloud-haproxy-internal_api.crt'
      service_key: '/etc/pki/tls/private/overcloud-haproxy-internal_api.key'
      hostname: "%{hiera('cloud_name_internal_api')}"
      postsave_cmd: "" # TODO
      principal: "haproxy/%{hiera('cloud_name_internal_api')}"

We can make this more automatic by iterating the networks that the services
listen on in tripleo-heat-templates.

Now, HAProxy takes the certificate and key in PEM format, but requires them to
be appended together. This is why we have a field for the certificate, the key,
and the appended PEM that will actually be read by HAProxy. And fortunately,
we have entries in hiera to get the FQDN that's assigned to a VIP for each of
the networks, so we'll use those.

So, having these specs for the certificates, we'll just let puppet execute
``ensure_resources`` using that hash, and it'll end up calling certmonger to do
the hard work for us.

For HAProxy we can only pass the path of the PEM file for the public
endpoints, and, given that we have the paths for the certificates in the spec,
I thought it would be a good idea to pass in the spec itself to the haproxy
manifest, and get the paths from there. This way, for each service we can
choose an appropriate certificate depending on the network it's listening on,
thus reducing the complexity of this.

Finally, we have to remember to set the endpoints for the services to https,
which we do by having an environment that sets the values of the EndpointMap to
https in all endpoints, and uses CLOUDNAME for all the endpoints (since we need
to use FQDNs and not IP addresses).

## OpenStack services

Some services are already running over Apache HTTPd, so these we can easily
start running with TLS enabled. However, We don't want to run cryptographic
operations in Python. So we'll do these services separately.

### Services running over Apache HTTPd

Taking as a reference the same approach we used for HAProxy, we'll do something
similar here. We'll re-use the `generate_service_certificates` flag and base
the certificate provisioning on hashes which we refer as specs. However,
we'll also add a flag that tells the services whether to get the paths of the
certificates and pass those to the services or not. We'll call this flag
`enable_internal_tls` and pass it via hiera.

Now, since httpd does take a separate file for the certificate and the
key, the specs don't need the `service_pem` key. So our spec for the
certificates will look as the following:

    httpd-<NETWORK name>:
      service_certificate: '/etc/pki/tls/certs/httpd-<NETWORK name>.crt'
      service_key: '/etc/pki/tls/private/httpd-<NETWORK name>.key'
      hostname: "%{::fqdn_<NETWORK name>}"
      principal: "HTTP/%{::fqdn_<NETWORK name>}"

Noting that we need a certificate per-network since some OpenStack services
also listen on networks different than internal-api. Thankfully, we do have
facts in puppet to get the hostname for the node depending on the network, so
we use those in the specs (we change this to hiera in the near future).

We already have `mod_ssl` installed in the overcloud nodes (since it's part of
the image) so enabling TLS with the paths that come from the specs is just a
matter of passing those paths to the vhost resource, and puppet will do its
work.
