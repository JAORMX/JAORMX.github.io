---
layout: post
title:  "Where is the certmonger local CA cert?"
date:   2016-06-22 14:13:03 +0300
categories: tripleo certmonger
image: /images/cup.jpg
---

_There is a TLDR in the end._

So, I'm looking a bit more into certmonger. And in this case, I want to replace
the hardcoded openssl commands that autogenerate the CA and server certificates
for the undercloud, for a certmonger-based solution.

While setting up the pieces in the undercloud code I decided to first try with
the 'local' CA from certmonger, to be able to test what I'm doing easily. But
then I realized that I actually have no clue where this certificate is stored.

So after digging a bit in the certmonger code-base, I found out that the
certificate is stored in a pkcs12 file in this path:
_/var/lib/certmonger/local_. The file name is creds, and in order to check out
the contents, you can do the following:

{% highlight bash %}
pk12util -l creds
{% endhighlight %}

Note that the file has no password.

So, even if the PKCS12 format is nice and all, we need the certificate in PEM
format to be actually used by the overcloud. So we can export it with the
following command:

{% highlight bash %}
openssl pkcs12 -in creds -out $OUTPUT_FILE -nokeys -nodes -passin pass:""
{% endhighlight %}

_-nokeys-_ is used to prevent the private key from being exported as well to
the PEM file. For our use-case, we only need the certificate.

## TLDR;

In Fedora and CentOS It's in a PKCS12 file which is this:

    /var/lib/certmonger/local/creds

### Important note

Please note that the 'local' CA from certmonger shouldn't be used in
production. A real CA should be used instead.
