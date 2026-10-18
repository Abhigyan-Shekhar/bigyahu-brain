# GitHub connector

Company Brain can prepare and publish GitHub issues, draft pull requests and
top-level comments on issues or pull requests in the selected repository.

Install GitHub CLI on the computer running the application, then connect your
account there:

```sh
gh auth login --hostname github.com
gh auth status --hostname github.com
```

The application uses that account through `gh api`; credentials are not entered
in the browser, put in command arguments, or saved in application SQLite state.
The account needs permission for the operation in the selected repository.
Organization policies and token permissions can restrict writes even when account
connection succeeds. The current connector targets github.com.

Issue drafts and publication check whether the repository has Issues enabled.
If disabled, no issue is submitted; a repository administrator must enable Issues
in repository settings, or the operator must select another repository. Public
issue creation does not generally require push access. Disabling Issues does not
disable this connector's draft PR or PR-comment workflows.

Open **GitHub** in the repository workspace. Choose an issue, draft PR or comment,
edit its text, then choose **Review draft**. The review shows the destination,
connected account and exact body. **Publish** sends that reviewed draft and
returns the GitHub link. Recent drafts and publication outcomes persist locally.

In chat, explicitly ask for an issue, PR or comment and provide the relevant
details. The agent's `draft_github_action` tool prepares a local draft for that
repository. The GitHub button shows drafts created in the latest turn; open it
and select **Recent GitHub actions → Review**. The agent has no publication tool.
Alternatively, **Use latest answer** copies the latest answer into the editable
form. Review this text before publishing, especially if it includes document or
memory content you do not want to share with repository collaborators.

Pull requests use an **existing pushed head branch**, optionally `owner:branch`,
and a base branch (the repository default when blank). They are created as draft
PRs. This connector does not commit or push the isolated coding action's patch;
apply and push it to a branch first. Comments are conversation comments, not
inline diff review comments. No merge, deployment or repository deletion actions
are exposed.

Draft consent binds the exact payload, repository identity and account. Account
or payload changes require review again. Concurrent publication retries consume
one local transition, and retrying a successfully published draft returns its
saved link. A timeout or failed response after a write starts leaves an **unknown**
outcome: inspect GitHub before making another draft. Structured, explicit GitHub
rejections (such as permission denial or invalid fields) are recorded as
**rejected**, with a credential-free HTTP status explanation. Transport failures,
timeouts, server errors and unrecognized responses remain **unknown**. The
connector never retries the write automatically. Earlier unknown records are
retained as recorded; newer diagnostics do not rewrite their history.

Protocol references: [creating issues](https://docs.github.com/en/rest/issues/issues#create-an-issue),
[creating PRs](https://docs.github.com/en/rest/pulls/pulls#create-a-pull-request),
and [issue/PR comments](https://docs.github.com/en/rest/issues/comments#create-an-issue-comment).

Validation uses mocked GitHub HTTP responses through the actual CLI adapter,
application endpoints and MCP draft tool. No live issues, PRs or comments are
created by the automated tests.
