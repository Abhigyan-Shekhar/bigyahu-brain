# Reconstructed demo: redirect and replay review

This document was written for the local Company Brain Browser demonstration.
It is not an upstream urllib3 design document or an approved organization policy.

Review merged urllib3 [PR #5161](https://github.com/urllib3/urllib3/pull/5161)
for historical context about dropping body framing and rewind state on 303
redirects. Its discussion and snapshot file associations are historical evidence,
not symbol-level constraints or human approval of this document.

At pinned revision `a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8`, review
`src/urllib3/connectionpool.py::HTTPConnectionPool.urlopen`, including its
`set_file_position` call and the 303 cleanup branch. See merged
[PR #3780](https://github.com/urllib3/urllib3/pull/3780) and the pinned
`src/urllib3/util/request.py` implementation for rewind-error behavior.

The isolated demo proposes D-1 for preserving 303 cleanup, then D-2 as a broader
replacement also preserving explicit replay errors. Both proposals require
independent human review through the operator CLI. This document does not
approve either proposal. Approval and supersession must never be inferred
from a merged upstream PR.
