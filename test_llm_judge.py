"""Test script for LLM-as-a-Judge validation"""
import os
from openai import OpenAI

from src.validation import validate_answer, load_ground_truth, Verdict
from src.validation.verdict import GroundTruthEntry


def test_ground_truth_loading():
    """Test loading ground truth dataset"""
    print("\n" + "="*70)
    print("Test 1: Ground Truth Loading")
    print("="*70)

    ground_truth = load_ground_truth()

    print(f"\nLoaded {len(ground_truth)} ground truth entries:")
    for query, entry in ground_truth.items():
        print(f"\n  Query: {query}")
        print(f"  Key facts: {len(entry.key_facts)}")
        print(f"  Common errors: {len(entry.common_errors)}")

    if len(ground_truth) > 0:
        print(f"\n✓ PASS: Ground truth loaded successfully")
        return True, ground_truth
    else:
        print(f"\n✗ FAIL: No ground truth entries loaded")
        return False, {}


def test_correct_answer(llm_client, ground_truth):
    """Test judge with correct answer (should be CORRECT)"""
    print("\n" + "="*70)
    print("Test 2: Correct Answer Validation")
    print("="*70)

    query = "Is NeMo Retriever approved for production use?"
    gt_entry = ground_truth.get(query)

    if not gt_entry:
        print(f"✗ Ground truth not found for query")
        return False

    # Correct answer (matches ground truth)
    correct_answer = (
        "Yes, NeMo Retriever is approved for production use. "
        "It requires Python 3.10 or higher and CUDA 12.0 or higher. "
        "The recommended GPU is NVIDIA A100 or H100 with at least 40GB VRAM. "
        "It supports vector databases including ChromaDB, Milvus, and Pinecone."
    )

    print(f"\nQuery: {query}")
    print(f"\nAgent Answer: {correct_answer[:100]}...")
    print(f"\nExpected: {gt_entry.expected_answer[:100]}...")

    print("\nCalling LLM Judge...")
    verdict = validate_answer(
        query=query,
        agent_answer=correct_answer,
        ground_truth=gt_entry,
        llm_client=llm_client
    )

    print(f"\nVerdict: {verdict.verdict.value}")
    print(f"Confidence: {verdict.confidence:.2f}")
    print(f"Reasoning: {verdict.reasoning}")
    print(f"Errors: {verdict.errors}")

    if verdict.is_correct:
        print(f"\n✓ PASS: Correct answer validated as CORRECT")
        return True
    else:
        print(f"\n✗ FAIL: Correct answer marked as {verdict.verdict.value}")
        return False


def test_incorrect_answer_stale_data(llm_client, ground_truth):
    """Test judge with incorrect answer from stale data (should be INCORRECT)"""
    print("\n" + "="*70)
    print("Test 3: Incorrect Answer (Stale Data) Detection")
    print("="*70)

    query = "Is NeMo Retriever approved for production use?"
    gt_entry = ground_truth.get(query)

    if not gt_entry:
        print(f"✗ Ground truth not found for query")
        return False

    # Incorrect answer with stale info (Python 3.8, CUDA 11.0)
    stale_answer = (
        "Yes, NeMo Retriever is approved for production use. "
        "It requires Python 3.8 and CUDA 11.0. "
        "The recommended GPU is NVIDIA V100 with at least 16GB VRAM. "
        "It supports ChromaDB for vector storage."
    )

    print(f"\nQuery: {query}")
    print(f"\nAgent Answer (STALE): {stale_answer}")
    print(f"\nExpected: {gt_entry.expected_answer[:100]}...")

    print("\nCalling LLM Judge...")
    verdict = validate_answer(
        query=query,
        agent_answer=stale_answer,
        ground_truth=gt_entry,
        llm_client=llm_client
    )

    print(f"\nVerdict: {verdict.verdict.value}")
    print(f"Confidence: {verdict.confidence:.2f}")
    print(f"Reasoning: {verdict.reasoning}")
    print(f"Errors found: {len(verdict.errors)}")

    if verdict.errors:
        print(f"\nDetected errors:")
        for i, error in enumerate(verdict.errors, 1):
            print(f"  {i}. {error}")

    if verdict.key_facts_incorrect:
        print(f"\nIncorrect facts:")
        for fact in verdict.key_facts_incorrect:
            print(f"  - {fact}")

    if verdict.is_incorrect or (verdict.has_errors and verdict.confidence > 0.5):
        print(f"\n✓ PASS: Stale data errors correctly detected")
        return True
    else:
        print(f"\n✗ FAIL: Stale data not detected as incorrect")
        return False


