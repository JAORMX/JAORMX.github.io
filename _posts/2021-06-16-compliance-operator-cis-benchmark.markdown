---
layout: post
title:  "Compliance Operator CIS benchmark"
date:   2021-06-16 11:42:21 +0300
categories: openshift
---

The Compliance Operator offers support for OpenShift’s inspired by CIS
benchmark. The benchmark is based on the CIS Kubernetes Benchmark,
but adjusted to the opinionated decisions OpenShift made to implement
Kubernetes. The benchmark serves as a guideline to implement security
best-practices on a Kubernetes/OpenShift deployment, so it's quite useful
to follow and implement.

For those of you who might not be acquainted with it, the Compliance Operator
is a tool we developed to help folks assess the technical compliance status of
their OpenShift clusters in a Kubernetes-native way. We wrap OpenSCAP in a
Kubernetes operator and automate tasks that administrators must complete
to ensure compliance  with technical security and regulatory controls on their
clusters.

With this in mind, today, we’ll scan our cluster and ensure we’re compliant with the controls inspired by the CIS Kubernetes benchmark. Let’s begin!

# Using the operator

Assuming you installed the operator from OperatorHub, consider the following:


1.  Make sure you’re in the operator’s recommended namespace. In the terminal, do:

	```
	$ oc project openshift-compliance
	```


2. Choose appropriate settings for your scan. Let’s see what defaults the operator gives us:


	```
	$ oc get scansettings
	NAME                     AGE
	default                  4h40m
	default-auto-apply   	 4h40m
	```


	* default: creates a scan that runs every day at 1 in the morning. It will leave findings to the administrator to fix. It’ll also allocate 1Gi to store our raw results (in case they’re needed).
	* default-auto-apply: has very similar settings as the default settings, except that it auto-remediates any issues found by the operator. This is what we’ll use!


3. For completeness, let’s see what the default-auto-apply settings look like:


	```
	$ oc describe scansettings default-auto-apply -o yaml
	Name:                          default-auto-apply
	Namespace:                     openshift-compliance
	Labels:                        <none>
	Annotations:                   <none>
	API Version:                   compliance.openshift.io/v1alpha1
	Auto Apply Remediations:   true
	Auto Update Remediations:  true
	Kind:                          ScanSetting
	...
	Raw Result Storage:
	Pv Access Modes:
		ReadWriteOnce
	Rotation:  3
	Size:          1Gi
	Roles:
	worker
	master
	Scan Tolerations:
	Effect:        NoSchedule
	Key:           node-role.kubernetes.io/master
	Operator:  Exists
	Schedule:        0 1 * * *
	```

	The main thing to note is that Auto Apply Remediations and Auto Update Remediations are set to true.


# Running scans

Let’s try it out! To run a scan, we’ll create a ScanSettingsBinding object. As
the name suggests, this object’s purpose is to bind scan settings to other
objects. The objects that scan settings can be bound to are Profiles and
TailoredProfiles. In our case, we want to use the defaults, so binding to the
CIS profiles will do.

The following manifest will bind the ocp4-cis and ocp4-cis-node profiles to the
settings we want to scan with.

```
---
apiVersion: compliance.openshift.io/v1alpha1
kind: ScanSettingBinding
metadata:
  name: cis
profiles:
- apiGroup: compliance.openshift.io/v1alpha1
  kind: Profile
  name: ocp4-cis
- apiGroup: compliance.openshift.io/v1alpha1
  kind: Profile
  name: ocp4-cis-node
settingsRef:
  apiGroup: compliance.openshift.io/v1alpha1
  kind: ScanSetting
  name: default-auto-apply
```

After applying this, we can sit back and enjoy life!

The above manifest created a **ComplianceSuite** object with the same name as
the ScanSettingBinding, which contains a lot of valuable information and helps
us track our scans.

The **ComplianceSuite** itself generates low-level objects called
**ComplianceScans** which have different scopes of execution but ensure the
right parameters are used during the scan. Let’s take a quick look at the
**ComplianceScans**:

```
$ oc get compliancescans
NAME                   PHASE   RESULT
ocp4-cis               DONE        NON-COMPLIANT
ocp4-cis-node-master   DONE        NON-COMPLIANT
ocp4-cis-node-worker   DONE        NON-COMPLIANT
```


If we want to programmatically wait for the scan to finish, we can do so with the following command:

```
$ oc wait --timeout 120s --for condition=ready compliancesuite cis
```

This usually won’t take more than a couple of minutes to execute. Once it’s done, you should see the following output:

```
compliancesuite.compliance.openshift.io/cis condition met
```

When a scan is done, we can be sure that all results are available and ready to
view.

# Viewing results

Let’s look at our results:

