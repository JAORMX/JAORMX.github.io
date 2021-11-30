---
layout: post
title:  "A quick update on SELinux as a resource in Kubernetes"
date:   2021-11-30 10:06:59 +0200
categories: openshift
---

It's been a while since I've blogged about SELinux as a resource in Kubernetes,
and I thought it was time to do so.

The `selinux-operator` and `selinux-policy-helper-operator` saw some interest.
And, as it turns out, we were not the only ones with security profile
installation enhancements in mind. The up-and-coming project called
[Security Profiles Operator (or SPO)](https://github.com/kubernetes-sigs/security-profiles-operator)
had the same goal in mind!

Some time ago, my colleague Jakub and I reached out to the team involved in the
SPO and we decided to join efforts in order to have a more complete and relevant
project. So, we moved all of the functionality from the `selinux-operator` and
the `security-policy-helper-operator` into the Security Profiles Operator.

Things have evolved very nicely ever since.

* The SPO now has support for installing Seccomp, SELinux and AppArmor profiles.
* We've converged all projects to use common components (such as a common
  profile-node status)
* We've re-architected the SELinux parts to require less dependencies and work
  in a more efficient manner when auto-generating profiles (we call this a recording)
* We've also introduced a new and more user-friendly format for SELinux profiles.
* For folks introducing SELinux profiles coming from another tool, we also enable
  using the raw profile. This is done through the `RawSelinuxProfile` CRD.
* We also have appropriate metrics for all of our supported technologies, so one
  could build appropriate alerts for these.

Overall, I'm very excited about the path the SPO is taking!