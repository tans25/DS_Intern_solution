# AI Collaboration Note

## Did You Use AI?

I used Claude code to help me with this challenge namely with designing the visualizations, and the HTMl web page. 

## How You Used It

I prompted Claude to create specific visualizations with the columns of interest as well as asked it to design the HTMl artifact. 

## One Prompt, Workflow, Or Moment That Helped

An example prompt I used: 

* I want section 1 to start with the answers. So start by answering Which workflow seems the most useful right now? And then following this section we will give the metrics we trusted and the ones we are flagging as untrustworthy
* Start section 2 with the metrics table as it is shown right now
* Section 3 is then our explanation. Include what rows are bad and how they skew results. Incomplete days, and the confidence evidence.
* Follow this up with per workflow, split by route section but reword it because it sounds too complex than it is and don't change the language of the dataset - they use Source so use Source and not Route. Say "Rank by source instead of workflow" and explain in a simple paragraph saying "This is Simpson's Paradox at work" and go on to explain how pooling the results can be misleading as Lead Summary is actually better performing in both sources but not when you look at the pooled result because we end up ranking their input mix and not their performances.
* Keep the What to investigate section at last as it is right now

## One Thing You Verified Or Decided Yourself

I decided which questions the artifact is supposed to answer, I also explored the data and decided which columns are trustworthy. 