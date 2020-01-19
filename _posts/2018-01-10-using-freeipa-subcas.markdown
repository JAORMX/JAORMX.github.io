---
layout: post
title:  "Using FreeIPA SubCAs"
date:   2018-01-10 12:14:46 +0200
categories: freeipa
image: /images/cup.jpg
---

Using lightweight CAs in FreeIPA is quite straight forward.

With an existing FreeIPA installation, you can add a sub CA with the following
command:

{% highlight bash %}

ipa ca-add

{% endhighlight %}

It will ask you to name the sub CA, and specify the Common Name and will give
an output such as the following:

{% highlight bash %}

Name: mysubca
Subject DN: CN=SUBCA
--------------------
Created CA "mysubca"
--------------------
  Name: mysubca
  Authority ID: 2e668254-d080-4913-aa85-e69d4e69e670
  Subject DN: CN=SUBCA
  Issuer DN: CN=Certificate Authority,O=RDOCLOUD
  Certificate: ...

{% endhighlight %}

The Common Name you specify is what you'll see in the "issuer" section of the
certificates you request with this sub CA. The name is a nickname of your
choice, which in this case, I used mysubca.

If you try to request certificates with just this, you'll get an error saying
you don't have sufficient privileges. To address this, we need to set the
relevant ACL for the CA.

you can see what ACLs are currently available with the following command:

{% highlight bash %}

ipa caacl-find

{% endhighlight %}

The output will look like this:

{% highlight bash %}

----------------
1 CA ACL matched
----------------
  ACL name: hosts_services_caIPAserviceCert
  Enabled: TRUE
  Host category: all
  Service category: all
----------------------------
Number of entries returned 1
----------------------------

{% endhighlight %}

To add the ACL for enabling service certificates for the new sub CA we do:

{% highlight bash %}

ipa caacl-add-ca hosts_services_caIPAserviceCert --cas=mysubca

{% endhighlight %}

Note that to specify the CA that you're adding the ACL to, you need to use the
nickname of the sub CA.

Finally, you can request certificates from your sub CA. to do so, you need to
do:

{% highlight bash %}

getcert request -c IPA -I mycert -k mykey.pem -f mycert.pem -D myinstance.rdocloud -K test/myinstance.rdocloud -N 'CN=myinstance.rdocloud' -U id-kp-clientAuth -U id-kp-clientAuth -X mysubca

{% endhighlight %}
