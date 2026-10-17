# v5 release preflight — Friday 16 October 2026 (IST)

Integration update, 17 October: the [combined merge verification](merge-verification.md)
records fresh live tests and rebuilds after combining v5 and the Browser branch.
The reconstructed Browser demo has separate visual and approval receipts; the
original v5 paths and final narrated video remain separate gates. The preflight
and checklist below retain their historical scope and do not certify publication.

Reviewed commit `90c20855c6195b555a3684f95ab533048556c807` and its complete
HEAD ancestry. This is a Friday preflight, not completion of the required
Saturday publication review. No visibility change, approval, graph mutation or
trial rerun was performed during this review.

## Verified now

- `python scripts/check_publication.py --history` passed for **111 indexed
  files and complete reachable history**. The guard screens raw-record paths,
  runtime trace names, host-specific home/temp paths and selected credential
  shapes. The indexed tree had no findings under those rules.
- A supplemental text scan of reachable historical blobs screened credential
  assignments, cloud access-key shapes, credential-bearing URLs and private IPv4
  addresses. Its two candidate categories were reviewed: an absolute placeholder
  `password_file` path in the cloud example and a private-IP example within an
  attributed public Requests snapshot. These candidates did not establish an
  exposed credential. This limited scan is not an exhaustive secret scan and
  does not replace a fresh dedicated scanner or human review.
- **76/76 SHA-256 checks matched**: six frozen input files, twenty backend files,
  protocol, oracle, six public patches and all forty-two locally retained trial
  artifacts named by the public result manifest. No artifact was rewritten.
- `data/sources/urllib3/work.json` contains exactly **#5161 and #3780**, matches
  its manifest digest, and contains no screened issue/PR URL or `#number`
  references to #5181, #5191 or #5242. Manifest exclusions are metadata; the
  excluded source records are absent. The broader Requests dataset is separate
  from this eligible urllib3 reconstruction input.
- Lifecycle and document evidence exports agree with the evaluation corpus hash:
  `b16fc995c9d4429a54c20601ae471bbc7a789d61a1256184068aa30c5ef688f6`.
- The reproduction guide specifies the upstream pin, locked Lite environment,
  isolated database, included snapshot directory, `prepare` phase, separate
  interactive human approval/supersession and read-only freeze. Source ingestion
  remains non-binding. The guide explicitly distinguishes driver traversal from
  Browser verification and does not claim the Docker alternative was tested.
- Public results report the complete six-session tie, 12/12 per session, n=3
  limitations, missing D-2 exposure in graph-1, and absence of document excerpts
  in coding sessions. Graph-2 is identified as fresh frozen-v5 demonstration
  material without claiming that approved context caused its success.

No new clean-room rebuild or backend test campaign was needed for this read-only
review. The existing clean-room and 134-test results remain attributed to their
recorded verification, not to this preflight.

## Open release gates

`docs/demo/demo.mp4` is a tracked binary and contains the older failed 9/12
attempt. The text guard skips binary content; this review did not certify its
frames or audio. It must not serve as the fresh successful v5 demonstration.
All retained binary footage still needs human privacy/export review, including
any newly recorded video and screenshots.

Actual Browser traversal, the fresh video and the live submission form remain
unverified gates in the execution log. A driver query or a green connection
indicator does not close the Browser gate. The form must be checked for its
actual fields and URL requirements before submitting.

The prior public trace exposure and history rewrite remain disclosed in
[security remediation](security-remediation.md). This ancestry check cannot
certify removal from old clones, cached GitHub objects or unrelated refs. Do not
merge old ancestry back into the cleaned release history. Do not describe the
current automated preflight as a complete privacy audit.

## Saturday 17 October release checklist

- [ ] Select and record the exact final release commit after the new evidence,
  video and documentation are ready; review all changes since this preflight.
- [ ] On that commit, run `python scripts/check_publication.py --history` and a
  fresh dedicated secret scanner with redacted output. Check commit metadata and
  refs intended for publication as well as the release tree/history.
- [ ] Manually review source, snapshots, author/contact information, configuration
  examples, exported evidence and video frames/audio for credentials, personal
  information, private graph content and local environment details. Keep raw
  traces, DB files, local configs and scan findings ignored.
- [ ] Verify the source manifest, patch/evidence hashes, source attribution and
  retained upstream license notices on the final commit. Follow the documented
  local setup from a clean checkout; do not claim untested Docker/Cloud support
  has been validated.
- [ ] Check the actual submission form; complete Browser verification and the
  new video. Confirm that the video shows the fresh graph-2 run, or explicitly
  labels any earlier-graph footage, and reports the full 3+3 tie honestly.
- [ ] After the manual review, make the repository public **Saturday night**.
  Open the repository, release README/setup, evidence links and final video in
  a logged-out window and confirm access. Record the checked commit and URLs.
- [ ] Leave Sunday 18 October for fixes and submission; verify the live deadline
  and required fields before submitting. Do not mark access complete from an
  owner-authenticated API response.

All boxes above remain open. The checklist records the user's release order;
it is not authorization to skip review or a claim that a public release happened.
