## FURTHER IDEAS THAT I HAVE RE: DATA STRUCTURE
- Maintain some sort of graph-/tree-/relational database that stores experimental runs/dates by name of dir and classifies based on metadata (i.e. different configs)
  - Can also store experimental results as "metadata" as well  
- Engineer new prompts for fundamental rules of the experiment
  - this could eventually be turned into a web search agent or something that browses papers and automates the "domain knowledge gathering" part of things, especially with large-context like meta llama 4
- Combine the overall agent system, i.e. using fundamental rules to query through the database, read what's necessary and see which "direction" is the right way (gathering this domain data should allow you to see bigger trends as well)

Next steps: going from "these are ideas" to "this is a prototype we can build and test"

# TODO -- 10 Apr
## 1. misc bugfixes and whatnot
- `galvo_scan.py` 57 (and other relevant locations) -- take a command line argument for the new "runs" dir folder structure to store the data in the right place

## 2. begin datastructure creation
Within the database, experiments are labelled by the script they call (e.g. `ESR` or `galvo_scan`) and the time/date
Data storage is on paper (refer to it).
Automate the creation of links?? to related other experiments

___

# TODO -- 03 Apr 
## 1. tighten up the ship
### a. update file structure to be nicer e.g.
```
projects/
  MyProject/
    runs/
      run_3_20250321_153055/
        configs/
          config_esr_1.json  (made by the agent)
        data/
          data_esr_1.json
          plot_esr_1.png
          data_find_nv_1.json
          plot_find_nv_1.png
          ...
        logs/
          log_3.txt
```

PROBLEM -- should we store default configs and data in the projects dir? (which I'm doing right now)
- This should probably get updated to a contextual call once the database is properly set up.

PROBLEM -- different OS = different filepath convention
- Currently I have agent_mac.py and agent.py, but we should probably somehow detect the OS.
## **SHOULD BE DONE** + all the prompts and whatnot as well

- This will lend itself to being more of a structured database that the agent can knowledge-extract from (e.g. RAG, another action that involves reading from the database structure, etc.)
    - Becomes a dynamic database and long-term memory almost? Especially w/ human supervision
    - No longer starting from scratch W, everything is saved into a log
        - But it has to be more efficient...first glean fundamental rules, then selectively do logs based on similarity to present experiment
    - *improves decision-making*

### b. make the CLI less buggy
- Parsing = agent + experimental runs doesn't quite match up, just make it a bit better lol

## **SHOULD ALSO BE DONE** (not something I can reproduce anymore, @Ruolan please feel free to test as well + send reproducible bugginess)

## set sail?!
Refer to "This will lend itself..." for next big step.
ReAct prompting? -- could be good to daisy-chain together data, especially with the structured database, chaining experiments, etc.
