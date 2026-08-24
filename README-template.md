# Submission README

## Track Chosen

Track A: Fictional Domain Packet

## What I Built


**Artifact** — `signaldesk_read.py`

```
python report_script.py product_usage_events.csv -o read.html
```

The artifact is a webpafe that turns an export into a one-page HTML read. It answers the question — which workflow is most useful now and how much to trust that call — then ranks the five metrics by whether they're safe to act on, shows the evidence, breaks acceptance down by source rather than pooling it, and ends with the one question worth investigating before a wider rollout plus the cheapest way to answer it.

**Data Exploration Notebook** - `data_exploration.ipynb`

This is the notebook that shows how the conclusions in the artifact were reached. The visualizations show how confidence is an untrustworthy metric, the Simpson's paradox in effect, and what the number of outputs (completed or flagged for review or otherwise) say about each workflow and source. 

## Who It Is For

The webpage is for the team using the AI-assisted workflows. This report will help the team understand which workflow is beneficial and which metrics to trust. 


## Assumptions I Made

An assumption I made was that the completed sessions column and the accepted output have a one-to-one relationship i.e. each session has one output which is either accpted, flagged for review, neither, or both. 

## Data Issues Or Caveats I Noticed

* Two rows that weren't counted (a demo-account spike and a duplicate export row together 38% of one workflow's apparent volume)
* There are three incomplete days with less than 6 recorded workflows 
* The `completed`, `accepted_output` and `flagged_for_review` columns don't reconcile, leaving 7–15% of finished sessions with no recorded outcome. 

## What I Would Do Next With More Time

I would analyse what change in prompt or policy caused uncertainty and refine the webpage. 