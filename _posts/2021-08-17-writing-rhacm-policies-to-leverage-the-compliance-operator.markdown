---
layout: post
title:  "Writing RHACM policies to leverage the Compliance Operator"
date:   2021-08-17 14:48:21 +0300
categories: openshift
---

From even before the Red Hat Advanced Cluster Manager (RHACM) was open sourced,
we've been working closely with that team to ensure that the Compliance Operator
works well along side it. And as more releases come, RHACM has added more and
functionality to leverage all the information that the Compliance Operator
outputs and to present it in a nice and digestable way.

However, even if I've been talking often about how well the Compliance
Operator and RHACM work together, it's still quite unclear for folks
how to write RHACM policies to leverage the Compliance Operator, and
what everything means in such policies. So, I thought I'd take some time to
explain this and hopefully someone finds this useful.

# A sample policy

Let's take a sample RHACM policy and dissect it. Here's a
[sample policy](https://github.com/open-cluster-management/policy-collection/blob/main/stable/CM-Configuration-Management/policy-compliance-operator-cis-scan.yaml) that's already
in the [policy-collection repo](https://github.com/open-cluster-management/policy-collection).

Here's the full policy with the bits needed to deploy it:

```yaml
apiVersion: policy.open-cluster-management.io/v1
kind: Policy
metadata:
  name: policy-cis-scan
  annotations:
    policy.open-cluster-management.io/standards: NIST SP 800-53
    policy.open-cluster-management.io/categories: CM Configuration Management
    policy.open-cluster-management.io/controls: CM-6 Configuration Settings
spec:
  remediationAction: inform
  disabled: false
  policy-templates:
    - objectDefinition:
        apiVersion: policy.open-cluster-management.io/v1
        kind: ConfigurationPolicy
        metadata:
          name: compliance-cis-scan
        spec:
          remediationAction: enforce
          severity: high
          object-templates:
            - complianceType: musthave # this template creates ScanSettingBinding:cis
              objectDefinition:
                apiVersion: compliance.openshift.io/v1alpha1
                kind: ScanSettingBinding
                metadata:
                  name: cis
                  namespace: openshift-compliance
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
                  name: default
    - objectDefinition: 
        apiVersion: policy.open-cluster-management.io/v1
        kind: ConfigurationPolicy
        metadata:
          name: compliance-suite-cis
        spec:
          remediationAction: inform
          severity: high
          object-templates:
            - complianceType: musthave # this template checks if scan has completed by checking the status field
              objectDefinition:
                apiVersion: compliance.openshift.io/v1alpha1
                kind: ComplianceSuite
                metadata:
                  name: cis
                  namespace: openshift-compliance
                status:
                  phase: DONE
    - objectDefinition:
        apiVersion: policy.open-cluster-management.io/v1
        kind: ConfigurationPolicy
        metadata:
          name: compliance-suite-cis-results
        spec:
          remediationAction: inform
          severity: high
          object-templates:
            - complianceType: mustnothave # this template reports the results for scan suite: cis by looking at ComplianceCheckResult CRs
              objectDefinition:
                apiVersion: compliance.openshift.io/v1alpha1
                kind: ComplianceCheckResult
                metadata:
                  namespace: openshift-compliance
                  labels:
                    compliance.openshift.io/check-status: FAIL
                    compliance.openshift.io/suite: cis
---
apiVersion: policy.open-cluster-management.io/v1
kind: PlacementBinding
metadata:
  name: binding-policy-cis-scan
placementRef:
  name: placement-policy-cis-scan
  kind: PlacementRule
  apiGroup: apps.open-cluster-management.io
subjects:
- name: policy-cis-scan
  kind: Policy
  apiGroup: policy.open-cluster-management.io
---
apiVersion: apps.open-cluster-management.io/v1
kind: PlacementRule
metadata:
  name: placement-policy-cis-scan
spec:
  clusterConditions:
  - status: "True"
    type: ManagedClusterConditionAvailable
  clusterSelector:
    matchExpressions:
      - {key: vendor, operator: In, values: ["OpenShift"]}
```

You'll note there are three Kubernetes objects in this YAML:

* The `Policy` object is the one that defines the actual RHACM
  policy, and what we care about the most in this blog post.

* The `PlacementRule` defines under what conditions should a
  policy be scheduled for a specific cluster.

* The `PlacementBinding` ties together the policy to the rule,
  hence getting RHACM to actually take the policy into use and
  deploy it to the appropriate managed clusters.

This is all I'll mention about `PlacementRules` and `PlacementBindings`,
as I'm sure there are better resources for understanding these better.
Let's focus on the policy now.

# The Policy

The policy might look big and overwhelming, but it's really not as
intimidating once we take a closer look, so let's dive in!

## Annotations

Let's start with something easy. For correctness, most (if not all)
policies that do scans using the Compliance Operator fall under the
NIST SP 800-53 CM-6 control. So you'll see (and use) something as follows:

```yaml
  annotations:
    policy.open-cluster-management.io/standards: NIST SP 800-53
    policy.open-cluster-management.io/categories: CM Configuration Management
    policy.open-cluster-management.io/controls: CM-6 Configuration Settings
```

The control states the following:

> The organization:
> a. Establishes and documents configuration settings for information
> technology products employed within the information system using
> [Assignment: organization-defined security configuration checklists] that reflect the most restrictive mode consistent with operational requirements;
> b. Implements the configuration settings;
> c. Identifies, documents, and approves any deviations from established
> configuration settings for [Assignment: organization-defined information
> system components] based on [Assignment: organization-defined operational
> requirements]; and
> d. Monitors and controls changes to the configuration settings in
> accordance with organizational policies and procedures.

As the Compliance Operator deals with monitoring configuration settings
and ensuring they're configured appropriately and in a compliant manner,
it fits to the **.d** point of this control.

## The structure

Policies are able to enforce and check for several objects in the deployment.
These are reflected as several entries in the `policy-templates` section of
the spec.

For the Compliance Operator, we want to check the following:

* What am I complying with and how?

* Is the compliance scan running? (optional)

* Am I passing the compliance scan?

### What am I complying with and how?

This question is answered in the following section of the policy:

```yaml
    - objectDefinition:
        apiVersion: policy.open-cluster-management.io/v1
        kind: ConfigurationPolicy
        metadata:
          name: compliance-cis-scan
        spec:
          remediationAction: enforce
          severity: high
          object-templates:
            - complianceType: musthave # this template creates ScanSettingBinding:cis
              objectDefinition:
                apiVersion: compliance.openshift.io/v1alpha1
                kind: ScanSettingBinding
                metadata:
                  name: cis
                  namespace: openshift-compliance
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
                  name: default
```

This checks for an object of the type `ScanSettingBinding` and will fail
if it doesn't exist. To ensure that RHACM creates it, the `remediationAction`
field is set to `enforce`.

In the Compliance Operator, ScanSettingBindings define scans by answering
what do you want to comply with and how.

In this case, we want to comply with the CIS benchmark for OpenShift, and
we do this by using the `ocp4-cis` and the `ocp4-cis-node` profiles. This
is represented in the following snippet:

```yaml
                ...
                profiles:
                - apiGroup: compliance.openshift.io/v1alpha1
                  kind: Profile
                  name: ocp4-cis
                - apiGroup: compliance.openshift.io/v1alpha1
                  kind: Profile
                  name: ocp4-cis-node
                ...
```

You can see the list of available profiles in the Compliance Operator with the
following command

```bash
$ oc get -n openshift-compliance profiles.compliance
```

---

Note that this assumes that the Compliance Operator is also installed in the
Hub cluster, which allows you to run the command there.

---

You'll also want to tell the Compliance Operator how to do the scan. This means
the following:

* What storage options to use for the raw results.
* How often to effectuate scans.
* What tolerations to give the scan pods.
* What node roles to take into account.

To make things easier for administrators, we have some reasonable defaults
that come as part of the default Compliance Operator deployment. These
are `ScanSetting` objects, and the default ones are the following:

* `default`:

  - It allocates 1Gi of storage for the raw results, with a rotation
  policy of 3 scans.
  - It'll run a scan every monday at 1 in the morning.
  - It'll allow the scans to run on master nodes.
  - It'll schedule scans for `worker` and `master` nodes.
  - It does not auto-apply remediations.
  - it does not auto-update applied remediations.

* `default-auto-apply`: This is exactly the same as `default`, except:

  - It auto-applies remediations.
  - It auto-updates applied remediations.


If you need to change something from these settings, you'd need
to write a new `ScanSetting` object and distribute it via a RHACM policy. Then,
you'd use the name of that `ScanSetting` object in the policy that creates
the scans.

### Is the compliance scan running?

As a sanity check, we want to verify that the scan is actually running. This is
done as follows:

```yaml
    - objectDefinition: 
        apiVersion: policy.open-cluster-management.io/v1
        kind: ConfigurationPolicy
        metadata:
          name: compliance-suite-cis
        spec:
          remediationAction: inform
          severity: high
          object-templates:
            - complianceType: musthave # this template checks if scan has completed by checking the status field
              objectDefinition:
                apiVersion: compliance.openshift.io/v1alpha1
                kind: ComplianceSuite
                metadata:
                  name: cis
                  namespace: openshift-compliance
                status:
                  phase: DONE
```

This will verify that a `ComplianceSuite` object has been created and that\
it actually reaches the `DONE` state. This object keeps track of scans and is
able to output events that tell us when a scan is done. If you create a
`ScanSettingBinding` that refers to an unexistent profile or scan setting,
the `ScanSettingBinding` won't generate a `ComplianceSuite`, and RHACM will
report a violation for this specific part of the policy.

This can be skipped, but is a good sanity check to have.

It's important to note that the name of the `ComplianceSuite` will be
exactly the same as the name of the `ScanSettingBinding` that was written
in the policy.

In this case, the `remediationAction` is `inform` as we want RHACM to only
verify that this object exists, and it should not attempt to create it. The
Compliance Operator is in charge of creating this object.


### Am I passing the compliance scan?

Finally, we want to get events for the actual results of the scan, and know if
we're actually passing our compliance check.

This is done with the following section of the policy:

```yaml
    - objectDefinition:
        apiVersion: policy.open-cluster-management.io/v1
        kind: ConfigurationPolicy
        metadata:
          name: compliance-suite-cis-results
        spec:
          remediationAction: inform
          severity: high
          object-templates:
            - complianceType: mustnothave # this template reports the results for scan suite: cis by looking at ComplianceCheckResult CRs
              objectDefinition:
                apiVersion: compliance.openshift.io/v1alpha1
                kind: ComplianceCheckResult
                metadata:
                  namespace: openshift-compliance
                  labels:
                    compliance.openshift.io/check-status: FAIL
                    compliance.openshift.io/suite: cis
```

The Compliance Operator outputs results as `ComplianceCheckResult` objects.
There will be as many of these as there are rules in a specific profile.

With this, we check that we should not have rules that failed:

```yaml
                    compliance.openshift.io/check-status: FAIL
```

and that the results rules belong to the appropriate scan:

```yaml
                    compliance.openshift.io/suite: cis
```

---

Note that the `compliance.openshift.io/suite` label value must match the
name that was given to the `ScanSettingBinding` object.

---

While the compliance operator actually has a `status` section where the
result could be checked, in this case we use labels for easier and faster
access.

For reference, an actual ComplianceCheckResult would normally look as follows:

```yaml
apiVersion: compliance.openshift.io/v1alpha1
description: |-
  Ensure that Audit Log Forwarding Is Enabled
  Retaining logs ensures the ability to go back in time to investigate or correlate any events.
  Offloading audit logs from the cluster ensures that an attacker that has access to the cluster will not be able to
  tamper with the logs because of the logs being stored off-site.
id: xccdf_org.ssgproject.content_rule_audit_log_forwarding_enabled
instructions: |-
  Run the following command:
  oc get clusterlogforwarders instance -n openshift-logging -ojson | jq -r '.spec.pipelines[].inputRefs | contains(["audit"])'
  The output should return true.
kind: ComplianceCheckResult
metadata:
  annotations:
    compliance.openshift.io/rule: audit-log-forwarding-enabled
  creationTimestamp: "2021-08-17T12:42:14Z"
  generation: 1
  labels:
    compliance.openshift.io/check-severity: medium
    compliance.openshift.io/check-status: FAIL
    compliance.openshift.io/scan-name: ocp4-cis
    compliance.openshift.io/suite: cis
  name: ocp4-cis-audit-log-forwarding-enabled
  namespace: openshift-compliance
  ownerReferences:
  - apiVersion: compliance.openshift.io/v1alpha1
    blockOwnerDeletion: true
    controller: true
    kind: ComplianceScan
    name: ocp4-cis
    uid: c2826b99-8db7-45f5-b3e8-e98487e56d90
  resourceVersion: "205033"
  uid: 386e462d-a75a-487a-8a8d-442df18c0dfb
severity: medium
status: FAIL
```

This contains information about the check, the results and even instructions
on how to manually audit this specific setting. This can be viewed in the RHACM
console by viewing the violation's YAML representation.

---

If you want even more information about the result, you can use the 
[oc-compliance plugin](https://github.com/openshift/oc-compliance/):

```bash
$ oc compliance view-result ocp4-cis-audit-log-forwarding-enabled

+----------------------+-----------------------------------------------------------------------------------------+
|         KEY          |                                          VALUE                                          |
+----------------------+-----------------------------------------------------------------------------------------+
| Title                | Ensure that Audit Log                                                                   |
|                      | Forwarding Is Enabled                                                                   |
+----------------------+-----------------------------------------------------------------------------------------+
| Status               | FAIL                                                                                    |
+----------------------+-----------------------------------------------------------------------------------------+
| Severity             | medium                                                                                  |
+----------------------+-----------------------------------------------------------------------------------------+
| Description          | OpenShift audit works at the                                                            |
|                      | API server level, logging                                                               |
|                      | all requests coming to the                                                              |
|                      | server. Audit is on by default                                                          |
|                      | and the best practice is                                                                |
|                      | to ship audit logs off the                                                              |
|                      | cluster for retention. The                                                              |
|                      | cluster-logging-operator is                                                             |
|                      | able to do this with the                                                                |
|                      |                                                                                         |
|                      |                                                                                         |
|                      |                                                                                         |
|                      | ClusterLogForwarders                                                                    |
|                      |                                                                                         |
|                      |                                                                                         |
|                      |                                                                                         |
|                      | resource. The forementioned resource can be configured to logs to different third party |
|                      | systems. For more information on this, please reference the official documentation:     |
|                      | https://docs.openshift.com/container-platform/4.6/logging/cluster-logging-external.html |
+----------------------+-----------------------------------------------------------------------------------------+
| Rationale            | Retaining logs ensures the                                                              |
|                      | ability to go back in time to                                                           |
|                      | investigate or correlate any                                                            |
|                      | events. Offloading audit logs                                                           |
|                      | from the cluster ensures that                                                           |
|                      | an attacker that has access                                                             |
|                      | to the cluster will not be                                                              |
|                      | able to tamper with the logs                                                            |
|                      | because of the logs being                                                               |
|                      | stored off-site.                                                                        |
+----------------------+-----------------------------------------------------------------------------------------+
| Instructions         | Run the following command:                                                              |
|                      |                                                                                         |
|                      | oc get clusterlogforwarders                                                             |
|                      | instance -n openshift-logging                                                           |
|                      | -ojson | jq -r                                                                          |
|                      | '.spec.pipelines[].inputRefs |                                                          |
|                      | contains(["audit"])'                                                                    |
|                      |                                                                                         |
|                      | The output should return true.                                                          |
+----------------------+-----------------------------------------------------------------------------------------+
| NIST-800-53 Controls | AC-2(12), AU-6, AU-6(1),                                                                |
|                      | AU-6(3), AU-9(2), SI-4(16),                                                             |
|                      | AU-4(1), AU-11, AU-7, AU-7(1)                                                           |
+----------------------+-----------------------------------------------------------------------------------------+
| CIS-OCP Controls     | 1.2.23                                                                                  |
+----------------------+-----------------------------------------------------------------------------------------+
| NERC-CIP Controls    | CIP-003-3 R5.2, CIP-004-3                                                               |
|                      | R2.2.2, CIP-004-3 R2.2.3,                                                               |
|                      | CIP-004-3 R3.3, CIP-007-3                                                               |
|                      | R.1.3, CIP-007-3 R5, CIP-007-3                                                          |
|                      | R5.1.1, CIP-007-3 R5.2,                                                                 |
|                      | CIP-007-3 R5.3.1, CIP-007-3                                                             |
|                      | R5.3.2, CIP-007-3 R5.3.3,                                                               |
|                      | CIP-007-3 R6.5                                                                          |
+----------------------+-----------------------------------------------------------------------------------------+
| Available Fix        | No                                                                                      |
+----------------------+-----------------------------------------------------------------------------------------+
| Result Object Name   | ocp4-cis-audit-log-forwarding-enabled                                                   |
+----------------------+-----------------------------------------------------------------------------------------+
| Rule Object Name     | ocp4-audit-log-forwarding-enabled                                                       |
+----------------------+-----------------------------------------------------------------------------------------+
| Remediation Created  | No                                                                                      |
+----------------------+-----------------------------------------------------------------------------------------+

```

---

# In a nutshell

When writing a RHACM policy to do scans using the Compliance Operator, the
main object to leverage is the `ScanSettingBinding` object. This defines
what to comply with and how; this is done by binding together `Profile`
objects with `ScanSetting` objects.

The available profiles for the Compliance Operator can be viewed with
the following command:

```bash
$ oc get -n openshift-compliance profiles.compliance
```

And the available scan settings can be viewed with the following command:

```bash
$ oc get -n openshift-compliance scansettings
```

If the default settings don't suite your needs, you can create a new
`ScanSetting` object and deploy with RHACM. For more information
on the available parameters for this, the
[upstream documentation](https://github.com/openshift/compliance-operator/blob/master/doc/crds.md#the-scansetting-and-scansettingbinding-objects)
is quite useful.

Then, you'll want to check that the scan runs to completion. this is done
by verifying that the `ComplianceSuite` reaches the `DONE` state.

Finally, you want to ensure that you don't get failures in the results. 
This is done by verifying that you don't get `ComplianceCheckResult`
objects with a `FAIL` status.

Note that all references to the `ScanSettingBinding` and `ComplianceSuite` 
names must have the same value as these objects have the same name.

Hopefully this helps folks understand what these policies mean, thanks for
reading!