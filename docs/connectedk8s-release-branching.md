# Connectedk8s release branching

## Goals

The connectedk8s fork keeps the detailed history of individual development
pull requests. The upstream `Azure/azure-cli-extensions` repository generally
receives a connectedk8s release as one squashed pull request. The branch model
must therefore:

- preserve individual pull request history in the fork;
- keep an exact reference to upstream history;
- identify the exact source tree shipped in each release;
- record which downstream changes were included;
- avoid replaying changes that are already present in an upstream squash; and
- keep upstream pull request commit lists and diffs reviewable.

## Branch roles

### `origin/main`

Development integration branch for connectedk8s pull requests. It preserves
the individual downstream commits and is not expected to have commit-for-commit
parity with upstream after upstream squashes a release.

### `origin/sync/upstream-main`

Exact fast-forward mirror of `upstream/main`. Do not add connectedk8s-specific
commits to this branch.

Update it with:

```bash
git fetch upstream origin
git switch sync/upstream-main
git merge --ff-only upstream/main
git push origin sync/upstream-main
```

### `release/connectedk8s-vX.Y.Z`

Release assembly branch created from a pinned `upstream/main` commit:

```bash
git fetch upstream origin --tags
git switch -c release/connectedk8s-vX.Y.Z upstream/main
```

The branch should contain only the connectedk8s changes selected for that
release and any release metadata changes under `src/connectedk8s/`. Do not
include changes outside that directory, including changes to `testing/`,
pipelines, or repository-level automation.

## Release procedure

### Step 1 - Create the release branch and select changes

The content tag records the last feature commit selected for a release. Use the
following format:

```text
connectedk8s-X.Y.Z-content
```

For example, `connectedk8s-1.12.0-content` marks the last feature commit
included in version `1.12.0`. The tag belongs on the corresponding commit in
`origin/main`, not on the release metadata commit.

Before assembling a new release, verify that the previous release's content
tag points to the last feature pull request included in that release. If the
tag does not exist yet, create and push it:

```bash
git switch main
git pull --ff-only origin main
git tag -a connectedk8s-X.Y.Z-content <last-feature-commit> \
  -m "Connectedk8s X.Y.Z content cutoff"
git push origin connectedk8s-X.Y.Z-content
```

Create the new release branch from the pinned upstream base:

```bash
git fetch upstream origin --tags
git switch -c release/connectedk8s-vA.B.C upstream/main
```

List candidate commits after the previous content cutoff in their original
topological order:

```bash
git log --reverse --topo-order --format='%H %s' \
  connectedk8s-X.Y.Z-content..origin/main -- src/connectedk8s
```

Maintain an ordered release manifest in the release work item or pull request.
For every selected change, record:

- the downstream pull request number;
- the downstream commit hash;
- whether the change is included, excluded, or deferred; and
- any prerequisite commits.

Begin with the commit following the previous content tag and cherry-pick
selected commits in manifest order. Exclude the prior release's documentation
or version bump; it is release metadata, not new feature content.

```bash
git cherry-pick <first-commit> <second-commit> <third-commit>
```

Each resulting release commit must modify only `src/connectedk8s/`. Before
cherry-picking, inspect the paths changed by each candidate:

```bash
git diff-tree --no-commit-id --name-only -r <commit>
```

If a commit also changes files outside `src/connectedk8s/`, use a no-commit
cherry-pick, remove the out-of-scope changes from the index and working tree,
then commit the scoped result with the original commit message:

```bash
git cherry-pick --no-commit <commit>
git restore --source=HEAD --staged --worktree -- <out-of-scope-path>...
git commit -C <commit>
```

Also remove any newly added out-of-scope files before committing. Confirm the
scoped result with `git status --short` and `git diff --cached --name-only`.
Every listed path must begin with `src/connectedk8s/`.

Do not assume that commit date alone defines a safe order. If a selected commit
depends on an excluded commit, include the prerequisite or adapt the selected
change explicitly and document the decision.

After the feature cherry-picks are complete, tag the corresponding source
commit on `origin/main` for the last selected feature with the new release
cutoff:

```bash
git tag -a connectedk8s-A.B.C-content <last-selected-origin-main-commit> \
  -m "Connectedk8s A.B.C content cutoff"
git push origin connectedk8s-A.B.C-content
```

Do not tag the cherry-picked commit on the release branch: the next release
uses this tag as the starting point for an `origin/main` commit range. Create
the tag before making the release metadata changes in Step 2.

### Step 2 - Make release changes

Apply the following release metadata changes on
`release/connectedk8s-vA.B.C`:

