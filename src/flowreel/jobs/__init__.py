"""Jobs on a Slurm cluster (plan Section 19.6): partitions, job scripts, the resources
a job was given, and a render split into array tasks.

FlowReel writes and submits its own job scripts (``shot render --slurm FILE
--submit``), so a long render runs on a compute node without hand-written scripts.
"""
