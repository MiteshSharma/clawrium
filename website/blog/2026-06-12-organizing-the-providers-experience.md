---
authors: [maurice]
tags: [release]
---
# Cleaning up Provider Management

Managing model providers is now more intuitive. We have separated the act of configuring credentials from the act of discovering available models.

<!-- truncate -->

## A Clearer Provider Interface

The Providers page now uses a two-tab layout to separate concerns. The "Configured" tab is the landing page where you manage your active provider records. The "Registry" tab serves as a read-only catalog of everything clawrium supports. This split prevents the UI from conflating your specific credentials with the general list of available models. Operators no longer have to scroll past a massive model list to find their own settings.

Related: [#694](https://github.com/ric03uec/clawrium/issues/694), [#696](https://github.com/ric03uec/clawrium/pull/696), [#697](https://github.com/ric03uec/clawrium/pull/697)

## Better Visibility for Configured Providers

We replaced the card-based list with a high-density table. This view includes columns for the provider icon, name, type, and the default model assigned to that record. A new "Used by" column explicitly lists the agents attached to the provider. If no agents are using it, an "Unassigned" pill appears. You can also see exactly when a provider was created. This helps team leads audit which credentials are still necessary and which can be deleted.

Related: [#694](https://github.com/ric03uec/clawrium/issues/694), [#696](https://github.com/ric03uec/clawrium/pull/696), [#697](https://github.com/ric03uec/clawrium/pull/697)

## Dedicated Model Registry

The model catalog has moved to its own dedicated tab. Instead of one long list, a dropdown allows you to filter models by provider type. You can select "All providers" for a complete view or choose a specific provider like OpenRouter. Because some providers offer hundreds of models, the list is now paginated. If you select Ollama, the rest of the page swaps to a helper message explaining that models are discovered live from the local daemon.

Related: [#694](https://github.com/ric03uec/clawrium/issues/694), [#696](https://github.com/ric03uec/clawrium/pull/696), [#697](https://github.com/ric03uec/clawrium/pull/697)

## Corrected Bedrock Credentials

The credential flow for AWS Bedrock has been completely reworked. The form no longer asks for a generic API key, which was incorrect for this provider. Instead, it prompts for an AWS Access Key ID and Secret Access Key. You can also define the AWS Region, which defaults to `us-east-1` but remains editable. For security, these fields use password-style inputs with show/hide toggles. This ensures that the setup process matches actual AWS requirements.

Related: [#694](https://github.com/ric03uec/clawrium/issues/694), [#696](https://github.com/ric03uec/clawrium/pull/696), [#697](https://github.com/ric03uec/clawrium/pull/697)

## Validation Metrics

These are the automated validation metrics for the features
described above. Numbers aggregate every [ATX](https://github.com/atx-ci)
review iteration across the PRs that shipped these changes. ATX
is the multi-agent code review system that runs against every
PR; the metrics below reflect its work.

| Metric | Value |
|---|---|
| PRs covered | 2 |
| Automated review iterations | 4 |
| Blocking issues resolved | 17 |
| Total review cost | ~$8.52 |
| Total review time | ~21 min |
| Models used by [ATX](https://github.com/atx-ci) | _Not exposed per agent today; see [#704](https://github.com/ric03uec/clawrium/issues/704)_ |
| Models used by gtm pipeline | gather: `qwen3-coder:30b-128k` · writer: `gemma4:31b` · reviewer: `qwen3-coder:30b-128k` |
