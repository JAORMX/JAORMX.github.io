---
layout: post
title:  "protectKernelDefaults in OpenShift"
date:   2020-11-17 13:33:19 +0200
categories: openshift
---

Lately, we've been looking into applying the CIS benchmark to OpenShift. To my pleasant surprise,
the distribution is mostly compliant by default. However, one item that called my interest more
than others was the `protectKernelDefaults` option for the Kubelet.

# What is it?

`protectKernelDefaults` (formerly a command-line flag called `--protect-kernel-defaults`) is a
[boolean option](https://github.com/kubernetes/kubernetes/blob/release-1.19/pkg/kubelet/apis/config/types.go#L295)
that controls how the Kubelet behaves if it finds a *sysctl* with a value that doesn't match what it expects.

This is option is set to `false` by default, which means that the kubelet will set sysctl's
as necessary to operate as expected.

Setting this to `true` is desired, as it would ensure that the kubelet leaves your defaults
untouched and hardened.

# So... Can't I just set it to `true` ?

Not really... Your distribution most likely doesn't have the values that the Kubelet needs by
default.

When the Kubelet encounters a value that differs from what it wants, [it'll error out](
https://github.com/kubernetes/kubernetes/blob/release-1.19/pkg/kubelet/cm/container_manager_linux.go#L433).

So, applying this will result in your node being stuck and not coming back to a usable state.

# What are these sysctl's and their values?

These sysctl's are merely values that the Kubelet expects to find in order for it to operate normally.
The values are [hardcoded into the code-base](
https://github.com/kubernetes/kubernetes/blob/release-1.19/pkg/kubelet/cm/container_manager_linux.go#L409-L415),
However, a file that sets them would look similar to this:

```
# /etc/sysctl.d/75-kubelet.conf
kernel.keys.root_maxbytes=25000000
kernel.keys.root_maxkeys=1000000
kernel.panic=10
kernel.panic_on_oops=1
vm.overcommit_memory=1
vm.panic_on_oom=0
```

## What do these do?

### `kernel.keys.root_maxkeys=1000000`

This is the maximum number of keys that the root user (UID 0 in the root user
namespace) may own. The Kubelet (and the Container Runtime) need this since [a
session key is created for every container in the system](
https://github.com/opencontainers/runc/pull/488).

### `kernel.keys.root_maxbytes=25000000`

This is the maximum number of bytes that the root user (UID 0 in the root user
namespace) may own per key. This number is dervied from the number of keys configured
in the aforementioned parameter; That number is multiplied by 25, thus allocating 25
bytes per key.

### `kernel.panic=10`

Setting `kernel.panic` to something other than zero will ensure that the
system reboots after a panic instead of the default action which is to halt.

### `kernel.panic_on_oops=1`

Setting `kernel.panic_on_oops` ensures a delay in the system before the panic.
This allows services (such as like klogd) to record the output of the panic before
the reboot happens.

### `vm.overcommit_memory=1`

Setting the `overcommit_memory` parameter to `1` will disable checking if the
system has enough memory when allocating memory for a process, until memory actually
runs out. The Kubelet has memory guarantees for pods, for which scheduling
decisions are made. These guarantees are set through the `request` resource 
setting

### `vm.panic_on_oom=0`

Setting the `panic_on_oom` parameter to `0` will ensure the kernel doesn't panic
if an OOM error arises. The Kubelet pro-actively monitors the node against total
resource starvation and will fail one or more Pods when needed to reclaim the
starved resource.


# Applying this in OpenShift

Setting this Kubelet configuration option in a running OpenShift cluster requires a
two-step process.

First, we'll need to create a file that sets these parameters on the nodes.

Assuming you have only master and worker nodes, this yaml would do the trick:

```
# kubelet-sysctls.yaml
---
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  labels:
    machineconfiguration.openshift.io/role: master
  name: 75-master-kubelet-sysctls
spec:
  config:
    ignition:
      version: 3.1.0
    storage:
      files:
      - contents:
          source: data:,vm.overcommit_memory%3D1%0Avm.panic_on_oom%3D0%0Akernel.panic%3D10%0Akernel.panic_on_oops%3D1%0Akernel.keys.root_maxkeys%3D1000000%0Akernel.keys.root_maxbytes%3D25000000
        mode: 0644
        path: /etc/sysctl.d/90-kubelet.conf
---
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  labels:
    machineconfiguration.openshift.io/role: worker
  name: 75-worker-kubelet-sysctls
spec:
  config:
    ignition:
      version: 3.1.0
    storage:
      files:
      - contents:
          source: data:,vm.overcommit_memory%3D1%0Avm.panic_on_oom%3D0%0Akernel.panic%3D10%0Akernel.panic_on_oops%3D1%0Akernel.keys.root_maxkeys%3D1000000%0Akernel.keys.root_maxbytes%3D25000000
        mode: 0644
        path: /etc/sysctl.d/90-kubelet.conf
```

**NOTE**: I'm using OpenShift 4.6. So the MachineConfigs will only work there. For older
OpenShift deployments you'll need to adjust the ignition configuration to match version `2.2.0`.

You can apply it as follows:

```
$ oc apply -f kubelet-sysctls.yaml
```

Please make sure to wait for the **MachineConfigOperator** to persist this configuration
in all of the nodes in the cluster.

You'll need to wait for the `MachineConfigPools` to be udpated. The following command will show you
the overall status of the pools:

```
$ oc get mcp -w
NAME     CONFIG                                             UPDATED   UPDATING   DEGRADED   MACHINECOUNT   READYMACHINECOUNT   UPDATEDMACHINECOUNT   DEGRADEDMACHINECOUNT   AGE
master   rendered-master-7ca5fa4e9cd73555b9866be7cb375c32   True      False      False      3              3                   3                     0                      127m
worker   rendered-worker-641218057b4c80cf7f1d4bc80bd73097   True      False      False      4              4                   4                     0                      127m
```

Ensure that the `UPDATED` column is set to `True` for all the pools.

When this is done, you can finally apply, the kubelet config setting as follows:

```
# protectkerneldefaults.yaml
---
apiVersion: machineconfiguration.openshift.io/v1
kind: KubeletConfig
metadata:
  name: master-protect-kernel-defaults
spec:
  machineConfigPoolSelector:
    matchLabels:
      pools.operator.machineconfiguration.openshift.io/master: ""
  kubeletConfig:
    protectKernelDefaults: true
---
apiVersion: machineconfiguration.openshift.io/v1
kind: KubeletConfig
metadata:
  name: worker-protect-kernel-defaults
spec:
  machineConfigPoolSelector:
    matchLabels:
      pools.operator.machineconfiguration.openshift.io/worker: ""
  kubeletConfig:
    protectKernelDefaults: true

```

**NOTE**: You'll have to create an object per pool, as the `machineConfigPoolSelector` will
not make a match for any pool if you leave the selector empty. The other option is to
label all the pools with a common label. This way, you could apply the same configuration
to all pools.

Apply the configuration as follows:

```
$ oc apply -f protectkerneldefaults.yaml
```

In the background, this will also create a `MachineConfig` object per pool, so you'll need to wait
for all the pools to update.

## What about scaling?

The aforementioned two-step process is not needed when scaling your existing pools.

This is because on first-boot the MachineConfigDaemon will run before the Kubelet.
This is important, as the **MachineConfigDaemon** ultimately applies the file
configurations in the OpenShift nodes, so we want the sysctl's to be in-place before
the Kubelet runs. That way, the Kubelet won't error out when it's time to run.

## Verifying

When the pools have updated, or your new node joins the cluster, you can verify the
sysctl's have been set with the following command:

```
$ oc debug node/ip-10-0-137-231.ec2.internal -- sysctl -p /host/etc/sysctl.d/90-kubelet.conf
Creating debug namespace/openshift-debug-node-lglph ...
Starting pod/ip-10-0-137-231ec2internal-debug ...
To use host binaries, run `chroot /host`
vm.overcommit_memory = 1
vm.panic_on_oom = 0
kernel.panic = 10
kernel.panic_on_oops = 1
kernel.keys.root_maxkeys = 1000000
kernel.keys.root_maxbytes = 25000000

Removing debug pod ...
Removing debug namespace/openshift-debug-node-lglph ...
```

You can also verify that the `protectKernelDefaults` parameter is set in the Kubelet's 
configuration file as follows:

```
$ oc debug node/ip-10-0-137-231.ec2.internal -- grep protectKernelDefaults /host/etc/kubernetes/kubelet.conf
Creating debug namespace/openshift-debug-node-ltvnd ...
Starting pod/ip-10-0-137-231ec2internal-debug ...
To use host binaries, run `chroot /host`
  "protectKernelDefaults": true,

Removing debug pod ...
Removing debug namespace/openshift-debug-node-ltvnd ...
```