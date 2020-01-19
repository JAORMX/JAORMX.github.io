---
layout: post
title:  "SELinux and docker notes"
date:   2018-02-13 13:13:59 +0200
categories: docker selinux
image: /images/cup.jpg
---

SELinux and docker notes
========================

Since the Pike release, we run most of the TripleO services on containers. As
part of trying to harden the deployment, I'm investigating what it takes to run
our containers with SELinux enabled.

Here are some of the things I learned.

Enabling SElinux for docker containers
--------------------------------------

Docker has the ``--selinux-enabled`` flag by default in CentOS 7.4.1708.
However, in case your image or your configuration management tool is disabling
it, as was the case for our puppet module verify this, you verify by running
the following command:

{% highlight bash %}

$ docker info | grep 'Security Options'
Security Options: seccomp

{% endhighlight %}

To enable it, you need to modify the ``/etc/sysconfig/docker`` file, which you
can use to enable SELinux for docker. In this file you'll notice the
``$OPTIONS`` variable defined there, where you can append the relevant option
as follows:

{% highlight bash %}

OPTIONS="--log-driver=journald --signature-verification=false --selinux-enabled"

{% endhighlight %}

After restarting docker:

{% highlight bash %}

$ systemctl restart docker

{% endhighlight %}

You'll see SELinux is enabled as a security option:

{% highlight bash %}

$ docker info | grep 'Security Options'
Security Options: seccomp selinux

{% endhighlight %}

Note that for this to actually have any effect, SELinux must be enforcing in
the host itself.

Docker containers can read ``/etc`` and ``/usr``
------------------------------------------------

SELinux blocks writes to files in ``/etc/`` and ``/usr/``, but it allows
reading them.

Lets say we create a file in the /etc/ directory:

{% highlight bash %}

$ echo "Hello from the host" | sudo tee /etc/my-file.txt
Hello from the host
$ ls -lZ /etc/my-file.txt
-rw-r--r--. root root unconfined_u:object_r:etc_t:s0   /etc/my-file.txt

{% endhighlight %}

Now, lets mount the file in a container and attempt to read and write it.

{% highlight bash %}

$ docker run -ti -v /etc/my-file.txt:/tmp/my-file.txt alpine sh
(container)$ cat /tmp/my-file.txt
Hello from the host
(container)$ echo "Hello from the container" >> /tmp/my-file.txt
sh: can't create /tmp/my-file.txt: Permission denied

{% endhighlight %}

The same is possible if the file contains labeling more standard to the
/etc/directory:

{% highlight bash %}

# ls -lZ /etc/my-file.txt
-rw-r--r--. root root system_u:object_r:etc_t:s0       /etc/my-file.txt
$ docker run -ti -v /etc/my-file.txt:/tmp/my-file.txt alpine sh
(container)$ cat /tmp/my-file.txt
Hello from the host
(container)$ echo "Hello from the container" >> /tmp/my-file.txt
sh: can't create /tmp/my-file.txt: Permission denied

{% endhighlight %}

This same behavior is not seen if we attempt it in another directory. Say, the
user's home directory:

{% highlight bash %}

$ pwd
/home/stack
$ mkdir test
$ echo "Hello from the host" >> test/my-file.txt
$ ls -lZ test/my-file.txt
-rw-rw-r--. stack stack unconfined_u:object_r:user_home_t:s0 test/my-file.txt
$ docker run -ti -v /home/stack/test/my-file.txt:/tmp/my-file.txt alpine sh
(container)$ cat /tmp/my-file.txt
cat: can't open '/tmp/my-file.txt': Permission denied
(container)$ ls /tmp/
ls: /tmp/my-file.txt: Permission denied

{% endhighlight %}

This might be useful if we want to mount a CA certificate for the container to
trust, as it will effectively be read-only:

{% highlight bash %}