def test_partial_answer(llm_client, ground_truth):
    """Test judge with partially correct answer (should be PARTIAL or INCORRECT)"""
    print("\n" + "="*70)
    print("Test 4: Partial Answer Detection")
    print("="*70)

    query = "What are the hardware requirements for NeMo Retriever?"
    gt_entry = ground_truth.get(query)

    if not gt_entry:
        print(f"✗ Ground truth not found for query")
        return False

    # Partial answer (missing some key facts)
    partial_answer = (
        "NeMo Retriever requires NVIDIA A100 GPUs. "
        "You'll need CUDA 12.0 or higher."
    )

    print(f"\nQuery: {query}")
    print(f"\nAgent Answer (PARTIAL): {partial_answer}")
    print(f"\nExpected: {gt_entry.expected_answer[:100]}...")

    print("\nCalling LLM Judge...")
    verdict = validate_answer(
        query=query,
        agent_answer=partial_answer,
        ground_truth=gt_entry,
        llm_client=llm_client
    )

    print(f"\nVerdict: {verdict.verdict.value}")
    print(f"Confidence: {verdict.confidence:.2f}")
    print(f"Reasoning: {verdict.reasoning}")

    if verdict.key_facts_missing:
        print(f"\nMissing facts:")
        for fact in verdict.key_facts_missing:
            print(f"  - {fact}")

    if verdict.verdict.value in ["PARTIAL", "INCORRECT"]:
        print(f"\n✓ PASS: Partial answer correctly identified")
        return True
    else:
        print(f"\n✗ FAIL: Partial answer marked as {verdict.verdict.value}")
        return False


def main():
    """Run all LLM Judge tests"""
    print("\n" + "="*70)
    print("LLM-as-a-Judge Validation Test Suite")
    print("="*70)

    # Check for API key
    if not os.getenv("NVIDIA_API_KEY"):
        print("\n✗ ERROR: NVIDIA_API_KEY not found in environment")
        print("Please set NVIDIA_API_KEY to run LLM Judge tests")
        return

    # Initialize LLM client
    print("\nInitializing NVIDIA LLM client...")
    llm_client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.getenv("NVIDIA_API_KEY")
    )
    print("✓ Client initialized")

    # Run tests
    tests = [
        ("Ground Truth Loading", lambda: test_ground_truth_loading()),
    ]

    # Load ground truth first
    success, ground_truth = test_ground_truth_loading()
    if not success or not ground_truth:
        print("\n✗ Cannot proceed without ground truth")
        return

    # Run validation tests
    validation_tests = [
        ("Correct Answer", lambda: test_correct_answer(llm_client, ground_truth)),
        ("Stale Data Detection", lambda: test_incorrect_answer_stale_data(llm_client, ground_truth)),
        ("Partial Answer", lambda: test_partial_answer(llm_client, ground_truth))
    ]

    results = [(tests[0][0], success)]

    for name, test_func in validation_tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ All LLM Judge tests passed!")
        print("\nThe judge can:")
        print("  - Validate correct answers")
        print("  - Detect stale data errors (Python 3.8 vs 3.10, CUDA 11 vs 12)")
        print("  - Identify missing key facts")
    else:
        print(f"\n✗ {total - passed} test(s) failed")

    print("="*70 + "\n")


if __name__ == "__main__":
    main()