```
$ oc get compliancecheckresults
NAME                                                                               STATUS               SEVERITY
ocp4-cis-accounts-restrict-service-account-tokens                                  MANUAL               medium
ocp4-cis-accounts-unique-service-account                                           MANUAL               medium
ocp4-cis-api-server-admission-control-plugin-alwaysadmit                           PASS                 medium
ocp4-cis-api-server-admission-control-plugin-alwayspullimages                      PASS                 high
ocp4-cis-api-server-admission-control-plugin-namespacelifecycle                    PASS                 medium
ocp4-cis-api-server-admission-control-plugin-noderestriction                       PASS                 medium
ocp4-cis-api-server-encryption-provider-cipher                                     FAIL                 medium
ocp4-cis-api-server-encryption-provider-config                                     FAIL                 medium
ocp4-cis-api-server-etcd-ca                                                        PASS                 medium
…
```

## Why are some results not applicable?

You may have noticed that some check results had the status `NOT-APPLICABLE`,
this is normal and expected, as not all nodes run all services in OpenShift.

Let’s look at some examples:

```
$ oc get compliancecheckresults \
-l compliance.openshift.io/check-status=NOT-APPLICABLE \
--no-headers
ocp4-cis-node-worker-etcd-unique-ca                                       NOT-APPLICABLE   medium
ocp4-cis-node-worker-file-groupowner-controller-manager-kubeconfig        NOT-APPLICABLE   medium
ocp4-cis-node-worker-file-groupowner-etcd-data-dir                        NOT-APPLICABLE   medium
...
```

While it may be concerning at first sight, this is just fine as the worker
nodes run neither etcd nor the kubernetes controller manager services.

## Viewing failed results

OpenShift ships with reasonable and secure defaults, however, there are some
extra recommendations from the benchmark that we need to take into account.
Those will show up as violations.

Normally, we only care about our violations since we need to act on these and fix them. Let’s filter and look at those:

```
$ oc get compliancecheckresults \
-l compliance.openshift.io/check-status=FAIL \
--no-headers
ocp4-cis-api-server-encryption-provider-cipher                                     FAIL   medium
ocp4-cis-api-server-encryption-provider-config                                     FAIL   medium
ocp4-cis-audit-log-forwarding-enabled                                              FAIL   medium
ocp4-cis-node-master-kubelet-configure-event-creation                              FAIL   medium
ocp4-cis-node-master-kubelet-configure-tls-cipher-suites                           FAIL   medium
ocp4-cis-node-master-kubelet-enable-protect-kernel-defaults                        FAIL   medium
ocp4-cis-node-master-kubelet-eviction-thresholds-set-hard-imagefs-available        FAIL   medium
ocp4-cis-node-master-kubelet-eviction-thresholds-set-hard-imagefs-inodesfree   FAIL   medium
ocp4-cis-node-master-kubelet-eviction-thresholds-set-hard-memory-available         FAIL   medium
ocp4-cis-node-master-kubelet-eviction-thresholds-set-hard-nodefs-available         FAIL   medium
ocp4-cis-node-master-kubelet-eviction-thresholds-set-hard-nodefs-inodesfree        FAIL   medium
ocp4-cis-node-master-kubelet-eviction-thresholds-set-soft-imagefs-available        FAIL   medium
ocp4-cis-node-master-kubelet-eviction-thresholds-set-soft-imagefs-inodesfree   FAIL   medium
ocp4-cis-node-master-kubelet-eviction-thresholds-set-soft-memory-available         FAIL   medium
ocp4-cis-node-master-kubelet-eviction-thresholds-set-soft-nodefs-available         FAIL   medium
ocp4-cis-node-master-kubelet-eviction-thresholds-set-soft-nodefs-inodesfree        FAIL   medium
...
```

One thing to note is that the results have the scan-name prepended to them.
This will be useful in the future.

## Remediations applied by the operator

There are many types of remediations, and the operator can help with many of
them. Let’s look at the remediations the operator generated automatically:

```
$ oc get complianceremediations
ocp4-cis-api-server-encryption-provider-cipher   Applied
ocp4-cis-api-server-encryption-provider-config   Applied
```

For this particular benchmark, only these remediations were generated, as the
rest of the issues require the cluster admin to make some choices. Given that
we used the default-auto-apply ScanSettings, these remediations will
automatically apply the fixes for these two items. To veryify this, all we
need to do is trigger a re-scan:

```
$ # Trigger a re-scan
$ oc annotate compliancescan ocp4-cis "compliance.openshift.io/rescan="
compliancescan.compliance.openshift.io/ocp4-cis annotated
$ # Wait for scan to finish
$ oc wait --timeout 120s --for condition=ready compliancesuite cis
compliancesuite.compliance.openshift.io/cis condition met
```

