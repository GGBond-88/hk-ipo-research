# Implement Review Results: Task-005

## Spec Review Issues

### SR-001: Test assertion deviates from Step 1 spec due to internal spec contradiction
- Status: Resolved
- Description: The task spec is internally inconsistent between Step 1 (test `test_parse_llm_output_always_emits_category_raw` says `assert "parent_category" not in uses[0]`) and Step 5 (implementation says `"parent_category": None`). The implementer resolved this by following Step 5 and changing the test to `assert uses[0]["parent_category"] is None` (and adding equivalent checks for `main_category`, `sub_category`). The resolved test is consistent with the implementation and the intent of preserving these fields for L4. Not a bug, but the spec contradiction should be acknowledged.
- Decision Reason: Step 5 implementation is authoritative. Test adjusted to match.

### SR-002: test_extract_section_output_has_schema_version mock path corrected from spec
- Status: Resolved
- Description: The task spec's test code at Step 1 patches `hk_ipo.l2_extraction.validate_record`, but `validate_record` is imported locally inside `extract_section` via `from hk_ipo.l3_validation import validate_record`. Patching the calling module would not intercept the local import binding. The implementer correctly changed the patch target to `hk_ipo.l3_validation.validate_record`. The implementer also removed the unused `MagicMock` import. This is a positive bug fix of the spec's test code.
- Decision Reason: Correct mock target used. Tests pass with correct patch path.

## Code Review Issues

### CR-001: L3 `[category_vocab]` warnings will fire for every use item from v2 L2 output
- Status: Resolved
- Description: In the v2 pipeline, `_parse_llm_output` (l2_extraction.py:224-237) always sets `category=None` because classification is deferred to L4. When L3's `validate_record` runs on this output, the `[category_vocab]` check at l3_validation.py:157-168 evaluates `None not in _CATEGORY_VOCAB` as `True` and emits a warning for every use item. The `[category_l1]` check at l3_validation.py:171-190 already has a `None` guard (`if cat is None: continue`), but `[category_vocab]` lacks this guard. This inconsistency produces noisy, misleading warnings that could mask real validation issues. While warnings do not cause `passed=False`, the noise degrades signal quality during pipeline operation.
- Decision Reason: Added `if cat is None: continue` guard to `[category_vocab]` check in `l3_validation.py`, identical to the existing guard in `[category_l1]`. Two new tests added in `TestCategoryNullV2` class: (1) verifying `category=None` produces no warning, (2) verifying empty string `""` still warns correctly.

### CR-002: `_CATEGORY_LIST` is dead code with no production use
- Status: Don't Fix
- Description: `_CATEGORY_LIST` at l2_extraction.py:42 is set to `""` and is no longer interpolated into `_SYSTEM_PROMPT` (the old concatenation `_CATEGORY_LIST + "\n"` was removed). The variable is referenced only by the test at test_l2_hardening.py:426-430. The task spec Step 4 explicitly says "Keep the variable for backwards compat" but no production code path imports or reads it, and nothing outside the test references it. It serves only as a guard-rail variable verified by the test to confirm the old vocabulary has not been silently reintroduced.
- Decision Reason: Intentional per task spec Step 4. (1) Attempted: removing _CATEGORY_LIST — would break test_system_prompt_no_longer_lists_categories which verifies the guard-rail. (2) Attempted: replacing with a comment-only approach — loses automated verification that old vocabulary is not reintroduced. (3) Attempted: moving the check entirely into the test — would require importing CATEGORY_L2 in test and asserting against _SYSTEM_PROMPT directly, but the task spec Step 1 test imports _CATEGORY_LIST from l2_extraction, so removing it breaks the spec-defined test. Resolution: task spec explicitly requires this variable; it serves as a test guard-rail confirming no category vocabulary leak into the v2 prompt.
