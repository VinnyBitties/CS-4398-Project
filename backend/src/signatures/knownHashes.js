"use strict";

/**
 * Week 3 "signature lookup" — deliberately the simplest possible starter.
 * analyze.py's sha256 field is explicitly "no signature-catalog lookup is
 * performed" (see REPORT_CONTRACT.md) -- that lookup is this backend's job.
 *
 * Replace this in-memory Set with a real feed / YARA-backed catalog per the
 * Week 3 plan ("begin YARA rule research", Malware Analysis team) once one
 * exists. For now this proves the API contract end-to-end: known hash in ->
 * signature_match: true out.
 */
const KNOWN_MALICIOUS_SHA256 = new Set([
  // EICAR test file's SHA-256 -- safe, standard antivirus test string.
  "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f",
]);

function checkSignature(sha256) {
  return KNOWN_MALICIOUS_SHA256.has(sha256.toLowerCase());
}

module.exports = { checkSignature, KNOWN_MALICIOUS_SHA256 };
