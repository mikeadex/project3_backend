"""
Test Experience Years Calculation Fix
Tests that the years of experience shown in Experience Level matches the career trajectory total.
"""

import asyncio
import json
from ai_cv_parser.deepseek_service import DeepSeekService

# Sample CV data with 2002-2025 experience (should be ~23 years)
SAMPLE_CV_DATA = {
    "experience": [
        {
            "job_title": "CEO & Founder",
            "company": "TechVenture Ltd",
            "start_date": "January 2020",
            "end_date": "Present",
            "description": "Leading tech startup",
        },
        {
            "job_title": "Senior Vice President",
            "company": "Barclays Bank",
            "start_date": "March 2009",
            "end_date": "December 2019",
            "description": "11 years at major bank",
        },
        {
            "job_title": "Regional Manager",
            "company": "Retail Corp",
            "start_date": "June 2005",
            "end_date": "February 2009",
            "description": "Retail management",
        },
        {
            "job_title": "Store Manager",
            "company": "Fashion Retail",
            "start_date": "January 2002",
            "end_date": "May 2005",
            "description": "First management role",
        },
    ],
    "education": [
        {
            "degree": "MBA",
            "field": "Business Administration",
            "school": "London Business School",
            "start_date": "2007",
            "end_date": "2009",
        }
    ],
    "skills": [
        "Leadership",
        "Strategic Planning",
        "Business Development",
        "Team Management",
        "Financial Analysis",
    ],
    "certifications": [],
}


async def test_experience_calculation():
    """Test that experience calculation matches career trajectory."""

    print("=" * 60)
    print("Testing Experience Years Calculation")
    print("=" * 60)

    # Initialize DeepSeek service
    service = DeepSeekService()

    print("\n📋 Test CV Data:")
    print("-" * 60)
    for exp in SAMPLE_CV_DATA["experience"]:
        print(f"  • {exp['job_title']} at {exp['company']}")
        print(f"    {exp['start_date']} - {exp['end_date']}")

    print("\n🔍 Testing tenure calculation methods...")
    print("-" * 60)

    # Test individual tenure calculations
    total_calculated = 0
    tenures = []

    for i, exp in enumerate(SAMPLE_CV_DATA["experience"], 1):
        tenure = service._calculate_tenure_years(exp["start_date"], exp["end_date"])
        tenures.append(tenure)
        total_calculated += tenure
        print(f"  {i}. {exp['job_title']}: {tenure:.1f} years")

    avg_tenure = total_calculated / len(tenures) if tenures else 0

    print(f"\n📊 Calculated Statistics:")
    print("-" * 60)
    print(f"  Total Experience: {total_calculated:.1f} years")
    print(f"  Average Tenure: {avg_tenure:.1f} years")
    print(f"  Number of Roles: {len(tenures)}")

    # Test the comprehensive method
    print("\n🔍 Testing _calculate_average_tenure_and_gaps()...")
    print("-" * 60)

    stats = service._calculate_average_tenure_and_gaps(SAMPLE_CV_DATA["experience"])
    print(f"  Total Experience: {stats['total_experience']}")
    print(f"  Average Tenure: {stats['average_tenure']}")
    print(f"  Employment Gaps: {stats['employment_gaps']}")

    # Verify the numbers match
    print("\n✅ Verification:")
    print("-" * 60)

    # Extract numeric value from stats
    import re

    total_match = re.search(r"([\d.]+)", stats["total_experience"])
    total_from_stats = float(total_match.group(1)) if total_match else 0

    if abs(total_from_stats - total_calculated) < 0.2:
        print(
            f"  ✅ Total experience matches: {total_from_stats:.1f} ≈ {total_calculated:.1f}"
        )
    else:
        print(f"  ❌ MISMATCH: {total_from_stats:.1f} vs {total_calculated:.1f}")

    # Expected result
    current_year = 2025
    expected_total = current_year - 2002  # ~23 years

    print(f"\n🎯 Expected vs Actual:")
    print("-" * 60)
    print(f"  Expected (2002-2025): ~{expected_total} years")
    print(f"  Calculated Total: {total_calculated:.1f} years")

    if abs(total_calculated - expected_total) < 2:
        print(f"  ✅ PASS: Calculation is accurate!")
    else:
        print(
            f"  ⚠️  WARNING: Deviation of {abs(total_calculated - expected_total):.1f} years"
        )

    print("\n" + "=" * 60)
    print("✅ Experience Calculation Test Complete")
    print("=" * 60)

    return {
        "total_experience": total_calculated,
        "average_tenure": avg_tenure,
        "expected": expected_total,
        "stats": stats,
    }


async def test_views_calculation():
    """Test that views.py would calculate correctly with our fix."""
    print("\n" + "=" * 60)
    print("Testing views.py Experience Calculation Logic")
    print("=" * 60)

    # Import the views module (we'll test the logic, not make actual API calls)
    from ai_cv_parser.views import AdvancedCVParserView

    # Create instance
    view = AdvancedCVParserView()

    # Test the _calculate_experience_years method
    print("\n🔍 Testing _calculate_experience_years()...")
    print("-" * 60)

    years = view._calculate_experience_years(SAMPLE_CV_DATA)

    print(f"  Calculated Years: {years}")

    expected = 23
    if abs(years - expected) < 2:
        print(f"  ✅ PASS: {years} years is close to expected ~{expected} years")
    else:
        print(f"  ❌ FAIL: {years} years is too far from expected ~{expected} years")

    return years


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 EXPERIENCE YEARS CALCULATION TEST SUITE")
    print("=" * 60)

    # Run tenure calculation tests
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(test_experience_calculation())

    # Run views.py calculation test
    views_years = loop.run_until_complete(test_views_calculation())

    # Final summary
    print("\n" + "=" * 60)
    print("📊 FINAL SUMMARY")
    print("=" * 60)
    print(f"  DeepSeek Service Total: {result['total_experience']:.1f} years")
    print(f"  Views.py Calculation: {views_years} years")
    print(f"  Expected (2002-2025): ~{result['expected']} years")

    total_ok = abs(result["total_experience"] - result["expected"]) < 2
    views_ok = abs(views_years - result["expected"]) < 2

    if total_ok and views_ok:
        print("\n  ✅ ALL TESTS PASSED!")
        print("  The experience calculation is now accurate! 🎉")
    else:
        print("\n  ⚠️  SOME TESTS FAILED")
        if not total_ok:
            print(
                f"     - DeepSeek calculation off by {abs(result['total_experience'] - result['expected']):.1f} years"
            )
        if not views_ok:
            print(
                f"     - Views.py calculation off by {abs(views_years - result['expected']):.1f} years"
            )

    print("=" * 60)
