# Evals

Cases for `claude plugin eval`, which scores whether a skill actually fires and
behaves, with a no-plugin baseline arm so you can see whether it helped at all.

```bash
claude plugin eval .                        # all cases
claude plugin eval . --case spend-ambiguity # one
```

> **Status:** `claude plugin eval` is in early access and was not enabled on the
> account these cases were written on, so they are written to the documented
> `<eval dir>/**/case.yaml` schema but have never been executed. Expect to fix
> field names on the first real run.

Why these three: each covers a failure that is invisible without an eval.
A skill can be present and simply never fire; a description edit can silently
stop it firing; and a routing skill can answer confidently from the wrong
source. None of that shows up in a lint or a manifest check.

When you change a skill's `description`, run its case. That field is the whole
trigger mechanism, and it is the easiest thing in this repo to break by making
it *better* prose.
