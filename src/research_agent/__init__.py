"""Research-and-report agent: a supervisor-routed pipeline with a critic.

The graph itself lives in `graph`; `service` is the HTTP surface over it and
`chat` the terminal one. Nothing is imported here on purpose -- importing the
graph would build a memory store as a side effect of importing the package,
which is exactly the eager-construction problem the lazy clients avoid.
"""