| File | Required change |
| --- | --- |
| `src/connectedk8s/setup.py` | Set `VERSION = "A.B.C"`. |
| `src/connectedk8s/HISTORY.rst` | Add the new release entry at the very top. |
| `src/connectedk8s/azext_connectedk8s/_constants.py` | Update `CLIENT_PROXY_VERSION` to the proxy version stated in the release notes. |
| `src/connectedk8s/azext_connectedk8s/azext_metadata.json` | Update `azext.minCliCoreVersion` only if the release requires a newer Azure CLI. The current minimum is `2.70.0`. |

Use this `HISTORY.rst` format:

```rst
<version>
++++++++++
* <description of changes>
```

Keep the entry above all previous versions. The `+` underline must be at least
as long as the version heading; matching the heading length is the convention
used by the existing entries.

Commit the release metadata separately from the feature cherry-picks so it can
be applied cleanly to `origin/main`:

```bash
git add src/connectedk8s
git commit -m "chore(connectedk8s): prepare A.B.C release"
```

### Step 3 - Verify and push the release branch

Verify that the branch contains no changes outside `src/connectedk8s/`:

```bash
git diff --name-only upstream/main...HEAD
git diff --stat upstream/main...HEAD -- src/connectedk8s
git rev-list --count --merges upstream/main..HEAD
```

Every path from the first command must begin with `src/connectedk8s/`, and the
merge commit count should be zero.

Push the release branch and its content tag:

```bash
git push -u origin release/connectedk8s-vA.B.C
git push origin connectedk8s-A.B.C-content
```

The branch name must include the `connectedk8s-` prefix; do not use
`release/vA.B.C`.

### Step 4 - Open the release pull requests

Open the release pull request from `release/connectedk8s-vA.B.C` against the
appropriate upstream or fork mirror base described below.

For consistency, also apply the Step 2 release metadata commit to a branch
created from `origin/main`, push it, and open a separate pull request back to
`origin/main`:

```bash
git switch -c update/connectedk8s-vA.B.C-release-metadata origin/main
git cherry-pick <release-metadata-commit>
git push -u origin update/connectedk8s-vA.B.C-release-metadata
```

Do not cherry-pick the assembled feature commits back to `origin/main`; they
already originated there. This pull request contains only the release
versioning and history changes from Step 2.

## Upstream squash commits

After a release is squash-merged upstream, the upstream commit contains the
combined source changes but no longer maps one-to-one to the downstream
commits. Git patch IDs cannot reliably reconstruct that mapping.

After the upstream merge:

1. Fast-forward `sync/upstream-main` to the new upstream state.
2. Record the upstream squash commit in the release manifest.
3. Start the next release branch from the new upstream squash commit.

The `connectedk8s-X.Y.Z-content` tag identifies the final downstream feature
commit selected for the release. The ordered release manifest remains the
source of truth for exclusions, deferred changes, prerequisites, and any
path-scoping performed during cherry-picks.

## Pull request bases

The pull request base must be an ancestor of the release branch.

- For an upstream submission, target `Azure/azure-cli-extensions:main`.
- For review within the fork, target `sync/upstream-main`.
- Do not target `origin/main` with a release branch based on upstream history.
  `origin/main` preserves independent downstream history and may not be an
  ancestor of the release branch.

Before pushing or force-pushing, verify the intended base:

```bash
git merge-base --is-ancestor upstream/main HEAD
git rev-list --count upstream/main..HEAD
git rev-list --count --merges upstream/main..HEAD
git diff --name-only upstream/main...HEAD
```

The first command must exit successfully. The commit count should represent
only the intended release work, and every changed path must be under
`src/connectedk8s/`.

For an internal pull request based on `sync/upstream-main`, substitute
`origin/sync/upstream-main` in these commands.

## Unexpected commits after a force push

If a pull request suddenly shows unrelated upstream or merge commits, inspect
its base before changing the release branch again:

```bash
git merge-base <pr-base> HEAD
git merge-base --is-ancestor <pr-base> HEAD
git rev-list --count <pr-base>..HEAD
git log --oneline --merges <pr-base>..HEAD
```

If the base is not an ancestor, change the pull request base to the appropriate
upstream mirror. Repeating the rebase does not fix a pull request that targets
the wrong history.

## Rebase policy

Rebasing an unpublished release branch is acceptable before review. Avoid
rebasing a shared or published release branch.

When upstream already contains a squashed release, do not replay all of its
original downstream commits. Start from the upstream squash and cherry-pick
only changes that are not present upstream. This prevents partial commits,
duplicate code, and misleading history.
