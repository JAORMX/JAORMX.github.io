---
layout: post
title:  "Porting Glance to run over Apache HTTPd"
date:   2016-09-23 09:03:47 +0300
categories: openstack
image: /images/cup.jpg
---

In the quest of getting TLS everywhere in TripleO, with a bunch of
work-in-progress patches I got services running over httpd to use TLS for the
internal network. Now the question is, what do we do with the rest of the
services? Not many people want to run their crypto on python, so we need to
figure out something else. There are two options: Run a proxy in front of the
service or port that service to run over httpd (which we already would have
patches to enable TLS for it). So I opted for the second option.

For some reason I decided to go and try to do Glance first.

Getting a wsgi script that httpd will fetch was not a big problem. I couldn't
use the same approach as Keystone did, because Glance's wsgi script is very
tied to eventlet. However, Nova already has a [script][nova-script] that looks
fairly simple and straight forward, so I went ahead and based Glance's on that
one. Now, I had to do a couple of extra imports and configurations (such as
loading glance\_store and it's configuration options). But it runs!

It might have been too big of a step, but I also decided to write the puppet
manifest at the same time, in order to test that in conjunction with TripleO's
undercloud deployment. Based on the work that's already done in puppet-keystone
and puppet-barbican, that wasn't too hard either; and after several failures
due to me messing up puppet syntax, it was running!

One thing to note is that Glance sends images with [chunked transfer
encoding][chunked-transfer], so we need to add this to the vhost configuration:

    WSGIChunkedRequest On

Else we will get a bunch of errors where our request gets rejected due to the
content-length.

### So it was time to try it out!

Doing `openstack image list` did exactly what I needed, and deleting the
_overcloud-full_ image (in order to re-upload it) was working too. So I went
ahead and tried to do `openstack overcloud image upload --update-existing`
which will go through all the images needed in TripleO, check if they're
up-to-date and for each image that is not up-to-date it will upload the new
version.

... This didn't work out. I started getting errors related to the _disk format_
not being specified. Which is strange... Using the _--debug_ option, I could
clearly see that x-image-meta-disk\_format was being included in the headers.
So what's going on?

So I went ahead and ran _tcpdump_ on the HAProxy endpoint and the glance
endpoint, and noticed this:

* python-tripleoclient uses Glance's internal endpoint, not the public one.
  This currently goes directly to Glance (I'm trying to fix that).

* Doing _tcpdump_ on glance is not a smart idea. While in the end I got the
  information I needed. I realized that since glance is trying to upload the
  image, the amount of packages dumped was REALLY big, and since the packages
  are chunked, it doesn't help to filter them by size.

But I did notice that the header was actually being sent to the endpoint. So
the problem lies somewhere within.

I ended up modifying the [cors middleware][cors] to print the headers of
incoming requests, and here I noticed that indeed the
x-image-meta-disk\_format was missing. However, other headers like
x-image-meta-name were actually present. Was it an issue with the underscores?

### Yes... it was the underscores

After searching around (which I should have done from the start) I then
stumbled upon [this][httpd-doco]:

    Translation of headers to environment variables is more strict than before
    to mitigate some possible cross-site-scripting attacks via header
    injection. Headers containing invalid characters (including underscores)
    are now silently dropped. Environment Variables in Apache has some pointers
    on how to work around broken legacy clients which require such headers.
    (This affects all modules which use these environment variables.)

... And glance uses underscores in the headers... Fortunately, the Glance team
is aware of the [issue][glance-bug] and it has been fixed on the server-side.
So nowadays, glance-api will also accept hyphens instead of underscores.

### Going around the issue (and failing)

The Apache documentation has a [recommendation][fixheaders] to go around this
issue. This consists of getting each header individually, storing the value in
an environment variable, and then writing the header back (with hyphens
instead) with the value of that environment variable. This means that I have to
do that for each header that glance uses with underscores.

I couldn't figure figure out how to have a more generic solution for httpd, so
if you know a way, please let me know.

So, getting that list from glance's code-base, This is the resulting
configuration that I needed to add:

    SetEnvIfNoCase ^x.image.meta.is.public$ ^(.+)$ image_meta_is_public=$1
    SetEnvIfNoCase ^x.image.meta.disk.format$ ^(.+)$ image_meta_disk_format=$1
    SetEnvIfNoCase ^x.image.meta.container.format$ ^(.+)$ image_meta_container_format=$1
    SetEnvIfNoCase ^x.image.meta.copy.from$ ^(.+)$ image_meta_copy_from=$1
    SetEnvIfNoCase ^x.image.meta.created.at$ ^(.+)$ image_meta_created_at=$1
    SetEnvIfNoCase ^x.image.meta.updated.at$ ^(.+)$ image_meta_updated_at=$1
    SetEnvIfNoCase ^x.image.meta.deleted.at$ ^(.+)$ image_meta_deleted_at=$1
    SetEnvIfNoCase ^x.image.meta.min.ram$ ^(.+)$ image_meta_min_ram=$1
    SetEnvIfNoCase ^x.image.meta.min.disk$ ^(.+)$ image_meta_min_disk=$1
    SetEnvIfNoCase ^x.image.meta.virtual.size$ ^(.+)$ image_meta_virtual_size=$1
    RequestHeader set x-image-meta-is-public %{image_meta_is_public}e env=image_meta_is_public
    RequestHeader set x-image-meta-disk-format %{image_meta_disk_format}e env=image_meta_disk_format
    RequestHeader set x-image-meta-container-format %{image_meta_container_format}e env=image_meta_container_format
    RequestHeader set x-image-meta-copy-from %{image_meta_copy_from}e env=image_meta_copy_from
    RequestHeader set x-image-meta-created-at %{image_meta_created_at}e env=image_meta_created_at
    RequestHeader set x-image-meta-updated-at %{image_meta_updated_at}e env=image_meta_updated_at
    RequestHeader set x-image-meta-deleted-at %{image_meta_deleted_at}e env=image_meta_deleted_at
    RequestHeader set x-image-meta-min-ram %{image_meta_min_ram}e env=image_meta_min_ram
    RequestHeader set x-image-meta-min-disk %{image_meta_min_disk}e env=image_meta_min_disk
    RequestHeader set x-image-meta-virtual-size %{image_meta_virtual_size}e env=image_meta_virtual_size

Testing this out glance is finally able to upload images... But now the crash
was in python-tripleoclient. As a property for the image, it specifies the
'kernel_id' which it also sends with an underscore. And since the properties is
not something that's defined. It seems that the Apache solution is not
sufficient for our case.

### Do it in haproxy?

So the other option I tried was to modify the headers via HAProxy. For which
the regsub function would have been really good. But it seems that the version
of HAProxy we're using is too old. So that's a no go. On the other hand, I
could try to use _reqrep_ but that would be replacing underscores for hyphens
in all the request header (including the value) which is not something I want.
And after some time, I didn't come up with a clever enough regex.

### Did I get it working?

Well... In the end I patched up python-glanceclient to stop using those invalid
characters. And that worked just fine. No need for fancy httpd or HAProxy
configuration. So I submitted the patch. Lets see how that goes.

[nova-script]: https://github.com/openstack/nova/blob/master/nova/wsgi/nova-api.py
[chunked-transfer]: https://en.wikipedia.org/wiki/Chunked_transfer_encoding
[cors]: https://github.com/openstack/oslo.middleware/blob/master/oslo_middleware/cors.py
[httpd-doco]: https://httpd.apache.org/docs/trunk/new_features_2_4.html
[glance-bug]: https://bugs.launchpad.net/glance/+bug/1276887
[fixheaders]: https://httpd.apache.org/docs/trunk/env.html#fixheader