$ ls -lZ /etc/pki/ca-trust/source/anchors/cm-local-ca.pem
-rw-r--r--. root root unconfined_u:object_r:cert_t:s0  /etc/pki/ca-trust/source/anchors/cm-local-ca.pem
$ docker run -ti -v /etc/pki/ca-trust/source/anchors/cm-local-ca.pem:/tmp/ca.crt alpine sh
(container)$ cat /tmp/ca.crt
-----BEGIN CERTIFICATE-----
MIIDjTCCAnWgAwIBAgIQD6sfY0A+T7SHIG6yzfh//zANBgkqhkiG9w0BAQsFADBQ
MSAwHgYDVQQDDBdMb2NhbCBTaWduaW5nIEF1dGhvcml0eTEsMCoGA1UEAwwjMGZh
YjFmNjMtNDAzZTRmYjQtODcyMDZlYjItY2RmODdmZmYwHhcNMTgwMjAyMTUzNDI5
WhcNMTkwMjAyMTUzNDI5WjBQMSAwHgYDVQQDDBdMb2NhbCBTaWduaW5nIEF1dGhv
cml0eTEsMCoGA1UEAwwjMGZhYjFmNjMtNDAzZTRmYjQtODcyMDZlYjItY2RmODdm
ZmYwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQDhEJJzGBkWNslk0iav
g1E2p39uYfTE6CCdeIRxFXpiKuPg/AO1lQXkUElGcakWJcJ7bWY/be6PGfp8EoRY
OCXtuggpVHXHdfOWhnPwhwdv51frFZwchL6jiaqDz+yEB9nTlhJ6cy4JQMcriZUP
6I/Djl1lzQQiBI/leA0ieNxTfGYifXHEGCDnNiyxIq32BzLcKUaMkl1sNmXjLZ1U
JW5ThPNs7IR/2zZgTyicDZTgLNUsn7oAQMXDffBOLOrx+MpX9k3o+XqBVcnb2+5Q
eQBxOAEjhbjel7GTTbkEajlCohcxvcycTot6hrd9xY3MTM3NHE/ysIs0zdnEkwLx
84v7AgMBAAGjYzBhMA8GA1UdEwEB/wQFMAMBAQEwHQYDVR0OBBYEFDWB9zN+m0K6
xSauu4CUYdrcdtr/MB8GA1UdIwQYMBaAFDWB9zN+m0K6xSauu4CUYdrcdtr/MA4G
A1UdDwEB/wQEAwIBhjANBgkqhkiG9w0BAQsFAAOCAQEAlrTvxDBUNqx/nbF5DSkk
R1WqbfNLt07u3kqo+dBfYo4XTEfu2kQ2UzngzirAKokJfm7D8aNJqn6lLVpP0ffc
5VM+mW96tHFearImVZS3Z8gWe5MoD7hDziF3BKW1E0vBYqKOR773H4GpLkYcBLaP
sfujE/uxle2MpNn6i56AeiRwOVIejFSKFKA6rlUDuffu9NE9eKXmO5PW0KT/ojak
JoeC4LnDug+eOU3DrLCmBYEPU+JrHwtuPDCZgVoldVHbd/k+2vvOOvEWoSrTpmoH
3PH2UINW9t7cVxGipyPX3DYu1MrLJ+k73bny5pORgx0sqWh+RoWv8yKE92PP/O5r
Pw==
-----END CERTIFICATE-----
(container)$ echo "I'm trying to tamper with the CA" >> /tmp/ca.crt
sh: can't create /tmp/ca.crt: Permission denied

{% endhighlight %}

Just be careful that the files from ``/etc/`` or ``/usr/`` that you mount into
the containers don't contain any sensitive data that you don't really want to
share.

Enabling access to files protected by SELinux
---------------------------------------------

In order to give a container access to files protected by SELinux, you need to
use one of the following volume options: z or Z.

* ``z``(lower): relabels the content you're mounting into the container, and
  makes it shareable between containers.
* ``Z``(upper): relabels the content you're mounting into the container, and
  makes it private. So, mounting this file in another container won't work.

Lets show how the ``z``(lower) flag works in practice:

{% highlight bash %}