---
**NOTE**: We’re working on an oc plugin to make this process easier.
So, with it, you’ll be able to simply do:

```
$ oc compliance rerun-now scansettingbinding cis
```
---


Let’s now verify that the issue is indeed fixed:


```
$ oc get compliancecheckresult ocp4-cis-api-server-encryption-provider-config
NAME                                                 STATUS   SEVERITY
ocp4-cis-api-server-encryption-provider-config   PASS         medium
```


# Addressing the rest of the issues

Our profiles include some opinionated rules to guide people on what to do
to remediate issues found during compliance scans. However, we recognize
that different organizations have different requirements. For this reason,
you can configure your scans to skip some checks using a **TailoredProfile**.


Let’s take one example:

```
$ oc get compliancecheckresult | grep audit-log-forwarding
ocp4-cis-audit-log-forwarding-enabled     FAIL                 medium
```


With this object alone, we are able to get the rationale of why this check is problematic:

```
$ oc describe ccr ocp4-cis-audit-log-forwarding-enabled
Name:             ocp4-cis-audit-log-forwarding-enabled
Namespace:        openshift-compliance
Labels:           compliance.openshift.io/check-severity=medium
                  compliance.openshift.io/check-status=FAIL
                  compliance.openshift.io/scan-name=ocp4-cis
                  compliance.openshift.io/suite=cis
Annotations:  compliance.openshift.io/rule: audit-log-forwarding-enabled
API Version:  compliance.openshift.io/v1alpha1
Description:  Ensure that Audit Log Forwarding Is Enabled
Retaining logs ensures the ability to go back in time to investigate or correlate any events.
Offloading audit logs from the cluster ensures that an attacker that has access to the cluster will not be able to
tamper with the logs because of the logs being stored off-site.
Id:                xccdf_org.ssgproject.content_rule_audit_log_forwarding_enabled
Instructions:  Run the following command:
oc get clusterlogforwarders instance -n openshift-logging -ojson | jq -r '.spec.pipelines[].inputRefs | contains(["audit"])'
The output should return true.
Kind:  ComplianceCheckResult
...
```

Here are some essential things:
* The rule in the annotations: Which allows us to search for more documentation on this check
* Description: This will enable us to understand why this is recommended.
* Instructions: how to manually audit this. This is useful for auditors that
  that would like to verify things manually.


The Compliance Operator bundles up the relevant information about all the rules we ship, so, if  you want to search for more answers, you can do so as follows:

```
$ oc get rules | grep audit-log-forwarding-enabled
ocp4-audit-log-forwarding-enabled       5h18m
```


Let’s examine this rule:

```
$ oc describe rule ocp4-audit-log-forwarding-enabled
Name:             ocp4-audit-log-forwarding-enabled
Namespace:        openshift-compliance
Labels:           compliance.openshift.io/profile-bundle=ocp4
Annotations:  compliance.openshift.io/image-digest: pb-ocp47nk7b
                  compliance.openshift.io/rule: audit-log-forwarding-enabled
                  control.compliance.openshift.io/CIS-OCP: 1.2.23
                  control.compliance.openshift.io/NIST-800-53: AU-9(2)
                  policies.open-cluster-management.io/controls: 1.2.23,AU-9(2)
                  policies.open-cluster-management.io/standards: CIS-OCP,NIST-800-53
API Version:  compliance.openshift.io/v1alpha1
Description:  OpenShift audit works at the API server level, logging all requests coming to the server.&#xA;Audit is on by default and the best practice is to ship audit logs off the cluster for retention.&#xA;The cluster-logging-operator is able to do this with the<html:pre>ClusterLogForwarders</html:pre>resource.&#xA;The forementioned resource can be configured to logs to different third party systems.&#xA;For more information on this, please reference the official documentation:<html:a href="https://docs.openshift.com/container-platform/4.6/logging/cluster-logging-external.html">https://docs.openshift.com/container-platform/4.6/logging/cluster-logging-external.html</html:a>
Id:               xccdf_org.ssgproject.content_rule_audit_log_forwarding_enabled
Kind:             Rule
Rationale:                     Retaining logs ensures the ability to go back in time to investigate or correlate any events.&#xA;Offloading audit logs from the cluster ensures that an attacker that has access to the cluster will not be able to&#xA;tamper with the logs because of the logs being stored off-site.
Severity:                      medium
Title:                         Ensure that Audit Log Forwarding Is Enabled
```


This gives us actionable information. We need to install the Cluster Logging Operator and ensure we’re forwarding our logs somewhere secure.


