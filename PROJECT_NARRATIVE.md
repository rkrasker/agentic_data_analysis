# Workflow Challenges:

## I. Synthetic Data Construction
Building a synthetic data set one which reflected degredation and confusion but was ultimately coherent [NOT THE RIGHT WORD] was among the most time consuming tasks, one which required several iterations, including a complete mid-process rebuild.  

### Synthetic Data Requirements:

The data needed to have a realistic structure and then get captured in distorted permutations which were realistic rather than merely random.  We wanted the LLM to be able to discover some common notation patterns, but also to be able to adapt to other, rarer, renderings of the key organizational terms. The data needed to have confounding terms (letters or numbers that could reasonably appear in the notations, and which were similar to the key terms to be extracted, but which held other, irrelevant meanings). 

Data needed to support a number of types of advanced inference: For example, we wanted the LLM to be able to make inferences from "incidental" vocabularly, and to set the stage for followon analytic phases where the LLM could make inferences about one entry in a given document based on other elements in the same document.

### Rebooting scenario to avoid context pollution
The initial synthetic data was intended to closely resemble the actual records we wanted to parse, but we soon found that the parsing LLM had so much training data related to US Military in WWII that it could not stop making inferences based on its own reference knowledge rather than our instructions and injected data.  We therefore decided to create a totally fictional scenario involving a colonial corporation in space and to regenerate all the synthetic data in that context, hopefully forcing the LLM to engage only within the boundaries of our inputs.

## II. 