$ ls -lZ test/my-file.txt
-rw-rw-r--. stack stack unconfined_u:object_r:user_home_t:s0 test/my-file.txt
$ docker run -ti -v /home/stack/test/my-file.txt:/tmp/my-file.txt:z alpine sh
(container)$ echo "Hello from container 1" >> /tmp/my-file.txt
(container)$ exit
$ cat test/my-file.txt
Hello from the host
Hello from container 1
$ ls -lZ test/my-file.txt
-rw-rw-r--. stack stack system_u:object_r:svirt_sandbox_file_t:s0 test/my-file.txt

{% endhighlight %}

Note that we were now able to append to the file. As we can see, from the
host we could see the changes reflected in the file. Finally, checking the
SELinux context, we will note that docker has changed the type to be
``svirt_sandbox_file_t``, which makes it shareable between containers.

If we run another container and append to that file, we will be able to do so:

{% highlight bash %}

$ docker run -ti -v /home/stack/test/my-file.txt:/tmp/my-file.txt:z alpine sh
(container2)$ echo "Hello from container 2" >> /tmp/my-file.txt
(container2)$ exit
$ cat test/my-file.txt
Hello from the host
Hello from container 1
Hello from container 2

{% endhighlight %}

Now, lets try using the ``Z``(upper) option. If we grab the same file and mount
it in a container with that option we'll see the following:

{% highlight bash %}

$ docker run -ti -v /home/stack/test/my-file.txt:/tmp/my-file.txt:Z alpine sh
(container3)$ echo "Hello from container 3" >> /tmp/my-file.txt

{% endhighlight %}

If we open another terminal, and try to append to that file, we won't be able
to:

{% highlight bash %}

$ docker run -ti -v /home/stack/test/my-file.txt:/tmp/my-file.txt:Z alpine sh
(container4)$ echo "Hello from container 4" >> /tmp/my-file.txt
sh: can't create /tmp/my-file.txt: Permission denied

{% endhighlight %}

We can verify the contents of the file:

{% highlight bash %}

$ cat test/my-file.txt
Hello from the host
Hello from container 1
Hello from container 2
Hello from container 3
$ ls -lZ test/my-file.txt
-rw-rw-r--. stack stack system_u:object_r:svirt_sandbox_file_t:s0:c829,c861 test/my-file.txt

{% endhighlight %}

Now we can see that the MCS label for the container changed and is specific to
the container that first accessed it. Assuming the container that first mounted
and accessed the file is named ``reverent_davinci``, we can check the
container's label with the following command:

{% highlight bash %}

{% raw %}
$ docker inspect -f '{{ .ProcessLabel }}' reverent_davinci
{% endraw %}
system_u:system_r:svirt_lxc_net_t:s0:c829,c861

{% endhighlight %}

And we can see that the container's MCS label matches that of the file.

Disabling SELinux for a specific container
------------------------------------------

While this is not ideal, it is possible to do by using the ``--security-opt
label:disable`` option:

{% highlight bash %}

$ docker run -ti -v /home/stack/test/my-file.txt:/tmp/my-file.txt --security-opt label:disable alpine sh
(container)$ cat /tmp/my-file.txt
Hello from the host
Hello from container 1
Hello from container 2
Hello from container 3

{% endhighlight %}

References
----------

* [https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux_atomic_host/7/html/container_security_guide/docker_selinux_security_policy]()
* [https://medium.com/lucjuggery/docker-selinux-30-000-foot-view-30f6ef7f621]()
* [https://prefetch.net/blog/index.php/2017/09/30/using-docker-volumes-on-selinux-enabled-servers/]()
* [https://www.projectatomic.io/blog/2017/02/selinux-policy-containers/]()
* [http://www.projectatomic.io/blog/2015/06/using-volumes-with-docker-can-cause-problems-with-selinux/]()
* [https://docs.docker.com/storage/bind-mounts/#configure-the-selinux-label]()
* Thanks Jason Brooks, who helped via [twitter](https://twitter.com/jasonbrooks/status/963442252642058240)