To do this, follow [the appropriate documentation](https://docs.openshift.com/container-platform/4.6/logging/cluster-logging-external.html).


Once you are forwarding the logs as recommended by the benchmark, you can do the following to verify the results after a re-scan:

```
$ oc get ccr ocp4-cis-audit-log-forwarding-enabled
NAME                                        STATUS   SEVERITY
ocp4-cis-audit-log-forwarding-enabled   PASS         medium
```

# The rest of the way


Let’s finish remediating the rest of the issues. Mostly, they’re related to the Kubelet’s configuration, so let’s get fixing!

Normally, you'd follow the same process as described in the previous section,
however, to save time, I'll just jump right into the remediations.

First, we want to make sure the needed sysctl’s are created on the nodes and picked up on-boot:

```
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
        overwrite: true
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
        overwrite: true
```


This ensures that we’re able to start the Kubelet with the
**protectKernelDefaults** parameter set. After applying this manifest,
the Machine Config Operator will do its job and apply the changes to both
the “master” and “worker” pools, and reboot them all. We’ll have to wait
for this to happen before following the next step.

Once the reboot is complete, we can apply the following configuration:

```
---
apiVersion: machineconfiguration.openshift.io/v1
kind: KubeletConfig
metadata:
  name: kubelet-config-test-master
spec:
  machineConfigPoolSelector:
    matchLabels:
      pools.operator.machineconfiguration.openshift.io/master: ""
  kubeletConfig:
    protectKernelDefaults: true
    eventRecordQPS: 10
    evictionSoft:
      memory.available: "500Mi"
      nodefs.available: "10%"
      nodefs.inodesFree: "5%"
      imagefs.available: "15%"
      imagefs.inodesFree: "10%"
    evictionSoftGracePeriod:
      memory.available: "1m30s"
      nodefs.available: "1m30s"
      nodefs.inodesFree: "1m30s"
      imagefs.available: "1m30s"
      imagefs.inodesFree: "1m30s"
    evictionHard:
      memory.available: "200Mi"
      nodefs.available: "5%"
      nodefs.inodesFree: "4%"
      imagefs.available: "10%"
      imagefs.inodesFree: "5%"
    evictionPressureTransitionPeriod: 0s
    imageMinimumGCAge: 5m
    imageGCHighThresholdPercent: 80
    imageGCLowThresholdPercent: 75
    tlsCipherSuites:
    - TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
    - TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384
    - TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
    - TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
---
apiVersion: machineconfiguration.openshift.io/v1
kind: KubeletConfig
metadata:
  name: kubelet-config-test-worker
spec:
  machineConfigPoolSelector:
    matchLabels:
      pools.operator.machineconfiguration.openshift.io/worker: ""
  kubeletConfig:
    protectKernelDefaults: true
    eventRecordQPS: 10
    evictionSoft:
      memory.available: "500Mi"
      nodefs.available: "10%"
      nodefs.inodesFree: "5%"
      imagefs.available: "15%"
      imagefs.inodesFree: "10%"
    evictionSoftGracePeriod:
      memory.available: "1m30s"
      nodefs.available: "1m30s"
      nodefs.inodesFree: "1m30s"
      imagefs.available: "1m30s"
      imagefs.inodesFree: "1m30s"
    evictionHard:
      memory.available: "200Mi"
      nodefs.available: "5%"
      nodefs.inodesFree: "4%"
      imagefs.available: "10%"
      imagefs.inodesFree: "5%"
    evictionPressureTransitionPeriod: 0s
    imageMinimumGCAge: 5m
    imageGCHighThresholdPercent: 80
    imageGCLowThresholdPercent: 75
    tlsCipherSuites:
    - TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
    - TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384
    - TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
    - TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
```

This will create a custom Kubelet configuration for each Machine Config Pool that complies with the CIS standard. As with the previous MachineConfig object, this will also trigger a reboot of the nodes in the cluster. We need to wait for this to happen.


Once the reboot is done, we can retrigger the whole suite:

```
$ oc get compliancescans \
-ojsonpath='{range .items[*]}{@.metadata.name}{"\n"}{end}' | \
xargs -n1 -I % oc annotate compliancescan % \
"compliance.openshift.io/rescan="
compliancescan.compliance.openshift.io/ocp4-cis annotated
compliancescan.compliance.openshift.io/ocp4-cis-node-master annotated
compliancescan.compliance.openshift.io/ocp4-cis-node-worker annotated
```

Once the scans are done running, we can assert that the cluster is compliant:

```
$ oc get compliancesuites cis
NAME   PHASE   RESULT
cis        DONE        COMPLIANT
```

# Conclusion
The Compliance Operator provides a kube-native way of checking your cluster’s compliance status in a declarative way.


Now that the ScanSettings are created in your cluster, they’ll run every day, and so you’ll always have recent results to show auditors.


The OpenShift Infrastructure Security & Compliance team constantly works on
more rules and enables more profiles, so stay tuned! We’re also working on
allowing more automation as part of the Compliance Operator.
