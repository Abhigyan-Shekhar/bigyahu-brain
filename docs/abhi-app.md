# Portable memory in the application

Open **Team Brain → Portable memory · .abhi import and export**. This uses the
existing strict [abhi/2 graph format](abhi-format.md), not a second interchange
schema. The app accepts up to 50 selected records, 100 relationships and 1 MB of
UTF-8; the format's existing topology bounds still apply.

## Export and import

1. Select accepted records visible in the current team/member view. Imported and
   shared copies display their distinct local IDs. Select one copy of each
   portable record; exporting both an original and its identical portable copy
   would duplicate the portable ID and is rejected.
2. Enter a collection identifier. Optionally select accepted relationships whose
   exact endpoint records are both selected. Preview the complete file: selected
   text, citation references, expiry, portable IDs, nodes, edges and checksum.
3. **Download reviewed selection as .abhi** rechecks the exact record versions and
   preview digest. The downloaded file contains no grants, identities, acceptance
   or executable instructions. Selected text and citation URIs can themselves be
   sensitive; inspect the preview before choosing an external recipient.
4. Choose an `.abhi` file and **Validate and preview import**. The configured tenant
   and selected authorized destination team must match the envelope. There is no
   silent tenant/team remapping or automatic creation of membership. Invalid
   checksums/topology, duplicate keys, forbidden fields, unsupported formats and
   conflicting collection parents are rejected or explicitly reported.
5. **Confirm exact import as proposals** binds the validated envelope digest.
   Records and assertions import through the existing transactional CAS contract.
   A bad record rolls back the whole batch. Identical replay preserves existing
   review states; it cannot re-propose an accepted record or accept a pending one.
6. Inspect and review each imported record in the team memory list. Its source
   explicitly identifies the importing principal and distinguishes file integrity
   from source-origin authentication. Imported text remains advisory evidence.
7. Review imported relationships separately under **Source-backed memory
   relationships**. Both exact endpoint records must already be accepted. A
   relationship can be accepted, rejected or have its acceptance revoked, with a
   required reason and expected-state check. Record acceptance never accepts an
   assertion automatically.
8. Re-export the reviewed imported records and selected relationships. Stable
   portable IDs and selected citation/identifier topology survive the round trip.
   The local member/brain structure is reconstructed under destination permissions.

Readers can export accepted authorized evidence but cannot import or review it.
Writers may import proposals; a reviewer must publish the shared graph. App chat
has no import, export, grant or review tools. CLI abhi/1 import remains available;
the application deliberately accepts abhi/2 only.

## Source verification and recovery

Import saves a content-addressed canonical envelope and separate selected-record
snapshots. Review, agent retrieval and citation clicks validate the envelope
checksum, original selected record version, record snapshot and native graph.
The shared source view returns the selected text and its citation references,
not the whole envelope. These checks do not authenticate the source author or
prove that an external citation's contents are correct. The citation inspector
labels reviewed imports accordingly.

The underlying importer commits records/assertions atomically. App snapshot
proofs are derived after that transaction. If the application stops between these
steps, the records remain unavailable for acceptance/retrieval until identical
replay repairs the missing proofs. Replay checks the exact imported content hash
and does not reset review. Missing or modified envelope/record snapshots fail
closed. Local file administration remains outside the app permission boundary.

## Verification

The full isolated live suite passed **350 tests**. Added coverage includes strict
preview consent, malformed envelopes, tenant mismatch, reader restrictions,
source-envelope tampering, recovery by replay, atomic record conflicts, independent
assertion review and exact record/assertion topology after import/re-export.

Browser acceptance on the disposable retry fixture downloaded an actual one-record
file, uploaded that file through the picker, imported a proposal, independently
accepted it, and downloaded the re-export. Both complete parsed envelopes match:
one portable Memory node, one Source node and one `SUPPORTED_BY` edge. Native
agent search excluded the imported proposal before review and retrieved it after
acceptance. Relationship-bearing round trips are covered by live tests; this
browser file contained no assertions.

The subsequent real Codex investigation combined the reviewed import with indexed
company policy and current code, called `check_change`, and returned three checked
claims. See the [verification report](application-exchange-verification.json)
and [integrated demo guide](application-integrated-demo.md). Raw files, browser
screenshots, catalogs and model traces remain under ignored validation storage.
