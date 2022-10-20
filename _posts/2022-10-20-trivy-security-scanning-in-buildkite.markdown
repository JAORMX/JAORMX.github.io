---
layout: post
title:  "Trivy security scanning in Buildkite"
date:   2022-10-20 13:18:24  +0300
categories: trivy security buildkite
---

It's not secret that I'm a big fan of the new vulnerability open source vulnerability scanners.
Namely, I've been rolling out scanning everything with [Trivy from Aqua
Security](https://aquasecurity.github.io/trivy): From repositories to container images,
and even Kubernetes clusters! It certainly is a Swiss-army knife for security scanning.

And, while doing automated scanning like this is not a silver-bullet for your security
posture, I believe it can be really useful in providing clarity, applying organizational
guidelines, and making teams aware of potential threats or common mistakes.

So, in our effort to empower teams to take more responsibility in the security of the
components their responsible for, we decided to add Trivy scanning to every repository
for every team. This was done with friendly defaults, of course, as the intent is to
inform, educate and help, as opposed to block folks.

The folks at Aqua have been kind enough to also provide several integrations with popular
CI systems, such as [GitHub Actions](https://github.com/aquasecurity/trivy-action). However,
our CI is based on [Buildkite](https://buildkite.com/) so that didn't quite help us.

Instead of complaining, we decided to write our own plugin. And in the same spirit as
Trivy itself, this is also an open source project: [Trivy buildkite plugin](https://github.com/equinixmetal-buildkite/trivy-buildkite-plugin).

Yeah... the name is not very creative, but hey! At least it describes what it does.

## How do I use it?

In your Buildkite pipeline, simply add the following:

```yaml
steps:

  ...

  - command: "echo '--- :shield: Trivy security scan'"
    plugins:
      - equinixmetal-buildkite/trivy#v1.16.2:
          severity: "CRITICAL,HIGH"
          ignore-unfixed: true
```

By default, this will download the latest Trivy binary and analyse your repository
for vulnerable packages or IaaC security issues. It will ignore unfixed vulnerabilities,
as we don't want to block developers for something they can't fix and getting them to
hate the security team! Don't worry, we can also use Trivy to scan this out of CI, e.g.
directly in your Kubernetes clusters (I might write about this another day).

You can also do scanning for detecting hardcoded secrets! If you want that, you can do that as follows:

```yaml
  - command: "echo '--- :shield: Trivy security scan'"
    plugins:
      - equinixmetal-buildkite/trivy#v1.16.2:
          severity: "CRITICAL,HIGH"
          ignore-unfixed: true
          security-checks: 'config,secret,vuln'
```

This also works with repositories that contain Helm charts, as it'll automatically
render the chart and perform IaaC configuration checks on it! (Trivy is magical that way!)

## What about containers?

More often than not, the `Dockerfile` will be in the same repository with the application.
So we decided to integrate container scanning into the same plugin. You simply need to
give it the container tag to scan and it'll do it!

```yaml
  - command: |
      docker build -t quay.io/my-org/my-cool-image:$BUILDKITE_TAG .
    plugins:
      - equinixmetal-buildkite/trivy#v1.16.2:
          severity: "CRITICAL,HIGH"
          ignore-unfixed: true
          security-checks: 'config,secret,vuln'
          image-ref: 'quay.io/my-org/my-cool-image:$BUILDKITE_TAG'
```

Note that this assumes, that the image exists locally on the buildkite-agent runner. To ensure
that, we build the image as part of that build step.

This also integrates with other Buildkite plugins we've been working on:

* [The docker-metadata plugin](https://github.com/equinixmetal-buildkite/docker-metadata-buildkite-plugin/),
  which will automatically try to detect environmental variables that define tags, labels for you!
* [The docker-build plugin](https://github.com/equinixmetal-buildkite/docker-build-buildkite-plugin),
  which helps you build a container taking into account the nice defaults that `docker-metadata` added for you.

```yaml
    plugins:
      - equinixmetal-buildkite/docker-metadata#v1.0.0:
          images:
          - 'quay.io/equinixmetal/gov-github-addon'
          extra_tags:
          - latest
      # Build the container
      - equinixmetal-buildkite/docker-build#v0.2.0:
      # Scan the repository and the container
      - equinixmetal-buildkite/trivy#v1.16.2:
          severity: CRITICAL,HIGH
      # Push container to the registry
      - equinixmetal-buildkite/docker-build#v0.2.0:
          push: true
```

Note that you didn't have to tell the Trivy plugin what image tag to scan.
It can already detect that `docker-metadata` is being used and read the
appropriate label(s) to scan.

## Status

If all goes well, you should see the following in the Buildkite UI:

![Trivy buildkite plugin status](/images/trivy/trivystatus.png)

You may also see all the detail in the Buildkite job logs:

![Trivy buildkite plugin logs](/images/trivy/trivybklogs.png)

## What's next?

We'd like to more easily distribute this to new repositories and new teams
by providing more examples, and even including this in a central [Buildkite dynamic
pipeline](https://buildkite.com/docs/pipelines/defining-steps#dynamic-pipelines).

We'd like this to be as frictionless as possible, so that teams can just start
using it without having to do much work.

# Conclusion

Scanning your containers and repositories has never been this easy!

Buildkite allows for easy integration of such tooling via plugins, and I hope
someone else finds this useful, we'd love some feedback and contributions!

I'd like to thank the Trivy community for being so helpful and answering
my questions and even helping me do a couple of contributions.

Get scanning!