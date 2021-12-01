---
layout: post
title:  "Enforcing policies on Selinux profiles in Kubernetes"
date:   2021-11-30 10:28:50 +0200
categories: selinux kubernetes
---

We recently introduced a more user-friendly representation for SelinuxProfiles
in the [Security Profiles Operator](https://github.com/kubernetes-sigs/security-profiles-operator/pull/675).

As opposed to having our users know CIL, they'll be now exposed to a subset
of operations that allow for simpler profile writing. A sample profile looks
as follows:

```yaml
---
apiVersion: security-profiles-operator.x-k8s.io/v1alpha2
kind: SelinuxProfile
metadata:
  name: errorlogger
  namespace: my-namespace
spec:
  inherit:
    - name: container
  allow:
    var_log_t:
      dir:
        - open
        - read
        - getattr
        - lock
        - search
        - ioctl
        - add_name
        - remove_name
        - write
      file:
        - getattr
        - read
        - write
        - append
        - ioctl
        - lock
        - map
        - open
        - create
      sock_file:
        - getattr
        - read
        - write
        - append
        - open
```

This will be compiled to [CIL](https://github.com/SELinuxProject/cil) and taken
into use by [selinuxd](https://github.com/containers/selinuxd). The SPO will then
output an appropriate status in the same CRD, so as a user you'll see what's the
state of the profile.

We also have a raw counterpart for this that allows folks to take policies generated
by tools like [Udica](https://github.com/containers/udica). The profile looks as follows:

```yaml
---
apiVersion: security-profiles-operator.x-k8s.io/v1alpha2
kind: RawSelinuxProfile
metadata:
  name: errorlogger
spec:
  policy: |
    (blockinherit container)
    (allow process var_log_t ( dir ( open read getattr lock search ioctl add_name remove_name write ))) 
    (allow process var_log_t ( file ( getattr read write append ioctl lock map open create  ))) 
    (allow process var_log_t ( sock_file ( getattr read write append open  ))) 
```

# So... why is this a good thing?

Besides looking a little more Kubernetes-like. The new `SelinuxProfile` format brings
some advantages:

* We now have a subset of CIL which is easier to manage: most people don't need the
  full power of the language.
* We can now more easily validate each part of the profile: we plan to get more
  information from selinuxd to know if the labels, object classes and permissions
  are even possible to use. Thus making debugging more targeted.
* We can now take into use advanced policy engines like Gatekeeper to restrict
  SELinux usage (more on this later).

... And, for people who need more advanced policies; they can still use the raw
version and take all of CIL's capabilities into use.

As we get more feedback on people's needs and use-cases, we can expand
this format. We want this to be useful for most folks!

# Policies on top of SELinux?

In most cases, the fact that workload would need another SELinux profile
other than the default is already an advanced case. Normally you do
want to re-evaluate your application and see if you can get rid of those
extra permissions that make you even need that custom SELinux profile.

However, as we're all aware, there will always be special cases where
the application does need extra privilege. e.g. mounting a device on the
host to use SR-IOV, mount the audit logs to do log forwarding, or use
special hardware device.

And even so, do you want to allow profile writers to use all labels and
object classes?

Probably not!

Let's use Gatekeeper to lock down what profile writes can do
and audit when they do something they're not supposed to.

## The Gatekeeper policy

In this case, we'll disallow profile writers from using the
`security_t` and any label starting with `selinux_`.  We don't
want them to touch these as they pertain the host's SELinux
configuration and management.

The ConstraintTemplate would look as follows:

```yaml
---
apiVersion: templates.gatekeeper.sh/v1beta1
kind: ConstraintTemplate
metadata:
  name: disallowsposelinuxlabels
  annotations:
    description: |-
      Disallows SelinuxProfile objects from using SELinux-specific labels in
      their profiles
spec:
  crd:
    spec:
      names:
        kind: DisallowSPOSelinuxLabels
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package disallowsposelinuxlabels

        violation[{"msg": msg}] {
          input.review.object.kind == "SelinuxProfile"
          sprofobj := input.review.object
          label_is_selinux_related(sprofobj)
          msg := sprintf("SelinuxProfiles aren't allowed to use labels pertaining to SELinux management %v", [sprofobj.metadata.name])
        }

        label_is_selinux_related(sprofobj) = true {
          some label
          sprofobj.spec.allow[label]
          is_security_t(label)
        }

        label_is_selinux_related(sprofobj) = true {
          some label
          sprofobj.spec.allow[label]
          is_selinux_specific(label)
        }

        is_security_t(label) = true {
          label = "security_t"
        }

        is_selinux_specific(label) = true {
          startswith(label, "selinux_")
        }
```

Rego might be a little cryptic, but basically this verifies that the object's
kind is indeed `SelinuxProfile`, and if so, it'll issue a violation if:
The any label in the allow list is `security_t` or any label in the allow
list starts with `selinux_`.

Once this is applied, we can enforce it by creating the constraint:

```yaml
---
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: DisallowSPOSelinuxLabels
metadata:
  name: disallow-spo-selinux-labels
spec:
  match:
    kinds:
      - apiGroups: ["security-profiles-operator.x-k8s.io"]
        kinds: ["SelinuxProfile"]
```

once Gatekeeper has persisted the above configuration and it starts
validating it. We can try it out!

The errorlogger profile that we mentioned above should be applicable:

```
$ oc apply -f examples/selinuxprofile.yaml
selinuxprofile.security-profiles-operator.x-k8s.io/errorlogger created
```

Note that `examples/selinuxprofile.yaml` exists in the Security Profiles
Operator repository.

Now, let's see a profile that would fail:

```yaml
---
apiVersion: security-profiles-operator.x-k8s.io/v1alpha2
kind: SelinuxProfile
metadata:
  name: profile-that-uses-selinux
spec:
  inherit:
    - name: container
  allow:
    var_log_t:
      dir: ["open", "read", "getattr", "lock", "search", "ioctl", "add_name", "remove_name", "write"]
      file: ["getattr", "read", "write", "append", "ioctl", "lock", "map", "open", "create"]
      sock_file: ["getattr", "read", "write", "append", "open"]
    selinux_config_t:
      dir: ["open", "read", "getattr", "lock", "search", "ioctl", "add_name", "remove_name", "write"]
      file: ["getattr", "read", "write", "append", "ioctl", "lock", "map", "open", "create"]
```

As you can tell, this adds several permissions to the container that
enable it to modify files labeled with `selinux_config_t`. This is not
good, as it could give the container the ability to modify the
SELinux configuration in unexpected ways.

Let's try to apply this policy then:

```
$ oc apply -f path-to-bad-policy.yaml
Error from server ([disallow-spo-selinux-labels] SelinuxProfiles aren't allowed to use labels pertaining to SELinux management profile-that-uses-selinux): error when creating "path-to-bad-policy.yaml": admission webhook "validation.gatekeeper.sh" denied the request: [disallow-spo-selinux-labels] SelinuxProfiles aren't allowed to use labels pertaining to SELinux management profile-that-uses-selinux
```

As we can see, Gatekeeper denied the request as it violated out policy.

While this was a very simple rule, we can start creating more comprehensive ones that
would disallow profile writes from gaining dangerous privileges. We could
even make our Gatekeeper policy parametrized so we could make these labels
configurable by system administrators!

# Conclusion

The more we move towards kube-native resources (even for our SELinux profiles)
the more advantage we can take of all the amazing tooling in the ecosystem.

The intent of creating user-friendly SelinuxProfile objects was not only to
allow for more readable profile writing, but also to be able to do more
complex things with cloud-native tooling.

While this was a small demo, I'm sure we can do more things with this.

The Security Profiles Operator is surely moving in interesting paths!