# The Frontstep name

**The code is free. The name is not part of it.**

Frontstep is released under the Apache License 2.0, which is deliberately
generous: use it, change it, sell it, build a product on it. But section 6 of
that License grants **no rights to trade names, trademarks or product names** —
and this file says what that means in practice, so nobody has to guess.

## What you may always do

- use Frontstep, privately or commercially, for anything;
- fork it, change it, publish your changes;
- say truthfully what your thing is: *"based on Frontstep"*, *"a fork of
  Frontstep"*, *"compatible with Frontstep status documents"*;
- keep the name in file paths, imports and configuration keys — `frontstep.toml`
  and `import frontstep` are how the software works, not branding.

## What a fork is called

**A published fork keeps the name Frontstep and puts its own beside it.**
`Frontstep-Evolution`, `Go-Frontstep`, `Goofie-Frontstep` — either order, both
names visible. Not `Frontstep` alone, and not a name with no Frontstep in it.

Two reasons, and neither is vanity.

The genealogy stays readable: anybody who runs into your build knows at a glance
what it grew out of, and can find the convention, the documents and this
repository without having to be told.

And the two stay **told apart**, which protects your users more than it protects
me. This dashboard writes into other people's files. If two different programs
answer to the same name and behave differently at that moment, the name has
stopped promising anything — and the person whose status documents get rewritten
is the one who pays for it.

So, not without asking:

- **Frontstep** on its own, for a published fork, product or service: that name
  is this build;
- a domain, package name, social account or app-store listing where **Frontstep**
  stands alone as the name of the thing;
- a logo or wordmark that would have someone believe your build is this one.

## What a fork's footer has to say

Renaming the product is required by this file. Dropping the attribution is a
different matter, and the License does not allow it: `NOTICE` designates the
**foot of the page** as the display where section 4(d) attribution appears in
this application.

So a fork changes the name at the top and keeps this at the bottom:

```
Forked from a project by G.J.C. 🧠 · <short link to this project>
```

Your own name goes next to it, not in its place. In the source that line is
`AUTHOR` / `AUTHOR_MARK` in `core.py` and the `sig-mark` element of the footer;
a test in `tests/test_web.py` checks it is still on the page, because it went
missing once by accident and nobody noticed.

## The NOTICE file is a separate obligation

`NOTICE` carries the attribution, and section 4(d) of the License requires it to
travel with every distribution that includes it. You may add your own notices to
it; you may not remove what is there. That is the License talking, not this
file.

## Asking

Permission to use the name beyond the above is given case by case, and asking is
usually enough. Open an issue.
